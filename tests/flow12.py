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

    # имя и «Выйти» — в правом верхнем углу шапки, правее счётчика готовности
    pos = pg.evaluate("""() => {
      const bar = document.querySelector('.topbar-in').getBoundingClientRect();
      const who = document.querySelector('.topbar .who').getBoundingClientRect();
      const ready = document.querySelector('.topbar .ready').getBoundingClientRect();
      return {gap: bar.right - who.right, afterReady: who.left - ready.right};
    }""")
    assert pos['gap'] <= 21, 'имя не прижато к правому краю шапки (20px — отбивка шапки): %s' % pos
    assert pos['afterReady'] >= 0, 'имя стоит левее счётчика готовности: %s' % pos
    print('шапка: имя и «Выйти» в правом верхнем углу')

    # панель этапов вместо навигации по разделам
    assert pg.query_selector('.topbar .nav') is None, 'в шапке осталась старая навигация'
    assert pg.query_selector('.hero .nav') is None, 'в герое осталась старая навигация'
    assert pg.inner_text('#tbStage') == 'До выхода', 'в шапке не тот этап: ' + pg.inner_text('#tbStage')
    names = pg.eval_on_selector_all('.st .st-t', 'els => els.map(e => e.textContent)')
    assert names == ['До выхода', '1-й день', 'Первая неделя', 'Первый месяц', 'Окончание испытательного срока'], \
        'этапы не те: %s' % names
    print('панель этапов:', ' · '.join(names))

    # кнопки этапов достаточно крупные, чтобы попасть пальцем
    h = pg.eval_on_selector_all('.st', 'els => els.map(e => e.getBoundingClientRect().height)')
    assert min(h) >= 44, 'мишень для пальца мала: %s px' % min(h)
    print('кнопка этапа: высота %.0f px' % min(h))

    # шаги идут карточками в одной колонке и пронумерованы по порядку
    nums = pg.eval_on_selector_all('#stagePre section[data-step] .s-num', 'els => els.map(e => e.textContent)')
    assert nums == ['01', '02', '03', '04', '05', '06'], 'нумерация шагов поехала: %s' % nums
    print('шаги:', ' · '.join(nums))

    # на телефоне панель этапов становится лентой и страница не едет вбок
    pg.set_viewport_size({'width':430, 'height':900}); pg.wait_for_timeout(400)
    over = pg.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
    assert over <= 0, 'на телефоне страница едет вбок на %s px' % over
    assert pg.eval_on_selector('.st-list', 'e => getComputedStyle(e).flexDirection') == 'row', \
        'на телефоне этапы не стали лентой'
    print('телефон: этапы лентой, страница не едет вбок')
    pg.set_viewport_size({'width':1280, 'height':1000}); pg.wait_for_timeout(400)

    ids = pg.eval_on_selector_all('#stagePre > section, #stagePre > header', 'els => els.map(e => e.id)')
    assert ids == ['hero', 'form', 'about', 'culture', 'team', 'docs', 'dress', 'faq', 'contacts'], \
        'порядок блоков не тот: %s' % ids
    print('порядок блоков:', ' → '.join(ids))

    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
