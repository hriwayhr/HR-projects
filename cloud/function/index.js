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
const { memoryStore, ydbStore, logStore } = require('./store');

function config(env = process.env) {
  const list = s => String(s || '').split(',').map(x => x.trim().toLowerCase()).filter(Boolean);
  return {
    baseUrl: String(env.BASE_URL || '').replace(/\/$/, ''),
    clientId: env.OAUTH_CLIENT_ID, clientSecret: env.OAUTH_CLIENT_SECRET, sessionSecret: env.SESSION_SECRET,
    domains: list(env.ALLOWED_DOMAINS), admins: list(env.ADMIN_EMAILS), bucket: env.BACKUP_BUCKET,
    local: env.LOCAL === '1',   // локальная версия: сервер на этом ПК, вход по логину и паролю из «Команды»
    webImport: env.LOCAL === '1' && env.WEB_IMPORT !== '0',   // загрузка данных со страницы — только на своём ПК; на открытом сервере — из файла (server.js)
  };
}

// Страница — src/hr-metrics.html как есть; здесь она получает документ и флаг облачного режима
let PAGE = null;
function pageHtml(local) {
  if (!PAGE) {
    const raw = fs.readFileSync(process.env.PAGE_SRC || path.join(__dirname, 'static', 'page.html'), 'utf8');
    PAGE = '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' +
      '<script>window.' + (local ? 'HR_LOCAL' : 'HR_CLOUD') + ' = true;</script>' + raw + '</body></html>';
  }
  return PAGE;
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

function page(local) {
  const nonce = crypto.randomBytes(16).toString('base64');
  const html = pageHtml(local).replace(/<script>/g, '<script nonce="' + nonce + '">');
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
  const user = acl.userByEmail((team || {}).people, email, cfg.local ? 'login' : 'email');
  if (!user) return null;
  const people = (team || {}).people || {}, vacations = {};
  // отпуска команды — для прав на вакансии коллеги, которые пользователь ведёт на время его отпуска
  await Promise.all(Object.keys(people).map(async p => { const d = await store.get('vacations/' + p); if (d && Array.isArray(d.list)) vacations[p] = d.list; }));
  return Object.assign(user, { people, vacations });
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
  let changed = await store.changes(since);
  // передача начинается и кончается по дате, а не правкой документа: вакансии коллеги в отпуске отдаём каждый раз целиком
  if (since && !user.admin && acl.ownersFor(user).length > 1) {
    const seen = new Set(changed.map(d => d.path));
    changed = changed.concat((await store.changes(0)).filter(d => d.path.startsWith('vacancies/') && !seen.has(d.path) && d.data !== null &&
      acl.readable(user, d.path, d.data, user.people) !== null));
  }
  const docs = changed.map(d => ({ path: d.path, ver: d.ver, data: d.data === null ? null : acl.readable(user, d.path, d.data, user.people) }));
  // невидимое после изменения (вакансию передали другому) приходит как удалённое — страница его уберёт
  // при полной загрузке невидимое не отдаём совсем — даже адресом
  return { ver: docs.reduce((m, d) => Math.max(m, d.ver), since), docs: docs.filter(d => since || d.data !== null).map(d => ({ path: d.path, data: d.data })) };
}

// Слияние трёх версий: base — документ, как его видела страница до правки, mine — с правкой, theirs — сейчас в базе.
// Применяется только то, что человек поменял: поля, которые за это время поменял коллега, не затираются.
const isObj = o => o !== null && typeof o === 'object' && !Array.isArray(o);
const canon = o => isObj(o) ? '{' + Object.keys(o).sort().map(k => JSON.stringify(k) + ':' + canon(o[k])).join(',') + '}' : Array.isArray(o) ? '[' + o.map(canon).join(',') + ']' : JSON.stringify(o === undefined ? null : o);
const same = (a, b) => (a === undefined) === (b === undefined) && canon(a) === canon(b);
function merge3(b, m, t) {
  if (same(m, b)) return t;
  if (same(t, b) || same(t, m)) return m;
  if (isObj(m) && isObj(t)) {
    const bo = isObj(b) ? b : {}, out = {};
    new Set(Object.keys(bo).concat(Object.keys(m), Object.keys(t))).forEach(k => { const v = merge3(bo[k], m[k], t[k]); if (v !== undefined) out[k] = v; });
    return out;
  }
  return m;   // одно и то же поле поменяли оба — побеждает эта правка
}

async function write(user, store, body) {
  const { path: p, op, data } = body || {};
  if (typeof p !== 'string' || !['set', 'update', 'delete'].includes(op)) return json(400, { error: 'Неверный запрос.' });
  let err = '';
  const ver = await store.tx(p, prev => {
    let next = op === 'delete' ? null : op === 'update' ? Object.assign({}, prev || {}, data)
      : 'base' in body ? merge3(body.base === null ? undefined : body.base, data, prev === null ? undefined : prev) : data;
    if (next === undefined) next = null;
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

// ---------- локальная версия: вход по паролю и первичная загрузка данных ----------
// Пароль — тот же SHA-256(salt + '::' + пароль), что выдаёт «Команда»; проверяет сервер, страница хешей не получает.
// Перебор: после 10 неудачных попыток подряд логин закрыт на 15 минут, после 100 за 15 минут — вход закрыт для всех
const FAILS = new Map(), LOCK_MS = 15 * 60e3;
let allFails = { n: 0, at: 0 };
async function passwordLogin(cfg, store, b) {
  const people = ((await store.get('config/team')) || {}).people || {}, login = acl.norm(b.login);
  const now = Date.now(), f = FAILS.get(login);
  if (now - allFails.at > LOCK_MS) allFails = { n: 0, at: now };
  if ((f && f.n >= 10 && now - f.at < LOCK_MS) || allFails.n >= 100)
    return json(429, { error: 'Слишком много неудачных попыток — подождите 15 минут.' });
  const pid = Object.keys(people).find(p => acl.norm(people[p].login) === login), t = pid && people[pid];
  const want = Buffer.from(String((t && t.hash) || '')), got = Buffer.from(crypto.createHash('sha256').update(String((t && t.salt) || '') + '::' + String(b.password || '')).digest('hex'));
  if (!t || !t.hash || want.length !== got.length || !crypto.timingSafeEqual(want, got)) {
    FAILS.set(login, { n: (f && now - f.at < LOCK_MS ? f.n : 0) + 1, at: now }); allFails.n++;
    if (FAILS.size > 10000) FAILS.clear();                 // память не растёт от случайных логинов
    await new Promise(r => setTimeout(r, 400));             // перебор паролей — медленно
    return json(401, { error: 'Неверный логин или пароль.' });
  }
  FAILS.delete(login);
  if (t.archived) return json(403, { error: 'Учётная запись в архиве — обратитесь к администратору.' });
  return respond(200, { ok: true }, {}, { multiValueHeaders: { 'Set-Cookie': [auth.sessionCookie(cfg.sessionSecret, login)] } });
}
// Только в пустую базу: данные из версии для ПК или резервной копии; нужен администратор с паролем
// Возвращает число загруженных документов или текст ошибки
async function importDocs(store, docs) {
  if ((await store.count()) > 0) return 'В папке уже есть данные.';
  const people = ((docs || {})['config/team'] || {}).people || {};
  if (!Object.keys(people).some(p => people[p].admin && people[p].login && people[p].hash && !people[p].archived))
    return 'В файле нет администратора с паролем — загрузите версию для ПК «HR-метрики.html».';
  const paths = Object.keys(docs).filter(p => acl.PATH_RE.test(p) && docs[p] && typeof docs[p] === 'object' && !Array.isArray(docs[p]));
  for (const p of paths) await store.tx(p, () => JSON.parse(JSON.stringify(docs[p])), 'import');
  return paths.length;
}
// Данные из файла версии для ПК (HTML, внутри — SEED) или резервной копии (JSON с docs)
function docsFromFile(text) {
  const a = text.indexOf('var SEED = '), z = text.indexOf(';\n  var TEMPLATE = ');
  return a >= 0 && z > a ? JSON.parse(text.slice(a + 11, z)).data : JSON.parse(text).docs;
}
// Замена всех данных журналами папки data локальной версии (changes-*.jsonl): администратор переносит их через страницу.
// Журналы сводятся так же, как их читает сама локальная версия; в новой команде должен быть администратор с паролем.
async function replaceFromJournals(store, user, b) {
  const files = Array.isArray(b.files) ? b.files.filter(t => typeof t === 'string' && t) : [];
  if (!files.length) return json(400, { error: 'Выберите файлы changes-….jsonl из папки data.' });
  const dir = fs.mkdtempSync(path.join(require('os').tmpdir(), 'hr-journals-'));
  let docs = {};
  try {
    files.forEach((t, i) => fs.writeFileSync(path.join(dir, 'changes-f' + i + '.jsonl'), t.endsWith('\n') ? t : t + '\n'));
    (await logStore(dir, 'replace-read').changes(0)).forEach(d => { if (d.data !== null) docs[d.path] = d.data; });
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
  const people = (docs['config/team'] || {}).people || {};
  if (!Object.keys(people).some(p => people[p].admin && people[p].login && people[p].hash && !people[p].archived))
    return json(400, { error: 'В файлах нет команды с администратором и паролем — выберите все файлы changes-….jsonl из папки data.' });
  const keep = Object.keys(docs).filter(p => acl.PATH_RE.test(p) && isObj(docs[p]));
  const old = (await store.changes(0)).filter(d => d.data !== null && !keep.includes(d.path)).map(d => d.path);
  for (const p of old) await store.tx(p, () => null, user.email);
  for (const p of keep) await store.tx(p, () => JSON.parse(JSON.stringify(docs[p])), user.email);
  return json(200, { ok: true, docs: keep.length, removed: old.length });
}
async function importInitial(store, b) {
  const r = await importDocs(store, b.docs);
  return typeof r === 'number' ? json(200, { ok: true, docs: r }) : json(r === 'В папке уже есть данные.' ? 403 : 400, { error: r });
}

function makeHandler(store, cfg, fetchFn) {
  return async function handler(event, context) {
    try {
      if (event && (event.messages || (event.event_metadata && /Timer/.test(event.event_metadata.event_type || '')))) return await backup(cfg, store, context, fetchFn);
      // API Gateway: в url — настоящий адрес запроса, в path — шаблон маршрута ("/{proxy+}")
      const method = event.httpMethod, url = String(event.url || event.path || '/').split('?')[0], headers = event.headers || {}, query = event.queryStringParameters || {};
      if (method === 'GET' && url === '/') return page(cfg.local);
      if (!cfg.local && method === 'GET' && url === '/api/login') return auth.loginRedirect(cfg);
      if (!cfg.local && method === 'GET' && url === '/api/callback') return await callback(cfg, store, query, headers, fetchFn);
      if (!url.startsWith('/api/')) return respond(404, 'Не найдено');
      // запись — только со своей страницы: свой заголовок кросс-доменный сайт без разрешения CORS не пошлёт
      if (method !== 'GET' && auth.headerOf(headers, 'x-hr') !== '1') return json(403, { error: 'Запрос не со страницы приложения.' });
      const body = () => { try { return JSON.parse(event.isBase64Encoded ? Buffer.from(event.body || '', 'base64').toString() : event.body || ''); } catch (e) { return null; } };
      if (cfg.local && method === 'POST' && url === '/api/plogin') return await passwordLogin(cfg, store, body() || {});
      if (cfg.webImport && method === 'POST' && url === '/api/import-initial') return await importInitial(store, body() || {});
      const user = await currentUser(cfg, store, headers);
      if (!user) return json(401, { error: 'Нужно войти.', empty: cfg.webImport ? (await store.count()) === 0 : undefined });
      if (cfg.local && user.admin && method === 'POST' && url === '/api/replace-data') return await replaceFromJournals(store, user, body() || {});
      if (method === 'GET' && url === '/api/me') return json(200, { pid: user.pid, email: user.email, admin: user.admin });
      if (method === 'GET' && url === '/api/sync') return json(200, await sync(user, store, Math.max(0, Number(query.since) || 0)));
      if (method === 'POST' && url === '/api/doc') {
        const b = body();
        return b ? await write(user, store, b) : json(400, { error: 'Неверный JSON.' });
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
module.exports.create = (store, cfg, f) => withLogout(makeHandler(store, cfg, f));
module.exports.config = config;
module.exports.importDocs = importDocs;
module.exports.docsFromFile = docsFromFile;
module.exports.forTests = { makeHandler: (store, cfg, f) => withLogout(makeHandler(store, cfg, f)), config, memoryStore };
