from playwright.sync_api import sync_playwright
import pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / 'shots').mkdir(exist_ok=True)
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
import json, hashlib, re
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+str(pathlib.Path(base+'preview.html').resolve())
salt='e9a5250d81066992'
h=hashlib.sha256((salt+'::'+'тест').encode('utf-8')).hexdigest()
seed={'employees/IW-TEST':{'code':'IW-TEST','login':'тест','lastName':'Тест','firstName':'Тест',
 'dept':'Тестовый отдел (пример)','email':'t.test@iway.ru','personalEmail':'test@example.com',
 'startDate':'2026-10-01','createdAt':'2026-09-18T00:00:00.000Z','openedAt':'','sentAt':'',
 'salt':salt,'hash':h,'progress':{'doc0':True,'doc2':True,'doc3':True,'day0':True}},
 'config/departments':{'list':[{'name':'Тестовый отдел (пример)','head':'Мария Соколова, руководитель отдела','senior':'Дмитрий Орлов, старший специалист','chat':'#test-team'}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':900})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+';')
    pg.goto(url); pg.wait_for_timeout(300)
    pg.evaluate("Object.assign(window.__store, window.__seed)")
    pg.reload(); pg.wait_for_timeout(700)
    pg.evaluate("Object.assign(window.__store, window.__seed)")
    # вход кириллическим логином
    pg.fill('#gateLogin','тест'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(900)
    print('вход тест/тест:', 'OK' if not pg.is_hidden('#viewEmployee') else 'НЕ РАБОТАЕТ')
    print('приветствие:', pg.inner_text('#heroName'), '| команда:', pg.inner_text('#tHead'))
    print('готовность:', pg.inner_text('#readyPct'))
    # регистр и пробелы не мешают
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','  ТеСт '); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(800)
    print('вход «  ТеСт »:', 'OK' if not pg.is_hidden('#viewEmployee') else 'НЕ РАБОТАЕТ')
    # старый код тоже работает
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','IW-TEST'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(800)
    print('вход по коду IW-TEST:', 'OK' if not pg.is_hidden('#viewEmployee') else 'НЕ РАБОТАЕТ')
    # и по корпоративной почте
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','t.test@iway.ru'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(800)
    print('вход по почте:', 'OK' if not pg.is_hidden('#viewEmployee') else 'НЕ РАБОТАЕТ')
    # мусорный логин не роняет форму
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','кто-то/левый'); pg.fill('#gatePass','123'); pg.click('#gateForm button'); pg.wait_for_timeout(700)
    print('мусорный логин:', pg.inner_text('#gateErr')[:38], '| форма жива:', not pg.is_disabled('#gateForm button'))
    b.close()
print('ОШИБКИ:', errs or 'нет')
