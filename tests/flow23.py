# -*- coding: utf-8 -*-
# Список «Выданные доступы» — строки, а не плитки: колонки, свёрнутые
# подробности, раскрытие по клику и память о раскрытых строках.
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

def rec(code, first, last, gender='f', **kw):
    r={'code':code,'login':code.lower(),'firstName':first,'lastName':last,'gender':gender,
       'dept':'Операционный отдел','email':'','personalEmail':first.lower()+'@ex.com',
       'startDate':'2026-10-05','startTime':'10:00','createdAt':'2026-09-18','openedAt':'','sentAt':'',
       'salt':salt,'hash':h,'progress':{}}
    r.update(kw); return r

def cand(code, first, last, **kw):
    r=rec(code, first, last, **kw); r['hash']=''; r['salt']=''; r['login']=''; return r

seed={
 'employees/IW-C1': cand('IW-C1','Мария','Зотова', offerSentAt='2026-09-19T10:00:00Z', offerReply='yes'),
 'employees/IW-1': rec('IW-1','Кристина','Белова'),
 'employees/IW-2': rec('IW-2','Анна','Иванова', sentAt='2026-09-18T08:00:00Z', openedAt='2026-09-19T09:00:00Z',
                       progress={'passport':1}, cardChoice='need'),
 'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]

def rows(pg):
    return pg.eval_on_selector_all('.prow', """els => els.map(e => ({
      code: e.getAttribute('data-code'),
      who: e.querySelector('.pr-who').textContent,
      id: e.querySelector('.pr-id').textContent,
      dept: e.querySelector('.pr-dept').textContent,
      date: e.querySelector('.pr-date').textContent,
      docs: e.querySelector('.pr-prog').textContent,
      status: e.querySelector('.pr-status .chip').textContent,
      open: e.classList.contains('open'),
      expanded: e.querySelector('.pr-head').getAttribute('aria-expanded'),
      bodyHidden: e.querySelector('.pr-body').hidden
    }))""")

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000}, device_scale_factor=2)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    pg.click('#tabPeople'); pg.wait_for_timeout(400)

    # ——— шапка колонок и по строке на человека
    caps = pg.eval_on_selector_all('.pl-cap span', 'els => els.map(e => e.textContent).filter(Boolean)')
    assert caps == ['Сотрудник','Отдел','Выход','Документы','Статус'], caps
    r = rows(pg)
    assert len(r) == 3, r
    print('колонки:', ' · '.join(caps), '| строк:', len(r))

    # ——— в шапке строки всё для просмотра сверху вниз
    anna = [x for x in r if x['who'] == 'Иванова Анна'][0]
    assert anna['id'].startswith('iw-2') and 'нужна карта' in anna['id'], anna['id']
    assert anna['dept'] == 'Операционный отдел' and '05.10.2026' in anna['date'] and '10:00' in anna['date'], anna
    assert '1 из 4' in anna['docs'] and anna['status'] == 'собирает документы', anna
    maria = [x for x in r if x['who'] == 'Зотова Мария'][0]
    assert maria['id'] == 'кандидат' and maria['docs'] == 'нет доступа', maria
    print('строка:', anna['who'], '·', anna['dept'], '·', anna['docs'].replace('\n',' '), '·', anna['status'])

    # ——— свёрнуто по умолчанию, кнопок не видно
    assert all(x['bodyHidden'] and x['expanded'] == 'false' for x in r), r
    assert not pg.locator('.pr-body button').first.is_visible()
    heights = pg.eval_on_selector_all('.pr-head', 'els => els.map(e => Math.round(e.getBoundingClientRect().height))')
    assert max(heights) <= 80, heights
    print('свёрнуто: строки по', min(heights), '—', max(heights), 'px, кнопок не видно')

    # ——— раскрытие
    pg.locator('.prow', has_text='Иванова').locator('.pr-head').click(); pg.wait_for_timeout(300)
    anna = [x for x in rows(pg) if x['who'] == 'Иванова Анна'][0]
    assert anna['open'] and anna['expanded'] == 'true' and not anna['bodyHidden'], anna
    assert pg.locator('.prow', has_text='Иванова').locator('.pr-body button', has_text='Настроить').is_visible()
    others = [x for x in rows(pg) if x['who'] != 'Иванова Анна']
    assert all(x['bodyHidden'] for x in others), 'раскрылись чужие строки'
    print('раскрыто: подробности и кнопки только у одной строки')

    # ——— живое обновление базы не схлопывает раскрытую строку
    pg.evaluate("""() => {
      const r = window.__store['employees/IW-2'];
      r.progress = {passport:1, snils:1};
      window.__notify();
    }""")
    pg.wait_for_timeout(700)
    anna = [x for x in rows(pg) if x['who'] == 'Иванова Анна'][0]
    assert not anna['bodyHidden'], 'строка схлопнулась при обновлении списка'
    assert '2 из 4' in anna['docs'], anna['docs']
    print('после обновления базы:', anna['docs'].replace('\n',' '), '| строка осталась раскрытой')

    # ——— повторный клик сворачивает
    pg.locator('.prow', has_text='Иванова').locator('.pr-head').click(); pg.wait_for_timeout(300)
    assert all(x['bodyHidden'] for x in rows(pg)), 'строка не свернулась'
    print('повторный клик сворачивает')

    # ——— пустой этап: рамка со шапкой не висит без строк
    pg.click('#peopleFilters [data-filter="sent"]'); pg.wait_for_timeout(400)
    assert pg.is_hidden('#peopleList') and not pg.is_hidden('#peopleEmpty')
    pg.click('#peopleFilters [data-filter="all"]'); pg.wait_for_timeout(400)
    assert not pg.is_hidden('#peopleList')
    print('пустой этап: списка нет, подпись есть')

    pg.screenshot(path=base+'shots/people-list.png', clip={'x':600,'y':420,'width':1140,'height':460})

    # ——— телефон: строка складывается, страница не едет вбок
    pg.set_viewport_size({'width':430,'height':900}); pg.wait_for_timeout(500)
    over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert over <= 0, over
    assert len(pg.query_selector_all('.prow')) == 3
    assert pg.eval_on_selector('.pl-cap', "e => getComputedStyle(e).display") == 'none', 'шапка колонок на телефоне'
    print('телефон: страница не едет вбок, шапка колонок скрыта')
    b.close()
print('ОШИБКИ:', errs or 'нет')
