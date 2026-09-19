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
def emp(code, first, last, gender, **kw):
    r={'code':code,'login':code.lower(),'firstName':first,'lastName':last,'gender':gender,'dept':'Операционный отдел',
       'email':'','personalEmail':'x@ex.com','startDate':'2026-10-05','startTime':'10:00','createdAt':'2026-09-18',
       'openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}}
    r.update(kw); return r
seed={
 'employees/IW-1': emp('IW-1','Кристина','Тестовая','f', sentAt=''),
 'employees/IW-2': emp('IW-2','Пётр','Петров','m', sentAt='2026-09-19T08:00:00Z', startDate='2026-09-30'),
 'employees/IW-3': emp('IW-3','Анна','Иванова','f', sentAt='2026-09-18T08:00:00Z', openedAt='2026-09-19T09:00:00Z',
                       progress={'passport':1,'snils':1}, cardChoice='need', email='a.ivanova@iway.ru', startDate='2026-10-12'),
 'employees/IW-4': emp('IW-4','Олег','Смирнов','m', sentAt='2026-09-17T08:00:00Z', openedAt='2026-09-18T09:00:00Z',
                       progress={'passport':1,'snils':1,'military':1,'labor':1,'inn':1}, cardChoice='have',
                       demoPass='тест', startDate='2026-09-28'),
 'config/departments':{'list':[{'name':'Операционный отдел','head':'','senior':'','chat':''},{'name':'Маркетинг','head':'','senior':'','chat':''}]}}
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1100}, device_scale_factor=2)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url+'#admin'); pg.wait_for_timeout(1300)
    pg.click('#tabPeople'); pg.wait_for_timeout(300)   # список — на своей вкладке
    print('фильтры:', pg.inner_text('#peopleFilters').replace('\n',' | '))
    print('карточек:', len(pg.query_selector_all('.pcard')))
    # фильтр «Готовы к выходу»
    pg.get_by_role('button', name='Собраны, ждут отправки 1').click(); pg.wait_for_timeout(400)
    print('после фильтра готовых:', [c.query_selector('.pc-name').inner_text() for c in pg.query_selector_all('.pcard')])
    pg.get_by_role('button', name='Все 4').click(); pg.wait_for_timeout(300)
    # поиск
    pg.fill('#peopleSearch','пётр'); pg.wait_for_timeout(400)
    print('поиск «пётр»:', [c.query_selector('.pc-name').inner_text() for c in pg.query_selector_all('.pcard')])
    pg.fill('#peopleSearch',''); pg.wait_for_timeout(300)
    box = pg.query_selector('#peopleFilters').bounding_box()
    pg.screenshot(path=base+'shots/panel.png', clip={'x':120,'y':box['y']-70,'width':1060,'height':620})
    # окно настроек
    pg.query_selector_all('.pcard')[0].get_by_role = None
    pg.locator('.pcard').first.locator('button', has_text='Настроить').click(); pg.wait_for_timeout(500)
    print('окно настроек:', pg.inner_text('#editTitle'), '|', pg.inner_text('#editSub'))
    pg.fill('#eTime','09:30'); pg.select_option('#eGender','m'); pg.click('#editSave'); pg.wait_for_timeout(700)
    rec = pg.evaluate("window.__store['employees/IW-1']")
    print('сохранено:', rec['startTime'], rec['gender'])
    pg.screenshot(path=base+'shots/panel2.png', clip={'x':120,'y':box['y']-70,'width':1060,'height':500})
    b.close()
print('ОШИБКИ:', errs or 'нет')
