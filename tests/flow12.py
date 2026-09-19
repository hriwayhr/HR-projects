from playwright.sync_api import sync_playwright
import pathlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
import json, hashlib
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()
seed={'employees/IW-N':{'code':'IW-N','login':'аня','firstName':'Анна','lastName':'Иванова','gender':'f',
      'dept':'Операционный отдел','email':'','personalEmail':'x@ex.com','startDate':'2026-09-30','startTime':'10:00',
      'createdAt':'2026-09-18','openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}},
      'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':900})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url); pg.wait_for_timeout(700)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)

    # с первого экрана убраны кнопка и рабочая почта
    assert pg.query_selector('#mEmail') is None, 'рабочая почта осталась в герое'
    assert pg.query_selector('.hero .actions a.ghost') is None, 'кнопка «Что взять с собой» осталась'
    print('герой: почта и кнопка убраны')

    # первый экран — навигация в герое, в шапке скрыта
    pg.evaluate('window.scrollTo(0,0)'); pg.wait_for_timeout(400)
    assert pg.is_visible('.hero .nav'), 'на первом экране нет навигации в герое'
    assert not pg.is_visible('.topbar .nav'), 'на первом экране навигация дублируется в шапке'
    print('первый экран: навигация в герое')

    # ушли с первого экрана — навигация наверху
    pg.evaluate("window.scrollTo(0, window.scrollY + document.getElementById('hero').getBoundingClientRect().bottom)")
    pg.wait_for_timeout(500)
    assert pg.is_visible('.topbar .nav'), 'после первого экрана навигация не появилась в шапке'
    assert not pg.is_visible('.hero .nav'), 'навигация в герое осталась видимой'
    print('после первого экрана: навигация в шапке')

    # шапка держит высоту — переключение не двигает вёрстку
    pg.evaluate('window.scrollTo(0,0)'); pg.wait_for_timeout(500)
    assert pg.is_visible('.hero .nav'), 'возврат наверх не вернул навигацию в герой'
    assert not pg.is_visible('.topbar .nav'), 'возврат наверх не убрал навигацию из шапки'
    print('возврат наверх: навигация снова в герое')

    # ссылки работают из героя
    pg.click('.hero .nav a[href="#team"]'); pg.wait_for_timeout(600)
    assert pg.evaluate('window.scrollY') > 0, 'ссылка из героя не прокрутила страницу'
    print('ссылка из героя прокручивает к разделу')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
