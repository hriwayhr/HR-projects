# Код на почту в портале на сервере: первый вход с нового устройства, знакомое устройство, «Забыли пароль?».
# Почта — поддельный SMTP-сервер с TLS (как smtp.yandex.ru:465), письма складываются в список.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib, subprocess, os, tempfile, ssl, socket, threading, base64, re, email
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sha = lambda s, p: hashlib.sha256((s + '::' + p).encode()).hexdigest()
tmp = pathlib.Path(tempfile.mkdtemp(prefix='hr-2fa-'))
subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost',
                '-keyout', str(tmp / 'k.pem'), '-out', str(tmp / 'c.pem')], check=True, capture_output=True)
mails = []
def smtp_server():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(tmp / 'c.pem', tmp / 'k.pem')
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(('127.0.0.1', 0)); srv.listen()
    def serve():
        while True:
            c, _ = srv.accept()
            try:
                s = ctx.wrap_socket(c, server_side=True); f = s.makefile('rb'); s.sendall(b'220 fake\r\n')
                while True:
                    line = f.readline().decode().strip()
                    if line.startswith('EHLO'): s.sendall(b'250-fake\r\n250 AUTH PLAIN\r\n')
                    elif line.startswith('AUTH'): s.sendall(b'235 ok\r\n' if base64.b64decode(line[11:]) == b'\0noreply@iway.ru\0app-pass' else b'535 bad\r\n')
                    elif line == 'DATA':
                        s.sendall(b'354 go\r\n'); data = b''
                        while not data.endswith(b'\r\n.\r\n'): data += f.readline()
                        mails.append(email.message_from_bytes(data[:-5])); s.sendall(b'250 queued\r\n')
                    elif line == 'QUIT': s.sendall(b'221 bye\r\n'); break
                    else: s.sendall(b'250 ok\r\n')
                s.close()
            except Exception as e: print('smtp', e)
    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1]
smtp_port = smtp_server()
def last_code():
    m = mails[-1]; return re.search(r': (\d{6})', m.get_payload(decode=True).decode()).group(1), m['To']

seed = {'data': {'config/team': {'people': {
  'yulia': {'name': 'Юлия', 'login': 'ny@iway.ru', 'salt': 's1', 'hash': sha('s1', 'Y-1'), 'admin': True, 'order': 1},
  'anna': {'name': 'Анна', 'login': 'anna', 'email': 'shua@iway.ru', 'salt': 's2', 'hash': sha('s2', 'A-2'), 'recruiter': True, 'order': 2}}}}}
data = tempfile.mkdtemp(prefix='hr-portal2-')
(pathlib.Path(data) / 'import.html').write_text('<script>\n  var SEED = ' + json.dumps(seed, ensure_ascii=False) + ';\n  var TEMPLATE = "";</script>', encoding='utf-8')
PORT = 8835; BASE = 'http://localhost:%d' % PORT
env = dict(os.environ, DATA_DIR=data, PORT=str(PORT), AUTH='password', SESSION_SECRET='s' * 48, NODE_NO_WARNINGS='1',
           SMTP_HOST='localhost', SMTP_PORT=str(smtp_port), SMTP_USER='noreply@iway.ru', SMTP_PASS='app-pass',
           NODE_TLS_REJECT_UNAUTHORIZED='0')   # только в тесте: у поддельной почты самоподписанный сертификат
srv = subprocess.Popen(['node', str(ROOT / 'server' / 'server.js')], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
while 'слушают' not in srv.stdout.readline(): pass
errs = []
try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    def fresh():
        ctx = b.new_context(viewport={'width': 1280, 'height': 900}); pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); return ctx, pg
    def password(pg, l, pw):
        pg.goto(BASE + '/'); pg.wait_for_selector('#viewGate:not([hidden])')
        pg.fill('#gateLogin', l); pg.fill('#gatePass', pw); pg.click('#gateForm button')

    # новое устройство: после пароля — код на рабочую почту
    ctx, pg = fresh()
    password(pg, 'anna', 'A-2')
    pg.wait_for_selector('#codeForm:not([hidden])')
    assert 's•••@iway.ru' in pg.inner_text('#codeLead'), pg.inner_text('#codeLead')
    code, to = last_code(); assert to == 'shua@iway.ru'
    pg.screenshot(path=str(HERE / '.cache' / 'portal-code.png'))
    pg.fill('#codeInput', '000000' if code != '000000' else '111111'); pg.click('#codeForm button[type=submit]')
    pg.wait_for_selector('#gateErr:not([hidden])'); assert 'Неверный код' in pg.inner_text('#gateErr')
    pg.fill('#codeInput', code); pg.click('#codeForm button[type=submit]')
    pg.wait_for_selector('#viewHome:not([hidden])')
    # выход и снова вход на том же устройстве — хватает пароля
    pg.goto(BASE + '/#exit'); pg.wait_for_selector('#viewGate:not([hidden])')
    n = len(mails); password(pg, 'anna', 'A-2'); pg.wait_for_selector('#viewHome:not([hidden])'); assert len(mails) == n
    ctx.close()

    # «Забыли пароль?» на другом устройстве: код, новый пароль — и сразу внутри
    ctx, pg = fresh()
    pg.goto(BASE + '/'); pg.wait_for_selector('#viewGate:not([hidden])')
    pg.click('#resetOpen'); pg.fill('#resetLogin', 'ny@iway.ru'); pg.click('#resetBtn')
    pg.wait_for_selector('#resetStep2:not([hidden])')
    code, to = last_code(); assert to == 'ny@iway.ru'
    pg.fill('#resetCode', code); pg.fill('#resetPass', 'Новый-пароль-9'); pg.fill('#resetPass2', 'другой'); pg.click('#resetBtn')
    pg.wait_for_selector('#gateErr:not([hidden])'); assert 'не совпадают' in pg.inner_text('#gateErr')
    pg.fill('#resetPass2', 'Новый-пароль-9'); pg.click('#resetBtn')
    pg.wait_for_selector('#viewHome:not([hidden])'); assert 'администратор' in pg.inner_text('#homeWho')
    pg.goto(BASE + '/#exit'); pg.wait_for_selector('#viewGate:not([hidden])')
    n = len(mails); password(pg, 'ny@iway.ru', 'Новый-пароль-9'); pg.wait_for_selector('#viewHome:not([hidden])'); assert len(mails) == n
    ctx.close()
    # старый пароль больше не подходит
    ctx, pg = fresh(); password(pg, 'ny@iway.ru', 'Y-1')
    pg.wait_for_selector('#gateErr:not([hidden])'); assert 'Неверный' in pg.inner_text('#gateErr')
    b.close()
finally:
  srv.kill()
assert not errs, errs
print('flow35 ok')
