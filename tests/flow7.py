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
url='file://'+str(pathlib.Path(base+'preview.html').resolve())
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    # системные окна заблокированы, как в артефакте
    pg.add_init_script("window.confirm=function(){console.log('confirm blocked');return false;};window.prompt=function(){return null;};window.alert=function(){};")
    pg.add_init_script(path=base+'mockdb.js')
    pg.goto(url+'#admin'); pg.wait_for_timeout(700)
    pg.click('#tabAdmins'); pg.fill('#aName','Юля'); pg.fill('#aMail','ny@iway.ru')
    pg.click('#adminForm button[type=submit]'); pg.wait_for_timeout(500)
    pg.click('#tabDepts'); pg.click('#addDept'); pg.wait_for_timeout(200)
    ins=pg.query_selector_all('#deptRows tr td input'); ins[0].fill('Клиентский сервис'); ins[1].fill('М. Соколова')
    pg.click('#saveDepts'); pg.wait_for_timeout(400)
    pg.click('#tabPeople'); pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','a@ex.com')
    pg.select_option('#fDept','Клиентский сервис'); pg.fill('#fDate','2026-10-05')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(900)
    print('карточек до удаления:', len(pg.query_selector_all('.pcard')))

    # логин меняется в окне настроек
    pg.locator('.pcard').first.locator('button', has_text='Настроить').click(); pg.wait_for_timeout(500)
    pg.fill('#eLogin','анна'); pg.click('#editSave'); pg.wait_for_timeout(700)
    print('логин в базе:', pg.evaluate("Object.values(window.__store).find(v=>v.code)?.login"))

    # отмена удаления
    pg.locator('.pcard').first.locator('button', has_text='Настроить').click(); pg.wait_for_timeout(400)
    pg.click('#editDelete'); pg.wait_for_timeout(500)
    print('диалог удаления:', pg.inner_text('#dlgTitle'))
    pg.click('#dlgCancel'); pg.wait_for_timeout(500)
    print('после отмены карточек:', len(pg.query_selector_all('.pcard')))

    # подтверждение удаления
    pg.locator('.pcard').first.locator('button', has_text='Настроить').click(); pg.wait_for_timeout(400)
    pg.click('#editDelete'); pg.wait_for_timeout(400)
    pg.screenshot(path=base+'shots/d1-dialog.png')
    pg.click('#dlgOk'); pg.wait_for_timeout(800)
    print('после удаления карточек:', len(pg.query_selector_all('.pcard')))
    print('в базе остались сотрудники:', [k for k in pg.evaluate("Object.keys(window.__store)") if k.startswith('employees/')] or 'нет')

    pg.click('#tabAdmins'); pg.wait_for_timeout(300)
    rows = pg.query_selector_all('#adminRows tr')
    print('админов:', len(rows), '| кнопка удаления есть:', bool(rows and rows[0].query_selector_all('button')[1:]))
    b.close()
print('ОШИБКИ:', errs or 'нет')
