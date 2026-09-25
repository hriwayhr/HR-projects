# -*- coding: utf-8 -*-
# Этапы списка «Выданные доступы» — панель слева: все этапы видны сразу,
# у каждого счётчик людей; поиск сужает список, но не счётчики.
from playwright.sync_api import sync_playwright
import pathlib, hashlib, json
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / 'shots').mkdir(exist_ok=True)
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()

def rec(code, first, last, gender='f', **kw):
    r={'code':code,'login':code.lower(),'firstName':first,'lastName':last,'gender':gender,
       'dept':'Операционный отдел','email':'','personalEmail':first.lower()+'@ex.com',
       'startDate':'2026-10-05','startTime':'10:00','createdAt':'2026-09-18',
       'openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}}
    r.update(kw); return r

def cand(code, first, last, **kw):
    r = rec(code, first, last, **kw)
    r['hash']=''; r['salt']=''; r['login']=''      # без пароля — это кандидат, войти нельзя
    return r

seed={
 # кандидаты: четыре этапа до создания доступа
 'employees/IW-C1': cand('IW-C1','Дарья','Черновик', offerSentAt='', offerReply=''),
 'employees/IW-C2': cand('IW-C2','Егор','Ждущий', gender='m', offerSentAt='2026-09-20T10:00:00Z', offerReply=''),
 'employees/IW-C3': cand('IW-C3','Мария','Принявшая', offerSentAt='2026-09-19T10:00:00Z', offerReply='yes'),
 'employees/IW-C4': cand('IW-C4','Игорь','Отказавшийся', gender='m', offerSentAt='2026-09-18T10:00:00Z', offerReply='no'),
 # сотрудники с доступом
 'employees/IW-1': rec('IW-1','Кристина','Письмова'),
 'employees/IW-2': rec('IW-2','Пётр','Незашедший', gender='m', sentAt='2026-09-19T08:00:00Z'),
 'employees/IW-3': rec('IW-3','Анна','Собирает', sentAt='2026-09-18T08:00:00Z', openedAt='2026-09-19T09:00:00Z',
                       progress={'passport':1}, cardChoice='need'),
 'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]

def rail(pg):
    return pg.eval_on_selector_all('#peopleFilters .st', """els => els.map(e => ({
      key: e.getAttribute('data-filter'),
      title: e.querySelector('.st-t').textContent,
      count: e.querySelector('.st-s').textContent,
      current: e.getAttribute('aria-current'),
      dim: e.classList.contains('dim')
    }))""")

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1100}, device_scale_factor=2)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    pg.click('#tabPeople'); pg.wait_for_timeout(400)

    # ——— состав панели: группы и все этапы, включая пустые
    caps = pg.eval_on_selector_all('#peopleFilters .st-cap', 'els => els.map(e => e.textContent)')
    assert caps == ['Кандидаты','Сотрудники','Отметки'], caps
    items = rail(pg)
    keys = [i['key'] for i in items]
    assert keys == ['all','draft','offered','accepted','declined',
                    'tosend','waiting','collecting','ready','sent','card'], keys
    print('панель этапов:', ' · '.join(i['title'] for i in items))

    # ——— счётчики по этапам
    got = {i['key']: i['count'] for i in items}
    want = {'all':'7 человек','draft':'1 человек','offered':'1 человек','accepted':'1 человек',
            'declined':'1 человек','tosend':'1 человек','waiting':'1 человек','collecting':'1 человек',
            'ready':'0 человек','sent':'0 человек','card':'1 человек'}
    assert got == want, got
    print('счётчики:', ', '.join(i['title'] + ' — ' + i['count'] for i in items if i['key'] != 'all'))

    # пустые этапы остаются в панели и приглушены
    assert [i['key'] for i in items if i['dim']] == ['ready','sent'], [i['key'] for i in items if i['dim']]
    assert [i['key'] for i in items if i['current']=='true'] == ['all']

    # ——— переход по этапам
    pg.click('#peopleFilters [data-filter="accepted"]'); pg.wait_for_timeout(300)
    names = [c.query_selector('.pr-who').inner_text() for c in pg.query_selector_all('.prow')]
    assert names == ['Принявшая Мария'], names
    cur = [i['key'] for i in rail(pg) if i['current']=='true']
    assert cur == ['accepted'], cur
    print('этап «Оффер принят»:', names[0], '| отмечен в панели')

    pg.click('#peopleFilters [data-filter="sent"]'); pg.wait_for_timeout(300)
    assert not pg.query_selector_all('.prow')
    assert not pg.is_hidden('#peopleEmpty'), 'пустой этап без подписи'
    print('пустой этап:', pg.inner_text('#peopleEmpty'))

    # ——— поиск сужает список, но не счётчики
    pg.click('#peopleFilters [data-filter="all"]'); pg.wait_for_timeout(300)
    pg.fill('#peopleSearch','егор'); pg.wait_for_timeout(400)
    names = [c.query_selector('.pr-who').inner_text() for c in pg.query_selector_all('.prow')]
    assert names == ['Ждущий Егор'], names
    assert {i['key']: i['count'] for i in rail(pg)} == want, 'поиск сдвинул счётчики'
    print('поиск «егор»:', names[0], '| счётчики не изменились')
    pg.fill('#peopleSearch',''); pg.wait_for_timeout(300)

    # ——— раскладка: панель слева от карточек, кнопка не мельче 44 px
    box = pg.query_selector('#peopleFilters').bounding_box()
    grid = pg.query_selector('#peopleList').bounding_box()
    assert box['x'] + box['width'] <= grid['x'] + 1, (box, grid)
    hgt = pg.query_selector('#peopleFilters .st').bounding_box()['height']
    assert hgt >= 44, hgt
    print('панель слева от карточек, кнопка %d px' % hgt)
    pg.screenshot(path=base+'shots/people-rail.png', clip={'x':100,'y':box['y']-90,'width':1090,'height':700})

    # ——— телефон: этапы лентой, страница не едет вбок
    pg.set_viewport_size({'width':430,'height':900}); pg.wait_for_timeout(500)
    over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    flow = pg.eval_on_selector('#peopleFilters .st-list', "e => getComputedStyle(e).flexDirection")
    assert over <= 0 and flow == 'row', (over, flow)
    print('телефон: этапы лентой, страница не едет вбок')
    pg.screenshot(path=base+'shots/people-rail-phone.png', full_page=False)
    b.close()
print('ОШИБКИ:', errs or 'нет')
