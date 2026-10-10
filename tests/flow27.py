# Облачная версия целиком: страница из cloud/build.py + сервер (тот же код функции, хранилище в памяти).
# Вход через Яндекс ID подменён: «страница Яндекса» сразу возвращает код = почта.
from playwright.sync_api import sync_playwright
import pathlib, json, subprocess, os, time, urllib.request, urllib.parse
HERE = pathlib.Path(__file__).resolve().parent
CLOUD = HERE.parent / 'cloud'
subprocess.run(['python3', str(CLOUD / 'build.py')], check=True, capture_output=True)
PORT = 8787; BASE = 'http://localhost:%d' % PORT
srv = subprocess.Popen(['node', 'test/dev-server.js'], cwd=CLOUD / 'function', env=dict(os.environ, PORT=str(PORT)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
assert 'ready' in srv.stdout.readline()
def store(): return json.loads(urllib.request.urlopen(BASE + '/__store').read())

backup = {'format': 'hr-metrics', 'at': '2026-10-10T10:00:00Z', 'docs': {
  'config/team': {'people': {
    'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'salt': 's', 'hash': 'h', 'admin': True, 'order': 1},
    'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'salt': 's', 'hash': 'h', 'order': 2},
    'test': {'name': 'Тест', 'login': 'test', 'hash': 'h', 'admin': True, 'recruiter': False, 'order': 3}}},
  'months/yulia_2026-10': {'person': 'yulia', 'month': '2026-10', 'days': {'2026-10-01': {'int_planned': 4, 'int_done': 3}}},
  'months/anna_2026-10': {'person': 'anna', 'month': '2026-10', 'days': {'2026-10-01': {'int_planned': 2, 'int_done': 1}}},
  'vacancies/a': {'title': 'Логист', 'status': 'активна', 'manager': 'Немчинова', 'publishedAt': '2026-09-01'},
  'vacancies/b': {'title': 'Диспетчер', 'status': 'активна', 'manager': 'Шулятицкая', 'publishedAt': '2026-09-01'},
}}
bfile = HERE / '.cache'; bfile.mkdir(exist_ok=True); bfile = bfile / 'backup.json'; bfile.write_text(json.dumps(backup, ensure_ascii=False), encoding='utf-8')

errs, csp = [], []
try:
  with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = b.new_context(viewport={'width': 1280, 'height': 1000}, accept_downloads=True)
    who = {'email': None}
    def yandex(route):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(route.request.url).query)
        assert q['redirect_uri'] == [BASE + '/api/callback'] and q['response_type'] == ['code']
        route.fulfill(status=302, headers={'Location': BASE + '/api/callback?' + urllib.parse.urlencode({'code': who['email'], 'state': q['state'][0]})})
    ctx.route('https://oauth.yandex.ru/**', yandex)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: csp.append(m.text) if 'Content Security Policy' in m.text or 'Refused' in m.text else None)
    pg.clock.set_fixed_time('2026-10-07T12:00:00')
    def login(email):
        who['email'] = email
        pg.goto(BASE + '/'); pg.wait_for_selector('#yaBtn', state='visible')
        pg.click('#yaBtn')
        pg.wait_for_url(BASE + '/**'); pg.wait_for_selector('#tabs button, #yaErr:not(:empty)', timeout=10000)
        pg.wait_for_timeout(300)
    # 1. владелец входит первым — становится администратором
    login('boss@iway.ru')
    assert pg.is_visible('#tab_settings') and pg.inner_text('#meName') == 'boss', pg.inner_text('#meName')
    # 2. перенос: резервная копия из версии на claude.ai
    pg.click('#tab_settings'); pg.click('#sub_backup')
    assert pg.is_visible('#bImportPanel')
    pg.set_input_files('#bFile', str(bfile)); pg.wait_for_timeout(500); assert pg.query_selector('#bGo'), (pg.inner_text('#bStat'), errs)
    assert 'months — 2' in pg.inner_text('#bPreview') and pg.input_value('#bMe') == 'yulia'
    pg.click('#bGo'); pg.wait_for_selector('#bStat:has-text("Готово")', timeout=10000)
    st = store()
    yu = st['config/team']['people']['yulia']
    assert yu['email'] == 'boss@iway.ru' and yu['admin'] and not {'login', 'salt', 'hash'} & set(yu), yu
    assert len(st['config/team']['people']) == 3 and st['months/anna_2026-10']['days']['2026-10-01']['int_done'] == 1, st['config/team']
    assert pg.inner_text('#meName') == 'Юлия Немчинова', pg.inner_text('#meName')
    # 3. команда: почта вместо логина; задвоить почту нельзя
    pg.click('#sub_team'); pg.wait_for_timeout(200)
    assert 'Почта Яндекс 360' in pg.inner_html('#tUsers thead') and 'Выдать пароль' not in pg.inner_text('#tUsers')
    pg.fill('#tUsers input[data-p=anna][data-f=email]', 'boss@iway.ru'); pg.dispatch_event('#tUsers input[data-p=anna][data-f=email]', 'change'); pg.wait_for_timeout(200)
    assert 'уже у другого' in pg.inner_text('#tStat')
    pg.fill('#tUsers input[data-p=anna][data-f=email]', 'Ann@iway.ru'); pg.dispatch_event('#tUsers input[data-p=anna][data-f=email]', 'change'); pg.wait_for_timeout(500)
    assert store()['config/team']['people']['anna']['email'] == 'ann@iway.ru' and store()['config/team']['people']['yulia']['yid'] == 'yid-boss@iway.ru'
    assert pg.is_disabled('#tUsers input[data-p=yulia][data-f=email]')   # свою почту не сменить
    # 4. дашборд считает загруженное
    pg.click('#tab_day'); pg.select_option('#dMode', 'month'); pg.wait_for_timeout(300)
    assert 'Собеседования прошли\n4' in pg.inner_text('#dTiles'), pg.inner_text('#dTiles')
    # 5. резервная копия скачивается без паролей
    pg.click('#tab_settings'); pg.click('#sub_backup')
    with pg.expect_download() as dl: pg.click('#bExport')
    got = json.loads(pathlib.Path(dl.value.path()).read_text())
    assert got['format'] == 'hr-metrics' and len(got['docs']) == 5 and 'hash' not in json.dumps(got['docs']['config/team'])
    # 6. рекрутер: только своё — и сервер не даёт записать чужое, даже в обход страницы
    pg.click('#logout'); pg.wait_for_selector('#yaBtn', state='visible')
    login('ann@iway.ru')
    assert pg.inner_text('#tab_day') == 'Мой день' and not pg.query_selector('#tab_settings')
    pg.click('#tab_vac'); pg.select_option('#vStatus', ''); pg.wait_for_timeout(200)
    assert 'Диспетчер' in pg.inner_text('#vTable') and 'Логист' not in pg.inner_text('#vTable')
    seen = pg.evaluate("fetch('/api/sync', {headers:{'X-HR':'1'}}).then(r => r.json()).then(j => j.docs.map(d => d.path).sort())")
    assert seen == ['config/team', 'months/anna_2026-10', 'vacancies/b'], seen
    r = pg.evaluate("""fetch('/api/doc', {method:'POST', headers:{'X-HR':'1','Content-Type':'application/json'},
        body: JSON.stringify({path:'months/yulia_2026-10', op:'set', data:{person:'yulia', month:'2026-10', days:{}}})}).then(r => r.status)""")
    assert r == 403 and store()['months/yulia_2026-10']['days'], r
    # своё — сохраняется через страницу
    pg.click('#tab_entry'); pg.fill('#fDate', '2026-10-06'); pg.dispatch_event('#fDate', 'change'); pg.fill('#m_calls', '7'); pg.click('#fSave'); pg.wait_for_timeout(500)
    assert store()['months/anna_2026-10']['days']['2026-10-06']['calls'] == 7
    # 7. архив закрывает доступ на следующем же запросе
    pg.click('#logout'); pg.wait_for_selector('#yaBtn', state='visible')
    # 8. чужой домен и посторонние
    login('ann@gmail.com'); assert 'корпоративной почтой' in pg.inner_text('#yaErr')
    login('nobody@iway.ru'); assert 'нет в команде' in pg.inner_text('#yaErr') and 'login=' not in pg.url
    pg.screenshot(path=str(HERE / 'shots' / 'hr-cloud-login.png'))
    b.close()
finally:
    srv.terminate()
print('CSP:', csp or 'нет нарушений'); print('ОШИБКИ:', errs or 'нет')
assert not errs and not csp
