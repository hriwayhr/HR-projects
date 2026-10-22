# Портал на сервере (как iteamboard.ru): один вход на всех, роли администратор / HR-менеджер / сотрудник.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib, subprocess, os, tempfile
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sha = lambda s, p: hashlib.sha256((s + '::' + p).encode()).hexdigest()
seed = {'data': {
  'config/team': {'people': {
    'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'yulia', 'salt': 's1', 'hash': sha('s1', 'Y-1'), 'admin': True, 'order': 1},
    'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'anna', 'email': 'anna@iway.ru', 'salt': 's2', 'hash': sha('s2', 'A-2'), 'recruiter': True, 'order': 2}}},
  'months/anna_2026-10': {'person': 'anna', 'month': '2026-10', 'days': {}},
  'config/departments': {'list': [{'name': 'Логистика', 'head': 'Иван Петров', 'senior': 'Мария', 'chat': '@log'}]},
  'employees/IW-AAAA': {'code': 'IW-AAAA', 'login': 'n.novaya', 'email': 'n.novaya@iway.ru', 'firstName': 'Ника', 'lastName': 'Новая', 'gender': 'f',
                        'dept': 'Логистика', 'startDate': '2026-11-02', 'salt': 's3', 'hash': sha('s3', 'N-3'), 'sentAt': '2026-10-20T10:00:00Z'},
}}
data = tempfile.mkdtemp(prefix='hr-portal-')
(pathlib.Path(data) / 'import.html').write_text('<script>\n  var SEED = ' + json.dumps(seed, ensure_ascii=False) + ';\n  var TEMPLATE = "";</script>', encoding='utf-8')
PORT = 8834; BASE = 'http://localhost:%d' % PORT
srv = subprocess.Popen(['node', str(ROOT / 'server' / 'server.js')], env=dict(os.environ, DATA_DIR=data, PORT=str(PORT), AUTH='password', SESSION_SECRET='s' * 48, NODE_NO_WARNINGS='1'), stdout=subprocess.PIPE, text=True)
while 'слушают' not in srv.stdout.readline(): pass
errs, csp = [], []
try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    def fresh():
        ctx = b.new_context(viewport={'width': 1280, 'height': 900})
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.on('console', lambda m: csp.append(m.text) if 'Content Security Policy' in m.text or 'Refused' in m.text else None)
        return pg
    def login(pg, l, pw, url=BASE + '/'):
        pg.goto(url); pg.fill('#gateLogin', l); pg.fill('#gatePass', pw); pg.click('#gateForm button')
        pg.wait_for_load_state('networkidle')

    # сотрудник — по ссылке из письма (#code=…): своя страница, в метрики не пускает
    pg = fresh()
    pg.goto(BASE + '/#code=IW-AAAA')
    assert pg.input_value('#gateLogin') == 'IW-AAAA'
    pg.fill('#gatePass', 'плохой'); pg.click('#gateForm button')
    pg.wait_for_selector('#gateErr:not([hidden])'); assert 'Неверный' in pg.inner_text('#gateErr')
    pg.fill('#gateLogin', 'IW-AAAA'); pg.fill('#gatePass', 'N-3'); pg.click('#gateForm button')
    pg.wait_for_selector('#viewEmployee:not([hidden])')
    assert pg.is_hidden('#viewHome') and pg.is_hidden('#viewAdmin')
    pg.screenshot(path=str(HERE / '.cache' / 'portal-employee.png'))
    pg.goto(BASE + '/metrics'); pg.wait_for_load_state('networkidle')
    assert pg.url == BASE + '/', pg.url
    pg.wait_for_selector('#viewEmployee:not([hidden])')
    pg.goto(BASE + '/#exit'); pg.wait_for_selector('#viewGate:not([hidden])')
    pg.reload(); pg.wait_for_selector('#viewGate:not([hidden])')      # выход — на сервере, не только в окне

    # HR-менеджер — по почте: разделы, панель пребординга без «Администраторов», метрики в той же вкладке
    pg = fresh()
    login(pg, 'anna@iway.ru', 'A-2')
    pg.wait_for_selector('#viewHome:not([hidden])')
    assert 'HR-менеджер' in pg.inner_text('#homeWho'), pg.inner_text('#homeWho')
    assert pg.locator('#homeGrid .hub-card').count() == 2
    pg.click('[data-section="pre"]'); pg.wait_for_selector('#viewAdmin:not([hidden])')
    assert pg.is_hidden('#tabAdmins') and pg.locator('#preImport').count() == 0
    pg.click('#tabPeople'); pg.get_by_text('Новая Ника').first.wait_for()
    pg.screenshot(path=str(HERE / '.cache' / 'portal-hr.png'))
    # HR выдаёт доступ новичку — он входит выданным паролем
    pg.click('#tabNew')
    pg.fill('#fLast', 'Петрова'); pg.fill('#fFirst', 'Ольга'); pg.fill('#fPersonal', 'olga@ex.com')
    pg.select_option('#fDept', 'Логистика'); pg.fill('#fDate', '2026-11-09')
    pg.click('#newForm button[type=submit]'); pg.wait_for_selector('#issuedCode:has-text("IW-")')
    code, pw = [x.strip() for x in pg.inner_text('#issuedCode').split('·')]
    pg2 = fresh(); login(pg2, code, pw); pg2.wait_for_selector('#viewEmployee:not([hidden])')
    assert 'Ольга' in pg2.inner_text('#viewEmployee')
    pg.goto(BASE + '/'); pg.wait_for_selector('#viewHome:not([hidden])')
    pg.click('[data-section="metrics"]'); pg.wait_for_url(BASE + '/metrics')
    pg.wait_for_selector('#toPortal:not([hidden])')
    pg.wait_for_selector('#me:not([hidden])')
    assert 'Анна' in pg.inner_text('#meName')

    # администратор: роль в шапке, перенос пребординга
    pg = fresh()
    login(pg, 'yulia', 'Y-1')
    pg.wait_for_selector('#viewHome:not([hidden])')
    assert 'администратор' in pg.inner_text('#homeWho')
    pg.click('[data-section="pre"]'); pg.wait_for_selector('#preImport')
    f = pathlib.Path(data) / 'pre.json'; f.write_text(json.dumps({'docs': {'employees/IW-BBBB': {'code': 'IW-BBBB', 'firstName': 'Борис', 'lastName': 'Перенесённый'}}}, ensure_ascii=False))
    pg.set_input_files('#preImportFile', str(f))
    pg.wait_for_selector('#dlg[open]'); assert 'Загружено документов: 1' in pg.inner_text('#dlg')
    pg.click('#dlgOk'); pg.wait_for_selector('#viewAdmin:not([hidden])'); pg.click('#tabPeople'); pg.get_by_text('Перенесённый Борис').first.wait_for()
    b.close()
finally:
  srv.kill()
assert not errs, errs
assert not csp, csp
print('flow34 ok')
