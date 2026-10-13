'use strict';
// Сервер целиком: запуск, страница с CSP, отказ без входа, ночная копия. Запуск: node --test server/test.js
const test = require('node:test');
const assert = require('node:assert');
const { spawn } = require('child_process');
const fs = require('fs'); const os = require('os'); const path = require('path');

test('сервер: страница, защита, вход через Яндекс', async () => {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'hr-srv-'));
  const env = Object.assign({}, process.env, { DATA_DIR: data, PORT: '8799', BASE_URL: 'https://hr.example.ru', ALLOWED_DOMAINS: 'example.ru',
    ADMIN_EMAILS: 'boss@example.ru', OAUTH_CLIENT_ID: 'id', OAUTH_CLIENT_SECRET: 'sec', SESSION_SECRET: 's'.repeat(48), NODE_NO_WARNINGS: '1' });
  const p = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env });
  try {
    await new Promise((ok, no) => { p.stdout.on('data', d => /слушают/.test(d) && ok()); p.on('exit', c => no(new Error('вышел ' + c))); });
    const base = 'http://localhost:8799';
    const page = await fetch(base + '/');
    assert.equal(page.status, 200);
    assert.match(page.headers.get('content-security-policy'), /script-src 'nonce-/);
    assert.match(await page.text(), /window\.HR_CLOUD = true[\s\S]*HR-метрики/);
    assert.equal((await fetch(base + '/api/me')).status, 401);
    assert.equal((await fetch(base + '/api/sync', { headers: { Cookie: 'hr_s=forged.sig' } })).status, 401);
    const login = await fetch(base + '/api/login', { redirect: 'manual' });
    assert.match(login.headers.get('location'), /^https:\/\/oauth\.yandex\.ru\/authorize\?.*redirect_uri=https%3A%2F%2Fhr\.example\.ru%2Fapi%2Fcallback/);
    assert.equal((await fetch(base + '/api/doc', { method: 'POST', body: 'x'.repeat(5 * 1024 * 1024) }).catch(() => ({ status: 413 }))).status, 413);
    assert.deepEqual(fs.readdirSync(path.join(data, 'backups')), []);   // пустую базу не копируем
  } finally { p.kill(); }
  // без настроек сервер не стартует
  const bad = spawn(process.execPath, [path.join(__dirname, 'server.js')], { env: Object.assign({}, process.env, { DATA_DIR: data, SESSION_SECRET: '' }) });
  const code = await new Promise(ok => bad.on('exit', ok));
  assert.equal(code, 1);
});
