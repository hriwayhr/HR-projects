'use strict';
// HR-метрики, локальная версия для Windows. Программа и данные лежат в сетевой папке (например, «Обменник»),
// а сервер работает на каждом ПК свой и только для этого ПК (127.0.0.1) — в сеть ничего не открывается.
// Данные — журналы правок в папке data рядом с программой: каждый ПК пишет свой, читает чужие (store.js, logStore).
const http = require('http');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const fs = require('fs');
// в архиве код лежит в program/app, в репозитории — в cloud/function, а страница — в src/
const APP = fs.existsSync(path.join(__dirname, 'app')) ? './app' : '../cloud/function';
const { create, config } = require(APP + '/index');
const { logStore, dailyBackup } = require(APP + '/store');

const ROOT = path.join(__dirname, '..');                       // папка «HR-метрики»: program, data, ярлык запуска
const DATA = process.env.HR_DATA || path.join(ROOT, 'data'), PORT = +process.env.HR_PORT || 8790;
const name = (process.env.COMPUTERNAME || os.hostname()) + '-' + (process.env.USERNAME || os.userInfo().username);
const pc = name.replace(/[^A-Za-z0-9_-]/g, c => '~' + c.charCodeAt(0).toString(36));   // имя файла журнала этого ПК
if (!process.env.PAGE_SRC) process.env.PAGE_SRC = APP === './app' ? path.join(__dirname, 'app', 'static', 'page.html') : path.join(__dirname, '..', 'src', 'hr-metrics.html');

const cfg = config({ LOCAL: '1', SESSION_SECRET: crypto.randomBytes(32).toString('hex'), BASE_URL: 'http://localhost:' + PORT });
const store = logStore(DATA, pc);
const handler = create(store, cfg);
const MAX_BODY = 8 * 1024 * 1024;

const server = http.createServer((req, res) => {
  const chunks = []; let size = 0;
  req.on('data', c => { size += c.length; if (size > MAX_BODY) { res.writeHead(413).end(); req.destroy(); } else chunks.push(c); });
  req.on('end', async () => {
    if (res.writableEnded) return;
    const u = new URL(req.url, 'http://local');
    const r = await handler({ httpMethod: req.method, url: req.url, headers: req.headers, queryStringParameters: Object.fromEntries(u.searchParams), body: Buffer.concat(chunks).toString() }, {});
    const h = Object.assign({}, r.headers);
    if (r.multiValueHeaders && r.multiValueHeaders['Set-Cookie']) h['Set-Cookie'] = r.multiValueHeaders['Set-Cookie'];
    res.writeHead(r.statusCode, h); res.end(r.body);
  });
});
server.on('error', e => {
  if (e.code === 'EADDRINUSE') { console.log('HR-метрики уже запущены на этом ПК: http://localhost:' + PORT); process.exit(0); }
  throw e;
});
server.listen(PORT, '127.0.0.1', () => {
  console.log('HR-метрики работают: http://localhost:' + PORT);
  console.log('Данные: ' + DATA);
  console.log('Не закрывайте это окно, пока работаете. Закрыли — запустите «Запустить HR-метрики» снова.');
});

// копия всей базы раз в сутки в data/backups (хранится 60 дней)
const runBackup = () => dailyBackup(store, path.join(DATA, 'backups'), 60).catch(e => console.error('копия не сделана:', e.message));
runBackup(); setInterval(runBackup, 3600e3);
