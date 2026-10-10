'use strict';
// Сервер без облака: хранилище в памяти, Яндекс ID — подставной. Запуск: node --test test/
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const auth = require('../auth');
const acl = require('../acl');
const { forTests } = require('../index');

const dir = path.join(__dirname, '..', 'static');
if (!fs.existsSync(path.join(dir, 'index.html'))) { fs.mkdirSync(dir, { recursive: true }); fs.writeFileSync(path.join(dir, 'index.html'), '<!doctype html><script>1</script>'); }

const SECRET = 'x'.repeat(40);
const cfg = forTests.config({ BASE_URL: 'https://hr.example', OAUTH_CLIENT_ID: 'id', OAUTH_CLIENT_SECRET: 'sec', SESSION_SECRET: SECRET, ALLOWED_DOMAINS: 'iway.ru', ADMIN_EMAILS: 'boss@iway.ru' });

// подставной Яндекс: код → почта
function fakeYandex(emails) {
  return async (url, opts) => {
    if (url.startsWith('https://oauth.yandex.ru/token')) {
      const code = new URLSearchParams(opts.body).get('code');
      return emails[code] ? { ok: true, json: async () => ({ access_token: 't-' + code }) } : { ok: false, status: 400 };
    }
    if (url.startsWith('https://login.yandex.ru/info')) {
      const code = opts.headers.Authorization.replace('OAuth t-', '');
      return { ok: true, json: async () => ({ default_email: emails[code], id: 'yid-' + code.replace(/2$/, '') }) };
    }
    if (url.startsWith('https://storage.yandexcloud.net/')) { fakeYandex.put = { url, opts }; return { ok: true }; }
    throw new Error('unexpected ' + url);
  };
}
const EMAILS = { boss: 'Boss@iway.ru', ann: 'ann@iway.ru', ext: 'ann@gmail.com', bob: 'bob@iway.ru', gone: 'gone@iway.ru', other: 'ann@iway.ru' };

function setup() {
  const store = forTests.memoryStore();
  const h = forTests.makeHandler(store, cfg, fakeYandex(EMAILS));
  async function login(code) {
    const r1 = await h({ httpMethod: 'GET', path: '/api/login', headers: {} });
    const state = new URL(r1.headers.Location).searchParams.get('state');
    const r2 = await h({ httpMethod: 'GET', path: '/api/callback', headers: { Cookie: 'hr_st=' + state }, queryStringParameters: { code, state } });
    const set = (r2.multiValueHeaders || {})['Set-Cookie'] || [];
    const c = set.find(x => x.startsWith('hr_s='));
    return { res: r2, cookie: c ? c.split(';')[0] : null };
  }
  function call(cookie, method, p, body, extra = {}) {
    return h(Object.assign({ httpMethod: method, path: p, headers: Object.assign({ 'X-HR': '1' }, cookie ? { Cookie: cookie } : {}), queryStringParameters: {}, body: body ? JSON.stringify(body) : '' }, extra))
      .then(r => ({ status: r.statusCode, body: /json/.test(r.headers['Content-Type']) ? JSON.parse(r.body) : r.body, raw: r }));
  }
  const put = (c, p, data) => call(c, 'POST', '/api/doc', { path: p, op: 'set', data });
  const docs = async c => { const r = await call(c, 'GET', '/api/sync'); const o = {}; r.body.docs.forEach(d => { if (d.data) o[d.path] = d.data; }); return o; };
  return { store, h, login, call, put, docs };
}

