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
  let queue = Promise.resolve();
  return {
    audit,
    async get(path) { const r = rows.get(path); return r && !r.deleted ? JSON.parse(r.data) : null; },
    tx(path, fn, who) {
      const run = queue.then(async () => {
        const r = rows.get(path), prev = r && !r.deleted ? JSON.parse(r.data) : null;
        const next = await fn(prev);
        if (next === undefined) return null;
        const ver = newVer();
        rows.set(path, { data: JSON.stringify(next === null ? {} : next), ver, deleted: next === null });
        audit.push({ ts: ver, who, op: next === null ? 'delete' : 'set', path });
        return ver;
      });
      queue = run.catch(() => {});
      return run;
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

// ---------- SQLite: для своего сервера (Selectel и т. п.), встроена в Node.js 22 ----------
// Один процесс: записи выстраиваются в очередь, так что «прочитать → проверить → записать» не пересекаются.
function sqliteStore(file) {
  const { DatabaseSync } = require('node:sqlite');
  const db = new DatabaseSync(file);
  db.exec(`PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL;
    CREATE TABLE IF NOT EXISTS docs (path TEXT PRIMARY KEY, data TEXT NOT NULL, ver INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS docs_ver ON docs (ver);
    CREATE TABLE IF NOT EXISTS audit (ts INTEGER NOT NULL, who TEXT, op TEXT, path TEXT);`);
  const q = {
    get: db.prepare('SELECT data, deleted FROM docs WHERE path = ?'),
    put: db.prepare('INSERT INTO docs (path, data, ver, deleted) VALUES (?, ?, ?, ?) ON CONFLICT (path) DO UPDATE SET data = excluded.data, ver = excluded.ver, deleted = excluded.deleted'),
    audit: db.prepare('INSERT INTO audit (ts, who, op, path) VALUES (?, ?, ?, ?)'),
    changes: db.prepare('SELECT path, data, ver, deleted FROM docs WHERE ver > ? ORDER BY ver'),
    count: db.prepare('SELECT COUNT(*) AS n FROM docs WHERE deleted = 0'),
  };
  const read = path => { const r = q.get.get(path); return r && !r.deleted ? JSON.parse(r.data) : null; };
  let queue = Promise.resolve();
  return {
    async get(path) { return read(path); },
    tx(path, fn, who) {
      const run = queue.then(async () => {
        const next = await fn(read(path));
        if (next === undefined) return null;
        const ver = newVer();
        db.exec('BEGIN');
        try {
          q.put.run(path, JSON.stringify(next === null ? {} : next), ver, next === null ? 1 : 0);
          q.audit.run(ver, who || '', next === null ? 'delete' : 'set', path);
          db.exec('COMMIT');
        } catch (e) { db.exec('ROLLBACK'); throw e; }
        return ver;
      });
      queue = run.catch(() => {});
      return run;
    },
    async changes(since) { return q.changes.all(since).map(r => ({ path: r.path, ver: r.ver, data: r.deleted ? null : JSON.parse(r.data) })); },
    async count() { return q.count.get().n; },
    close() { db.close(); },
  };
}

// ---------- журнал правок в общей папке: локальная версия (Windows, сетевая папка) ----------
// Базу нельзя открывать с двух ПК по сети, поэтому каждый ПК пишет только свой файл changes-<ПК>.jsonl
// (дописывает строки) и читает файлы других. Строка — правка одного поля: {ts, pc, n, path, at: [ключи], v | del}.
// Значение поля — из правки с наибольшим (ts, pc, n): одинаково на всех ПК, разные поля не мешают друг другу.
function logStore(dir, pc) {
  const fs = require('fs'), pathm = require('path');
  fs.mkdirSync(dir, { recursive: true });
  const mineFile = 'changes-' + pc + '.jsonl';
  const ops = new Map(), docs = new Map(), offsets = {}, rests = {};
  let lastTs = 0, n = 0, polledAt = 0, queue = Promise.resolve();
  const isObj = o => o !== null && typeof o === 'object' && !Array.isArray(o);
  const canon = o => isObj(o) ? '{' + Object.keys(o).sort().map(k => JSON.stringify(k) + ':' + canon(o[k])).join(',') + '}' : Array.isArray(o) ? '[' + o.map(canon).join(',') + ']' : JSON.stringify(o === undefined ? null : o);
  const same = (a, b) => (a === undefined) === (b === undefined) && canon(a) === canon(b);
  const order = (a, b) => a.ts - b.ts || (a.pc < b.pc ? -1 : a.pc > b.pc ? 1 : 0) || a.n - b.n;
  function put(doc, at, v) {
    if (!at.length) return v === undefined ? undefined : JSON.parse(JSON.stringify(v));
    const out = isObj(doc) ? Object.assign({}, doc) : {}, k = at[0], child = put(out[k], at.slice(1), v);
    if (child === undefined) delete out[k]; else out[k] = child;
    return out;
  }
  function diffOps(a, b, at, out) {
    if (same(a, b)) return out;
    if (isObj(a) && isObj(b)) { new Set(Object.keys(a).concat(Object.keys(b))).forEach(k => diffOps(a[k], b[k], at.concat(k), out)); return out; }
    out.push(b === undefined ? { at, del: true } : { at, v: b });
    return out;
  }
  function ingest(o, touched) {
    if (!o || typeof o.path !== 'string' || !Array.isArray(o.at)) return;
    if (!ops.has(o.path)) ops.set(o.path, []);
    ops.get(o.path).push(o); touched.add(o.path);
    if (o.pc === pc) { lastTs = Math.max(lastTs, o.ts); n = Math.max(n, o.n + 1); }
  }
  function rebuild(touched) {
    touched.forEach(p => {
      let doc; ops.get(p).slice().sort(order).forEach(o => { doc = put(doc, o.at, o.del ? undefined : o.v); });
      const cur = docs.get(p);
      if (!cur || !same(cur.data, doc)) docs.set(p, { data: doc, ver: newVer() });
    });
  }
  // дочитать новые строки во всех журналах (свой — только при запуске: свои правки уже в памяти)
  function poll(force) {
    if (!force && Date.now() - polledAt < 1000) return;
    polledAt = Date.now();
    const touched = new Set();
    let files = [];
    try { files = fs.readdirSync(dir).filter(f => /^changes-.+\.jsonl$/.test(f)); } catch (e) { return; }   // папка недоступна — работаем с тем, что в памяти
    for (const f of files) {
      if (f === mineFile && f in offsets) continue;
      try {
        const size = fs.statSync(pathm.join(dir, f)).size, from = offsets[f] || 0;
        if (size <= from) continue;   // shortcut: усечённый или подменённый журнал не перечитывается — журналы только дописываются
        const fd = fs.openSync(pathm.join(dir, f), 'r'), buf = Buffer.alloc(size - from);
        fs.readSync(fd, buf, 0, buf.length, from); fs.closeSync(fd);
        const all = rests[f] ? Buffer.concat([rests[f], buf]) : buf, end = all.lastIndexOf(10) + 1;   // недописанная строка — до следующего раза
        rests[f] = all.subarray(end); offsets[f] = size;
        all.subarray(0, end).toString('utf8').split('\n').forEach(line => { if (line) try { ingest(JSON.parse(line), touched); } catch (e) {} });
      } catch (e) { /* файл занят или исчез — в следующий раз */ }
    }
    if (!(mineFile in offsets)) offsets[mineFile] = 0;
    rebuild(touched);
  }
  poll(true);
  const read = path => { const d = docs.get(path); return d && d.data !== undefined ? JSON.parse(JSON.stringify(d.data)) : null; };
  return {
    async get(path) { poll(); return read(path); },
    tx(path, fn, who) {
      const run = queue.then(async () => {
        poll(true);
        const prev = read(path), next = await fn(read(path));   // fn может поменять документ на месте — сравниваем с отдельной копией
        if (next === undefined) return null;
        const list = diffOps(prev === null ? undefined : prev, next === null ? undefined : next, [], []);
        if (!list.length) return docs.has(path) ? docs.get(path).ver : null;
        const ts = lastTs = Math.max(Date.now(), lastTs + 1), touched = new Set();
        const rows = list.map(o => Object.assign({ ts, pc, n: n++, who: who || '', path }, o));
        fs.appendFileSync(pathm.join(dir, mineFile), rows.map(r => JSON.stringify(r)).join('\n') + '\n');   // ошибка записи — до пользователя: «не сохранилось»
        rows.forEach(r => ingest(r, touched)); rebuild(touched);
        return docs.get(path).ver;
      });
      queue = run.catch(() => {});
      return run;
    },
    async changes(since) {
      poll();
      return [...docs.entries()].filter(([, d]) => d.ver > since).sort((a, b) => a[1].ver - b[1].ver)
        .map(([path, d]) => ({ path, ver: d.ver, data: d.data === undefined ? null : JSON.parse(JSON.stringify(d.data)) }));
    },
    async count() { poll(true); return [...docs.values()].filter(d => d.data !== undefined).length; },   // для «база пустая?» — всегда свежее
  };
}

// Ежедневная копия всей базы в dir/hr-ГГГГ-ММ-ДД.json; старше keepDays дней — удаляются
async function dailyBackup(store, dir, keepDays) {
  const fs = require('fs'), pathm = require('path');
  const day = new Date().toISOString().slice(0, 10), file = pathm.join(dir, 'hr-' + day + '.json');
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  if (!fs.existsSync(file)) {
    const docs = {};
    (await store.changes(0)).forEach(d => { if (d.data !== null) docs[d.path] = d.data; });
    if (!Object.keys(docs).length) return;   // пустую базу не копируем — иначе за этот день копия так и останется пустой
    fs.writeFileSync(file + '.tmp', JSON.stringify({ format: 'hr-metrics', at: new Date().toISOString(), docs }), { mode: 0o600 });
    fs.renameSync(file + '.tmp', file);
    console.log('копия: ' + file + ' (' + Object.keys(docs).length + ' документов)');
  }
  const old = Date.now() - keepDays * 864e5;
  fs.readdirSync(dir).filter(f => /^hr-\d{4}-\d{2}-\d{2}\.json$/.test(f) && Date.parse(f.slice(3, 13)) < old).forEach(f => fs.unlinkSync(pathm.join(dir, f)));
}

module.exports = { memoryStore, ydbStore, sqliteStore, logStore, dailyBackup, newVer };
