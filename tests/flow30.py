# Обновление программы в рабочем файле версии для ПК без потери данных:
# сборка --update (без данных) подключается к рабочему файлу — данные из него, программа новая;
# открытая у коллеги старая версия файл назад не откатывает, а её правки доходят после перезагрузки.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib, subprocess, shutil, re
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
snap = HERE / '.cache' / 'offline-snap3'; shutil.rmtree(snap, ignore_errors=True)
def put(path, data):
    f = snap / (path + '.json'); f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
put('config/team', {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'salt': 's1', 'hash': hashlib.sha256(b's1::p1').hexdigest(), 'admin': True, 'order': 1}}})
put('vacancies/v1', {'title': 'Логист', 'status': 'активна', 'manager': 'Немчинова', 'publishedAt': '2026-09-01'})
work = HERE / '.cache' / 'shared3' / 'HR-метрики.html'; work.parent.mkdir(parents=True, exist_ok=True)
upd = HERE / '.cache' / 'HR-метрики (обновление).html'
build = lambda *a: subprocess.run(['python3', str(ROOT / 'tools' / 'build_offline.py'), *map(str, a)], check=True, capture_output=True)
ver = lambda t: int(re.search(r'var VERSION = (\d+);', t).group(1))
def data(): t = work.read_text(encoding='utf-8'); return json.loads(t[t.index('var SEED = ') + 11:t.index(';\n  var TEMPLATE = ')])['data']
build(snap, work); v1 = ver(work.read_text(encoding='utf-8'))

FAKE = """
window.__hrPoll = 300;
window.showOpenFilePicker = async () => [{ kind: 'file', name: 'HR-метрики.html',
  queryPermission: async () => 'granted', requestPermission: async () => 'granted',
  getFile: async () => ({ text: async () => await window.fsRead() }),
  createWritable: async () => { let buf = ''; return { write: async t => { buf = t; }, close: async () => { await window.fsWrite(buf); } }; } }];
"""
errs = []
def pc(b):
    ctx = b.new_context(viewport={'width': 1280, 'height': 900})
    ctx.expose_function('fsRead', lambda: work.read_text(encoding='utf-8'))
    ctx.expose_function('fsWrite', lambda t: work.write_text(t, encoding='utf-8'))
    ctx.add_init_script(FAKE)
    pg = ctx.new_page(); pg.on('pageerror', lambda e: errs.append(str(e))); pg.clock.set_fixed_time('2026-10-07T12:00:00')
    return pg
def login(pg):
    pg.wait_for_selector('#lLogin', state='visible'); pg.fill('#lLogin', 'y'); pg.fill('#lPass', 'p1'); pg.click('#lSubmit'); pg.wait_for_selector('#tabs button')
add = lambda pg, id, t: pg.evaluate("claude.use('db').then(db => db.doc('vacancies/%s').set({title: '%s', manager: 'Немчинова', status: 'активна'}))" % (id, t))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    # работа в старой версии: правка уходит в файл
    A = pc(b); A.goto(work.as_uri()); login(A); A.click('#offlineBar button'); A.wait_for_timeout(200)
    add(A, 'a1', 'До обновления'); A.wait_for_timeout(1200)
    assert data()['vacancies/a1']['title'] == 'До обновления'
    # обновление: пустая сборка, подключить рабочий файл
    build('--update', upd); v2 = ver(upd.read_text(encoding='utf-8')); assert v2 > v1
    assert json.loads(upd.read_text(encoding='utf-8').split('var SEED = ')[1].split(';\n  var TEMPLATE = ')[0])['data'] == {}
    B = pc(b); B.goto(upd.as_uri()); B.wait_for_selector('#offlineBar button')
    B.click('#offlineBar button'); login(B)                     # команда пришла из рабочего файла — можно войти
    t = work.read_text(encoding='utf-8')
    assert ver(t) == v2 and data()['vacancies/a1']['title'] == 'До обновления' and data()['vacancies/v1']['title'] == 'Логист'
    B.click('#tab_vac'); B.wait_for_timeout(200); assert 'До обновления' in B.inner_text('#vTable')
    # старая вкладка: правка не теряется, файл не откатывается, просьба перезагрузить
    add(A, 'a2', 'В старой вкладке'); A.wait_for_timeout(1500)
    assert ver(work.read_text(encoding='utf-8')) == v2 and 'a2' not in json.dumps(list(data()))
    assert 'перезагрузите страницу' in A.inner_text('#offlineBar')
    A.goto(work.as_uri()); A.wait_for_selector('#offlineBar button'); A.click('#offlineBar button'); A.wait_for_timeout(1200)
    assert data()['vacancies/a2']['title'] == 'В старой вкладке' and ver(work.read_text(encoding='utf-8')) == v2
    b.close()
print('ОШИБКИ:', errs or 'нет'); assert not errs
