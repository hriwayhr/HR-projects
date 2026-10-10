'use strict';
// Локальный запуск того же кода, что в облаке: хранилище в памяти, Яндекс ID подставной
// (код подтверждения = почта). Для сквозных тестов страницы: PORT=8787 node test/dev-server.js
const http = require('http');
const { forTests } = require('../index');
const cfg = forTests.config({ BASE_URL: 'http://localhost:' + (process.env.PORT || 8787), OAUTH_CLIENT_ID: 'dev', OAUTH_CLIENT_SECRET: 'dev',
  SESSION_SECRET: 'd'.repeat(40), ALLOWED_DOMAINS: 'iway.ru', ADMIN_EMAILS: 'boss@iway.ru' });
const fakeYandex = async (url, opts) => {
  if (url.startsWith('https://oauth.yandex.ru/token')) return { ok: true, json: async () => ({ access_token: new URLSearchParams(opts.body).get('code') }) };
  if (url.startsWith('https://login.yandex.ru/info')) { const e = opts.headers.Authorization.replace('OAuth ', ''); return { ok: true, json: async () => ({ default_email: e, id: 'yid-' + e }) }; }
  throw new Error('нет сети: ' + url);
};
const store = forTests.memoryStore();
const handler = forTests.makeHandler(store, cfg, fakeYandex);
http.createServer((req, res) => {
  let body = '';
  req.on('data', c => { body += c; });
  req.on('end', async () => {
    const u = new URL(req.url, 'http://x');
    if (u.pathname === '/__store') { res.end(JSON.stringify(Object.fromEntries(await Promise.all((await store.changes(0)).map(async d => [d.path, d.data]))))); return; }
    const r = await handler({ httpMethod: req.method, path: '/{proxy+}', url: req.url, headers: req.headers, queryStringParameters: Object.fromEntries(u.searchParams), body, isBase64Encoded: false }, {});
    const h = Object.assign({}, r.headers);
    if (r.multiValueHeaders && r.multiValueHeaders['Set-Cookie']) h['Set-Cookie'] = r.multiValueHeaders['Set-Cookie'];
    res.writeHead(r.statusCode, h); res.end(r.body);
  });
}).listen(process.env.PORT || 8787, () => console.log('dev-server ready'));
