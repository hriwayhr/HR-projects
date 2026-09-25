from playwright.sync_api import sync_playwright
import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / 'shots').mkdir(exist_ok=True)
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
import json, hashlib, re
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()
def emp(code, login, first, last, gender):
    return {'code':code,'login':login,'firstName':first,'lastName':last,'gender':gender,'dept':'Операционный отдел',
            'email':'','personalEmail':'x@ex.com','startDate':'2026-09-30','startTime':'10:00','createdAt':'2026-09-18',
            'openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}}
seed={'employees/IW-F': emp('IW-F','аня','Анна','Иванова','f'),
      'employees/IW-M': emp('IW-M','пётр','Пётр','Петров','m'),
      'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    # девушка: военного билета нет
    pg.goto(url); pg.wait_for_timeout(700)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    print('Ж — военный билет скрыт:', pg.is_hidden('#docList [data-doc="mil"]'), '| счётчик:', pg.inner_text('#docCount'))
    # отмечаем всё + заявка на карту
    pg.evaluate("document.querySelectorAll('#docList [data-key]').forEach(b=>{if(!b.hidden) b.click();})")
    pg.wait_for_timeout(500)
    pg.click('.cardrow .opt-btn[data-card="need"]'); pg.wait_for_timeout(800)
    print('после выбора карты:', pg.inner_text('#docCount'), '|', pg.inner_text('#docDone'))
    print('подпись у карты:', pg.inner_text('#cardNote')[:60])
    pg.locator('#docList').scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    pg.screenshot(path=base+'shots/g-female.png', clip={'x':240,'y':pg.query_selector('#docList').bounding_box()['y']-80,'width':800,'height':560})
    # парень: билет есть, без оговорки
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','пётр'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    mil = pg.query_selector('#docList [data-doc="mil"]')
    print('М — билет виден:', not pg.is_hidden('#docList [data-doc="mil"]'), '| текст:', mil.inner_text().strip(), '| счётчик:', pg.inner_text('#docCount'))
    # панель HR
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    for c in pg.query_selector_all('.prow'):
        print(' ', c.query_selector('.pr-who').inner_text(), '→',
              c.query_selector('.pr-num').inner_text(),
              '|', c.query_selector('.chip').inner_text(),
              '| карта:', bool(c.query_selector('.pr-mark')))
    b.close()
print('ОШИБКИ:', errs or 'нет')
