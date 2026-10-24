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
    // почта для кодов входа (Яндекс 360: smtp.yandex.ru:465, пароль приложения); не задана — вход только по паролю, как раньше
    smtp: env.SMTP_HOST && env.SMTP_USER && env.SMTP_PASS
      ? { host: env.SMTP_HOST, port: +env.SMTP_PORT || 465, user: env.SMTP_USER, pass: env.SMTP_PASS, from: env.SMTP_FROM || env.SMTP_USER } : null,
  };
}

// Страница — src/hr-metrics.html как есть; здесь она получает документ и флаг облачного режима.
// Если рядом лежит портал (src/iway-portal.html → static/portal.html), он открывается на «/» с общим входом, а метрики — на «/metrics».
const PORTAL_SRC = process.env.PORTAL_SRC || path.join(__dirname, 'static', 'portal.html');
const PAGES = {};
function pageHtml(local, which = 'metrics') {
  if (!PAGES[which]) {
    const portal = fs.existsSync(PORTAL_SRC);
    const raw = fs.readFileSync(which === 'portal' ? PORTAL_SRC : process.env.PAGE_SRC || path.join(__dirname, 'static', 'page.html'), 'utf8');
    const flags = which === 'portal' ? 'window.HR_SERVER = true;' : 'window.' + (local ? 'HR_LOCAL' : 'HR_CLOUD') + ' = true;' + (portal ? ' window.HR_PORTAL = true;' : '');
    PAGES[which] = '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' +
      '<script>' + flags + '</script>' + raw + '</body></html>';
  }
  return PAGES[which];
}
const portalOn = cfg => cfg.local && fs.existsSync(PORTAL_SRC);

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

function page(local, which) {
  const nonce = crypto.randomBytes(16).toString('base64');
  const html = pageHtml(local, which).replace(/<script>/g, '<script nonce="' + nonce + '">');
  return respond(200, html, {
    'Content-Type': 'text/html; charset=utf-8',
    'Content-Security-Policy': "default-src 'none'; script-src 'nonce-" + nonce + "'; style-src 'unsafe-inline'; img-src 'self' data:; font-src data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
  });
}

