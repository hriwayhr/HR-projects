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
    pg.click('#tabDepts'); pg.click('#addDept'); pg.wait_for_timeout(200)
    ins=pg.query_selector_all('#deptRows tr td input'); ins[0].fill('Бухгалтерия'); ins[1].fill('М. Чернякова')
    pg.click('#saveDepts'); pg.wait_for_timeout(400)

    # оффер заполняется прямо в форме создания
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    assert pg.is_visible('#offerNew [data-offer="position"]'), 'полей оффера нет в форме создания'
    pg.fill('#fLast','Иванова'); pg.fill('#fFirst','Анна'); pg.fill('#fPersonal','anna@example.com')
    pg.select_option('#fDept','Бухгалтерия'); pg.fill('#fDate','2026-10-05')
    pg.fill('#offerNew [data-offer="position"]', 'Бухгалтер по расчётам с международными контрагентами')
    pg.fill('#offerNew [data-offer="tasks"]', 'вести взаиморасчёты с иностранными контрагентами\nпроверять и согласовывать счета и акты')
    pg.fill('#offerNew [data-offer="probation"]', '3 месяца')
    pg.fill('#offerNew [data-offer="schedule"]', '5/2, 8-часовой рабочий день. Перерыв на обед 1 час.')
    pg.fill('#offerNew [data-offer="hours"]', '10:00 – 19:00')
    pg.fill('#offerNew [data-offer="head"]', 'Чернякова Марина, ведущий бухгалтер')
    pg.fill('#offerNew [data-offer="payProbation"]', '65 000 рублей на руки (после вычета НДФЛ)')
    pg.fill('#offerNew [data-offer="payAfter"]', '70 000 рублей на руки (после вычета НДФЛ)')
    pg.fill('#offerNew [data-offer="deadline"]', '2026-09-07')
    pg.click('#newForm button[type=submit]'); pg.wait_for_timeout(1200)

    assert pg.is_visible('#offerPanel'), 'после создания панель оффера не открылась'
    print('оффер заполнен при создании, панель открыта')

    # читаем письмо так, как его увидит кандидат: подставленные значения выделены
    # жирным, поэтому в исходном HTML цельных фраз нет — сверяем по тексту
    doc = pg.frame_locator('#offerPreview').locator('body').inner_text()
    for must in ['Здравствуйте, Анна!', 'Бухгалтер по расчётам с международными контрагентами',
                 'вести взаиморасчёты с иностранными контрагентами', 'проверять и согласовывать счета и акты',
                 '3 месяца', '10:00 – 19:00', 'Чернякова Марина', '65 000 рублей', '70 000 рублей',
                 '07.09.2026', 'ул. Депутатская', '28 календарных дней']:
        assert must in doc, 'в письме нет: ' + must
    print('в письме есть имя, должность, задачи, условия, руководитель и срок ответа')

    # порядок абзацев — как в исходном тексте оффера
    order = ['Здравствуйте, Анна!', 'Если вы получили это письмо',
             'предложение о работе в должности', 'Что предстоит делать:',
             'официальное трудоустройство, согласно ТК РФ', 'Испытательный срок составляет',
             'Рабочий график:', 'Часы работы:', 'Заработная плата:',
             'Также мы гарантируем:', 'Вашим непосредственным руководителем будет:',
             'Место работы:', 'Ответ на оффер необходимо дать до',
             'мы открыты к диалогу', 'Будем рады видеть вас частью нашей команды']
    pos = [doc.index(x) for x in order]
    for i in range(1, len(pos)):
        assert pos[i] > pos[i-1], 'порядок нарушен: «%s» идёт раньше «%s»' % (order[i], order[i-1])
    print('порядок абзацев совпадает с исходным письмом')

    # тема письма
    subj = pg.get_attribute('#offerCopySubject', 'title')
    want = 'Оффер для Иванова Анна на позицию «Бухгалтер по расчётам с международными контрагентами», i\u2019way'
    assert subj == want, 'тема письма не та:\n  получено: ' + subj + '\n  ожидалось: ' + want
    print('тема письма:', subj)

    # поля сохранились в записи
    saved = pg.evaluate("Object.values(window.__store).find(v => v.code)?.offer")
    assert saved and saved['position'].startswith('Бухгалтер'), 'оффер не сохранился в карточке: %s' % saved
    print('оффер записан в карточку:', saved['probation'], '|', saved['hours'])

    # форма создания очистилась
    pg.click('#tabNew'); pg.wait_for_timeout(300)
    assert pg.input_value('#offerNew [data-offer="position"]') == '', 'поля оффера не очистились после создания'
    print('форма создания очищена')

    # отметка об отправке и статус в карточке
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    assert 'заполнен, не отправлен' in open_row(pg).inner_text(), 'в строке нет статуса оффера'
    open_row(pg).locator('.pr-body button', has_text='Оффер').click(); pg.wait_for_timeout(700)
    assert pg.is_visible('#offerPanel'), 'оффер не открылся из карточки'
    pg.click('#offerSent'); pg.wait_for_timeout(700)
    assert 'Отправлено' in pg.inner_text('#offerSent'), 'отметка об отправке не встала'
    assert pg.evaluate("!!Object.values(window.__store).find(v => v.code)?.offerSentAt"), 'offerSentAt не сохранился'
    pg.click('#tabPeople'); pg.wait_for_timeout(400)
    assert 'отправлен ' in open_row(pg).inner_text(), 'строка не показала отправленный оффер'
    print('оффер отмечен отправленным, карточка это показывает')

    # правка из карточки долетает в письмо и в базу
    pg.fill('#offerEdit [data-offer="hours"]', '09:00 – 18:00'); pg.wait_for_timeout(1200)
    assert '09:00 – 18:00' in pg.get_attribute('#offerPreview', 'srcdoc'), 'правка не попала в предпросмотр'
    assert pg.evaluate("Object.values(window.__store).find(v => v.code)?.offer?.hours") == '09:00 – 18:00', 'правка не сохранилась'
    print('правка из панели сохраняется и видна в предпросмотре')

    # разметка в поле не исполняется
    pg.fill('#offerEdit [data-offer="position"]', 'Бухгалтер <b>международный</b>'); pg.wait_for_timeout(900)
    doc2 = pg.get_attribute('#offerPreview', 'srcdoc')
    assert '&lt;b&gt;международный&lt;/b&gt;' in doc2, 'разметка из поля попала в письмо как разметка'
    print('разметка в поле экранирована')

    pg.click('#offerClose'); pg.wait_for_timeout(400)
    assert not pg.is_visible('#offerPanel'), 'панель оффера не закрылась'
    print('панель закрывается')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
