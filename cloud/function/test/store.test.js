'use strict';
// Одни и те же требования к хранилищам в памяти и SQLite (YDB — в ydb.test.js)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs'); const os = require('os'); const path = require('path');
const { memoryStore, sqliteStore, logStore, dailyBackup } = require('../store');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-'));
for (const [name, make] of [['память', () => memoryStore()], ['SQLite', () => sqliteStore(path.join(tmp, 'a.sqlite'))], ['журнал', () => logStore(path.join(tmp, 'log1'), 'PC1')]]) {
  test('хранилище (' + name + '): транзакции, изменения, удаление, журнал', async () => {
    const s = make();
    assert.equal(await s.get('vacancies/a'), null);
    const v1 = await s.tx('vacancies/a', prev => { assert.equal(prev, null); return { n: 1, t: 'Логист «1»' }; }, 'boss@iway.ru');
    assert.equal(await s.tx('vacancies/a', () => undefined, 'x'), null);
    // параллельные приращения не теряются: каждое видит результат предыдущего
    await Promise.all(Array.from({ length: 20 }, () => s.tx('vacancies/a', p => Object.assign({}, p, { n: p.n + 1 }), 'x')));
    assert.deepEqual(await s.get('vacancies/a'), { n: 21, t: 'Логист «1»' });
    await s.tx('vacancies/b', () => ({ b: 1 }), 'x');
    const ch = await s.changes(v1);
    assert.deepEqual(ch.map(c => c.path), ['vacancies/a', 'vacancies/b']);
    await s.tx('vacancies/a', () => null, 'boss@iway.ru');
    assert.equal(await s.get('vacancies/a'), null);
    assert.equal((await s.changes(0)).find(c => c.path === 'vacancies/a').data, null);
    assert.equal(await s.count(), 1);
  });
}

test('SQLite: данные переживают перезапуск', async () => {
  const f = path.join(tmp, 'b.sqlite');
  const a = sqliteStore(f); await a.tx('config/team', () => ({ people: { y: { name: 'Юлия' } } }), 'x'); a.close();
  const b = sqliteStore(f);
  assert.equal((await b.get('config/team')).people.y.name, 'Юлия');
  b.close();
});

test('журнал: два ПК с одной папкой — правки разных полей сливаются, одно поле — побеждает позднее, у обоих одинаково', async () => {
  const dir = path.join(tmp, 'shared');
  const A = logStore(dir, 'A'), B = logStore(dir, 'B');
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await A.tx('months/anna_2026-10', () => ({ person: 'anna', month: '2026-10', days: { '2026-10-01': { calls: 4 } } }), 'a');
  await sleep(1100);
  // одновременно: оба прочитали один и тот же документ и меняют разные дни
  await Promise.all([
    A.tx('months/anna_2026-10', async p => { await sleep(50); p.days['2026-10-06'] = { calls: 9 }; return p; }, 'a'),
    B.tx('months/anna_2026-10', async p => { await sleep(50); p.days['2026-10-07'] = { calls: 5 }; return p; }, 'b'),
  ]);
  await sleep(1100);
  const want = { '2026-10-01': { calls: 4 }, '2026-10-06': { calls: 9 }, '2026-10-07': { calls: 5 } };
  assert.deepEqual((await A.get('months/anna_2026-10')).days, want);
  assert.deepEqual((await B.get('months/anna_2026-10')).days, want);
  // одно поле: позднее
  await A.tx('vacancies/v1', () => ({ title: 'Логист', comment: 'Юлия' }), 'a');
  await sleep(5);
  await B.tx('vacancies/v1', p => Object.assign({}, p || {}, { comment: 'Анна' }), 'b');
  await sleep(1100);
  assert.equal((await A.get('vacancies/v1')).comment, 'Анна'); assert.equal((await B.get('vacancies/v1')).comment, 'Анна');
  // удаление доходит; новый процесс (перезапуск, третий ПК) собирает то же из журналов
  await B.tx('vacancies/v1', () => null, 'b'); await sleep(1100);
  assert.equal(await A.get('vacancies/v1'), null);
  const C = logStore(dir, 'C');
  assert.deepEqual((await C.get('months/anna_2026-10')).days, want); assert.equal(await C.get('vacancies/v1'), null);
  assert.ok((await A.changes(0)).some(c => c.path === 'vacancies/v1' && c.data === null));
  // в журналах — кто правил; каждый ПК пишет только свой файл
  assert.deepEqual(fs.readdirSync(dir).sort(), ['changes-A.jsonl', 'changes-B.jsonl']);
  assert.ok(fs.readFileSync(path.join(dir, 'changes-B.jsonl'), 'utf8').split('\n').filter(Boolean).every(l => JSON.parse(l).who === 'b'));
});

test('журнал: недописанная строка (запись идёт прямо сейчас) читается, когда допишется', async () => {
  const dir = path.join(tmp, 'partial'); fs.mkdirSync(dir);
  const line = JSON.stringify({ ts: 1, pc: 'X', n: 0, who: 'x', path: 'vacancies/x', at: [], v: { title: 'Привет' } }) + '\n';
  const buf = Buffer.from(line), cut = 20;
  fs.writeFileSync(path.join(dir, 'changes-X.jsonl'), buf.subarray(0, cut));
  const A = logStore(dir, 'A');
  assert.equal(await A.get('vacancies/x'), null);
  fs.appendFileSync(path.join(dir, 'changes-X.jsonl'), buf.subarray(cut));
  await new Promise(r => setTimeout(r, 1100));
  assert.equal((await A.get('vacancies/x')).title, 'Привет');
});

test('ночная копия: раз в день, права 600, пустую базу не копирует, старые удаляет', async () => {
  const dir = path.join(tmp, 'bk'), s = memoryStore();
  await dailyBackup(s, dir, 30); assert.deepEqual(fs.readdirSync(dir), []);
  await s.tx('vacancies/a', () => ({ t: 1 }), 'x');
  fs.writeFileSync(path.join(dir, 'hr-2000-01-01.json'), '{}');
  await dailyBackup(s, dir, 30);
  const files = fs.readdirSync(dir);
  assert.equal(files.length, 1); assert.match(files[0], /^hr-\d{4}-\d{2}-\d{2}\.json$/);
  assert.equal((fs.statSync(path.join(dir, files[0])).mode & 0o777).toString(8), '600');
  assert.deepEqual(Object.keys(JSON.parse(fs.readFileSync(path.join(dir, files[0]))).docs), ['vacancies/a']);
});
