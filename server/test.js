'use strict';
// Сервер целиком: запуск, страница с CSP, отказ без входа, ночная копия. Запуск: node --test server/test.js
const test = require('node:test');
const assert = require('node:assert');
const { spawn } = require('child_process');
const fs = require('fs'); const os = require('os'); const path = require('path');

test('сервер: страница, защита, вход через Яндекс', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-srv-'));
  const env = Object.assign({}, process.env, { DATA_DIR: data, PORT: '8799', BASE_URL: 'https://hr.example.ru', ALLOWED_DOMAINS: 'example.ru',
    ADMIN_EMAILS: 'boss@example.ru', OAUTH_CLIENT_ID: 'id', OAUTH_CLIENT_SECRET: 'sec', SESSION_SECRET: 's'.repeat(48), NODE_NO_WARNINGS: '1' });
  const p = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env });
  try {
    await new Promise((ok, no) => { p.stdout.on('data', d => /слушают/.test(d) && ok()); p.on('exit', c => no(new Error('вышел ' + c))); });
    const base = 'http://localhost:8799';
    const page = await fetch(base + '/');
    assert.equal(page.status, 200);
    assert.match(page.headers.get('content-security-policy'), /script-src 'nonce-/);
    assert.match(await page.text(), /window\.HR_CLOUD = true[\s\S]*HR-метрики/);
    assert.equal((await fetch(base + '/api/me')).status, 401);
    assert.equal((await fetch(base + '/api/sync', { headers: { Cookie: 'hr_s=forged.sig' } })).status, 401);
    const login = await fetch(base + '/api/login', { redirect: 'manual' });
    assert.match(login.headers.get('location'), /^https:\/\/oauth\.yandex\.ru\/authorize\?.*redirect_uri=https%3A%2F%2Fhr\.example\.ru%2Fapi%2Fcallback/);
    assert.equal((await fetch(base + '/api/doc', { method: 'POST', body: 'x'.repeat(17 * 1024 * 1024) }).catch(() => ({ status: 413 }))).status, 413);
    assert.deepEqual(fs.readdirSync(path.join(data, 'backups')), []);   // пустую базу не копируем
  } finally { p.kill(); }
  // без настроек сервер не стартует
  const bad = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env: Object.assign({}, process.env, { DATA_DIR: data, SESSION_SECRET: '' }) });
  const code = await new Promise(ok => bad.on('exit', ok));
  assert.equal(code, 1);
});