// команда: boss — администратор (создан первым входом), ann и bob — рекрутеры, gone — в архиве
async function seeded() {
  const s = setup();
  const boss = (await s.login('boss')).cookie;
  const team = (await s.docs(boss))['config/team'];
  const bossId = Object.keys(team.people)[0];
  team.people.ann = { name: 'Анна', surname: 'Шулятицкая', email: 'ann@iway.ru', order: 2 };
  team.people.bob = { name: 'Боб', surname: 'Петров', email: 'bob@iway.ru', order: 3 };
  team.people.gone = { name: 'Гоша', email: 'gone@iway.ru', archived: true, order: 4 };
  assert.equal((await s.put(boss, 'config/team', team)).status, 200);
  await s.put(boss, 'months/ann_2026-10', { person: 'ann', month: '2026-10', days: { '2026-10-01': { calls: 3 } } });
  await s.put(boss, 'months/bob_2026-10', { person: 'bob', month: '2026-10', days: { '2026-10-01': { calls: 5 } } });
  await s.put(boss, 'vacancies/v1', { title: 'Логист', manager: 'Шулятицкая', status: 'активна' });
  await s.put(boss, 'vacancies/v2', { title: 'Диспетчер', manager: 'Петров Б.', status: 'активна' });
  await s.put(boss, 'rejections/2026-10', { month: '2026-10', items: [{ d: '2026-10-01', r: 'Зарплата', w: 'Анна Шулятицкая', n: 2 }, { d: '2026-10-01', r: 'Опыт', w: 'Петров', n: 1 }] });
  return Object.assign(s, { boss, bossId, ann: (await s.login('ann')).cookie, bob: (await s.login('bob')).cookie });
}

test('страница: CSP с nonce, запрет встраивания, HSTS', async () => {
  const { call } = setup();
  const r = await call(null, 'GET', '/');
  const csp = r.raw.headers['Content-Security-Policy'], nonce = csp.match(/'nonce-([^']+)'/)[1];
  assert.match(r.body, new RegExp('<script nonce="' + nonce.replace(/[+/=]/g, '\\$&') + '">'));
  assert.match(csp, /frame-ancestors 'none'/); assert.match(csp, /connect-src 'self'/);
  assert.equal(r.raw.headers['X-Frame-Options'], 'DENY'); assert.match(r.raw.headers['Strict-Transport-Security'], /max-age/);
});

test('вход: первый — владелец из ADMIN_EMAILS, чужой домен и посторонние не входят', async () => {
  const s = setup();
  assert.equal((await s.login('ext')).res.headers.Location, '/?login=domain');
  assert.equal((await s.login('ann')).res.headers.Location, '/?login=noaccess');   // в команде ещё нет
  const b = await s.login('boss');
  assert.equal(b.res.headers.Location, '/'); assert.ok(b.cookie);
  assert.match(b.res.multiValueHeaders['Set-Cookie'][0], /HttpOnly; Secure; SameSite=Lax/);
  const me = await s.call(b.cookie, 'GET', '/api/me');
  assert.deepEqual([me.body.email, me.body.admin], ['boss@iway.ru', true]);
  // второй вход владельца не плодит администраторов
  await s.login('boss');
  assert.equal(Object.keys((await s.docs(b.cookie))['config/team'].people).length, 1);
});

test('вход: подмена state и неверный код — отказ', async () => {
  const s = setup();
  const r = await s.h({ httpMethod: 'GET', path: '/api/callback', headers: { Cookie: 'hr_st=aaa' }, queryStringParameters: { code: 'boss', state: 'bbb' } });
  assert.equal(r.headers.Location, '/?login=failed');
  const r2 = await s.h({ httpMethod: 'GET', path: '/api/callback', headers: { Cookie: 'hr_st=aaa' }, queryStringParameters: { code: 'nope', state: 'aaa' } });
  assert.equal(r2.headers.Location, '/?login=failed');
});

test('почта привязана к аккаунту Яндекса первого входа: другой аккаунт с той же почтой не войдёт', async () => {
  const s = await seeded();
  assert.ok(s.store && (await s.docs(s.boss))['config/team'].people.ann.yid === 'yid-ann');
  assert.equal((await s.login('other')).res.headers.Location, '/?login=noaccess');   // личный Яндекс ID с рабочим адресом
  assert.equal((await s.login('ann')).res.headers.Location, '/');
});

