# Версия для ПК (tools/build_offline.py): один HTML с данными внутри, без claude.ai и без интернета.
# Вход по паролю, ввод дня, данные переживают перезагрузку (localStorage), «Скачать файл с данными»
# даёт копию, в которой изменения уже вшиты, и предупреждение о несохранённом.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib, subprocess
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
snap = HERE / '.cache' / 'offline-snap'
def put(path, data):
    f = snap / (path + '.json'); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
h = hashlib.sha256('s1::secret1'.encode()).hexdigest()
put('config/team', {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'salt': 's1', 'hash': h, 'admin': True, 'order': 1},
                               'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'order': 2}}})
put('months/anna_2026-10', {'person': 'anna', 'month': '2026-10', 'days': {'2026-10-01': {'int_planned': 2, 'int_done': 1, 'calls': 4}}})
put('vacancies/v1', {'title': 'Логист', 'status': 'активна', 'manager': 'Шулятицкая', 'publishedAt': '2026-09-01'})
out = HERE / '.cache' / 'HR-метрики.html'
subprocess.run(['python3', str(ROOT / 'tools' / 'build_offline.py'), str(snap), str(out)], check=True, capture_output=True)

errs, ext = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    ctx = b.new_context(viewport={'width': 1280, 'height': 1000}, accept_downloads=True)
    ctx.add_init_script('delete window.showSaveFilePicker;')     # как в браузерах без доступа к файлам — копия скачивается
    ctx.route('http*://**', lambda r: (ext.append(r.request.url), r.abort()))
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time('2026-10-07T12:00:00')
    pg.goto(out.as_uri()); pg.wait_for_selector('#lLogin', state='visible')
    pg.fill('#lLogin', 'y'); pg.fill('#lPass', 'secret1'); pg.click('#lSubmit'); pg.wait_for_selector('#tabs button')
    assert pg.inner_text('#meName') == 'Юлия Немчинова' and pg.is_hidden('#offlineBar')
    # ввод дня за Анну
    pg.click('#tab_entry'); pg.select_option('#fPerson', 'anna'); pg.fill('#fDate', '2026-10-06'); pg.dispatch_event('#fDate', 'change')
    pg.fill('#m_calls', '9'); pg.click('#fSave'); pg.wait_for_timeout(300)
    assert pg.is_visible('#offlineBar') and 'несохранённые' in pg.inner_text('#offlineBar')
    # новая вакансия (документ без id) и частичное обновление
    pg.click('#tab_vac'); pg.click('#vAdd'); pg.fill('#v_title', 'Диспетчер'); pg.fill('#v_manager', 'Шулятицкая'); pg.click('#vSave'); pg.wait_for_timeout(300)
    store = pg.evaluate("JSON.parse(localStorage.getItem('hr-offline-db')).data")
    assert store['months/anna_2026-10']['days']['2026-10-06']['calls'] == 9
    assert any(v.get('title') == 'Диспетчер' for k, v in store.items() if k.startswith('vacancies/'))
    # перезагрузка: данные с этого ПК на месте
    pg.reload(); pg.wait_for_selector('#tabs button')
    pg.click('#tab_vac'); pg.select_option('#vStatus', ''); pg.wait_for_timeout(200)
    assert 'Диспетчер' in pg.inner_text('#vTable') and pg.is_visible('#offlineBar')
    # скачать файл с данными — в нём уже есть изменения
    with pg.expect_download() as dl: pg.click('#offlineBar button')
    saved = pathlib.Path(dl.value.path()); assert dl.value.suggested_filename == 'HR-метрики.html'
    assert pg.is_hidden('#offlineBar')
    # новый ПК (чистый браузер) открывает скачанный файл
    ctx2 = b.new_context(); ctx2.route('http*://**', lambda r: (ext.append(r.request.url), r.abort()))
    pg2 = ctx2.new_page(); pg2.on('pageerror', lambda e: errs.append(str(e)))
    copy = HERE / '.cache' / 'copy.html'; copy.write_bytes(saved.read_bytes())
    pg2.goto(copy.as_uri()); pg2.wait_for_selector('#lLogin', state='visible')
    pg2.fill('#lLogin', 'y'); pg2.fill('#lPass', 'secret1'); pg2.click('#lSubmit'); pg2.wait_for_selector('#tabs button')
    pg2.click('#tab_vac'); pg2.select_option('#vStatus', ''); pg2.wait_for_timeout(200)
    assert 'Диспетчер' in pg2.inner_text('#vTable')
    d = pg2.evaluate("JSON.parse(localStorage.getItem('hr-offline-db')).data['months/anna_2026-10'].days['2026-10-06'].calls")
    assert d == 9, d
    # резервная копия со страницы — обычное скачивание
    pg2.click('#tab_settings'); pg2.click('#sub_backup')
    with pg2.expect_download() as dl2: pg2.click('#bExport')
    assert json.loads(pathlib.Path(dl2.value.path()).read_text())['format'] == 'hr-metrics'
    b.close()
print('внешние запросы:', ext or 'нет'); print('ОШИБКИ:', errs or 'нет')
assert not errs and not ext
