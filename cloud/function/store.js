'use strict';
// Хранилище документов: путь → JSON. Удаление — пометка deleted, чтобы открытые страницы узнали о нём.
// ver — момент записи в микросекундах; страница забирает только изменённое после своей последней ver.
//
// Интерфейс: get(path) · tx(path, fn(prev) → next | null | undefined) · changes(since) · count() · all()
// tx выполняет fn над текущей версией и записывает результат в одной транзакции (undefined — ничего не писать).

// строго возрастает в пределах экземпляра; между экземплярами страница перезапрашивает последние секунды
let lastVer = 0;
function newVer() { lastVer = Math.max(lastVer + 1, Date.now() * 1000); return lastVer; }

// ---------- в памяти: для тестов и локального запуска ----------
function memoryStore() {
  const rows = new Map(), audit = [];
  return {
    audit,
    async get(path) { const r = rows.get(path); return r && !r.deleted ? JSON.parse(r.data) : null; },
    async tx(path, fn, who) {
      const r = rows.get(path), prev = r && !r.deleted ? JSON.parse(r.data) : null;
      const next = await fn(prev);
      if (next === undefined) return null;
      const ver = newVer();
      rows.set(path, { data: JSON.stringify(next === null ? {} : next), ver, deleted: next === null });
      audit.push({ ts: ver, who, op: next === null ? 'delete' : 'set', path });
      return ver;
    },
    async changes(since) {
      return [...rows.entries()].filter(([, r]) => r.ver > since).sort((a, b) => a[1].ver - b[1].ver)
        .map(([path, r]) => ({ path, ver: r.ver, data: r.deleted ? null : JSON.parse(r.data) }));
    },
    async count() { return [...rows.values()].filter(r => !r.deleted).length; },
  };
}

// ---------- YDB ----------
const PAGE = 500;   // в ответе YDB не больше 1000 строк — читаем страницами

function ydbStore(connectionString) {
  const { Driver, getCredentialsFromEnv, TypedValues, TypedData, TableDescription, TableIndex, Column, Types } = require('ydb-sdk');
  const opt = t => Types.optional(t);
  // таблицы: docs (документы, индекс по ver — для «что изменилось») и audit (кто что менял)
  const TABLES = {
    docs: new TableDescription().withColumns(new Column('path', opt(Types.UTF8)), new Column('data', opt(Types.JSON)), new Column('ver', opt(Types.UINT64)), new Column('deleted', opt(Types.BOOL)))
      .withPrimaryKey('path').withIndex(new TableIndex('idx_ver').withIndexColumns('ver').withGlobalAsync(false)),
    audit: new TableDescription().withColumns(new Column('ts', opt(Types.UINT64)), new Column('who', opt(Types.UTF8)), new Column('op', opt(Types.UTF8)), new Column('path', opt(Types.UTF8)))
      .withPrimaryKeys('ts', 'path'),
  };
  let ready = null;
  function driver() {
    if (!ready) ready = (async () => {
      const d = new Driver({ connectionString, authService: getCredentialsFromEnv() });
      if (!await d.ready(10000)) { ready = null; throw new Error('YDB недоступна'); }
      await d.tableClient.withSessionRetry(async s => {
        for (const name of Object.keys(TABLES)) await s.describeTable(name).catch(() => s.createTable(name, TABLES[name]));
      });
      return d;
    })();
    return ready;
  }
  const num = v => Number(String(v));
  const rowsOf = res => res.resultSets.length ? TypedData.createNativeObjects(res.resultSets[0]) : [];
  async function run(fn) { const d = await driver(); return d.tableClient.withSessionRetry(fn); }

  return {
    async get(path) {
      return run(async s => {
        const res = await s.executeQuery('DECLARE $path AS Utf8; SELECT data, deleted FROM docs WHERE path = $path;', { $path: TypedValues.utf8(path) });
        const r = rowsOf(res)[0];
        return r && !r.deleted ? JSON.parse(r.data) : null;
      });
    },
    async tx(path, fn, who) {
      return run(async s => {
        const t = await s.beginTransaction({ serializableReadWrite: {} });
        try {
          const res = await s.executeQuery('DECLARE $path AS Utf8; SELECT data, deleted FROM docs WHERE path = $path;', { $path: TypedValues.utf8(path) }, { txId: t.id });
          const r = rowsOf(res)[0], prev = r && !r.deleted ? JSON.parse(r.data) : null;
          const next = await fn(prev);
          if (next === undefined) { await s.rollbackTransaction({ txId: t.id }); return null; }
          const ver = newVer();
          await s.executeQuery(`
            DECLARE $path AS Utf8; DECLARE $data AS Json; DECLARE $ver AS Uint64; DECLARE $del AS Bool; DECLARE $who AS Utf8; DECLARE $op AS Utf8;
            UPSERT INTO docs (path, data, ver, deleted) VALUES ($path, $data, $ver, $del);
            UPSERT INTO audit (ts, who, op, path) VALUES ($ver, $who, $op, $path);`, {
            $path: TypedValues.utf8(path), $data: TypedValues.json(JSON.stringify(next === null ? {} : next)), $ver: TypedValues.uint64(ver),
            $del: TypedValues.bool(next === null), $who: TypedValues.utf8(who || ''), $op: TypedValues.utf8(next === null ? 'delete' : 'set')
          }, { txId: t.id });
          await s.commitTransaction({ txId: t.id });
          return ver;
        } catch (e) {
          await s.rollbackTransaction({ txId: t.id }).catch(() => {});
          throw e;
        }
      });
    },
    async changes(since) {
      const out = [];
      for (;;) {
        const page = await run(async s => rowsOf(await s.executeQuery(
          `DECLARE $since AS Uint64; SELECT path, data, ver, deleted FROM docs VIEW idx_ver WHERE ver > $since ORDER BY ver LIMIT ${PAGE};`,
          { $since: TypedValues.uint64(since) })));
        page.forEach(r => out.push({ path: r.path, ver: num(r.ver), data: r.deleted ? null : JSON.parse(r.data) }));
        if (page.length < PAGE) return out;
        since = num(page[page.length - 1].ver);
      }
    },
    async count() {
      return run(async s => num(rowsOf(await s.executeQuery('SELECT COUNT(*) AS n FROM docs WHERE deleted = false;'))[0].n));
    },
  };
}

module.exports = { memoryStore, ydbStore, newVer };
