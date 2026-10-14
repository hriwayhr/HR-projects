# Локальная версия в браузере: папка данных в «Обменнике», две копии программы («два ПК»).
# Первый запуск — загрузка версии для ПК, вход по паролю, одновременный ввод дня, правки коллеги — сами.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib, subprocess, shutil, os, tempfile, time
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
snap = HERE / '.cache' / 'offline-snap4'; shutil.rmtree(snap, ignore_errors=True)
def put(path, data):
    f = snap / (path + '.json'); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
sha = lambda s, p: hashlib.sha256((s + '::' + p).encode()).hexdigest()
put('config/team', {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'yulia', 'salt': 's1', 'hash': sha('s1', 'p1'), 'admin': True, 'order': 1},
                               'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'anna', 'salt': 's2', 'hash': sha('s2', 'p2'), 'order': 2}}})
put('months/anna_2026-10', {'person': 'anna', 'month': '2026-10', 'days': {'2026-10-01': {'calls': 4}}})
put('vacancies/v1', {'title': 'Логист', 'status': 'активна', 'manager': 'Шулятицкая', 'publishedAt': '2026-09-01'})
offline = HERE / '.cache' / 'HR-метрики-для-импорта.html'
subprocess.run(['python3', str(ROOT / 'tools' / 'build_offline.py'), str(snap), str(offline)], check=True, capture_output=True)

data = tempfile.mkdtemp(prefix='obmennik-')
def start(port, pc):
    p = subprocess.Popen(['node', str(ROOT / 'local' / 'local.js')], env=dict(os.environ, HR_DATA=data, HR_PORT=str(port), COMPUTERNAME=pc, USERNAME='u', NODE_NO_WARNINGS='1'), stdout=subprocess.PIPE, text=True)
    assert 'работают' in p.stdout.readline(); return p
srvA, srvB = start(8821, 'PC1'), start(8822, 'PC2')
errs = []
try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    def page(port):
        ctx = b.new_context(viewport={'width': 1280, 'height': 900})
        ctx.route('http*://**', lambda r: r.continue_() if '127.0.0.1' in r.request.url or 'localhost' in r.request.url else r.abort())
        pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.clock.set_fixed_time('2026-10-07T12:00:00')
        pg.goto('http://localhost:%d/' % port); return pg
    A = page(8821)
    # первый запуск: пусто — загрузить версию для ПК
    A.wait_for_selector('#lImport', state='visible'); assert A.is_hidden('#loginForm')
    A.set_input_files('#lImportFile', str(offline)); A.wait_for_selector('#loginForm', state='visible')
    B = page(8822); B.wait_for_selector('#loginForm', state='visible'); assert B.is_hidden('#lImport')
    def login(pg, l, pw):
        pg.fill('#lLogin', l); pg.fill('#lPass', pw); pg.click('#lSubmit'); pg.wait_for_selector('#tabs button')
    B.fill('#lLogin', 'anna'); B.fill('#lPass', 'нет'); B.click('#lSubmit'); B.wait_for_timeout(700)
    assert 'Неверный логин или пароль' in B.inner_text('#lErr')
    login(A, 'yulia', 'p1'); login(B, 'anna', 'p2')
    assert A.inner_text('#meName') == 'Юлия Немчинова' and B.inner_text('#tab_day') == 'Мой день'
    # одновременно вносят разные дни одного месяца через форму
    def day(pg, d, v):
        pg.click('#tab_entry')
        if pg.is_visible('#fPerson'): pg.select_option('#fPerson', 'anna')
        pg.fill('#fDate', d); pg.dispatch_event('#fDate', 'change'); pg.fill('#m_calls', str(v)); pg.click('#fSave')
    day(A, '2026-10-06', 9); day(B, '2026-10-07', 5)
    time.sleep(4)
    for pg in (A, B):
        pg.click('#tab_entry')
        if pg.is_visible('#fPerson'): pg.select_option('#fPerson', 'anna')
        for d, v in (('2026-10-06', '9'), ('2026-10-07', '5')):
            pg.fill('#fDate', d); pg.dispatch_event('#fDate', 'change'); pg.wait_for_timeout(100)
            assert pg.input_value('#m_calls') == v, (d, pg.input_value('#m_calls'))
    # вакансия, добавленная Анной, сама появляется у Юлии
    B.click('#tab_vac'); B.click('#vAdd'); B.fill('#v_title', 'Диспетчер от Анны'); B.fill('#v_manager', 'Шулятицкая'); B.click('#vSave')
    A.click('#tab_vac'); A.evaluate("setVacStatus([])"); time.sleep(4)
    assert 'Диспетчер от Анны' in A.inner_text('#vTable')
    # в папке данных — журналы двух ПК; пароли и хеши в браузер рекрутера не попадают
    assert sorted(f for f in os.listdir(data) if f.startswith('changes-')) == ['changes-PC1-u.jsonl', 'changes-PC2-u.jsonl']
    assert 'hash' not in B.evaluate("fetch('/api/sync').then(r => r.text())")
    # перезапуск программы у Юлии — данные на месте, вход заново
    srvA.terminate(); srvA.wait(); srvA = start(8821, 'PC1')
    A.goto('http://localhost:8821/'); login(A, 'yulia', 'p1'); A.click('#tab_vac'); A.evaluate("setVacStatus([])"); A.wait_for_timeout(300)
    assert 'Диспетчер от Анны' in A.inner_text('#vTable')
    b.close()
finally:
    srvA.terminate(); srvB.terminate()
print('ОШИБКИ:', errs or 'нет'); assert not errs
