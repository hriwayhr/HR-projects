'use strict';
// HR-метрики на своём сервере (Selectel и т. п.). Тот же код входа и прав, что в Yandex Cloud (cloud/function),
// база — SQLite в DATA_DIR, каждую ночь — копия всей базы в DATA_DIR/backups (хранится BACKUP_KEEP_DAYS дней).
const http = require('http');
const fs = require('fs');
const path = require('path');
// в Docker код лежит в app/, в репозитории — в cloud/function, а страница — в src/
const APP = fs.existsSync(path.join(__dirname, 'app')) ? './app' : '../cloud/function';
if (APP !== './app' && !process.env.PAGE_SRC) process.env.PAGE_SRC = path.join(__dirname, '..', 'src', 'hr-metrics.html');
const { create, config } = require(APP + '/index');
const { sqliteStore, dailyBackup } = require(APP + '/store');

const DATA = process.env.DATA_DIR || '/data', PORT = +process.env.PORT || 8080, KEEP = +process.env.BACKUP_KEEP_DAYS || 30;
const MAX_BODY = 4 * 1024 * 1024;
const cfg = config();
const missing = ['SESSION_SECRET', 'OAUTH_CLIENT_ID', 'OAUTH_CLIENT_SECRET', 'BASE_URL', 'ALLOWED_DOMAINS', 'ADMIN_EMAILS'].filter(k => !process.env[k]);
if (missing.length || cfg.sessionSecret.length < 32) { console.error('Заполните в .env: ' + (missing.join(', ') || 'SESSION_SECRET (от 32 символов)')); process.exit(1); }

const store = sqliteStore(path.join(DATA, 'hr.sqlite'));
const handler = create(store, cfg);

http.createServer((req, res) => {
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
}).listen(PORT, () => console.log('HR-метрики слушают порт ' + PORT));

// ночная копия: раз в сутки файл hr-ГГГГ-ММ-ДД.json в DATA_DIR/backups, старше KEEP дней — удаляются
const runBackup = () => dailyBackup(store, path.join(DATA, 'backups'), KEEP).catch(e => console.error('копия не сделана:', e.message));
runBackup(); setInterval(runBackup, 3600e3);
