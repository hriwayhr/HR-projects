# -*- coding: utf-8 -*-
# Трудовая книжка впервые: документ остаётся обязательным, но у новичка его
# может ещё не быть — ответ «Да, впервые» закрывает пункт.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / 'shots').mkdir(exist_ok=True)
base = str(HERE) + '/'
html = pathlib.Path(str(ROOT / 'src' / 'iway-welcome.html')).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()
seed={'employees/IW-F': {'code':'IW-F','login':'iw-f','firstName':'Дарья','lastName':'Первая','gender':'f',
      'dept':'Операционный отдел','email':'','personalEmail':'d@ex.com','startDate':'2026-10-05','startTime':'10:00',
      'createdAt':'2026-09-18','openedAt':'','sentAt':'2026-09-19T08:00:00Z','salt':salt,'hash':h,'progress':{}},
      'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]

def enter(pg):
    pg.goto(url+'#exit'); pg.wait_for_timeout(400)
    pg.fill('#gateLogin','iw-f'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1100}, device_scale_factor=2)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    enter(pg)

    # подстрока стоит под трудовой книжкой и только под ней
    rows = pg.eval_on_selector_all('#docList [data-first-row]', 'els => els.map(e => e.getAttribute("data-first-row"))')
    assert rows == ['labor'], rows
    prev = pg.eval_on_selector('#docList [data-first-row]', 'e => e.previousElementSibling.getAttribute("data-key")')
    assert prev == 'labor', prev
    # документ остался обязательным: он в списке и в знаменателе счётчика
    assert pg.inner_text('#docCount') == '0 из 4', pg.inner_text('#docCount')
    print('подстрока под трудовой, счётчик:', pg.inner_text('#docCount'))

    # ——— «Да, впервые» закрывает пункт
    pg.click('#docList [data-first-btn="labor"]'); pg.wait_for_timeout(500)
    item = pg.query_selector('#docList [data-key="labor"]')
    assert item.get_attribute('aria-pressed') == 'true'
    assert item.get_attribute('aria-disabled') == 'true'
    assert not pg.is_hidden('#docList [data-first-row] .card-note')
    assert pg.inner_text('#docCount') == '1 из 4', pg.inner_text('#docCount')
    rec = pg.evaluate("window.__store['employees/IW-F']")
    assert rec['firstTime'] == {'labor': True} and rec['progress']['labor'] is True, rec.get('firstTime')
    print('ответ «впервые»:', pg.inner_text('#docCount'), '|', pg.inner_text('#docList [data-first-row] .card-note'))

    # отметку руками не снять, пока стоит ответ: кнопка помечена aria-disabled
    # (playwright такой клик не делает), да и обработчик его не принимает
    pg.eval_on_selector('#docList [data-key="labor"]', 'e => e.click()'); pg.wait_for_timeout(300)
    assert pg.query_selector('#docList [data-key="labor"]').get_attribute('aria-pressed') == 'true'
    assert pg.evaluate("window.__store['employees/IW-F'].progress.labor") is True
    print('пункт заблокирован, пока стоит ответ')

    # ——— HR видит причину
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    pg.locator('.prow').first.locator('.pr-head').click(); pg.wait_for_timeout(300)
    pg.locator('.prow').first.locator('.linky').click(); pg.wait_for_timeout(400)
    txt = pg.inner_text('#dlgText')
    assert 'Оформляем впервые (приносить нечего): Трудовая книжка' in txt.replace('\n',' '), txt
    print('в панели HR:', [l for l in txt.split('\n') if 'впервые' in l][0][:80])
    pg.click('#dlgOk'); pg.wait_for_timeout(300)

    # ——— повторный ответ снимает и отметку
    enter(pg)
    assert pg.query_selector('#docList [data-first-btn="labor"]').get_attribute('aria-pressed') == 'true', 'ответ не восстановился'
    pg.click('#docList [data-first-btn="labor"]'); pg.wait_for_timeout(500)
    assert pg.inner_text('#docCount') == '0 из 4', pg.inner_text('#docCount')
    assert pg.query_selector('#docList [data-key="labor"]').get_attribute('aria-disabled') == 'false'
    rec = pg.evaluate("window.__store['employees/IW-F']")
    assert not rec.get('firstTime') and rec['progress']['labor'] is False, rec
    # и пункт снова отмечается руками
    pg.click('#docList [data-key="labor"]'); pg.wait_for_timeout(300)
    assert pg.inner_text('#docCount') == '1 из 4', pg.inner_text('#docCount')
    print('ответ снят: пункт снова обычный')

    # ——— флаг ставит HR: он переживает пересборку списка
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.check('[data-docreq="first4"]')          # ИНН — пятый обязательный документ
    pg.click('#savePage'); pg.wait_for_timeout(700)
    saved = pg.evaluate("window.__store['config/page'].sections.docs.items")
    assert [i.get('first', False) for i in saved] == [False, False, False, True, True], saved
    enter(pg)
    rows = pg.eval_on_selector_all('#docList [data-first-row]', 'els => els.map(e => e.getAttribute("data-first-row"))')
    assert rows == ['labor','inn'], rows
    print('флаг HR: подстроки у', ', '.join(rows))

    # снятый флаг убирает подстроку
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.uncheck('[data-docreq="first4"]')
    pg.click('#savePage'); pg.wait_for_timeout(700)
    enter(pg)
    rows = pg.eval_on_selector_all('#docList [data-first-row]', 'els => els.map(e => e.getAttribute("data-first-row"))')
    assert rows == ['labor'], rows
    print('флаг снят: подстрока убрана')

    pg.evaluate("document.querySelector('#docs').scrollIntoView()"); pg.wait_for_timeout(600)
    pg.screenshot(path=base+'shots/docs-first.png')
    b.close()
print('ОШИБКИ:', errs or 'нет')