test('сервер: вход по паролю, данные из файла, защита от перебора', async () => {
  const crypto = require('crypto');
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-srv-'));
  const hash = crypto.createHash('sha256').update('s1::Secret-1').digest('hex');
  const seed = { data: { 'config/team': { people: { y: { name: 'Юля', login: 'yulia@example.ru', salt: 's1', hash, admin: true } } }, 'months/y_2026-10': { person: 'y', month: '2026-10', days: {} } } };
  fs.writeFileSync(path.join(data, 'import.html'), '<script>\n  var SEED = ' + JSON.stringify(seed) + ';\n  var TEMPLATE = "";</script>');
  const env = Object.assign({}, process.env, { DATA_DIR: data, PORT: '8798', AUTH: 'password', SESSION_SECRET: 's'.repeat(48), NODE_NO_WARNINGS: '1' });
  const p = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env });
  try {
    await new Promise((ok, no) => { p.stdout.on('data', d => /слушают/.test(d) && ok()); p.on('exit', c => no(new Error('вышел ' + c))); });
    const base = 'http://localhost:8798', post = (u, b) => fetch(base + u, { method: 'POST', headers: { 'X-HR': '1', 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
    assert.ok(!fs.existsSync(path.join(data, 'import.html')));   // загружен и удалён
    assert.match(await (await fetch(base + '/')).text(), /window\.HR_SERVER = true/);   // на «/» — портал с общим входом
    assert.equal((await fetch(base + '/metrics', { redirect: 'manual' })).status, 302);    // метрики — только после входа
    assert.equal((await post('/api/import-initial', { docs: seed.data })).status, 401);   // со страницы на сервере — нельзя
    // больше 1 МБ без входа — сервер обрывает приём, память не забивается
    const big = await fetch(base + '/api/plogin', { method: 'POST', headers: { 'X-HR': '1' }, body: 'x'.repeat(2 * 1024 * 1024) }).then(r => r.status, () => 'обрыв');
    assert.ok(big === 413 || big === 'обрыв', String(big));
    // перенос журналов (до 16 МБ) — только с действующей сессией; без неё и 2 МБ не принимаем
    const big2 = await fetch(base + '/api/replace-data', { method: 'POST', headers: { 'X-HR': '1' }, body: 'x'.repeat(2 * 1024 * 1024) }).then(r => r.status, () => 'обрыв');
    assert.ok(big2 === 413 || big2 === 'обрыв', String(big2));
    const me = await (await fetch(base + '/api/me')).json();
    assert.equal(me.empty, undefined);
    const ok = await post('/api/plogin', { login: 'Yulia@Example.ru', password: 'Secret-1' });
    assert.equal(ok.status, 200);
    const cookie = ok.headers.get('set-cookie').split(';')[0];
    assert.match(await (await fetch(base + '/metrics', { headers: { Cookie: cookie } })).text(), /window\.HR_LOCAL = true; window\.HR_PORTAL = true/);
    const sync = await (await fetch(base + '/api/sync', { headers: { Cookie: cookie } })).json();
    assert.ok(sync.docs.some(d => d.path === 'months/y_2026-10'));
    for (let i = 0; i < 10; i++) assert.equal((await post('/api/plogin', { login: 'yulia@example.ru', password: 'bad' })).status, 401);
    assert.equal((await post('/api/plogin', { login: 'yulia@example.ru', password: 'Secret-1' })).status, 429);   // даже верный пароль — после 10 ошибок по логину с адреса ждать
  } finally { p.kill(); }
});

test('вход по паролю: администратор меняет свой логин на почту', async () => {
  const { forTests } = require('../cloud/function/index');
  const store = forTests.memoryStore();
  await store.tx('config/team', () => ({ people: { y: { name: 'Юля', login: 'yulia_n', salt: 's', hash: 'h', admin: true } } }));
  const h = forTests.makeHandler(store, forTests.config({ LOCAL: '1', SESSION_SECRET: 's'.repeat(48) }));
  const auth = require('../cloud/function/auth');
  const cookie = auth.sessionCookie('s'.repeat(48), 'yulia_n|' + forTests.pwMark('h')).split(';')[0];
  const r = await h({ httpMethod: 'POST', url: '/api/doc', headers: { 'x-hr': '1', cookie }, body: JSON.stringify({ path: 'config/team', op: 'set',
    data: { people: { y: { name: 'Юля', login: 'yulia@iway.ru', salt: 's', hash: 'h', admin: true } } } }) });
  assert.equal(r.statusCode, 200, r.body);
  const r2 = await h({ httpMethod: 'POST', url: '/api/doc', headers: { 'x-hr': '1', cookie }, body: JSON.stringify({ path: 'config/team', op: 'set',
    data: { people: { y: { name: 'Юля', login: 'yulia@iway.ru', salt: 's', hash: 'h', admin: false } } } }) });
  assert.equal(r2.statusCode, 401);   // старый логин больше не действует — нужно войти заново
});

test('сервер: данные из папки data локальной версии — с паролями', async () => {
  const crypto = require('crypto');
  const { logStore } = require('../cloud/function/store');
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-srv-'));
  const hash = crypto.createHash('sha256').update('s2::Anna-pass').digest('hex');
  const local = logStore(path.join(data, 'import-data'), 'PC1');   // как пишет локальная версия в «Обменнике»
  await local.tx('config/team', () => ({ people: { y: { name: 'Юля', login: 'yulia', salt: 's1', hash: 'x', admin: true }, a: { name: 'Анна', login: 'anna', salt: 's2', hash } } }));
  await local.tx('months/a_2026-10', () => ({ person: 'a', month: '2026-10', days: { '2026-10-15': { calls: 3 } } }));
  const env = Object.assign({}, process.env, { DATA_DIR: data, PORT: '8796', AUTH: 'password', SESSION_SECRET: 's'.repeat(48), NODE_NO_WARNINGS: '1' });
  const p = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env });
  try {
    await new Promise((ok, no) => { p.stdout.on('data', d => /слушают/.test(d) && ok()); p.on('exit', c => no(new Error('вышел ' + c))); });
    assert.ok(!fs.existsSync(path.join(data, 'import-data')));   // загружено и удалено
    const r = await fetch('http://localhost:8796/api/plogin', { method: 'POST', headers: { 'X-HR': '1', 'Content-Type': 'application/json' }, body: JSON.stringify({ login: 'anna', password: 'Anna-pass' }) });
    assert.equal(r.status, 200);
    const sync = await (await fetch('http://localhost:8796/api/sync', { headers: { Cookie: r.headers.get('set-cookie').split(';')[0] } })).json();
    assert.deepEqual(sync.docs.find(d => d.path === 'months/a_2026-10').data.days['2026-10-15'], { calls: 3 });
  } finally { p.kill(); }
});