// Пользователь запроса: подпись cookie верна, почта — в команде и не в архиве. Проверяется на каждом запросе,
// поэтому архивация в «Команде» закрывает доступ сразу, не дожидаясь конца сессии.
async function currentUser(cfg, store, headers) {
  let email = auth.sessionEmail(cfg.sessionSecret, headers), mark = null;
  if (!email) return null;
  if (cfg.local) { [email, mark] = email.split('|'); if (!mark) return null; }
  const team = await store.get('config/team');
  // новичок портала: в сессии «emp:<код>»; удалили карточку — доступа нет сразу
  if (email.startsWith('emp:')) {
    const code = email.slice(4), rec = cfg.local && /^[A-Za-z0-9_-]{1,100}$/.test(code) ? await store.get('employees/' + code) : null;
    return rec && pwMark(rec.hash) === mark ? { pid: email, email, admin: false, role: 'employee', code, name: [rec.firstName, rec.lastName].filter(Boolean).join(' '), people: (team || {}).people || {}, vacations: {} } : null;
  }
  const user = acl.userByEmail((team || {}).people, email, cfg.local ? 'login' : 'email');
  if (!user || (cfg.local && pwMark(team.people[user.pid].hash) !== mark)) return null;
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
  // невидимое после изменения (вакансию передали другому) приходит как удалённое — страница его уберёт;
  // новичку удалённое не шлём вовсе: иначе он увидел бы адреса всех документов (коды коллег, месяцы метрик)
  // при полной загрузке невидимое не отдаём совсем — даже адресом
  return { ver: docs.reduce((m, d) => Math.max(m, d.ver), since), docs: docs.filter(d => (since && user.role !== 'employee') || d.data !== null).map(d => ({ path: d.path, data: d.data })) };
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

// ---------- письмо с кодом: SMTP по TLS (порт 465) без сторонних библиотек ----------
// shortcut: только неявный TLS (465), без STARTTLS (587) — Яндекс 360 и большинство почтовых сервисов 465 принимают
function smtpSend(smtp, to, subject, text, connect = opts => require('tls').connect(opts)) {
  const b64 = s => Buffer.from(s).toString('base64');
  const body = b64(text).replace(/.{76}/g, '$&\r\n');
  const msg = ['From: ' + smtp.from, 'To: ' + to, 'Subject: =?UTF-8?B?' + b64(subject) + '?=', 'Date: ' + new Date().toUTCString(),
    'Message-ID: <' + crypto.randomBytes(12).toString('hex') + '@' + smtp.from.split('@')[1] + '>', 'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=utf-8', 'Content-Transfer-Encoding: base64', '', body].join('\r\n');
  // команда → ожидаемый код ответа сервера
  const steps = [[null, 220], ['EHLO portal', 250], ['AUTH PLAIN ' + b64('\0' + smtp.user + '\0' + smtp.pass), 235],
    ['MAIL FROM:<' + smtp.from + '>', 250], ['RCPT TO:<' + to + '>', 250], ['DATA', 354], [msg + '\r\n.', 250], ['QUIT', 221]];
  return new Promise((ok, fail) => {
    const sock = connect({ host: smtp.host, port: smtp.port, servername: smtp.host });
    let buf = '', i = 0;
    const stop = e => { sock.destroy(); fail(e); };
    sock.setTimeout(15000, () => stop(new Error('SMTP: нет ответа')));
    sock.on('error', stop);
    sock.on('data', d => {
      buf += d;
      const last = buf.split('\r\n').filter(Boolean).pop() || '';
      if (!buf.endsWith('\n') || !/^\d{3} /.test(last)) return;   // многострочный ответ ещё не закончился
      buf = '';
      if (+last.slice(0, 3) !== steps[i][1]) return stop(new Error('SMTP ' + (steps[i][0] || 'приветствие').split(' ')[0] + ': ' + last.slice(0, 120)));
      if (++i === steps.length) { sock.end(); return ok(); }
      sock.write(steps[i][0] + '\r\n');
    });
  });
}

// Код на почту: при входе с нового устройства и при восстановлении пароля — только для команды и только если почта настроена.
// Знакомые устройства — в подписанной cookie (до 5 человек на браузер); смена пароля их сбрасывает (в записи — отпечаток пароля).
const DEV_COOKIE = 'hr_d', DEV_DAYS = 365, OTP = new Map(), SENT = new Map(), OTP_MS = 10 * 60e3, OTP_TRIES = 5;
const devList = (cfg, headers) => { const p = auth.verify(cfg.sessionSecret, auth.cookies(headers)[DEV_COOKIE]); return p ? p.e.split(',') : []; };
function devCookie(cfg, headers, pid, hash) {
  const list = [pid + ':' + pwMark(hash)].concat(devList(cfg, headers).filter(x => x.split(':')[0] !== pid)).slice(0, 5);
  return auth.setCookie(DEV_COOKIE, auth.sign(cfg.sessionSecret, { e: list.join(','), x: Date.now() + DEV_DAYS * 864e5 }), DEV_DAYS * 86400);
}
const mailOf = t => [t.email, t.login].map(acl.norm).find(e => /^[^\s<>@,]+@[^\s<>@,]+\.[^\s<>@,]+$/.test(e)) || '';
const twoFactor = (cfg, t) => !!(cfg.smtp || cfg.mailer) && portalOn(cfg) && !!mailOf(t);
// Отправить код: не чаще раза в минуту и 5 раз в час на человека. Возвращает номер заявки или текст ошибки.
async function sendCode(cfg, pid, t, kind, ip) {
  const now = Date.now(), sent = (SENT.get(pid) || []).filter(x => now - x < 3600e3);
  if (sent.length >= 5 || now - (sent[sent.length - 1] || 0) < 60e3) return 'Код уже отправлен — подождите минуту и проверьте почту.';
  const code = String(crypto.randomInt(0, 1e6)).padStart(6, '0'), ticket = crypto.randomBytes(16).toString('hex');
  const what = kind === 'reset' ? 'восстановления пароля' : 'входа';
  const text = 'Код ' + what + ' в портал i’way: ' + code + '\n\nДействует 10 минут. Запрос с адреса ' + (ip || 'неизвестен') + '.\n' +
    'Если это были не вы — никому не сообщайте код и смените пароль: кто-то знает ваш пароль или пытается его сменить.';
  try { await (cfg.mailer || ((to, s, x) => smtpSend(cfg.smtp, to, s, x)))(mailOf(t), 'Код ' + what + ': ' + code, text); }
  catch (e) { console.error('код не отправлен:', e.message); return 'Не удалось отправить код на почту — попробуйте позже или обратитесь к администратору.'; }
  SENT.set(pid, sent.concat(now));
  if (OTP.size > 10000) prune(OTP, now, 0, v => v.exp);
  OTP.set(ticket, { pid, kind, mark: pwMark(t.hash), hash: crypto.createHash('sha256').update(code).digest('hex'), tries: 0, exp: now + OTP_MS });
  return { ticket, to: mailOf(t).replace(/^(.).*?@/, '$1•••@') };
}
// Проверить код: заявка одноразовая, 5 попыток, 10 минут; пароль за это время не менялся. Возвращает {pid, t} или текст ошибки.
async function checkCode(store, b, kind) {
  const o = OTP.get(String(b.ticket || '')), now = Date.now();
  if (o && now > o.exp) OTP.delete(String(b.ticket));
  if (!o || o.kind !== kind || now > o.exp) return 'Код устарел — запросите новый.';
  const got = crypto.createHash('sha256').update(String(b.code || '').replace(/\s/g, '')).digest('hex');
  if (!crypto.timingSafeEqual(Buffer.from(got), Buffer.from(o.hash))) {
    if (++o.tries >= OTP_TRIES) { OTP.delete(b.ticket); return 'Код введён неверно 5 раз — запросите новый.'; }
    await new Promise(r => setTimeout(r, 400));
    return 'Неверный код.';
  }
  OTP.delete(b.ticket);
  const t = (((await store.get('config/team')) || {}).people || {})[o.pid];
  if (!t || t.archived || pwMark(t.hash) !== o.mark) return 'Код устарел — запросите новый.';
  return { pid: o.pid, t };
}
const sessionFor = (cfg, t) => auth.sessionCookie(cfg.sessionSecret, acl.norm(t.login) + '|' + pwMark(t.hash));
async function codeLogin(cfg, store, b, headers) {
  const r = await checkCode(store, b, 'login');
  if (typeof r === 'string') return json(401, { error: r });
  return respond(200, { ok: true }, {}, { multiValueHeaders: { 'Set-Cookie': [sessionFor(cfg, r.t), devCookie(cfg, headers, r.pid, r.t.hash)] } });
}
// Восстановление пароля (только команда): ответ одинаковый, есть такой человек или нет — по нему не узнать, чьи логины существуют
async function resetStart(cfg, store, b, ip) {
  if (!cfg.smtp && !cfg.mailer) return json(503, { error: 'Восстановление по почте не настроено — обратитесь к администратору.' });
  const now = Date.now(), key = 'rs:' + ip;
  if (failsOf(key, now) >= IP_MAX) return json(429, { error: 'Слишком много запросов — подождите 15 минут.' });
  addFail(key, now);
  const people = ((await store.get('config/team')) || {}).people || {}, login = acl.norm(b.login).slice(0, 200);
  const pid = Object.keys(people).find(p => people[p].login && (acl.norm(people[p].login) === login || acl.norm(people[p].email) === login));
  const t = pid && people[pid];
  if (t && !t.archived && twoFactor(cfg, t)) {
    const r = await sendCode(cfg, pid, t, 'reset', ip);
    if (typeof r === 'string') return json(r.startsWith('Не удалось') ? 502 : 429, { error: r });
    return json(200, { ok: true, ticket: r.ticket });
  }
  return json(200, { ok: true, ticket: crypto.randomBytes(16).toString('hex') });
}
async function resetFinish(cfg, store, b, headers) {
  const pw = String(b.password || '');
  if (pw.length < 8 || pw.length > 128) return json(400, { error: 'Пароль — от 8 до 128 символов.' });
  const r = await checkCode(store, b, 'reset');
  if (typeof r === 'string') return json(401, { error: r });
  const salt = crypto.randomBytes(8).toString('hex'), hash = crypto.createHash('sha256').update(salt + '::' + pw).digest('hex');
  await store.tx('config/team', prev => {
    const next = JSON.parse(JSON.stringify(prev));
    next.people[r.pid] = Object.assign(next.people[r.pid], { salt, hash });
    return next;
  }, 'reset:' + r.pid);
  const t = Object.assign({}, r.t, { salt, hash });
  return respond(200, { ok: true }, {}, { multiValueHeaders: { 'Set-Cookie': [sessionFor(cfg, t), devCookie(cfg, headers, r.pid, hash)] } });
}

// ---------- локальная версия: вход по паролю и первичная загрузка данных ----------
// Пароль — тот же SHA-256(salt + '::' + пароль), что выдаёт «Команда»; проверяет сервер, страница хешей не получает.
// Перебор (окно 15 минут):
//  - логин с одного адреса: 10 ошибок — этому адресу по этому логину ждать;
//  - адрес: 20 ошибок, логин со всех адресов: 50 — ждать новым адресам; кто уже входил этим логином с этого адреса, тот входит:
//    так чужой перебор не закроет вход ни владельцу логина, ни коллегам за тем же офисным адресом.
// Общего замка нет; счётчики целиком не стираются — при переполнении уходят устаревшие, а новые не заводятся.
const FAILS = new Map(), GOOD = new Map(), LOCK_MS = 15 * 60e3, GOOD_MS = 30 * 864e5, PAIR_MAX = 10, IP_MAX = 20, LOGIN_MAX = 50, KEYS_MAX = 200000;
function failsOf(key, now) { const f = FAILS.get(key); return f && now - f.at < LOCK_MS ? f.n : 0; }
function prune(map, now, ttl, get) { for (const [k, v] of map) if (now - get(v) >= ttl) map.delete(k); }
function addFail(key, now) {
  const n = failsOf(key, now);
  if (!n && FAILS.size >= KEYS_MAX) { prune(FAILS, now, LOCK_MS, v => v.at); if (FAILS.size >= KEYS_MAX) return; }
  FAILS.set(key, { n: n + 1, at: n ? FAILS.get(key).at : now });
}
// Адрес клиента: за Caddy (адрес из внутренней сети) — последний в X-Forwarded-For, его ставит Caddy; напрямую — адрес соединения
const PRIVATE_IP = /^(::ffff:)?(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)|^::1$|^f[cd]/;
function clientIp(event) {
  const sock = String(((event.requestContext || {}).identity || {}).sourceIp || '');
  const xff = String(auth.headerOf(event.headers, 'x-forwarded-for') || '').split(',').map(x => x.trim()).filter(Boolean);
  return (!sock || PRIVATE_IP.test(sock)) && xff.length ? xff[xff.length - 1] : sock;
}
// В сессии — отпечаток пароля: сменили пароль — прежние входы (в том числе украденная cookie) больше не действуют
const pwMark = hash => crypto.createHash('sha256').update('session::' + String(hash || '')).digest('hex').slice(0, 16);
async function passwordLogin(cfg, store, b, ip, headers) {
  const people = ((await store.get('config/team')) || {}).people || {}, login = acl.norm(b.login).slice(0, 200);
  const now = Date.now(), ipKey = 'ip:' + ip, loginKey = 'l:' + login, pairKey = 'p:' + login + '|' + ip, known = now - (GOOD.get(pairKey) || 0) < GOOD_MS;
  if (failsOf(pairKey, now) >= PAIR_MAX || (!known && (failsOf(ipKey, now) >= IP_MAX || failsOf(loginKey, now) >= LOGIN_MAX)))
    return json(429, { error: 'Слишком много неудачных попыток — подождите 15 минут.' });
  // команда — по логину или почте; иначе новичок портала — по логину, рабочей почте или коду доступа
  const pid = Object.keys(people).find(p => acl.norm(people[p].login) === login) || Object.keys(people).find(p => people[p].login && acl.norm(people[p].email) === login);
  let t = pid && people[pid], session = t && acl.norm(t.login);
  if (!t && portalOn(cfg) && login) {
    const emps = (await store.changes(0)).filter(d => d.path.startsWith('employees/') && d.data).map(d => d.data);
    t = emps.find(e => acl.norm(e.login) === login) || emps.find(e => acl.norm(e.email) === login) || emps.find(e => acl.norm(e.code) === login);
    session = t && 'emp:' + t.code;
  }
  const want = Buffer.from(String((t && t.hash) || '')), got = Buffer.from(crypto.createHash('sha256').update(String((t && t.salt) || '') + '::' + String(b.password || '')).digest('hex'));
  if (!t || !t.hash || want.length !== got.length || !crypto.timingSafeEqual(want, got)) {
    addFail(pairKey, now); addFail(ipKey, now); addFail(loginKey, now);
    await new Promise(r => setTimeout(r, 400));             // перебор паролей — медленно
    return json(401, { error: 'Неверный логин или пароль.' });
  }
  // счётчики адреса и логина не сбрасываем: иначе свой вход обнулял бы перебор чужих паролей
  FAILS.delete(pairKey);
  if (GOOD.size >= KEYS_MAX) prune(GOOD, now, GOOD_MS, v => v);
  if (GOOD.size < KEYS_MAX) GOOD.set(pairKey, now);
  if (t.archived) return json(403, { error: 'Учётная запись в архиве — обратитесь к администратору.' });
  if (pid && twoFactor(cfg, t) && !devList(cfg, headers).includes(pid + ':' + pwMark(t.hash))) {
    const r = await sendCode(cfg, pid, t, 'login', ip);
    if (typeof r === 'string') return json(r.startsWith('Не удалось') ? 502 : 429, { error: r });
    return json(200, { need: 'code', ticket: r.ticket, to: r.to });
  }
  return respond(200, { ok: true }, {}, { multiValueHeaders: { 'Set-Cookie': [auth.sessionCookie(cfg.sessionSecret, session + '|' + pwMark(t.hash))] } });
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
  // пребординг портала в журналах локальной версии не бывает — его не трогаем
  const old = (await store.changes(0)).filter(d => d.data !== null && !keep.includes(d.path) && !acl.isPreboard(d.path)).map(d => d.path);
  for (const p of old) await store.tx(p, () => null, user.email);
  for (const p of keep) await store.tx(p, () => JSON.parse(JSON.stringify(docs[p])), user.email);
  return json(200, { ok: true, docs: keep.length, removed: old.length });
}
// Перенос пребординга из прежнего артефакта: администратор загружает файл с документами employees/* и config/departments|page|templates.
// Учётные записи HR (admins/*) не переносятся: вход HR — из «Команды».
async function importPreboard(store, user, b) {
  const docs = isObj(b.docs) ? b.docs : {};
  const paths = Object.keys(docs).filter(p => acl.PATH_RE.test(p) && acl.isPreboard(p) && isObj(docs[p]));
  if (!paths.length) return json(400, { error: 'В файле нет данных пребординга.' });
  for (const p of paths) {
    const err = acl.writeError(user, p, null, docs[p], user.people);
    if (err) return json(400, { error: p + ': ' + err });
  }
  for (const p of paths) await store.tx(p, () => JSON.parse(JSON.stringify(docs[p])), user.email);
  return json(200, { ok: true, docs: paths.length });
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
      if (method === 'GET' && url === '/') return page(cfg.local, portalOn(cfg) ? 'portal' : 'metrics');
      if (method === 'GET' && url === '/metrics' && portalOn(cfg)) {
        // метрики — только команде; новичок и гость попадают на вход портала
        const u = await currentUser(cfg, store, headers);
        return u && u.role !== 'employee' ? page(cfg.local, 'metrics') : redirect('/');
      }
      if (!cfg.local && method === 'GET' && url === '/api/login') return auth.loginRedirect(cfg);
      if (!cfg.local && method === 'GET' && url === '/api/callback') return await callback(cfg, store, query, headers, fetchFn);
      if (!url.startsWith('/api/')) return respond(404, 'Не найдено');
      // запись — только со своей страницы: свой заголовок кросс-доменный сайт без разрешения CORS не пошлёт
      if (method !== 'GET' && auth.headerOf(headers, 'x-hr') !== '1') return json(403, { error: 'Запрос не со страницы приложения.' });
      const body = () => { try { return JSON.parse(event.isBase64Encoded ? Buffer.from(event.body || '', 'base64').toString() : event.body || ''); } catch (e) { return null; } };
      if (cfg.local && method === 'POST' && url === '/api/plogin') return await passwordLogin(cfg, store, body() || {}, clientIp(event), headers);
      if (portalOn(cfg) && method === 'POST' && url === '/api/plogin-code') return await codeLogin(cfg, store, body() || {}, headers);
      if (portalOn(cfg) && method === 'POST' && url === '/api/reset-start') return await resetStart(cfg, store, body() || {}, clientIp(event));
      if (portalOn(cfg) && method === 'POST' && url === '/api/reset-finish') return await resetFinish(cfg, store, body() || {}, headers);
      if (cfg.webImport && method === 'POST' && url === '/api/import-initial') return await importInitial(store, body() || {});
      const user = await currentUser(cfg, store, headers);
      if (!user) return json(401, { error: 'Нужно войти.', empty: cfg.webImport ? (await store.count()) === 0 : undefined });
      if (portalOn(cfg) && user.admin && method === 'POST' && url === '/api/import-preboard') return await importPreboard(store, user, body() || {});
      if (cfg.local && user.admin && method === 'POST' && url === '/api/replace-data') return await replaceFromJournals(store, user, body() || {});
      if (method === 'GET' && url === '/api/me') return json(200, { pid: user.pid, email: user.email, admin: user.admin, role: user.role, code: user.code,
        name: user.name || [(user.people[user.pid] || {}).name, (user.people[user.pid] || {}).surname].filter(Boolean).join(' ') });
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
module.exports.forTests = { makeHandler: (store, cfg, f) => withLogout(makeHandler(store, cfg, f)), config, memoryStore, pwMark, smtpSend, resetLimits: () => [FAILS, GOOD, OTP, SENT].forEach(m => m.clear()) };
