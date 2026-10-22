# -*- coding: utf-8 -*-
# Корпоративный портал: один вход на всех, разделы по уровню доступа,
# HR-метрики — только у HR.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib
from datetime import date, timedelta
def day(n):
    """дата относительно сегодня: иначе тесты протухают, когда жёстко
    зашитый «день выхода» уезжает в прошлое и кабинет открывает другой этап"""
    return (date.today() + timedelta(days=n)).isoformat()
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
(HERE / 'shots').mkdir(exist_ok=True)
base = str(HERE) + '/'
html = pathlib.Path(str(ROOT / 'src' / 'iway-portal.html')).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'

def pw(salt, p): return hashlib.sha256((salt + '::' + p).encode('utf-8')).hexdigest()
salt='s1'
seed={
 'admins/hr@iway.ru': {'email':'hr@iway.ru','name':'Юлия Немчинова','role':'Руководитель HR',
                       'salt':salt,'hash':pw(salt,'029750'),'createdAt':'2026-09-18T00:00:00.000Z'},
 'employees/IW-N1': {'code':'IW-N1','login':'iw-n1','firstName':'Дарья','lastName':'Ковалёва','gender':'f',
                     'dept':'Операционный отдел','email':'','personalEmail':'d@ex.com','startDate':day(11),
                     'startTime':'10:00','createdAt':'2026-10-01','openedAt':'','sentAt':'',
                     'salt':salt,'hash':pw(salt,'novichok'),'progress':{}},
 'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''}]}}
errs=[]

def login(pg, who, secret):
    pg.goto(url+'#exit'); pg.wait_for_timeout(500)
    pg.fill('#gateLogin', who); pg.fill('#gatePass', secret)
    pg.click('#gateForm button'); pg.wait_for_timeout(1500)

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000}, device_scale_factor=2)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')

    # ——— вход один на всех: вкладок «Сотрудник / HR» больше нет
    pg.goto(url); pg.wait_for_timeout(1200)
    assert pg.is_visible('#viewGate'), 'вход не показан'
    assert not pg.query_selector('#tabEmp') and not pg.query_selector('#tabHr'), 'остались вкладки входа'
    assert 'портал' in pg.inner_text('#gateTitle').lower(), pg.inner_text('#gateTitle')
    print('вход:', pg.inner_text('#gateTitle'), '| поле:', pg.inner_text('#gateLoginLabel'))

    # ——— HR попадает на экран разделов
    login(pg, 'hr@iway.ru', '029750')
    assert pg.is_visible('#viewHome'), 'HR не попал на разделы: ' + pg.inner_text('#gateErr')
    cards = pg.eval_on_selector_all('#homeGrid .hub-card', """els => els.map(e => ({
      key: e.getAttribute('data-section'),
      title: e.querySelector('.hub-t').textContent,
      href: e.getAttribute('href') || '',
      tag: e.tagName.toLowerCase()
    }))""")
    assert [c['key'] for c in cards] == ['pre','metrics'], cards
    assert 'claude.ai/artifact' in cards[1]['href'] and cards[1]['tag'] == 'a', cards[1]
    assert 'HR' in pg.inner_text('#homeWho') and 'Юлия' in pg.inner_text('#homeWho'), pg.inner_text('#homeWho')
    print('разделы HR:', ' · '.join(c['title'] for c in cards), '| кто:', pg.inner_text('#homeWho'))

    # ——— из разделов в панель HR и обратно
    pg.click('#homeGrid [data-section="pre"]'); pg.wait_for_timeout(700)
    assert pg.is_visible('#viewAdmin') and pg.is_visible('#hrBack'), 'панель HR не открылась'
    pg.click('#hrBack'); pg.wait_for_timeout(700)
    assert pg.is_visible('#viewHome'), 'из панели нет возврата к разделам'
    print('переход в панель HR и обратно работает')

    # ——— новичок: сразу своя страница, разделов и метрик не видит
    login(pg, 'iw-n1', 'novichok')
    assert pg.is_visible('#viewEmployee'), 'новичок не попал в кабинет: ' + pg.inner_text('#gateErr')
    assert pg.is_hidden('#viewHome')
    text = pg.inner_text('#viewEmployee').lower()
    assert 'метрик' not in text, 'в кабинете новичка упомянуты метрики'
    # прямой заход на #home и #admin ничего не открывает
    pg.goto(url+'#home'); pg.wait_for_timeout(1200)
    assert pg.is_visible('#viewEmployee') and pg.is_hidden('#viewHome'), 'новичку показали разделы'
    pg.goto(url+'#admin'); pg.wait_for_timeout(1200)
    assert pg.is_hidden('#viewAdmin'), 'новичок попал в панель HR'
    assert pg.is_visible('#viewGate') and 'только HR' in pg.inner_text('#gateErr'), pg.inner_text('#gateErr')
    print('новичок:', 'кабинет открыт, разделы и панель HR закрыты')

    # ——— чужой пароль не пускает
    login(pg, 'hr@iway.ru', '029751')
    assert pg.is_visible('#viewGate') and pg.is_hidden('#viewHome'), 'пустило с чужим паролем'
    print('чужой пароль:', pg.inner_text('#gateErr'))

    login(pg, 'hr@iway.ru', '029750')
    pg.screenshot(path=base+'shots/portal-home.png')
    b.close()
print('ОШИБКИ:', errs or 'нет')