test('сервер: администратор заменяет данные журналами локальной версии со страницы', async () => {
  const crypto = require('crypto');
  const { logStore } = require('../cloud/function/store');
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-srv-'));
  const sha = (s, p) => crypto.createHash('sha256').update(s + '::' + p).digest('hex');
  // сегодня: данные из версии для ПК — Юля и старая вакансия
  const seed = { data: { 'config/team': { people: { y: { name: 'Юля', login: 'yulia', salt: 's1', hash: sha('s1', 'Y-1'), admin: true }, a: { name: 'Анна', login: 'anna' } } },
    'vacancies/old': { title: 'Старая', manager: 'Юля' }, 'employees/IW-AAAA': { code: 'IW-AAAA', firstName: 'Новичок' } } };
  fs.writeFileSync(path.join(data, 'import.html'), '<script>\n  var SEED = ' + JSON.stringify(seed) + ';\n  var TEMPLATE = "";</script>');
  // завтра: журналы двух ПК из «Обменника» — у Анны появился пароль
  const jdir = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-obm-'));
  const pc1 = logStore(jdir, 'PC1'), pc2 = logStore(jdir, 'PC2');
  await pc1.tx('config/team', () => ({ people: { y: { name: 'Юля', login: 'yulia', salt: 's1', hash: sha('s1', 'Y-1'), admin: true }, a: { name: 'Анна', login: 'anna', salt: 's2', hash: sha('s2', 'A-2') } } }));
  await pc2.tx('months/a_2026-10', () => ({ person: 'a', month: '2026-10', days: { '2026-10-20': { calls: 7 } } }));
  const files = fs.readdirSync(jdir).map(f => fs.readFileSync(path.join(jdir, f), 'utf8'));
  const env = Object.assign({}, process.env, { DATA_DIR: data, PORT: '8795', AUTH: 'password', SESSION_SECRET: 's'.repeat(48), NODE_NO_WARNINGS: '1' });
  const p = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env });
  const base = 'http://localhost:8795', post = (u, b, c) => fetch(base + u, { method: 'POST', headers: Object.assign({ 'X-HR': '1', 'Content-Type': 'application/json' }, c ? { Cookie: c } : {}), body: JSON.stringify(b) });
  const login = async (l, pw) => { const r = await post('/api/plogin', { login: l, password: pw }); return r.status === 200 ? r.headers.get('set-cookie').split(';')[0] : null; };
  try {
    await new Promise((ok, no) => { p.stdout.on('data', d => /слушают/.test(d) && ok()); p.on('exit', c => no(new Error('вышел ' + c))); });
    assert.equal(await login('anna', 'A-2'), null);   // пароля у Анны пока нет
    const y = await login('yulia', 'Y-1');
    assert.equal((await post('/api/replace-data', { files: ['{"bad":1}\n'] }, y)).status, 400);   // не журналы — ничего не трогаем
    const r = await post('/api/replace-data', { files }, y);
    assert.equal(r.status, 200, await r.clone().text());
    const a = await login('anna', 'A-2');
    assert.ok(a);
    assert.equal((await post('/api/replace-data', { files }, a)).status, 404);   // не администратор — нельзя
    const docs = (await (await fetch(base + '/api/sync', { headers: { Cookie: y } })).json()).docs.map(d => d.path).sort();
    assert.deepEqual(docs, ['config/team', 'employees/IW-AAAA', 'months/a_2026-10']);   // старая вакансия ушла, журналы — целиком; пребординг портала цел
  } finally { p.kill(); }
});

