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
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.goto(url+'#admin'); pg.wait_for_timeout(700)
    pg.click('#tabAdmins'); pg.fill('#aName','Юля Немчинова'); pg.fill('#aRole','Руководитель HR'); pg.fill('#aMail','ny@iway.ru')
    pg.click('#adminForm button[type=submit]'); pg.wait_for_timeout(400)
    pg.click('#tabDepts'); pg.click('#addDept'); pg.wait_for_timeout(200)
    ins=pg.query_selector_all('#deptRows tr td input')
    ins[0].fill('Клиентский сервис'); ins[1].fill('Мария Соколова, руководитель отдела'); ins[2].fill('Дмитрий Орлов, старший специалист'); ins[3].fill('#cs-team')
    pg.click('#saveDepts'); pg.wait_for_timeout(400)
    pg.click('#tabPeople')
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','anna.ivanova@gmail.com')
    pg.select_option('#fDept','Клиентский сервис'); pg.fill('#fDate','2026-10-05'); pg.wait_for_timeout(200)
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(900)
    print('кому:', pg.inner_text('#mailTo'))
    print('личная почта в базе:', pg.evaluate("Object.values(window.__store).find(v=>v.personalEmail)?.personalEmail"))
    pg.wait_for_timeout(600)
    pg.locator('#mailPanel').scroll_into_view_if_needed(); pg.wait_for_timeout(400)
    pg.screenshot(path=base+'shots/m1-panel.png')
    # само письмо крупно
    fr = pg.frame_locator('#mailPreview')
    pg.set_viewport_size({'width':760,'height':1400})
    pg.wait_for_timeout(400)
    el = pg.query_selector('#mailPreview'); el.screenshot(path=base+'shots/m2-letter.png')
    b.close()
print('ОШИБКИ:', errs or 'нет')
