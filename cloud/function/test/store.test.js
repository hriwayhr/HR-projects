'use strict';
// Одни и те же требования к хранилищам в памяти и SQLite (YDB — в ydb.test.js)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs'); const os = require('os'); const path = require('path');
const { memoryStore, sqliteStore } = require('../store');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-'));
for (const [name, make] of [['память', () => memoryStore()], ['SQLite', () => sqliteStore(path.join(tmp, 'a.sqlite'))]]) {
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
