'use strict';
// Локальная версия целиком: две копии программы («два ПК») с одной папкой данных.
// Запуск: node --test local/test.js
const test = require('node:test');
const assert = require('node:assert');
const { spawn } = require('child_process');
const fs = require('fs'); const os = require('os'); const path = require('path'); const crypto = require('crypto');

const sha = (salt, pw) => crypto.createHash('sha256').update(salt + '::' + pw).digest('hex');
function start(data, port, pcName) {
  const p = spawn(process.execPath, [path.join(__dirname, 'local.js')], { env: Object.assign({}, process.env, { HR_DATA: data, HR_PORT: String(port), COMPUTERNAME: pcName, USERNAME: 'u', NODE_NO_WARNINGS: '1' }) });
  return new Promise((ok, no) => { p.stdout.on('data', d => /работают/.test(d) && ok(p)); p.on('exit', c => no(new Error('вышел ' + c))); });
}
function client(port) {
  let cookie = '';
  const call = (method, url, body) => fetch('http://127.0.0.1:' + port + url, { method, headers: Object.assign({ 'X-HR': '1', 'Content-Type': 'application/json' }, cookie ? { Cookie: cookie } : {}), body: body ? JSON.stringify(body) : undefined })
    .then(async r => { const sc = r.headers.get('set-cookie'); if (sc) cookie = sc.split(';')[0]; const t = await r.text(); let j = t; try { j = JSON.parse(t); } catch (e) {} return { status: r.status, body: j }; });
  return { call, docs: async () => { const r = await call('GET', '/api/sync'); const o = {}; r.body.docs.forEach(d => { if (d.data) o[d.path] = d.data; }); return o; } };
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

test('локальная версия: первый запуск, вход по паролю, два ПК в одних данных', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-local-'));
  const A = await start(data, 8811, 'PC-ЮЛИЯ'), B = await start(data, 8812, 'PC-ANNA');
  try {
    const a = client(8811), b = client(8812);
    // страница — в локальном режиме; без данных — просьба загрузить
    const page = await a.call('GET', '/');
    assert.match(page.body, /window\.HR_LOCAL = true/);
    const me = await a.call('GET', '/api/me');
    assert.equal(me.status, 401); assert.equal(me.body.empty, true);
    // первичная загрузка: без администратора с паролем — нельзя; потом — второй раз нельзя
    assert.equal((await a.call('POST', '/api/import-initial', { docs: { 'config/team': { people: { x: { name: 'X' } } } } })).status, 400);
    const docs = {
      'config/team': { people: { yulia: { name: 'Юлия', surname: 'Немчинова', login: 'yulia', salt: 's1', hash: sha('s1', 'p1'), admin: true, order: 1 },
                                 anna: { name: 'Анна', surname: 'Шулятицкая', login: 'anna', salt: 's2', hash: sha('s2', 'p2'), order: 2 } } },
      'months/anna_2026-10': { person: 'anna', month: '2026-10', days: { '2026-10-01': { calls: 4 } } },
      'vacancies/v1': { title: 'Логист', manager: 'Шулятицкая', status: 'активна' },
      'vacancies/v2': { title: 'Диспетчер', manager: 'Немчинова', status: 'активна' },
    };
    assert.equal((await a.call('POST', '/api/import-initial', { docs })).status, 200);
    assert.equal((await b.call('POST', '/api/import-initial', { docs })).status, 403);
    // вход: неверный пароль, верный; рекрутер не видит хешей и чужого
    assert.equal((await a.call('POST', '/api/plogin', { login: 'yulia', password: 'x' })).status, 401);
    assert.equal((await a.call('POST', '/api/plogin', { login: 'Yulia', password: 'p1' })).status, 200);
    assert.equal((await b.call('POST', '/api/plogin', { login: 'anna', password: 'p2' })).status, 200);
    assert.equal((await a.call('GET', '/api/me')).body.admin, true);
    const bd = await b.docs();
    assert.deepEqual(Object.keys(bd).sort(), ['config/team', 'months/anna_2026-10', 'vacancies/v1']);
    assert.ok(!JSON.stringify(bd['config/team']).includes('hash') && !JSON.stringify(bd['config/team']).includes('login'));
    // одновременно: администратор и рекрутер правят один месяц — разные дни; оба видят оба
    await Promise.all([
      a.call('POST', '/api/doc', { path: 'months/anna_2026-10', op: 'set', base: docs['months/anna_2026-10'], data: { person: 'anna', month: '2026-10', days: { '2026-10-01': { calls: 4 }, '2026-10-06': { calls: 9 } } } }),
      b.call('POST', '/api/doc', { path: 'months/anna_2026-10', op: 'set', base: docs['months/anna_2026-10'], data: { person: 'anna', month: '2026-10', days: { '2026-10-01': { calls: 4 }, '2026-10-07': { calls: 5 } } } }),
    ]);
    await sleep(1200);
    const want = { '2026-10-01': { calls: 4 }, '2026-10-06': { calls: 9 }, '2026-10-07': { calls: 5 } };
    assert.deepEqual((await a.docs())['months/anna_2026-10'].days, want);
    assert.deepEqual((await b.docs())['months/anna_2026-10'].days, want);
    // права действуют: рекрутер не пишет чужое
    assert.equal((await b.call('POST', '/api/doc', { path: 'vacancies/v2', op: 'set', data: { title: 'x', manager: 'Шулятицкая' } })).status, 403);
    // в папке — по журналу на ПК и ночная копия
    const files = fs.readdirSync(data).sort();
    assert.ok(files.includes('backups') && files.filter(f => f.startsWith('changes-')).length === 2, files.join());
  } finally { A.kill(); B.kill(); }
  // перезапуск: данные на месте; вторая копия на том же порту не мешает
  const A2 = await start(data, 8811, 'PC-ЮЛИЯ');
  try {
    const a = client(8811);
    assert.equal((await a.call('GET', '/api/me')).body.empty, false);
    await a.call('POST', '/api/plogin', { login: 'yulia', password: 'p1' });
    assert.equal(Object.keys((await a.docs())['months/anna_2026-10'].days).length, 3);
    const dup = spawn(process.execPath, [path.join(__dirname, 'local.js')], { env: Object.assign({}, process.env, { HR_DATA: data, HR_PORT: '8811', NODE_NO_WARNINGS: '1' }) });
    assert.equal(await new Promise(ok => dup.on('exit', ok)), 0);
  } finally { A2.kill(); }
});
