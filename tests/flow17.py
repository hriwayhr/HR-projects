# -*- coding: utf-8 -*-
# Вкладка «Шаблоны»: правка текста оффера и сообщений о стажировке,
# подстановки, необязательные куски в квадратных скобках, возврат исходных.
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
    pg.goto(url+'#admin'); pg.wait_for_timeout(800)

    # отделы: обычный и со стажировкой
    pg.click('#tabDepts')
    for name, head in [('Бухгалтерия','М. Соколова'), ('Отдел контроля','А. Петров')]:
        pg.click('#addDept'); pg.wait_for_timeout(200)
        row = pg.query_selector_all('#deptRows tr')[-1].query_selector_all('input')
        row[0].fill(name); row[1].fill(head)
    pg.check('[data-dept-intern="1"]')
    pg.click('#saveDepts'); pg.wait_for_timeout(500)

    # вкладка на месте, в полях — подсказка с исходным текстом
    pg.click('#tabTpl'); pg.wait_for_timeout(300)
    assert pg.is_visible('#paneTpl'), 'вкладка «Шаблоны» не открылась'
    assert not pg.is_visible('#panePage'), 'вкладка страницы осталась видимой'

    # шаблоны разложены по категориям: на экране только выбранная
    cats = pg.eval_on_selector_all('#tplStages .st', 'e => e.map(x => x.getAttribute("data-tpl-stage"))')
    assert cats == ['offer', 'intern'], 'категории шаблонов не те: %s' % cats
    assert pg.query_selector('[data-tpl="intern.first"]') is None, 'поля другой категории на экране'
    print('категории шаблонов:', ' · '.join(cats))
    # текущий текст лежит в самом поле — его правят с места, а не набирают заново
    cur = pg.input_value('[data-tpl="offer.body"]')
    assert 'Здравствуйте, {имя}!' in cur and 'Также мы гарантируем:' in cur, \
        'в поле нет текущего текста оффера:\n' + cur
    assert pg.input_value('[data-tpl="offer.subject"]').startswith('Оффер для {фамилия}'), \
        'в поле нет текущей темы письма'
    pg.click('#tplStages .st[data-tpl-stage="intern"]'); pg.wait_for_timeout(300)
    assert pg.input_value('[data-tpl="intern.second"]').startswith('Мы рады вашему положительному ответу!'), \
        'в поле нет текущего текста второго сообщения'
    pg.click('#tplStages .st[data-tpl-stage="offer"]'); pg.wait_for_timeout(300)
    print('вкладка «Шаблоны»: в полях текущий текст, готовый к правке')

    # правим шаблон оффера
    body = ('Здравствуйте, {имя}!\n\n'
            'Должность: {должность}[, руководитель {руководитель}].\n'
            'Испытательный срок: {испытательный срок}\n\n'
            'Условия:\n'
            '- зарплата {зарплата на испытательном};\n'
            '- график {график}.\n\n'
            'Теги <b>не работают</b>.')
    pg.fill('[data-tpl="offer.subject"]', 'Оффер {фамилия}[ — {должность}]')
    pg.fill('[data-tpl="offer.title"]', 'Наше предложение')
    pg.fill('[data-tpl="offer.body"]', body)
    pg.click('#tplStages .st[data-tpl-stage="intern"]'); pg.wait_for_timeout(300)
    pg.click('#tplStages .st[data-tpl-stage="offer"]'); pg.wait_for_timeout(300)
    assert pg.input_value('[data-tpl="offer.title"]') == 'Наше предложение', \
        'правка потерялась при переключении категории'
    pg.click('#saveTpl'); pg.wait_for_timeout(500)
    assert pg.is_visible('#tplSaved'), 'нет отметки о сохранении'
    saved = pg.evaluate("window.__store['config/templates'].tpl")
    assert saved['offer']['title'] == 'Наше предложение', 'шаблон не сохранился: %s' % saved
    print('шаблон оффера сохранён в базу')

    # письмо собирается по шаблону: испытательный срок не заполнен — строка выпадает
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','anna@example.com')
    pg.select_option('#fDept','Бухгалтерия'); pg.fill('#fDate','2026-10-05')
    pg.fill('#offerNew [data-offer="position"]', 'Бухгалтер')
    pg.fill('#offerNew [data-offer="head"]', 'Чернякова Марина')
    pg.fill('#offerNew [data-offer="payProbation"]', '65 000 рублей')
    pg.fill('#offerNew [data-offer="schedule"]', '5/2')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1300)
    assert pg.is_visible('#offerPanel'), 'панель оффера не открылась'

    doc = pg.frame_locator('#offerPreview').locator('body').inner_text()
    assert 'Наше предложение' in doc, 'заголовок из шаблона не подставился'
    assert 'Здравствуйте, Анна!' in doc, 'имя не подставилось'
    assert 'Должность: Бухгалтер, руководитель Чернякова Марина.' in doc, 'строка с подстановками собрана не так:\n' + doc
    assert 'Испытательный срок' not in doc, 'строка с пустым значением попала в письмо'
    assert 'зарплата 65 000 рублей;' in doc and 'график 5/2.' in doc, 'список из шаблона не собрался'
    assert '<b>не работают</b>' in doc, 'разметка из шаблона не экранирована'
    assert 'Также мы гарантируем' not in doc, 'в письме остался исходный текст, а не шаблон'
    subj = pg.get_attribute('#offerCopySubject', 'title')
    assert subj == 'Оффер Иванова — Бухгалтер', 'тема собрана не по шаблону: ' + subj
    print('оффер собран по шаблону, пустая подстановка убрала строку')

    # необязательный кусок исчезает, а строка остаётся
    pg.click('#tabTpl'); pg.wait_for_timeout(300)
    pg.click('#tplStages .st[data-tpl-stage="offer"]'); pg.wait_for_timeout(300)
    pg.fill('[data-tpl="offer.body"]', 'Должность: {должность}[, руководитель {руководитель}].')
    pg.fill('[data-tpl="offer.subject"]', 'Оффер {фамилия}[ — {несуществующее}]')
    pg.click('#saveTpl'); pg.wait_for_timeout(600)
    doc2 = pg.frame_locator('#offerPreview').locator('body').inner_text()
    assert 'Наше предложение' in doc2, 'правка шаблона не долетела в открытое письмо'
    pg.click('#tabNew'); pg.wait_for_timeout(200)
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    open_row(pg, 'Иванова').locator('.pr-body button', has_text='Оффер').click()
    pg.wait_for_timeout(800)
    assert pg.get_attribute('#offerCopySubject', 'title') == 'Оффер Иванова', 'необязательный кусок темы не исчез'
    print('необязательный кусок в скобках выпадает, строка остаётся')

    # шаблон стажировки
    pg.click('#tabTpl'); pg.wait_for_timeout(300)
    pg.click('#tplStages .st[data-tpl-stage="intern"]'); pg.wait_for_timeout(300)
    pg.fill('[data-tpl="intern.first"]', '{имя}, добрый день! Приглашаем на стажировку.')
    pg.fill('[data-tpl="intern.second"]', 'Ждём вас {дата выхода}[ в {время выхода}].\nЛогин: {логин}\nПароль: {пароль}')
    pg.click('#saveTpl'); pg.wait_for_timeout(500)
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    pg.fill('#fLast','Смирнова'); pg.fill('#fFirst','Ольга'); pg.fill('#fPersonal','olga@example.com')
    pg.select_option('#fDept','Отдел контроля'); pg.fill('#fDate','2026-10-05')   # время не указано
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1300)
    assert pg.is_visible('#chatPanel'), 'панель сообщений не открылась'
    assert pg.input_value('#chatMsg1') == 'Ольга, добрый день! Приглашаем на стажировку.', \
        'первое сообщение не из шаблона: ' + pg.input_value('#chatMsg1')
    m2 = pg.input_value('#chatMsg2')
    assert 'Ждём вас 5 октября.' in m2, 'без времени выхода потерялась дата:\n' + m2
    assert 'Пароль: ' in m2 and 'Логин: ' in m2, 'доступы не подставились:\n' + m2
    print('сообщения о стажировке собираются по шаблону')

    # возврат исходных
    pg.click('#tabTpl'); pg.wait_for_timeout(300)
    pg.click('#resetTpl'); pg.wait_for_timeout(400)
    pg.click('#dlgOk'); pg.wait_for_timeout(900)
    pg.click('#tplStages .st[data-tpl-stage="offer"]'); pg.wait_for_timeout(300)
    assert 'Также мы гарантируем:' in pg.input_value('[data-tpl="offer.body"]'), 'в поле не вернулся исходный текст'
    assert not (pg.evaluate("window.__store['config/templates'].tpl.offer") or {}).get('body'), 'шаблон не сброшен в базе'
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    open_row(pg, 'Иванова').locator('.pr-body button', has_text='Оффер').click()
    pg.wait_for_timeout(900)
    doc3 = pg.frame_locator('#offerPreview').locator('body').inner_text()
    assert 'Предложение о работе' in doc3 and 'Также мы гарантируем' in doc3, 'исходный текст оффера не вернулся'
    print('кнопка «Вернуть исходные» возвращает текст письма')

    # шаблон, сохранённый в базе, подхватывается при загрузке
    pg2 = b.new_page(viewport={'width':1280,'height':1000})
    pg2.on('pageerror', lambda e: errs.append(str(e)))
    pg2.add_init_script(path=base+'mockdb.js')
    pg2.add_init_script("""
      window.__store['config/departments'] = {list:[{name:'Бухгалтерия', head:'М. Соколова'}]};
      window.__store['config/templates'] = {tpl:{offer:{title:'Из базы', body:'Привет, {имя}!'}}};
      window.__store['employees/IW-9'] = {code:'IW-9', firstName:'Пётр', lastName:'Петров',
        dept:'Бухгалтерия', personalEmail:'p@example.com', offer:{position:'Бухгалтер'}};
    """)
    pg2.goto(url+'#admin'); pg2.wait_for_timeout(1000)
    pg2.click('#tabPeople'); pg2.wait_for_timeout(500)
    open_row(pg2, 'Петров').locator('.pr-body button', has_text='Оффер').click()
    pg2.wait_for_timeout(900)
    doc4 = pg2.frame_locator('#offerPreview').locator('body').inner_text()
    assert 'Из базы' in doc4 and 'Привет, Пётр!' in doc4, 'шаблон из базы не применился:\n' + doc4
    print('шаблон читается из базы при загрузке')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
