# -*- coding: utf-8 -*-
# Плитки прогресса на первом экране: те же цифры, что в блоках ниже,
# обновляются сразу после отметки и ведут в нужный раздел.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()
seed={'employees/IW-N':{'code':'IW-N','login':'аня','firstName':'Анна','lastName':'Иванова','gender':'f',
      'dept':'Операционный отдел','email':'','personalEmail':'x@ex.com','startDate':'2026-09-30','startTime':'10:00',
      'createdAt':'2026-09-18','openedAt':'','sentAt':'','salt':salt,'hash':h,
      'progress':{'passport':True,'snils':True,'day0':True}},
      'config/departments':{'list':[{'name':'Операционный отдел','head':'М. Соколова','senior':'И. Крылов','chat':''}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':900})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url); pg.wait_for_timeout(700)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)

    # плитки считают то же, что блоки ниже
    assert pg.inner_text('#hpDocs') == pg.inner_text('#docCount'), \
        'плитка документов и блок расходятся: %s / %s' % (pg.inner_text('#hpDocs'), pg.inner_text('#docCount'))
    assert pg.inner_text('#hpDay') == pg.inner_text('#dayCount'), \
        'плитка первого дня и блок расходятся: %s / %s' % (pg.inner_text('#hpDay'), pg.inner_text('#dayCount'))
    assert pg.inner_text('#hpDocs') == '2 из 4', 'в плитке не те отметки: ' + pg.inner_text('#hpDocs')
    print('плитки: документы %s, первый день %s' % (pg.inner_text('#hpDocs'), pg.inner_text('#hpDay')))

    # дата выхода и сколько осталось
    assert pg.inner_text('#mDate').startswith('30 сентября'), 'в плитке не та дата: ' + pg.inner_text('#mDate')
    left = pg.inner_text('#hpLeft')
    assert 'через' in left and 'дн' in left, 'нет срока до выхода: ' + left
    print('плитка выхода:', pg.inner_text('#mDate'), '·', left)

    # отметка в документах долетает до плитки сразу
    pg.click('#docList .check[data-key="labor"]'); pg.wait_for_timeout(600)
    assert pg.inner_text('#hpDocs') == '3 из 4', 'плитка не обновилась: ' + pg.inner_text('#hpDocs')
    assert pg.inner_text('#hpDocs') == pg.inner_text('#docCount'), 'плитка разошлась с блоком после отметки'
    w = pg.evaluate("getComputedStyle(document.getElementById('hpDocsFill')).width")
    assert w != '0px', 'полоса в плитке осталась пустой'
    note = pg.inner_text('#hpDocsNote')
    print('после отметки: %s · %s · полоса %s' % (pg.inner_text('#hpDocs'), note, w))

    # собрали все обязательные — подпись меняется
    pg.click('#docList .check[data-key="inn"]'); pg.wait_for_timeout(600)
    assert pg.inner_text('#hpDocs') == '4 из 4', 'не все отметились: ' + pg.inner_text('#hpDocs')
    assert 'отправл' in pg.inner_text('#hpDocsNote'), 'подпись не позвала отправить список: ' + pg.inner_text('#hpDocsNote')
    print('всё собрано, подпись:', pg.inner_text('#hpDocsNote'))

    # плитки ведут в свои разделы
    hrefs = pg.eval_on_selector_all('.hero-prog a.hp', 'els => els.map(e => e.getAttribute("href"))')
    assert hrefs == ['#docs', '#plan'], 'плитки ведут не туда: %s' % hrefs
    pg.click('.hero-prog a.hp[href="#docs"]'); pg.wait_for_timeout(900)
    top = pg.evaluate("document.getElementById('docs').getBoundingClientRect().top")
    assert abs(top) < 120, 'плитка не прокрутила к документам: top=%s' % top
    print('плитка документов прокручивает к разделу')

    # блоки проявляются при прокрутке и остаются видимыми
    pg.evaluate("window.scrollTo(0, document.getElementById('team').offsetTop)"); pg.wait_for_timeout(900)
    op = pg.evaluate("getComputedStyle(document.querySelector('.team-grid')).opacity")
    assert float(op) > .95, 'блок команды не проявился: opacity=%s' % op
    print('появление блоков: команда видна (opacity %s)' % op)
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