test('отпуск с передачей: коллега видит и ведёт вакансии только в дни отпуска', async () => {
  const { forTests } = require('../cloud/function/index');
  const auth = require('../cloud/function/auth'), acl = require('../cloud/function/acl');
  const S = 's'.repeat(48), store = forTests.memoryStore();
  const h = forTests.makeHandler(store, forTests.config({ LOCAL: '1', SESSION_SECRET: S }));
  const day = acl.todayMsk(), add = n => new Date(Date.parse(day) + n * 864e5).toISOString().slice(0, 10);
  await store.tx('config/team', () => ({ people: { y: { name: 'Юлия', surname: 'Немчинова', login: 'yulia', admin: true }, a: { name: 'Анна', surname: 'Шулятицкая', login: 'anna' } } }));
  await store.tx('vacancies/v1', () => ({ title: 'Логист', manager: 'Немчинова', status: 'активна' }));
  await store.tx('vacancies/v2', () => ({ title: 'Бухгалтер', manager: 'Немчинова', status: 'активна' }));
  const anna = { 'x-hr': '1', cookie: auth.sessionCookie(S, 'anna|' + forTests.pwMark(undefined)).split(';')[0] };
  const sync = async since => JSON.parse((await h({ httpMethod: 'GET', url: '/api/sync', headers: anna, queryStringParameters: { since: String(since || 0) } })).body);
  const put = async (data) => (await h({ httpMethod: 'POST', url: '/api/doc', headers: anna, body: JSON.stringify({ path: 'vacancies/v1', op: 'set', data }) })).statusCode;
  // отпуск Юлии впереди — у Анны её вакансий нет
  await store.tx('vacations/y', () => ({ list: [{ from: add(1), to: add(5), sub: 'a', pause: ['v2'] }] }));
  let s = await sync(); assert.deepEqual(s.docs.map(d => d.path).filter(p => p.startsWith('vacancies/')), []);
  assert.equal(await put({ title: 'Логист', manager: 'Немчинова', status: 'активна', comment: 'x' }), 403);
  // отпуск идёт — Анна видит обе (и на паузе — ради напоминаний), правит; ответственным остаётся Юлия
  const ver = s.ver;
  await store.tx('vacations/y', () => ({ list: [{ from: add(-1), to: add(3), sub: 'a', pause: ['v2'] }] }));
  s = await sync(); assert.deepEqual(s.docs.map(d => d.path).filter(p => p.startsWith('vacancies/')).sort(), ['vacancies/v1', 'vacancies/v2']);
  assert.ok(s.docs.some(d => d.path === 'vacations/y'));
  assert.deepEqual((await sync(ver)).docs.map(d => d.path).filter(p => p.startsWith('vacancies/')).sort(), ['vacancies/v1', 'vacancies/v2']);   // и в частичной синхронизации
  assert.equal(await put({ title: 'Логист', manager: 'Немчинова', status: 'активна', comment: 'продлила' }), 200);
  assert.equal(await put({ title: 'Логист', manager: 'Кто-то ещё', status: 'активна' }), 403);   // передать дальше нельзя
  // отпуск кончился — вакансии вернулись к Юлии
  await store.tx('vacations/y', () => ({ list: [{ from: add(-6), to: add(-1), sub: 'a' }] }));
  s = await sync(); assert.deepEqual(s.docs.map(d => d.path).filter(p => p.startsWith('vacancies/')), []);
  assert.equal(await put({ title: 'Логист', manager: 'Немчинова', status: 'активна' }), 403);
});

