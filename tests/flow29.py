# Совместная работа с одним файлом версии для ПК: два человека на разных ПК, файл в общей папке.
# Выбор файла (File System Access) подменён: оба «подключают» один и тот же файл на диске.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib, subprocess, shutil
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
snap = HERE / '.cache' / 'offline-snap2'
shutil.rmtree(snap, ignore_errors=True)
def put(path, data):
    f = snap / (path + '.json'); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
h = lambda s, pw: hashlib.sha256((s + '::' + pw).encode()).hexdigest()
put('config/team', {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'salt': 's1', 'hash': h('s1', 'p1'), 'admin': True, 'order': 1},
                               'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'salt': 's2', 'hash': h('s2', 'p2'), 'order': 2}}})
put('months/anna_2026-10', {'person': 'anna', 'month': '2026-10', 'days': {'2026-10-01': {'calls': 4}}})
put('vacancies/v1', {'title': 'Логист', 'status': 'активна', 'manager': 'Шулятицкая', 'publishedAt': '2026-09-01', 'comment': 'старый'})
shared = HERE / '.cache' / 'shared' / 'HR-метрики.html'; shared.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(['python3', str(ROOT / 'tools' / 'build_offline.py'), str(snap), str(shared)], check=True, capture_output=True)
def on_disk():
    t = shared.read_text(encoding='utf-8'); a = t.index('var SEED = '); z = t.index(';\n  var TEMPLATE = ')
    return json.loads(t[a + 11:z])['data']

FAKE = """
window.__hrPoll = 400;
window.showOpenFilePicker = async () => [{
  kind: 'file', name: 'HR-метрики.html',
  queryPermission: async () => 'granted', requestPermission: async () => 'granted',
  getFile: async () => ({ text: async () => await window.fsRead() }),
  createWritable: async () => { let buf = ''; return { write: async t => { buf = t; }, close: async () => { await window.fsWrite(buf); } }; },
}];
"""
errs, writes = [], []
def pc(b, login, pw):
    ctx = b.new_context(viewport={'width': 1280, 'height': 900})
    ctx.expose_function('fsRead', lambda: shared.read_text(encoding='utf-8'))
    def w(t): writes.append(login); shared.write_text(t, encoding='utf-8')
    ctx.expose_function('fsWrite', w)
    ctx.add_init_script(FAKE)
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(login + ': ' + str(e)))
    pg.clock.set_fixed_time('2026-10-07T12:00:00')
    pg.goto(shared.as_uri()); pg.wait_for_selector('#lLogin', state='visible')
    pg.fill('#lLogin', login); pg.fill('#lPass', pw); pg.click('#lSubmit'); pg.wait_for_selector('#tabs button')
    assert pg.is_visible('#offlineBar') and 'Подключите этот файл' in pg.inner_text('#offlineBar')
    pg.click('#offlineBar button'); pg.wait_for_timeout(300)
    assert pg.is_hidden('#offlineBar') and pg.evaluate('__offline.status().linked')
    return pg
def day(pg, d, k, v):
    pg.click('#tab_entry')
    if pg.is_visible('#fPerson'): pg.select_option('#fPerson', 'anna')
    pg.fill('#fDate', d); pg.dispatch_event('#fDate', 'change'); pg.fill('#m_' + k, str(v)); pg.click('#fSave'); pg.wait_for_timeout(100)
