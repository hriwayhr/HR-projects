'use strict';
// Вход через Яндекс ID (OAuth 2.0, код подтверждения) и сессия в подписанной cookie.
const crypto = require('crypto');

const SESSION_HOURS = 8;
const COOKIE = 'hr_s', STATE_COOKIE = 'hr_st';

function b64u(buf) { return Buffer.from(buf).toString('base64url'); }
function hmac(secret, s) { return crypto.createHmac('sha256', secret).update(s).digest('base64url'); }

function sign(secret, payload) {
  const body = b64u(JSON.stringify(payload));
  return body + '.' + hmac(secret, body);
}
function verify(secret, token, now = Date.now()) {
  if (typeof token !== 'string' || token.length > 2000) return null;
  const [body, mac] = token.split('.');
  if (!body || !mac) return null;
  const want = Buffer.from(hmac(secret, body)), got = Buffer.from(mac);
  if (want.length !== got.length || !crypto.timingSafeEqual(want, got)) return null;
  try {
    const p = JSON.parse(Buffer.from(body, 'base64url').toString());
    return p && typeof p.e === 'string' && p.x > now ? p : null;
  } catch (e) { return null; }
}

function cookies(headers) {
  const out = {}, raw = headerOf(headers, 'cookie') || '';
  raw.split(';').forEach(c => { const i = c.indexOf('='); if (i > 0) out[c.slice(0, i).trim()] = decodeURIComponent(c.slice(i + 1).trim()); });
  return out;
}
function headerOf(headers, name) {
  const k = Object.keys(headers || {}).find(h => h.toLowerCase() === name);
  return k ? headers[k] : undefined;
}
function setCookie(name, value, maxAge) {
  return name + '=' + encodeURIComponent(value) + '; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=' + maxAge;
}

function sessionCookie(secret, email) {
  return setCookie(COOKIE, sign(secret, { e: email, x: Date.now() + SESSION_HOURS * 3600e3 }), SESSION_HOURS * 3600);
}
function sessionEmail(secret, headers) {
  const p = verify(secret, cookies(headers)[COOKIE]);
  return p ? p.e : null;
}

// Шаг 1: на страницу входа Яндекса; state — защита от подмены ответа (сверяется с cookie)
function loginRedirect(cfg) {
  const state = b64u(crypto.randomBytes(18));
  const url = 'https://oauth.yandex.ru/authorize?' + new URLSearchParams({
    response_type: 'code', client_id: cfg.clientId, redirect_uri: cfg.baseUrl + '/api/callback', state, force_confirm: 'no'
  });
  return { statusCode: 302, headers: { Location: url, 'Cache-Control': 'no-store' }, multiValueHeaders: { 'Set-Cookie': [setCookie(STATE_COOKIE, state, 600)] }, body: '' };
}

// Шаг 2: код → токен → почта. Токен Яндекса не храним: он нужен только чтобы узнать, кто вошёл.
async function exchange(cfg, query, headers, fetchFn = fetch) {
  const st = cookies(headers)[STATE_COOKIE];
  if (!query.code || !query.state || !st || query.state !== st) throw new Error('state');
  const tok = await fetchFn('https://oauth.yandex.ru/token', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'authorization_code', code: query.code, client_id: cfg.clientId, client_secret: cfg.clientSecret }).toString()
  });
  if (!tok.ok) throw new Error('token ' + tok.status);
  const { access_token } = await tok.json();
  const info = await fetchFn('https://login.yandex.ru/info?format=json', { headers: { Authorization: 'OAuth ' + access_token } });
  if (!info.ok) throw new Error('info ' + info.status);
  const u = await info.json();
  return { email: String(u.default_email || '').toLowerCase(), yid: String(u.id || '') };
}

module.exports = { sign, verify, cookies, headerOf, setCookie, sessionCookie, sessionEmail, loginRedirect, exchange, COOKIE, STATE_COOKIE, SESSION_HOURS };