test('портал: один вход, роли администратор / HR-менеджер / сотрудник', async () => {
  process.env.PORTAL_SRC = path.join(__dirname, '..', 'src', 'iway-portal.html');
  delete require.cache[require.resolve('../cloud/function/index')];
  const { forTests } = require('../cloud/function/index');
  const crypto = require('crypto'), sha = (s, p) => crypto.createHash('sha256').update(s + '::' + p).digest('hex');
  const store = forTests.memoryStore();
  const h = forTests.makeHandler(store, forTests.config({ LOCAL: '1', SESSION_SECRET: 's'.repeat(48) }));
  await store.tx('config/team', () => ({ people: { y: { name: 'Юлия', login: 'yulia', salt: 's1', hash: sha('s1', 'Y-1'), admin: true },
    a: { name: 'Анна', surname: 'Шулятицкая', login: 'anna', email: 'anna@iway.ru', salt: 's2', hash: sha('s2', 'A-2') } } }));
  await store.tx('employees/IW-AAAA', () => ({ code: 'IW-AAAA', login: 'new.person', email: 'n.person@iway.ru', firstName: 'Ника', lastName: 'Новая', salt: 's3', hash: sha('s3', 'N-3'), offer: { salary: 1 } }));
  await store.tx('employees/IW-BBBB', () => ({ code: 'IW-BBBB', firstName: 'Другой' }));
  await store.tx('config/departments', () => ({ list: [{ name: 'Логистика' }] }));
  await store.tx('config/templates', () => ({ tpl: { offer: {} } }));
  await store.tx('months/a_2026-10', () => ({ person: 'a', month: '2026-10', days: {} }));
  const call = (method, url, cookie, body) => h({ httpMethod: method, url, headers: Object.assign({ 'x-hr': '1' }, cookie ? { cookie } : {}), body: body && JSON.stringify(body) });
  const login = async (l, pw) => { const r = await call('POST', '/api/plogin', null, { login: l, password: pw }); return r.statusCode === 200 ? r.multiValueHeaders['Set-Cookie'][0].split(';')[0] : null; };
  const paths = async c => JSON.parse((await call('GET', '/api/sync', c)).body).docs.map(d => d.path).sort();
  // как страница: base — документ, каким его видели; сервер применяет только правку поверх
  const put = async (c, p, data, base) => (await call('POST', '/api/doc', c, { path: p, op: 'set', data, base: base || null })).statusCode;

  // сотрудник: входит кодом, логином или почтой; видит свою карточку без пароля и справочник отделов
  assert.ok(await login('iw-aaaa', 'N-3') && await login('n.person@iway.ru', 'N-3'));
  const e = await login('new.person', 'N-3');
  const me = JSON.parse((await call('GET', '/api/me', e)).body);
  assert.deepEqual([me.role, me.code, me.name], ['employee', 'IW-AAAA', 'Ника Новая']);
  assert.deepEqual(await paths(e), ['config/departments', 'employees/IW-AAAA']);
  const own = JSON.parse((await call('GET', '/api/sync', e)).body).docs.find(d => d.path === 'employees/IW-AAAA').data;
  assert.equal(own.hash, undefined);
  assert.equal(await put(e, 'employees/IW-AAAA', Object.assign({}, own, { progress: { day1: true } }), own), 200);   // свои шаги — можно
  assert.equal((await store.get('employees/IW-AAAA')).hash, sha('s3', 'N-3'));                                 // пароль при этом цел
  assert.equal(await put(e, 'employees/IW-AAAA', Object.assign({}, own, { offer: { salary: 2 } }), own), 403);    // оффер — только HR
  assert.equal(await put(e, 'employees/IW-BBBB', { code: 'IW-BBBB' }), 403);
  assert.equal((await h({ httpMethod: 'GET', url: '/metrics', headers: { cookie: e } })).statusCode, 302);  // метрики сотруднику закрыты

  // HR-менеджер: входит почтой, правит пребординг целиком, в метриках — как рекрутер (своё), настройки — нет
  const a = await login('anna@iway.ru', 'A-2');
  assert.equal(JSON.parse((await call('GET', '/api/me', a)).body).role, 'hr');
  assert.deepEqual(await paths(a), ['config/departments', 'config/team', 'config/templates', 'employees/IW-AAAA', 'employees/IW-BBBB', 'months/a_2026-10']);
  assert.equal(await put(a, 'employees/IW-BBBB', { code: 'IW-BBBB', firstName: 'Другой', dept: 'Логистика' }), 200);
  assert.equal(await put(a, 'config/templates', { tpl: { offer: { subj: 'x' } } }), 200);
  assert.equal(await put(a, 'employees/IW-CCCC', { code: 'IW-CCCC', login: 'yulia' }), 403);   // логин занят командой
  assert.equal(await put(a, 'employees/IW-DDDD', { code: 'IW-XXXX' }), 403);
  assert.equal(await put(a, 'config/team', { people: {} }), 403);
  assert.equal((await h({ httpMethod: 'GET', url: '/metrics', headers: { cookie: a } })).statusCode, 200);
  assert.equal((await call('POST', '/api/import-preboard', a, { docs: {} })).statusCode, 404);

  // администратор: переносит пребординг из прежнего артефакта; учётные записи admins/* не переносятся
  const y = await login('yulia', 'Y-1');
  assert.equal(JSON.parse((await call('GET', '/api/me', y)).body).role, 'admin');
  const r = await call('POST', '/api/import-preboard', y, { docs: { 'employees/IW-EEEE': { code: 'IW-EEEE' }, 'config/page': { sections: {} }, 'admins/x@iway.ru': { hash: 'h' }, 'months/y_2026-10': { person: 'y' } } });
  assert.equal(JSON.parse(r.body).docs, 2);
  assert.equal(await store.get('admins/x@iway.ru'), null);
  assert.equal(await store.get('months/y_2026-10'), null);

  // удалили карточку — вход сотрудника закрыт сразу
  await store.tx('employees/IW-AAAA', () => null);
  assert.equal((await call('GET', '/api/me', e)).statusCode, 401);
});

