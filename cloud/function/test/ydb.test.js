'use strict';
// То же хранилище на настоящей YDB. Запускается, только если задан YDB_TEST (локальная YDB в Docker):
//   docker run -d -p 2136:2136 -e GRPC_PORT=2136 -e YDB_USE_IN_MEMORY_PDISKS=true ydbplatform/local-ydb
//   YDB_TEST=grpc://localhost:2136/local YDB_ANONYMOUS_CREDENTIALS=1 node --test test/
const test = require('node:test');
const assert = require('node:assert');
const { ydbStore } = require('../store');

test('YDB: запись, чтение, транзакция, изменения страницами, удаление, журнал', { skip: !process.env.YDB_TEST }, async () => {
  const s = ydbStore(process.env.YDB_TEST);
  const base = Date.now() * 1000;
  const tag = 't' + Date.now().toString(36);
  assert.equal(await s.get('vacancies/' + tag), null);
  const v1 = await s.tx('vacancies/' + tag, prev => { assert.equal(prev, null); return { title: 'Логист «1»', n: 1 }; }, 'boss@iway.ru');
  assert.deepEqual(await s.get('vacancies/' + tag), { title: 'Логист «1»', n: 1 });
  assert.equal(await s.tx('vacancies/' + tag, () => undefined, 'x'), null);   // отказ — ничего не пишется
  const v2 = await s.tx('vacancies/' + tag, prev => Object.assign({}, prev, { n: prev.n + 1 }), 'boss@iway.ru');
  assert.ok(v2 > v1);
  // больше одной страницы (500) изменений
  for (let i = 0; i < 520; i += 40) await Promise.all(Array.from({ length: 40 }, (_, j) => s.tx('months/' + tag + '_' + (i + j), () => ({ i: i + j }), 'x')));
  const ch = await s.changes(base);
  assert.ok(ch.filter(c => c.path.startsWith('months/' + tag)).length === 520, 'все 520 через страницы');
  assert.ok(ch.every((c, k) => !k || c.ver >= ch[k - 1].ver));
  await s.tx('vacancies/' + tag, () => null, 'boss@iway.ru');
  assert.equal(await s.get('vacancies/' + tag), null);
  const del = (await s.changes(v2)).find(c => c.path === 'vacancies/' + tag);
  assert.equal(del.data, null);
  assert.ok(await s.count() >= 520);
});
