'use strict';
// HR-метрики в Yandex Cloud: одна функция за API Gateway.
//   GET  /              страница (с CSP и nonce для скриптов)
//   GET  /api/login     вход через Яндекс ID → /api/callback → cookie сессии
//   POST /api/logout    выход
//   GET  /api/me        кто вошёл
//   GET  /api/sync      документы, изменённые после ?since=, только разрешённые пользователю
//   POST /api/doc       {path, op: set|update|delete, data} — запись с проверкой прав
//   таймер              ежедневная резервная копия всей базы в Object Storage
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const acl = require('./acl');
const auth = require('./auth');
const { memoryStore, ydbStore } = require('./store');

function config(env = process.env) {
  const list = s => String(s || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
  return {
    baseUrl: String(env.BASE_URL || '').replace(/\/$/, ''),
    clientId: env.OAUTH_CLIENT_ID, clientSecret: env.OAUTH_CLIENT_SECRET, sessionSecret: env.SESSION_SECRET,
    domains: list(env.ALLOWED_DOMAINS), admins: list(env.ADMIN_EMAILS), bucket: env.BACKUP_BUCKET,
  };
}

let STATIC = null;
function staticFiles() {
  if (!STATIC) {
    const dir = path.join(__dirname, 'static');
    STATIC = { html: fs.readFileSync(path.join(dir, 'index.html'), 'utf8') };
  }
  return STATIC;
}

const BASE_HEADERS = {
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};
function respond(status, body, headers = {}, extra = {}) {
  const isText = typeof body === 'string';
  return Object.assign({
    statusCode: status,
    headers: Object.assign({}, BASE_HEADERS, { 'Content-Type': isText ? 'text/plain; charset=utf-8' : 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }, headers),
    body: isText ? body : JSON.stringify(body),
  }, extra);
}
const json = (status, body) => respond(status, body);
const redirect = (to, cookies) => respond(302, '', { Location: to }, cookies ? { multiValueHeaders: { 'Set-Cookie': cookies } } : {});

function page() {
  const nonce = crypto.randomBytes(16).toString('base64');
  const html = staticFiles().html.replace(/<script>/g, '<script nonce="' + nonce + '">');
  return respond(200, html, {
    'Content-Type': 'text/html; charset=utf-8',
    'Content-Security-Policy': "default-src 'none'; script-src 'nonce-" + nonce + "'; style-src 'unsafe-inline'; img-src 'self' data:; font-src data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
  });
}

// Пользователь запроса: подпись cookie верна, почта — в команде и не в архиве. Проверяется на каждом запросе,
// поэтому архивация в «Команде» закрывает доступ сразу, не дожидаясь конца сессии.
async function currentUser(cfg, store, headers) {
  const email = auth.sessionEmail(cfg.sessionSecret, headers);
  if (!email) return null;
  const team = await store.get('config/team');
  const user = acl.userByEmail((team || {}).people, email);
  return user ? Object.assign(user, { people: (team || {}).people || {} }) : null;
}

function domainOk(cfg, email) { return cfg.domains.includes(email.split('@')[1] || ''); }

async function callback(cfg, store, query, headers, fetchFn) {
  let email, yid;
  try { ({ email, yid } = await auth.exchange(cfg, query, headers, fetchFn)); } catch (e) { console.error('login', e.message); return redirect('/?login=failed'); }
  if (!email || !yid || !domainOk(cfg, email)) return redirect('/?login=domain');
  // первый вход владельца: пока в команде нет администратора с почтой, адрес из ADMIN_EMAILS создаёт себя администратором
  if (cfg.admins.includes(email)) {
    await store.tx('config/team', prev => {
      const people = Object.assign({}, (prev || {}).people);
      const hasAdmin = Object.keys(people).some(p => people[p].admin && !people[p].archived && people[p].email);
      if (hasAdmin) return undefined;
      people['a' + Date.now().toString(36)] = { name: email.split('@')[0], email, admin: true, recruiter: false, order: Object.keys(people).length + 1 };
      return { people };
    }, email);
  }
  // почта привязывается к аккаунту Яндекса при первом входе: к личному Яндекс ID можно добавить
  // подтверждённый рабочий адрес, и после увольнения он вошёл бы им — теперь только тем же аккаунтом
  let bound = false;
  await store.tx('config/team', prev => {
    const people = (prev || {}).people || {}, u = acl.userByEmail(people, email);
    if (!u) return undefined;
    if (people[u.pid].yid) { bound = people[u.pid].yid === yid; return undefined; }
    bound = true;
    const next = Object.assign({}, people); next[u.pid] = Object.assign({}, people[u.pid], { yid });
    return { people: next };
  }, email);
  if (!bound) return redirect('/?login=noaccess');
  return redirect('/', [auth.sessionCookie(cfg.sessionSecret, email), auth.setCookie(auth.STATE_COOKIE, '', 0)]);
}

async function sync(user, store, since) {
  const docs = (await store.changes(since)).map(d => ({ path: d.path, ver: d.ver, data: d.data === null ? null : acl.readable(user, d.path, d.data, user.people) }));
  // невидимое после изменения (вакансию передали другому) приходит как удалённое — страница его уберёт
  // при полной загрузке невидимое не отдаём совсем — даже адресом
  return { ver: docs.reduce((m, d) => Math.max(m, d.ver), since), docs: docs.filter(d => since || d.data !== null).map(d => ({ path: d.path, data: d.data })) };
}

async function write(user, store, body) {
  const { path: p, op, data } = body || {};
  if (typeof p !== 'string' || !['set', 'update', 'delete'].includes(op)) return json(400, { error: 'Неверный запрос.' });
  let err = '';
  const ver = await store.tx(p, prev => {
    let next = op === 'delete' ? null : op === 'update' ? Object.assign({}, prev || {}, data) : data;
    if (op === 'update' && !prev) { err = 'Документа нет.'; return undefined; }
    if (next && typeof next === 'object') next = JSON.parse(JSON.stringify(next));   // только JSON, без прототипов
    err = acl.writeError(user, p, prev, next, user.people);
    return err ? undefined : next;
  }, user.email);
  if (err) return json(403, { error: err });
  return json(200, { ver });
}

async function backup(cfg, store, context, fetchFn = fetch) {
  const docs = {};
  (await store.changes(0)).forEach(d => { if (d.data !== null) docs[d.path] = d.data; });
  const key = 'backups/' + new Date().toISOString().slice(0, 10) + '.json';
  const token = context && context.token && context.token.access_token;
  const res = await fetchFn('https://storage.yandexcloud.net/' + cfg.bucket + '/' + key, {
    method: 'PUT', headers: { 'X-YaCloud-SubjectToken': token, 'Content-Type': 'application/json' }, body: JSON.stringify({ at: new Date().toISOString(), docs }),
  });
  if (!res.ok) throw new Error('backup ' + res.status + ' ' + await res.text());
  return { statusCode: 200, body: key + ': ' + Object.keys(docs).length };
}

function makeHandler(store, cfg, fetchFn) {
  return async function handler(event, context) {
    try {
      if (event && (event.messages || (event.event_metadata && /Timer/.test(event.event_metadata.event_type || '')))) return await backup(cfg, store, context, fetchFn);
      // API Gateway: в url — настоящий адрес запроса, в path — шаблон маршрута ("/{proxy+}")
      const method = event.httpMethod, url = String(event.url || event.path || '/').split('?')[0], headers = event.headers || {}, query = event.queryStringParameters || {};
      if (method === 'GET' && url === '/') return page();
      if (method === 'GET' && url === '/api/login') return auth.loginRedirect(cfg);
      if (method === 'GET' && url === '/api/callback') return await callback(cfg, store, query, headers, fetchFn);
      if (!url.startsWith('/api/')) return respond(404, 'Не найдено');
      // запись — только со своей страницы: свой заголовок кросс-доменный сайт без разрешения CORS не пошлёт
      if (method !== 'GET' && auth.headerOf(headers, 'x-hr') !== '1') return json(403, { error: 'Запрос не со страницы приложения.' });
      const user = await currentUser(cfg, store, headers);
      if (!user) return json(401, { error: 'Нужно войти.' });
      if (method === 'GET' && url === '/api/me') return json(200, { pid: user.pid, email: user.email, admin: user.admin });
      if (method === 'GET' && url === '/api/sync') return json(200, await sync(user, store, Math.max(0, Number(query.since) || 0)));
      if (method === 'POST' && url === '/api/doc') {
        let body;
        try { body = JSON.parse(event.isBase64Encoded ? Buffer.from(event.body || '', 'base64').toString() : event.body || ''); } catch (e) { return json(400, { error: 'Неверный JSON.' }); }
        return await write(user, store, body);
      }
      return json(404, { error: 'Не найдено.' });
    } catch (e) {
      console.error(e && e.stack || e);
      return json(500, { error: 'Ошибка сервера, попробуйте ещё раз.' });
    }
  };
}

// выход — отдельно: cookie надо стереть даже без действующей сессии
function withLogout(h) {
  return async (event, context) => {
    if (event && event.httpMethod === 'POST' && String(event.url || event.path || '').split('?')[0] === '/api/logout' && auth.headerOf(event.headers, 'x-hr') === '1')
      return respond(200, { ok: true }, {}, { multiValueHeaders: { 'Set-Cookie': [auth.setCookie(auth.COOKIE, '', 0)] } });
    return h(event, context);
  };
}

let prod = null;
module.exports.handler = (event, context) => {
  if (!prod) {
    const cfg = config();
    if (!cfg.sessionSecret || cfg.sessionSecret.length < 32 || !cfg.clientId || !cfg.clientSecret || !cfg.baseUrl || !cfg.domains.length || !process.env.YDB_ENDPOINT || !process.env.YDB_DATABASE)
      throw new Error('Не заданы переменные окружения: SESSION_SECRET (от 32 символов), OAUTH_CLIENT_ID/SECRET, BASE_URL, ALLOWED_DOMAINS, YDB_ENDPOINT, YDB_DATABASE');
    prod = withLogout(makeHandler(ydbStore(process.env.YDB_ENDPOINT + '/?database=' + process.env.YDB_DATABASE), cfg));
  }
  return prod(event, context);
};
module.exports.forTests = { makeHandler: (store, cfg, f) => withLogout(makeHandler(store, cfg, f)), config, memoryStore };