test('атаки на вход и данные портала', async () => {
  process.env.PORTAL_SRC = path.join(__dirname, '..', 'src', 'iway-portal.html');
  const { forTests } = require('../cloud/function/index');
  const crypto = require('crypto'), sha = (s, p) => crypto.createHash('sha256').update(s + '::' + p).digest('hex');
  const store = forTests.memoryStore();
  const h = forTests.makeHandler(store, forTests.config({ LOCAL: '1', SESSION_SECRET: 's'.repeat(48) }));
  await store.tx('config/team', () => ({ people: { y: { name: 'Юлия', login: 'yulia-sec', salt: 's1', hash: sha('s1', 'Y-1'), admin: true },
    a: { name: 'Анна', login: 'anna-sec', salt: 's2', hash: sha('s2', 'A-2') } } }));
  await store.tx('employees/IW-SEC1', () => ({ code: 'IW-SEC1', login: 'sec.one', salt: 's3', hash: sha('s3', 'N-3') }));
  // за Caddy: соединение из внутренней сети, адрес клиента — в X-Forwarded-For
  const login = (l, pw, ip, sock = '172.18.0.2') => h({ httpMethod: 'POST', url: '/api/plogin', requestContext: { identity: { sourceIp: sock } },
    headers: { 'x-hr': '1', 'x-forwarded-for': ip }, body: JSON.stringify({ login: l, password: pw }) });
  const cookieOf = r => r.multiValueHeaders['Set-Cookie'][0].split(';')[0];
  const call = (c, method, url, body) => h({ httpMethod: method, url, headers: { 'x-hr': '1', cookie: c }, body: body && JSON.stringify(body) });

  // анна уже входила из офиса (адрес 203.0.113.5) — потом с этого же адреса кто-то перебирает пароли
  assert.equal((await login('anna-sec', 'A-2', '203.0.113.5')).statusCode, 200);
  for (let i = 0; i < 10; i++) assert.equal((await login('yulia-sec', 'bad' + i, '203.0.113.5')).statusCode, 401);
  assert.equal((await login('yulia-sec', 'Y-1', '203.0.113.5')).statusCode, 429);       // этот логин с этого адреса — ждать
  for (let i = 0; i < 10; i++) await login('nobody' + i, 'x', '203.0.113.5');
  assert.equal((await login('sec.one', 'N-3', '203.0.113.5')).statusCode, 429);         // новый человек с этого адреса — ждать
  assert.equal((await login('anna-sec', 'A-2', '203.0.113.5')).statusCode, 200);        // а кто уже входил отсюда — входит
  assert.equal((await login('yulia-sec', 'Y-1', '198.51.100.7')).statusCode, 200);      // с другого адреса — всё работает
  // подменённый X-Forwarded-For при прямом соединении не помогает: считаем по адресу соединения
  assert.equal((await login('sec.one', 'N-3', '198.51.100.99', '203.0.113.5')).statusCode, 429);
  // перебор одного логина с многих адресов сразу (параллельно): новым адресам ждать, владелец со своего адреса входит
  await Promise.all(Array.from({ length: 60 }, (_, i) => login('yulia-sec', 'bad', '192.0.2.' + i, '8.8.' + i + '.1')));
  assert.equal((await login('yulia-sec', 'Y-1', '192.0.2.250', '8.8.250.1')).statusCode, 429);
  assert.equal((await login('yulia-sec', 'Y-1', '198.51.100.7')).statusCode, 200);
  // сменили пароль — прежняя сессия больше не действует
  const a = cookieOf(await login('anna-sec', 'A-2', '198.51.100.50'));
  assert.equal((await call(a, 'GET', '/api/me')).statusCode, 200);
  await store.tx('config/team', prev => { const p = JSON.parse(JSON.stringify(prev)); p.people.a.hash = sha('s2', 'new'); return p; });
  assert.equal((await call(a, 'GET', '/api/me')).statusCode, 401);
  // сессия без отпечатка пароля (подделка под старый формат) не принимается
  const auth = require('../cloud/function/auth');
  assert.equal((await call(auth.sessionCookie('s'.repeat(48), 'yulia-sec').split(';')[0], 'GET', '/api/me')).statusCode, 401);

  // сотрудник: в отметки — только ожидаемые значения, никакой разметки
  await store.tx('employees/IW-SEC2', () => ({ code: 'IW-SEC2', login: 'sec.two', salt: 's4', hash: sha('s4', 'N-4') }));
  const e = cookieOf(await login('sec.two', 'N-4', '198.51.100.60'));
  const own = JSON.parse((await call(e, 'GET', '/api/sync')).body).docs.find(d => d.path === 'employees/IW-SEC2').data;
  // обновления не раскрывают адреса чужих документов (коды коллег, месяцы метрик)
  await store.tx('months/a_2026-10', () => ({ person: 'a', month: '2026-10', days: {} }));
  await store.tx('employees/IW-SEC9', () => ({ code: 'IW-SEC9' }));
  await store.tx('employees/IW-SEC9', () => null);
  assert.deepEqual(JSON.parse((await call(e, 'GET', '/api/sync?since=1')).body).docs.map(d => d.path), ['employees/IW-SEC2']);
  const put = (c, p, data, base) => call(c, 'POST', '/api/doc', { path: p, op: 'set', data, base: base || null }).then(r => r.statusCode);
  assert.equal(await put(e, 'employees/IW-SEC2', Object.assign({}, own, { cardChoice: '<img src=x onerror=alert(1)>' }), own), 403);
  assert.equal(await put(e, 'employees/IW-SEC2', Object.assign({}, own, { progress: { docs: '<script>' } }), own), 403);
  assert.equal(await put(e, 'employees/IW-SEC2', Object.assign({}, own, { openedAt: 'не дата' }), own), 403);
  assert.equal(await put(e, 'employees/IW-SEC2', Object.assign({}, own, { cardChoice: 'need', progress: { docs: true } }), own), 200);
  assert.equal(await put(e, 'employees/IW-SEC2', Object.assign({}, own, { hash: 'x' }), own), 403);              // свой пароль — только через HR
  assert.equal((await call(e, 'POST', '/api/doc', { path: 'employees/IW-SEC2', op: 'delete' })).statusCode, 403);
  assert.equal((await call(e, 'POST', '/api/doc', { path: 'config/departments', op: 'set', data: { list: [] } })).statusCode, 403);
  assert.equal((await call(e, 'POST', '/api/doc', { path: '../config/team', op: 'set', data: {} })).statusCode, 403);
  // HR: пароль открытым текстом (страница без https) не сохраняется
  const y = cookieOf(await login('yulia-sec', 'Y-1', '198.51.100.7'));
  assert.equal(await put(y, 'employees/IW-SEC3', { code: 'IW-SEC3', salt: 'a', hash: 'plain:a::123' }), 403);
  // запрос не со страницы портала (без заголовка X-HR) — отклоняется
  assert.equal((await h({ httpMethod: 'POST', url: '/api/doc', headers: { cookie: y }, body: '{}' })).statusCode, 403);
});
