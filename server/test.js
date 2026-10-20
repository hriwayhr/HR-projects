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
    assert.match(await (await fetch(base + '/')).text(), /window\.HR_LOCAL = true/);
    assert.equal((await post('/api/import-initial', { docs: seed.data })).status, 401);   // со страницы на сервере — нельзя
    const me = await (await fetch(base + '/api/me')).json();
    assert.equal(me.empty, undefined);
    const ok = await post('/api/plogin', { login: 'Yulia@Example.ru', password: 'Secret-1' });
    assert.equal(ok.status, 200);
    const cookie = ok.headers.get('set-cookie').split(';')[0];
    const sync = await (await fetch(base + '/api/sync', { headers: { Cookie: cookie } })).json();
    assert.ok(sync.docs.some(d => d.path === 'months/y_2026-10'));
    for (let i = 0; i < 10; i++) assert.equal((await post('/api/plogin', { login: 'yulia@example.ru', password: 'bad' })).status, 401);
    assert.equal((await post('/api/plogin', { login: 'yulia@example.ru', password: 'Secret-1' })).status, 429);   // даже верный пароль — после 10 ошибок ждать
  } finally { p.kill(); }
});

test('вход по паролю: администратор меняет свой логин на почту', async () => {
  const { forTests } = require('../cloud/function/index');
  const store = forTests.memoryStore();
  await store.tx('config/team', () => ({ people: { y: { name: 'Юля', login: 'yulia_n', salt: 's', hash: 'h', admin: true } } }));
  const h = forTests.makeHandler(store, forTests.config({ LOCAL: '1', SESSION_SECRET: 's'.repeat(48) }));
  const auth = require('../cloud/function/auth');
  const cookie = auth.sessionCookie('s'.repeat(48), 'yulia_n').split(';')[0];
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
    'vacancies/old': { title: 'Старая', manager: 'Юля' } } };
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
    assert.deepEqual(docs, ['config/team', 'months/a_2026-10']);   // старая вакансия ушла, журналы — целиком
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
  const anna = { 'x-hr': '1', cookie: auth.sessionCookie(S, 'anna').split(';')[0] };
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
