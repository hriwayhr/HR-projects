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
seed={'employees/IW-TEST':{'code':'IW-TEST','login':'тест','lastName':'Кристина','firstName':'Тестовая',
 'dept':'Операционный отдел','email':'','personalEmail':'k@ex.com','startDate':'2026-09-30','startTime':'10:00',
 'createdAt':'2026-09-18','openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}},
 'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    # сотрудник отмечает 4 документа
    pg.goto(url); pg.wait_for_timeout(700)
    pg.fill('#gateLogin','тест'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    pg.evaluate("document.querySelectorAll('#docList .check').forEach((b,i)=>{if(i<4)b.click();})")
    pg.wait_for_timeout(900)
    print('в базе отмечено:', pg.evaluate("Object.keys(window.__store['employees/IW-TEST'].progress).length"))
    # HR открывает панель
    pg.goto(url+'#admin'); pg.wait_for_timeout(1200)
    card = pg.query_selector('.pcard')
    print('карточка:', card.query_selector('.pc-docs-top b').inner_text(), '|', card.query_selector('.chip').inner_text())
    pg.locator('.pcard .linky').click(); pg.wait_for_timeout(500)
    print('диалог:', pg.inner_text('#dlgTitle'))
    print('список:', pg.inner_text('#dlgText')[:130].replace('\n',' / '))
    pg.screenshot(path=base+'shots/adm-doc.png', clip={'x':330,'y':230,'width':620,'height':420})
    pg.click('#dlgOk'); pg.wait_for_timeout(300)
    # внешняя правка: сотрудник дособрал пакет — таблица должна обновиться сама
    pg.evaluate("""() => {
      const r = window.__store['employees/IW-TEST'];
      r.progress = {doc0:1,doc1:1,doc2:1,doc3:1,doc4:1,doc5:1,doc6:1,doc7:1};
      window.__notify();
    }""")
    pg.wait_for_timeout(900)
    print('после внешней правки:', pg.query_selector('.pcard .pc-docs-top b').inner_text(), '|', pg.query_selector('.pcard .chip').inner_text())
    pg.screenshot(path=base+'shots/adm-ready.png')
    b.close()
print('ОШИБКИ:', errs or 'нет')
