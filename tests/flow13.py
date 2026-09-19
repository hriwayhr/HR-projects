from playwright.sync_api import sync_playwright
import pathlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.goto(url+'#admin'); pg.wait_for_timeout(700)
    pg.click('#tabAdmins'); pg.fill('#aName','Юля'); pg.fill('#aMail','ny@iway.ru')
    pg.click('#adminForm button[type=submit]'); pg.wait_for_timeout(500)
    pg.click('#tabDepts'); pg.click('#addDept'); pg.wait_for_timeout(200)
    ins=pg.query_selector_all('#deptRows tr td input'); ins[0].fill('Клиентский сервис'); ins[1].fill('М. Соколова')
    pg.click('#saveDepts'); pg.wait_for_timeout(400)

    # по умолчанию открыт список, формы создания не видно
    pg.click('#tabPeople'); pg.wait_for_timeout(300)
    assert pg.is_visible('#peopleSearch'), 'список доступов не показан'
    assert not pg.is_visible('#newForm'), 'форма создания висит на вкладке со списком'
    print('вкладка «Выданные доступы»: список есть, формы создания нет')

    # на своей вкладке — наоборот
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    assert pg.is_visible('#newForm'), 'форма создания не показана'
    assert not pg.is_visible('#peopleSearch'), 'список висит на вкладке создания'
    print('вкладка «Новый доступ»: форма есть, списка нет')

    # создаём доступ — письмо открывается здесь же
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','a@ex.com')
    pg.select_option('#fDept','Клиентский сервис'); pg.fill('#fDate','2026-10-05')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1000)
    assert pg.is_visible('#mailPanel'), 'после создания письмо не показано'
    pass1 = pg.inner_text('#issuedCode')
    print('письмо собрано после создания:', pass1)

    # пароль одноразовый: смена вкладки не должна его терять
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    assert pg.is_visible('#mailPanel'), 'смена вкладки спрятала письмо с одноразовым паролем'
    print('письмо уцелело при переходе на другую вкладку')

    # письмо из карточки в списке — панель общая, иначе была бы невидима
    pg.locator('.pcard').first.locator('button', has_text='Письмо').click(); pg.wait_for_timeout(900)
    assert pg.is_visible('#mailPanel'), 'письмо из карточки не показано на вкладке со списком'
    print('письмо открывается из карточки:', pg.inner_text('#mailTo')[:42])
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
