# -*- coding: utf-8 -*-
# Оффер и приглашение — до создания доступа: письмо собирается из формы,
# карточка при этом не создаётся, пароль не выпускается.
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

def cards(pg):
    # считаем любые записи сотрудников, включая employees/undefined: черновик
    # без кода сохранился бы именно туда
    return pg.evaluate("Object.keys(window.__store).filter(k => k.indexOf('employees/') === 0).length")

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.goto(url+'#admin'); pg.wait_for_timeout(800)

    # справочник: обычный отдел и отдел со стажировкой
    pg.click('#tabDepts')
    for name, head in [('Бухгалтерия','М. Соколова'), ('Отдел контроля','А. Петров')]:
        pg.click('#addDept'); pg.wait_for_timeout(200)
        row = pg.query_selector_all('#deptRows tr')[-1].query_selector_all('input')
        row[0].fill(name); row[1].fill(head)
    pg.check('[data-dept-intern="1"]')
    pg.click('#saveDepts'); pg.wait_for_timeout(500)

    # ——— оффер без карточки
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    pg.select_option('#fDept','Бухгалтерия'); pg.wait_for_timeout(300)
    assert pg.is_visible('#offerDraft'), 'нет кнопки «Собрать оффер»'

    pg.click('#offerDraft'); pg.wait_for_timeout(500)
    assert pg.is_visible('#dlgTitle'), 'без имени и фамилии оффер собрался'
    print('без имени не собирается:', pg.inner_text('#dlgTitle'))
    pg.click('#dlgOk'); pg.wait_for_timeout(400)

    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','anna@example.com')
    pg.fill('#offerNew [data-offer="position"]', 'Бухгалтер')
    pg.fill('#offerNew [data-offer="head"]', 'Чернякова Марина')
    pg.click('#offerDraft'); pg.wait_for_timeout(800)

    assert pg.is_visible('#offerPanel'), 'панель оффера не открылась'
    assert cards(pg) == 0, 'черновик создал карточку сотрудника'
    assert not pg.is_visible('#offerSent'), 'у черновика есть отметка об отправке'
    assert 'Черновик' in pg.inner_text('#offerTo'), 'панель не отмечена как черновик: ' + pg.inner_text('#offerTo')
    doc = pg.frame_locator('#offerPreview').locator('body').inner_text()
    assert 'Бухгалтер' in doc and 'Чернякова Марина' in doc, 'в письме нет полей из формы'
    assert 'Анна' in doc, 'в письме нет имени'
    subj = pg.get_attribute('#offerCopySubject', 'title')
    assert subj == 'Оффер для Иванова Анна на позицию «Бухгалтер», i’way', 'тема черновика не та: ' + subj
    print('черновик оффера собран, карточек в базе:', cards(pg))

    # правка в панели черновика возвращается в форму
    pg.fill('#offerEdit [data-offer="probation"]', '3 месяца'); pg.wait_for_timeout(700)
    assert cards(pg) == 0, 'правка черновика создала карточку'
    pg.click('#offerClose'); pg.wait_for_timeout(500)
    assert pg.input_value('#offerNew [data-offer="probation"]') == '3 месяца', 'правка не вернулась в форму'
    assert pg.input_value('#offerNew [data-offer="position"]') == 'Бухгалтер', 'форма потеряла должность'
    print('правка из черновика вернулась в форму')

    # ——— создаём доступ: те же поля уходят в карточку
    pg.fill('#fDate','2026-10-05')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1300)
    assert cards(pg) == 1, 'карточка не создалась: %s' % cards(pg)
    saved = pg.evaluate("Object.values(window.__store).find(v => v && v.code).offer")
    assert saved['position'] == 'Бухгалтер' and saved['probation'] == '3 месяца', 'поля черновика не уехали в карточку: %s' % saved
    assert pg.is_visible('#offerSent'), 'у карточки нет отметки об отправке'
    assert 'Черновик' not in pg.inner_text('#offerTo'), 'карточку показали как черновик'
    print('после создания доступа: оффер в карточке', saved['position'], '·', saved['probation'])

    # ——— приглашение на стажировку без карточки
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    pg.select_option('#fDept','Отдел контроля'); pg.wait_for_timeout(300)
    assert pg.is_visible('#chatDraft') and not pg.is_visible('#offerBlock'), 'для стажировки нет кнопки приглашения'
    pg.fill('#fLast','Смирнова'); pg.fill('#fFirst','Ольга')
    pg.click('#chatDraft'); pg.wait_for_timeout(800)

    assert pg.is_visible('#chatPanel'), 'панель сообщений не открылась'
    assert cards(pg) == 1, 'черновик приглашения создал карточку'
    m1 = pg.input_value('#chatMsg1')
    assert m1.startswith('Ольга, здравствуйте!'), 'первое сообщение не то: ' + m1
    assert not pg.is_visible('#chatSecond'), 'второе сообщение показано без доступов'
    assert pg.is_visible('#chatLater'), 'нет пояснения про второе сообщение'
    assert not pg.is_visible('#chatSent'), 'у черновика есть отметка об отправке'
    print('черновик приглашения: только первое сообщение')

    # после создания доступа появляется второе сообщение с паролем
    pg.fill('#fPersonal','olga@example.com'); pg.fill('#fDate','2026-10-05'); pg.fill('#fTime','10:00')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1300)
    assert cards(pg) == 2, 'карточка стажёра не создалась'
    assert pg.is_visible('#chatSecond') and not pg.is_visible('#chatLater'), 'второе сообщение не появилось'
    assert pg.is_visible('#chatSent'), 'нет отметки об отправке'
    assert 'Пароль: ' in pg.input_value('#chatMsg2'), 'во втором сообщении нет пароля'
    print('после создания доступа: второе сообщение с паролем на месте')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