test('сессия: без cookie, с поддельной и просроченной — 401', async () => {
  const s = await seeded();
  assert.equal((await s.call(null, 'GET', '/api/sync')).status, 401);
  const forged = 'hr_s=' + auth.sign('y'.repeat(40), { e: 'boss@iway.ru', x: Date.now() + 1e6 });
  assert.equal((await s.call(forged, 'GET', '/api/sync')).status, 401);
  const old = 'hr_s=' + auth.sign(SECRET, { e: 'boss@iway.ru', x: Date.now() - 1 });
  assert.equal((await s.call(old, 'GET', '/api/sync')).status, 401);
  const tampered = s.ann.replace(/^hr_s=([^.]+)/, (m, b) => 'hr_s=' + Buffer.from(JSON.stringify({ e: 'boss@iway.ru', x: Date.now() + 1e6 })).toString('base64url'));
  assert.equal((await s.call(tampered, 'GET', '/api/sync')).status, 401);
});

test('рекрутер видит только своё; почты коллег не видит', async () => {
  const s = await seeded();
  const d = await s.docs(s.ann);
  assert.deepEqual(Object.keys(d).sort(), ['config/team', 'months/ann_2026-10', 'rejections/2026-10', 'vacancies/v1']);
  assert.equal(d['rejections/2026-10'].items.length, 1);
  assert.ok(Object.values(d['config/team'].people).every(p => !('email' in p)));
  const all = await s.docs(s.boss);
  assert.equal(Object.keys(all).length, 6); assert.equal(all['config/team'].people.ann.email, 'ann@iway.ru');
});

test('рекрутер пишет только своё', async () => {
  const s = await seeded();
  assert.equal((await s.put(s.ann, 'months/ann_2026-10', { person: 'ann', month: '2026-10', days: {} })).status, 200);
  assert.equal((await s.put(s.ann, 'months/bob_2026-10', { person: 'bob', month: '2026-10', days: {} })).status, 403);
  assert.equal((await s.put(s.ann, 'months/ann_2026-11', { person: 'bob', month: '2026-11', days: {} })).status, 403);
  assert.equal((await s.put(s.ann, 'vacancies/v2', { title: 'x', manager: 'Шулятицкая' })).status, 403);   // чужую не перехватить
  assert.equal((await s.put(s.ann, 'vacancies/v1', { title: 'x', manager: 'Петров' })).status, 403);     // свою не отдать
  assert.equal((await s.put(s.ann, 'vacancies/new1', { title: 'Новая', manager: 'Анна Шулятицкая' })).status, 200);
  assert.equal((await s.call(s.ann, 'POST', '/api/doc', { path: 'vacancies/v1', op: 'delete' })).status, 403);
  assert.equal((await s.call(s.ann, 'POST', '/api/doc', { path: 'vacancies/v1', op: 'update', data: { probation: { result: 'passed', at: '2026-10-03' } } })).status, 200);
  assert.equal((await s.call(s.ann, 'POST', '/api/doc', { path: 'vacancies/v1', op: 'update', data: { manager: 'Петров' } })).status, 403);
  assert.equal((await s.put(s.ann, 'vacations/ann', { list: [] })).status, 200);
  assert.equal((await s.put(s.ann, 'vacations/bob', { list: [] })).status, 403);
  assert.equal((await s.put(s.ann, 'config/team', { people: {} })).status, 403);
  assert.equal((await s.put(s.ann, 'config/metrics', { list: [] })).status, 403);
  assert.equal((await s.put(s.ann, 'rejections/2026-10', { items: [] })).status, 403);
  assert.equal((await s.put(s.ann, 'secrets/x', {})).status, 403);
  assert.equal((await s.put(s.boss, '../etc/passwd', {})).status, 403);
  assert.equal((await s.put(s.boss, 'months/x', { person: 'ann', month: '2026-10' })).status, 403);
});

test('без заголовка X-HR запись не проходит (защита от подделки запроса с чужого сайта)', async () => {
  const s = await seeded();
  const r = await s.h({ httpMethod: 'POST', path: '/api/doc', headers: { Cookie: s.boss }, body: JSON.stringify({ path: 'config/metrics', op: 'set', data: { list: [] } }) });
  assert.equal(r.statusCode, 403);
});

test('архив закрывает доступ сразу, даже с живой сессией', async () => {
  const s = await seeded();
  const team = (await s.docs(s.boss))['config/team'];
  team.people.ann.archived = true;
  await s.put(s.boss, 'config/team', team);
  assert.equal((await s.call(s.ann, 'GET', '/api/sync')).status, 401);
  assert.equal((await s.login('gone')).res.headers.Location, '/?login=noaccess');
});

