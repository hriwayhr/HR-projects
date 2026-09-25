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
    assert 'Черновик' in pg.inner_text('#offerTo'), 'панель не отмечена как черновик: ' + pg.inner_text('#offerTo')
    doc = pg.frame_locator('#offerPreview').locator('body').inner_text()
    assert 'Бухгалтер' in doc and 'Чернякова Марина' in doc, 'в письме нет полей из формы'
    assert 'Анна' in doc, 'в письме нет имени'
    subj = pg.get_attribute('#offerCopySubject', 'title')
    assert subj == 'Оффер для Иванова Анна на позицию «Бухгалтер», i’way', 'тема черновика не та: ' + subj
    print('черновик оффера собран, карточек в базе:', cards(pg))

    # ——— отметка «отправлен» превращает черновик в карточку кандидата
    assert pg.is_visible('#offerSent'), 'в черновике нет отметки об отправке'
    assert 'сохранить кандидата' in pg.inner_text('#offerSent'), 'кнопка не обещает сохранить кандидата'
    pg.click('#offerSent'); pg.wait_for_timeout(900)
    assert cards(pg) == 1, 'кандидат не сохранился: %s' % cards(pg)
    cand = pg.evaluate("Object.values(window.__store).find(v => v && v.code)")
    assert cand['offerSentAt'] and not cand.get('hash') and not cand.get('login'), \
        'кандидат сохранён с доступом: %s' % {k: cand.get(k) for k in ['offerSentAt', 'hash', 'login']}
    assert pg.input_value('#offerNew [data-offer="position"]') == '', 'форма не очистилась после сохранения кандидата'
    print('кандидат сохранён без доступа, оффер отправлен')

    # карточка кандидата: статус, ответ, кнопка выдачи доступа
    pg.click('#tabPeople'); pg.wait_for_timeout(500)
    # статусная плашка набрана капителью — сверяем без учёта регистра
    card = open_row(pg).inner_text().lower()
    assert 'ждём ответа' in card, 'в строке не тот статус: ' + card
    assert 'оффер' in card, 'в строке нет слова «оффер»: ' + card
    assert 'создать доступ' in card, 'в карточке кандидата нет кнопки выдачи доступа'
    assert 'документы' not in card, 'у кандидата показаны чек-листы'
    open_row(pg).locator('button[data-reply="yes"]').click(); pg.wait_for_timeout(700)
    assert 'принят' in open_row(pg).inner_text().lower(), 'ответ не отметился: ' + open_row(pg).inner_text()
    assert pg.evaluate("Object.values(window.__store).find(v => v && v.code).offerReply") == 'yes', 'ответ не сохранился'
    print('карточка кандидата: ответ отмечен')

    # выдача доступа: пароль появляется, письмо открывается
    open_row(pg).locator('.pr-body button', has_text='Создать доступ').click(); pg.wait_for_timeout(1300)
    rec = pg.evaluate("Object.values(window.__store).find(v => v && v.code)")
    assert rec['hash'] and rec['login'] and rec['accessAt'], 'доступ не выдан: %s' % {k: rec.get(k) for k in ['hash','login','accessAt']}
    assert rec['offerSentAt'] == cand['offerSentAt'], 'дата отправки оффера потерялась'
    assert pg.is_visible('#mailPanel'), 'письмо-приглашение не открылось'
    pg.click('#tabPeople'); pg.wait_for_timeout(500)
    assert 'письмо не отправлено' in pg.locator('.prow').first.inner_text().lower(), \
        'строка не перешла к обычному статусу: ' + pg.locator('.prow').first.inner_text()
    print('доступ выдан из карточки кандидата, письмо открыто')

    # ——— второй кандидат: снова черновик, теперь проверяем возврат правок в форму
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    pg.select_option('#fDept','Бухгалтерия'); pg.wait_for_timeout(300)
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','anna@example.com')
    pg.fill('#offerNew [data-offer="position"]', 'Бухгалтер')
    pg.fill('#offerNew [data-offer="head"]', 'Чернякова Марина')
    pg.click('#offerDraft'); pg.wait_for_timeout(800)

    # правка в панели черновика возвращается в форму
    pg.fill('#offerEdit [data-offer="probation"]', '3 месяца'); pg.wait_for_timeout(700)
    assert cards(pg) == 1, 'правка черновика создала карточку'   # в базе только первый, уже с доступом
    pg.click('#offerClose'); pg.wait_for_timeout(500)
    assert pg.input_value('#offerNew [data-offer="probation"]') == '3 месяца', 'правка не вернулась в форму'
    assert pg.input_value('#offerNew [data-offer="position"]') == 'Бухгалтер', 'форма потеряла должность'
    print('правка из черновика вернулась в форму')

    # ——— создаём доступ: те же поля уходят в карточку
    pg.fill('#fDate','2026-10-05')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1300)
    assert cards(pg) == 2, 'карточка не создалась: %s' % cards(pg)
    saved = pg.evaluate("Object.values(window.__store).filter(v => v && v.code).slice(-1)[0].offer")
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
    assert cards(pg) == 2, 'черновик приглашения создал карточку'
    m1 = pg.input_value('#chatMsg1')
    assert m1.startswith('Ольга, здравствуйте!'), 'первое сообщение не то: ' + m1
    assert not pg.is_visible('#chatSecond'), 'второе сообщение показано без доступов'
    assert pg.is_visible('#chatLater'), 'нет пояснения про второе сообщение'
    assert 'сохранить кандидата' in pg.inner_text('#chatSent'), 'кнопка не обещает сохранить кандидата'
    print('черновик приглашения: только первое сообщение')

    # отметка «отправлено» сохраняет кандидата-стажёра
    pg.click('#chatSent'); pg.wait_for_timeout(900)
    assert cards(pg) == 3, 'кандидат-стажёр не сохранился: %s' % cards(pg)
    pg.click('#tabPeople'); pg.wait_for_timeout(500)
    olga = open_row(pg, 'Смирнова').inner_text().lower()
    assert 'ждём ответа' in olga, 'у стажёра не тот статус: %s' % olga
    assert 'приглашение' in olga and 'оффер' not in olga, 'у стажёра оффер вместо приглашения: %s' % olga
    print('кандидат-стажёр в списке со статусом приглашения')

    # доступ выдаём из карточки — открывается второе сообщение с паролем
    open_row(pg, 'Смирнова').locator('.pr-body button', has_text='Создать доступ').click()
    pg.wait_for_timeout(1300)
    assert pg.is_visible('#chatPanel') and pg.is_visible('#chatSecond'), 'второе сообщение не открылось'
    assert 'Пароль: ' in pg.input_value('#chatMsg2'), 'во втором сообщении нет пароля'
    print('стажёру выдан доступ, второе сообщение с паролем')

    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
