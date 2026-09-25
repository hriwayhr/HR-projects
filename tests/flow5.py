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
    ctx=b.new_context(viewport={'width':1280,'height':1000}, permissions=['clipboard-read','clipboard-write'])
    pg=ctx.new_page()
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.goto(url+'#admin'); pg.wait_for_timeout(700)
    pg.click('#tabAdmins'); pg.fill('#aName','Юля Немчинова'); pg.fill('#aRole','Руководитель HR'); pg.fill('#aMail','ny@iway.ru')
    pg.click('#adminForm button[type=submit]'); pg.wait_for_timeout(400)
    pg.click('#tabDepts'); pg.click('#addDept'); pg.wait_for_timeout(200)
    ins=pg.query_selector_all('#deptRows tr td input')
    ins[0].fill('Клиентский сервис'); ins[1].fill('Мария Соколова, руководитель отдела'); ins[2].fill('Дмитрий Орлов, старший специалист')
    pg.click('#saveDepts'); pg.wait_for_timeout(400)
    pg.click('#tabNew')
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','anna.ivanova@gmail.com')
    pg.select_option('#fDept','Клиентский сервис'); pg.fill('#fDate','2026-10-05'); pg.wait_for_timeout(200)
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(900)
    pg.click('#mailCopyRich'); pg.wait_for_timeout(500)
    print('кнопка копирования:', pg.inner_text('#mailCopyRich'))
    flavor = pg.evaluate("""async () => {
      const items = await navigator.clipboard.read();
      return items[0].types;
    }""")
    print('форматы в буфере:', flavor)
    html_cb = pg.evaluate("""async () => {
      const items = await navigator.clipboard.read();
      for (const it of items) if (it.types.includes('text/html')) return (await (await it.getType('text/html')).text()).slice(0,60);
      return 'нет html';
    }""")
    print('начало HTML в буфере:', html_cb)
    pg.click('#mailSent'); pg.wait_for_timeout(600)
    print('кнопка отправки:', pg.inner_text('#mailSent'))
    print('в базе sentAt:', bool(pg.evaluate("Object.values(window.__store).find(v=>v.code)?.sentAt")))
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(300)
    pg.click('#tabPeople'); pg.wait_for_timeout(300)
    pg.locator('.plist').scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    card = pg.query_selector('.prow')
    print('статус карточки:', card.query_selector('.chip').inner_text(),
          '| приглашение:', [r.inner_text().replace('\n',' ') for r in card.query_selector_all('.pc-row')][-1])
    pg.locator('#mailPanel').scroll_into_view_if_needed(); pg.wait_for_timeout(400)
    pg.screenshot(path=base+'shots/n1-mailpanel.png')
    b.close()
print('ОШИБКИ:', errs or 'нет')
