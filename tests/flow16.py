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
    pg.goto(url+'#admin'); pg.wait_for_timeout(800)

    # два отдела: обычный и со стажировкой
    pg.click('#tabDepts')
    for name, head in [('Клиентский сервис','М. Соколова'), ('Отдел контроля','А. Петров')]:
        pg.click('#addDept'); pg.wait_for_timeout(200)
        ins = pg.query_selector_all('#deptRows tr td input[type=text], #deptRows tr td input:not([type])')
        row = pg.query_selector_all('#deptRows tr')[-1].query_selector_all('input')
        row[0].fill(name); row[1].fill(head)
    pg.check('[data-dept-intern="1"]')          # стажировка только у второго
    pg.click('#saveDepts'); pg.wait_for_timeout(500)
    assert pg.evaluate("window.__store['config/departments'].list[1].intern") is True, 'флажок стажировки не сохранился'
    print('справочник: отдел со стажировкой отмечен')

    # обычный отдел — оффер на месте
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    pg.select_option('#fDept','Клиентский сервис'); pg.wait_for_timeout(300)
    assert pg.is_visible('#offerBlock'), 'у обычного отдела нет блока оффера'
    assert not pg.is_visible('#offerSkip'), 'у обычного отдела лишняя оговорка про чат'

    # отдел со стажировкой — оффера нет
    pg.select_option('#fDept','Отдел контроля'); pg.wait_for_timeout(300)
    assert not pg.is_visible('#offerBlock'), 'у стажировки остался блок оффера'
    assert pg.is_visible('#offerSkip'), 'нет оговорки, что оффер не отправляется'
    print('в форме: для стажировки блок оффера скрыт')

    pg.fill('#fLast','Смирнова'); pg.fill('#fFirst','Ольга'); pg.fill('#fPersonal','olga@example.com')
    pg.fill('#fDate','2026-10-05'); pg.fill('#fTime','10:00')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1300)

    assert pg.is_visible('#chatPanel'), 'панель сообщений не открылась'
    assert not pg.is_visible('#mailPanel'), 'для стажировки открылось письмо'
    assert not pg.is_visible('#offerPanel'), 'для стажировки открылся оффер'
    print('после создания: только сообщения для чата')

    m1 = pg.input_value('#chatMsg1')
    want1 = ('Ольга, здравствуйте!\n\n'
             'Рады сообщить: по итогам собеседования мы приглашаем вас на стажировку.\n'
             'Готовы ли вы приступить?')
    assert m1 == want1, 'первое сообщение не то:\n' + m1
    print('сообщение 1 совпадает дословно')

    code_pass = pg.inner_text('#issuedCode')
    pas = code_pass.split('·')[-1].strip()
    m2 = pg.input_value('#chatMsg2')
    for must in ['Мы рады вашему положительному ответу!', 'Ждём вас 5 октября в 10:00.',
                 'Если появятся вопросы, остаемся на связи.', '#code=', 'Логин: ', 'Пароль: ' + pas]:
        assert must in m2, 'во втором сообщении нет: ' + must + '\n---\n' + m2
    assert m2.index('Ждём вас') < m2.index('Доступы к странице'), 'доступы идут раньше деталей выхода'
    print('сообщение 2: детали выхода и доступы на месте')

    # отметка об отправке — тот же признак, что у письма
    pg.click('#chatSent'); pg.wait_for_timeout(700)
    assert 'Отправлено' in pg.inner_text('#chatSent'), 'отметка не встала'
    assert pg.evaluate("!!Object.values(window.__store).find(v => v.code)?.sentAt"), 'sentAt не сохранился'
    pg.click('#tabPeople'); pg.wait_for_timeout(500)
    card = pg.inner_text('.pcard')
    assert 'Оффер' not in card, 'в карточке стажировки осталась строка про оффер'
    assert 'отправлено' in card, 'карточка не показала отправку'
    print('карточка: без оффера, отправка отмечена')

    btn = pg.locator('.pcard').first.locator('button', has_text='Сообщения')
    assert btn.count() == 1, 'в карточке нет кнопки «Сообщения»'
    btn.click(); pg.wait_for_timeout(900)
    assert pg.is_visible('#chatPanel'), 'сообщения не открылись из карточки'
    new_pass = pg.input_value('#chatMsg2').split('Пароль: ')[-1].strip()
    assert new_pass and new_pass != pas, 'при повторном открытии пароль не перевыпущен'
    print('повторное открытие выпускает новый пароль')

    pg.click('#chatClose'); pg.wait_for_timeout(300)
    assert not pg.is_visible('#chatPanel'), 'панель не закрылась'
    print('панель закрывается')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