def settle(*pgs):
    for _ in range(3):
        for pg in pgs: pg.evaluate('__offline.sync()')
    for pg in pgs: assert pg.evaluate('__offline.status().pending') == 0, pg.evaluate("JSON.stringify(JSON.parse(localStorage.getItem('hr-offline-db')).pending)")[:600]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    A = pc(b, 'y', 'p1'); B = pc(b, 'a', 'p2')
    # одновременно: разные дни одного месяца, одна и та же вакансия — разные поля, новая вакансия у каждого
    day(A, '2026-10-06', 'calls', 9); day(B, '2026-10-07', 'calls', 5)
    A.evaluate("claude.use('db').then(db => db.doc('vacancies/v1').update({status: 'выход сотрудника'}))")
    B.evaluate("claude.use('db').then(db => db.doc('vacancies/v1').update({comment: 'новый'}))")
    A.evaluate("claude.use('db').then(db => db.doc('vacancies/a1').set({title: 'От Юлии', manager: 'Немчинова', status: 'активна'}))")
    B.evaluate("claude.use('db').then(db => db.doc('vacancies/b1').set({title: 'От Анны', manager: 'Шулятицкая', status: 'активна'}))")
    A.wait_for_timeout(1500); settle(A, B)
    d = on_disk()
    days = {k: {f: v for f, v in x.items() if f != 'savedAt'} for k, x in d['months/anna_2026-10']['days'].items()}   # время ввода дня не сравниваем
    assert days == {'2026-10-01': {'calls': 4}, '2026-10-06': {'calls': 9}, '2026-10-07': {'calls': 5}}, d['months/anna_2026-10']
    assert d['vacancies/v1']['status'] == 'выход сотрудника' and d['vacancies/v1']['comment'] == 'новый', d['vacancies/v1']
    assert d['vacancies/a1']['title'] == 'От Юлии' and d['vacancies/b1']['title'] == 'От Анны'
    # у каждого на экране — правки коллеги, без перезагрузки
    A.click('#tab_vac'); A.evaluate("setVacStatus([])"); A.wait_for_timeout(200)
    assert 'От Анны' in A.inner_text('#vTable')
    assert B.evaluate("JSON.parse(localStorage.getItem('hr-offline-db')).data['months/anna_2026-10'].days['2026-10-06'].calls") == 9
    # одно и то же поле: остаётся правка, записанная последней; удаление доходит до коллеги
    A.evaluate("claude.use('db').then(db => db.doc('vacancies/v1').update({comment: 'Юлия'}))"); A.evaluate('__offline.sync()')
    B.evaluate("claude.use('db').then(db => db.doc('vacancies/v1').update({comment: 'Анна'}))"); B.evaluate('__offline.sync()')
    settle(A, B); assert on_disk()['vacancies/v1']['comment'] == 'Анна', on_disk()['vacancies/v1']
    A.evaluate("claude.use('db').then(db => db.doc('vacancies/a1').delete())"); settle(A, B)
    assert 'vacancies/a1' not in on_disk() and 'vacancies/a1' not in B.evaluate("JSON.parse(localStorage.getItem('hr-offline-db')).data")
    # правка без подключённого файла (например, до входа в общую папку) не теряется, когда файл подключат
    B.evaluate("claude.use('db').then(db => db.doc('vacancies/b2').set({title: 'Позже', manager: 'Шулятицкая', status: 'активна'}))")
    B.reload(); B.wait_for_selector('#tabs button')
    assert 'Есть несохранённые изменения' in B.inner_text('#offlineBar')    # браузер не помнит доступ — подключаем снова
    B.click('#offlineBar button'); B.wait_for_timeout(300)
    settle(A, B); assert on_disk()['vacancies/b2']['title'] == 'Позже'
    # нагрузка: оба быстро и одновременно вносят по 10 дней в один и тот же месяц — сохраняются все 20
    for i in range(10):
        A.evaluate("claude.use('db').then(db => db.doc('months/anna_2026-11').get().then(s => { var d = s.exists ? s.data() : {person:'anna', month:'2026-11', days:{}}; d.days['2026-11-%02d'] = {calls: %d}; return db.doc('months/anna_2026-11').set(d); }))" % (i + 1, i))
        B.evaluate("claude.use('db').then(db => db.doc('months/anna_2026-11').get().then(s => { var d = s.exists ? s.data() : {person:'anna', month:'2026-11', days:{}}; d.days['2026-11-%02d'] = {calls: %d}; return db.doc('months/anna_2026-11').set(d); }))" % (i + 11, i))
        A.wait_for_timeout(150)
    A.wait_for_timeout(1500); settle(A, B); settle(A, B)
    assert len(on_disk()['months/anna_2026-11']['days']) == 20, sorted(on_disk()['months/anna_2026-11']['days'])
    b.close()
print('записей в файл:', len(writes)); print('ОШИБКИ:', errs or 'нет')
assert not errs