test('команда: нельзя запереться и задвоить почту', async () => {
  const s = await seeded();
  const t = (await s.docs(s.boss))['config/team'];
  const noAdmin = JSON.parse(JSON.stringify(t)); noAdmin.people[s.bossId].admin = false;
  assert.equal((await s.put(s.boss, 'config/team', noAdmin)).status, 403);
  const dup = JSON.parse(JSON.stringify(t)); dup.people.bob.email = 'ann@iway.ru';
  assert.equal((await s.put(s.boss, 'config/team', dup)).status, 403);
  // перенос данных: администратор становится человеком из загруженной команды
  const moved = { people: { yulia: { name: 'Юлия', admin: true, email: 'boss@iway.ru' }, ann: t.people.ann } };
  assert.equal((await s.put(s.boss, 'config/team', moved)).status, 200);
  assert.equal((await s.call(s.boss, 'GET', '/api/me')).body.pid, 'yulia');
});

test('синхронизация: только изменённое; ставшее невидимым приходит удалённым', async () => {
  const s = await seeded();
  const first = await s.call(s.ann, 'GET', '/api/sync');
  assert.ok(first.body.docs.every(d => d.data !== null), 'в полной загрузке нет чужих адресов');
  const since = first.body.ver;
  const again = await s.call(s.ann, 'GET', '/api/sync', null, { queryStringParameters: { since: String(since) } });
  assert.deepEqual(again.body.docs, []);
  await s.put(s.boss, 'vacancies/v1', { title: 'Логист', manager: 'Петров', status: 'активна' });
  const ch = await s.call(s.ann, 'GET', '/api/sync', null, { queryStringParameters: { since: String(since) } });
  assert.deepEqual(ch.body.docs, [{ path: 'vacancies/v1', data: null }]);
});

test('журнал: кто и что записал', async () => {
  const s = await seeded();
  assert.ok(s.store.audit.some(a => a.who === 'boss@iway.ru' && a.path === 'vacancies/v1' && a.op === 'set'));
});

test('резервная копия по таймеру — в бакет с токеном функции', async () => {
  const s = await seeded();
  const cfg2 = Object.assign({}, cfg, { bucket: 'hr-backups' });
  const h = forTests.makeHandler(s.store, cfg2, fakeYandex(EMAILS));
  const r = await h({ messages: [{ event_metadata: { event_type: 'yandex.cloud.events.serverless.triggers.TimerMessage' } }] }, { token: { access_token: 'iam' } });
  assert.equal(r.statusCode, 200);
  assert.match(fakeYandex.put.url, /^https:\/\/storage\.yandexcloud\.net\/hr-backups\/backups\/\d{4}-\d{2}-\d{2}\.json$/);
  assert.equal(fakeYandex.put.opts.headers['X-YaCloud-SubjectToken'], 'iam');
  assert.equal(Object.keys(JSON.parse(fakeYandex.put.opts.body).docs).length, 6);
});

test('адрес из API Gateway: настоящий путь — в url, в path — шаблон', async () => {
  const s = await seeded();
  const r = await s.h({ httpMethod: 'GET', path: '/{proxy+}', url: '/api/me?x=1', headers: { Cookie: s.ann }, pathParams: { proxy: 'api/me' } });
  assert.equal(r.statusCode, 200); assert.equal(JSON.parse(r.body).pid, 'ann');
  const out = await s.h({ httpMethod: 'POST', path: '/{proxy+}', url: '/api/logout', headers: { 'X-HR': '1' } });
  assert.match(out.multiValueHeaders['Set-Cookie'][0], /^hr_s=; .*Max-Age=0/);
});

test('владелец вакансии — по фамилии, как на странице', () => {
  const people = { a: { name: 'Анна', surname: 'Шулятицкая', order: 1 }, y: { name: 'Юлия', order: 2 } };
  assert.equal(acl.ownerOf('Анна Шулятицкая', people), 'a');
  assert.equal(acl.ownerOf('шулятицкая', people), 'a');
  assert.equal(acl.ownerOf('Юлия', people), 'y');
  assert.equal(acl.ownerOf('Иванов', people), null);
});
