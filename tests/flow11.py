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
def emp(code, first, last, gender):
    return {'code':code,'login':code.lower(),'firstName':first,'lastName':last,'gender':gender,'dept':'Операционный отдел',
            'email':'','personalEmail':'x@ex.com','startDate':'2026-10-05','startTime':'10:00','createdAt':'2026-09-18',
            'openedAt':'2026-09-19','sentAt':'2026-09-19','salt':salt,'hash':h,'progress':{}}
seed={'employees/IW-F': emp('IW-F','Анна','Иванова','f'), 'employees/IW-M': emp('IW-M','Пётр','Петров','m'),
      'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1000,'height':900}, device_scale_factor=2)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url); pg.wait_for_timeout(700)
    pg.fill('#gateLogin','iw-f'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    print('Ж обязательных:', pg.inner_text('#docCount'), '| кнопка активна:', not pg.is_disabled('#docsSend'))
    print('подсказка:', pg.inner_text('#docsSendHint')[:60])
    # отмечаем 4 обязательных (без военного — он скрыт) и необязательные
    for k in ['passport','snils','labor','inn']:
        pg.click('#docList [data-key="%s"]' % k); pg.wait_for_timeout(150)
    pg.wait_for_timeout(600)
    print('после обязательных:', pg.inner_text('#docCount'), '| кнопка активна:', not pg.is_disabled('#docsSend'))
    print('подсказка:', pg.inner_text('#docsSendHint')[:70])
    pg.click('.cardrow .opt-btn[data-card="need"]'); pg.wait_for_timeout(600)
    print('ответ про карту:', pg.inner_text('#cardNote')[:60])
    print('подсказка:', pg.inner_text('#docsSendHint')[:60])
    pg.click('#docsSend'); pg.wait_for_timeout(900)
    print('после отправки:', pg.inner_text('#docsSend'), '|', pg.inner_text('#docsSendHint')[:55])
    print('в базе docsSentAt:', bool(pg.evaluate("window.__store['employees/IW-F'].docsSentAt")))
    pg.evaluate("document.querySelector('#docs').scrollIntoView()"); pg.wait_for_timeout(500)
    pg.screenshot(path=base+'shots/docs-new.png')
    # мужчина — 5 обязательных
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','iw-m'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    print('М обязательных:', pg.inner_text('#docCount'), '| билет виден:', not pg.is_hidden('#docList [data-doc="mil"]'))
    # панель
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    print('фильтры:', pg.inner_text('#peopleFilters').replace('\n',' | '))
    for c in pg.query_selector_all('.pcard'):
        print(' ', c.query_selector('.pc-name').inner_text(), '|', c.query_selector('.pc-docs-top b').inner_text(),
              '|', c.query_selector('.chip').inner_text(), '|', c.query_selector('.pc-sub').inner_text())
    pg.locator('.pcard').first.locator('.linky').click(); pg.wait_for_timeout(500)
    print('детали:', pg.inner_text('#dlgText').replace('\n',' / ')[:200])
    b.close()
print('ОШИБКИ:', errs or 'нет')
