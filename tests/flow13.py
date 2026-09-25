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
def open_row(pg, text=''):
    """строка списка сворачивается — раскрываем перед работой с подробностями"""
    r = pg.locator('.prow', has_text=text).first if text else pg.locator('.prow').first
    if r.locator('.pr-head').get_attribute('aria-expanded') != 'true':
        r.locator('.pr-head').click(); pg.wait_for_timeout(300)
    return r

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.goto(url+'#admin'); pg.wait_for_timeout(700)

    # порядок вкладок в шапке — как договорено с HR
    order = pg.eval_on_selector_all('#viewAdmin .tabs .tab', 'els => els.map(e => e.id)')
    want = ['tabNew', 'tabPeople', 'tabAdmins', 'tabDepts', 'tabTpl', 'tabPage']
    assert order == want, 'порядок вкладок не тот: %s' % order
    print('порядок вкладок:', ' · '.join(pg.eval_on_selector_all('#viewAdmin .tabs .tab', 'els => els.map(e => e.textContent)')))

    # имя и «Выйти» — в правом верхнем углу, отдельной строкой над вкладками.
    # Широкий экран: только на нём вкладки уместились бы в первую строку рядом
    # с именем, поэтому проверяем именно здесь.
    pg.set_viewport_size({'width': 1900, 'height': 1000}); pg.wait_for_timeout(200)
    pos = pg.evaluate("""() => {
      const bar = document.querySelector('#viewAdmin .admin-bar').getBoundingClientRect();
      const who = document.querySelector('#viewAdmin .who').getBoundingClientRect();
      const tabs = document.querySelector('#viewAdmin .tabs').getBoundingClientRect();
      return {gap: bar.right - who.right, above: tabs.top - who.bottom};
    }""")
    assert pos['gap'] <= 2, 'имя не прижато к правому краю шапки: %s' % pos
    assert pos['above'] >= 0, 'имя не над вкладками, а в одной строке с ними: %s' % pos
    print('шапка: имя и «Выйти» в правом верхнем углу')
    pg.set_viewport_size({'width': 1280, 'height': 1000}); pg.wait_for_timeout(200)

    # первая вкладка открыта по умолчанию
    assert pg.is_visible('#newForm'), 'по умолчанию открыта не вкладка «Новый доступ»'
    assert not pg.is_visible('#peopleSearch'), 'список виден на вкладке создания'
    print('по умолчанию открыт «Новый доступ»')

    pg.click('#tabAdmins'); pg.fill('#aName','Юля'); pg.fill('#aMail','ny@iway.ru')
    pg.click('#adminForm button[type=submit]'); pg.wait_for_timeout(500)
    pg.click('#tabDepts'); pg.click('#addDept'); pg.wait_for_timeout(200)
    ins=pg.query_selector_all('#deptRows tr td input'); ins[0].fill('Клиентский сервис'); ins[1].fill('М. Соколова')
    pg.click('#saveDepts'); pg.wait_for_timeout(400)

    pg.click('#tabPeople'); pg.wait_for_timeout(300)
    assert pg.is_visible('#peopleSearch'), 'список доступов не показан'
    assert not pg.is_visible('#newForm'), 'форма создания висит на вкладке со списком'
    print('вкладка «Выданные доступы»: список есть, формы создания нет')

    pg.click('#tabNew'); pg.wait_for_timeout(300)
    assert pg.is_visible('#newForm'), 'форма создания не показана'
    assert not pg.is_visible('#peopleSearch'), 'список висит на вкладке создания'
    print('вкладка «Новый доступ»: форма есть, списка нет')

    # создаём доступ — письмо открывается здесь же
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','a@ex.com')
    pg.select_option('#fDept','Клиентский сервис'); pg.fill('#fDate','2026-10-05')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1000)
    assert pg.is_visible('#mailPanel'), 'после создания письмо не показано'
    print('письмо собрано после создания:', pg.inner_text('#issuedCode'))

    # пароль одноразовый: смена вкладки не должна его терять
    pass1 = pg.inner_text('#issuedCode')
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    assert pg.is_visible('#mailPanel'), 'смена вкладки спрятала письмо с одноразовым паролем'
    print('письмо уцелело при переходе на другую вкладку')

    # на справочниках письма нет, но оно не потеряно: возврат его возвращает
    for tab in ['tabAdmins', 'tabDepts', 'tabTpl', 'tabPage']:
        pg.click('#' + tab); pg.wait_for_timeout(300)
        assert not pg.is_visible('#mailPanel'), 'письмо висит на вкладке ' + tab
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    assert pg.is_visible('#mailPanel'), 'письмо не вернулось на вкладку с доступами'
    assert pg.inner_text('#issuedCode') == pass1, 'пароль в письме подменился: %s / %s' % (pg.inner_text('#issuedCode'), pass1)
    print('на справочниках письма нет, пароль цел:', pass1)

    # закрытие неотправленного письма спрашивает подтверждение
    pg.click('#mailClose'); pg.wait_for_timeout(400)
    assert pg.is_visible('#dlgTitle'), 'закрытие неотправленного письма не спросило'
    print('закрытие спрашивает:', pg.inner_text('#dlgTitle'))
    pg.click('#dlgCancel'); pg.wait_for_timeout(400)
    assert pg.is_visible('#mailPanel'), 'отмена всё равно закрыла письмо'
    pg.click('#mailClose'); pg.wait_for_timeout(400)
    pg.click('#dlgOk'); pg.wait_for_timeout(400)
    assert not pg.is_visible('#mailPanel'), 'письмо не закрылось по подтверждению'
    print('письмо закрывается по подтверждению, отмена его сохраняет')

    # письмо из карточки в списке — панель общая, иначе была бы невидима
    open_row(pg).locator('.pr-body button', has_text='Письмо').click(); pg.wait_for_timeout(900)
    assert pg.is_visible('#mailPanel'), 'письмо из карточки не показано на вкладке со списком'
    print('письмо открывается из карточки:', pg.inner_text('#mailTo')[:42])

    # отмеченное отправленным закрывается без вопроса — терять нечего
    pg.click('#mailSent'); pg.wait_for_timeout(700)
    pg.click('#mailClose'); pg.wait_for_timeout(400)
    assert not pg.is_visible('#dlgTitle'), 'у отправленного письма лишний вопрос при закрытии'
    assert not pg.is_visible('#mailPanel'), 'отправленное письмо не закрылось'
    print('отправленное письмо закрывается сразу')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
