from playwright.sync_api import sync_playwright
import pathlib, json, hashlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()
seed={'employees/IW-P':{'code':'IW-P','login':'аня','firstName':'Анна','lastName':'Иванова','gender':'f',
      'dept':'Клиентский сервис','email':'','personalEmail':'x@ex.com','startDate':'2026-10-05','startTime':'10:00',
      'createdAt':'2026-09-18','openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}},
      'config/departments':{'list':[{'name':'Клиентский сервис','head':'М. Соколова','senior':'И. Ли','chat':''}]}}
errs=[]

def login(pg):
    pg.evaluate("location.hash='#exit'"); pg.wait_for_timeout(500)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест')
    pg.click('#gateForm button'); pg.wait_for_timeout(1400)

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url+'#admin'); pg.wait_for_timeout(1000)

    pg.click('#tabPage'); pg.wait_for_timeout(400)
    rows = pg.query_selector_all('#pageRows .pg-row')
    assert len(rows) >= 7, 'блоки страницы не отрисованы: %d' % len(rows)
    print('блоков в настройке:', len(rows))

    # текущий текст лежит в самом поле — его правят с места, не набирая заново
    default_title = pg.input_value('[data-field="docs.title"]')
    assert default_title, 'в поле нет текущего заголовка'
    assert pg.get_attribute('[data-field="docs.title"]', 'placeholder') == default_title, \
        'подсказка разошлась со значением поля'
    assert pg.input_value('[data-field="docs.lead"]'), 'в поле нет текущего подзаголовка'
    print('текст в поле:', default_title)

    # правим текст и скрываем «Жизнь»
    pg.fill('[data-field="docs.title"]', 'Документы к первому дню')
    pg.fill('[data-field="docs.lead"]', 'Короткий список — остальное разберём на месте.')
    pg.uncheck('[data-section="culture"]')
    pg.click('#savePage'); pg.wait_for_timeout(700)
    assert pg.is_visible('#pageSaved'), 'сохранение не подтверждено'
    print('настройки сохранены')

    login(pg)
    assert pg.inner_text('#docs h2') == 'Документы к первому дню', 'заголовок не подменён: ' + pg.inner_text('#docs h2')
    assert 'Короткий список' in pg.inner_text('#docs .lead'), 'подзаголовок не подменён'
    assert not pg.is_visible('#culture'), 'скрытый раздел всё равно виден'
    assert not pg.is_visible('#culture'), 'скрытый раздел остался виден карточкой'
    assert pg.is_visible('#team'), 'нетронутый раздел пропал'
    print('у сотрудника: текст подменён, «Жизнь» скрыта, навигация без неё')

    # пустое поле = вернуть текст из вёрстки
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.fill('[data-field="docs.title"]', '')
    pg.check('[data-section="culture"]')
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    assert pg.inner_text('#docs h2') == default_title, 'пустое поле не вернуло исходный заголовок'
    assert pg.is_visible('#culture'), 'раздел не вернулся'
    print('пустое поле вернуло исходный текст, раздел вернулся')

    # ——— вопросы: правка, добавление, удаление, возврат исходных ———
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    base_q = pg.eval_on_selector_all('#pageRows [data-faq^="q"]', 'e => e.map(x => x.value)')
    assert len(base_q) >= 5, 'вопросы не подставились в редактор: %d' % len(base_q)
    print('вопросов в редакторе:', len(base_q))

    pg.fill('[data-faq="q0"]', 'Во сколько приходить в первый день?')
    pg.fill('[data-faq="a0"]', 'К 10:00, точный адрес пришлёт HR-партнёр.')
    pg.click('#add-faq'); pg.wait_for_timeout(300)
    last = len(base_q)
    pg.fill('[data-faq="q%d"]' % last, 'Есть ли парковка?')
    pg.fill('[data-faq="a%d"]' % last, 'Да, по пропуску <b>оформим</b> в первый день.')
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    qs = pg.eval_on_selector_all('#faq details summary', 'e => e.map(x => x.textContent)')
    assert qs[0] == 'Во сколько приходить в первый день?', 'правка вопроса не доехала: ' + qs[0]
    assert 'Есть ли парковка?' in qs, 'добавленный вопрос не появился'
    assert len(qs) == len(base_q) + 1, 'не то число вопросов: %d' % len(qs)
    print('у сотрудника вопросов:', len(qs), '| первый:', qs[0])
    # HR пишет текст, а не разметку: теги не должны исполняться
    marked = pg.eval_on_selector_all('#faq details .a', 'e => e.map(x => x.innerHTML)')
    hit = [x for x in marked if 'оформим' in x]
    assert hit and '<b>' not in hit[0], 'разметка из поля HR попала в страницу: ' + (hit[0] if hit else 'нет ответа')
    print('разметка в ответе экранирована')

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.click('[data-faq-del="0"]'); pg.wait_for_timeout(300)
    pg.click('#savePage'); pg.wait_for_timeout(700)
    login(pg)
    assert len(pg.query_selector_all('#faq details')) == len(base_q), 'удаление вопроса не доехало'
    print('после удаления вопросов:', len(base_q))

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.click('#reset-faq'); pg.wait_for_timeout(300)
    pg.click('#savePage'); pg.wait_for_timeout(700)
    login(pg)
    qs2 = pg.eval_on_selector_all('#faq details summary', 'e => e.map(x => x.textContent)')
    assert qs2 == base_q, 'исходные вопросы не вернулись'
    print('«Вернуть исходные» восстановил список из вёрстки')

    # ——— контакты: правка, добавление, ссылки ———
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    base_c = pg.eval_on_selector_all('#pageRows [data-contact^="r"]', 'e => e.map(x => x.value)')
    assert len(base_c) == 3, 'контакты не подставились в редактор: ' + str(len(base_c))
    print('контактов в редакторе:', base_c)

    pg.fill('[data-contact="r0"]', 'HR-партнёр')
    pg.fill('[data-contact="v0"]', 'hr@iway.ru')
    pg.fill('[data-contact="href0"]', '')                        # почта сама станет ссылкой
    pg.fill('[data-contact="v1"]', '+7 495 000-00-00')
    pg.fill('[data-contact="href1"]', 'tel:+74950000000')
    pg.fill('[data-contact="href2"]', 'javascript:alert(1)')     # чужая схема — не пускаем
    pg.click('#add-contact'); pg.wait_for_timeout(300)
    pg.fill('[data-contact="r3"]', 'Телеграм HR')
    pg.fill('[data-contact="v3"]', 'iwayHR')
    pg.fill('[data-contact="href3"]', 'https://t.me/iwayHR')
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    rows = pg.eval_on_selector_all('#contacts .contact', 'e => e.map(x => ({r: x.querySelector(".r").textContent, v: x.querySelector(".v").textContent, href: x.querySelector("a.go") ? x.querySelector("a.go").getAttribute("href") : "", go: x.querySelector(".go").textContent}))')
    assert len(rows) == 4, 'не то число контактов: ' + str(len(rows))
    assert rows[0]['r'] == 'HR-партнёр' and rows[0]['href'] == 'mailto:hr@iway.ru', 'почта не стала ссылкой: ' + str(rows[0])
    assert rows[1]['href'] == 'tel:+74950000000' and 'Позвонить' in rows[1]['go'], 'телефон не стал ссылкой: ' + str(rows[1])
    assert rows[2]['href'] == '' and rows[2]['go'].strip() == 'Уточняется', 'javascript-ссылка прошла на страницу: ' + str(rows[2])
    assert rows[3]['href'] == 'https://t.me/iwayHR' and 'Открыть' in rows[3]['go'], 'внешняя ссылка не встала: ' + str(rows[3])
    print('контакты на странице:', [r['go'].strip() for r in rows])

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.click('#reset-contact'); pg.wait_for_timeout(300)
    pg.click('#savePage'); pg.wait_for_timeout(700)
    login(pg)
    back = pg.eval_on_selector_all('#contacts .contact .r', 'e => e.map(x => x.textContent)')
    assert back == base_c, 'исходные контакты не вернулись: ' + str(back)
    print('«Вернуть исходные» восстановил контакты')

    # ——— статьи к прочтению: тот же список, что контакты ———
    login(pg)
    arts = pg.eval_on_selector_all('#aboutReads .contact',
        'e => e.map(x => ({r: x.querySelector(".r").textContent, v: x.querySelector(".v").textContent,'
        ' href: x.querySelector("a.go") ? x.querySelector("a.go").getAttribute("href") : "",'
        ' tgt: x.querySelector("a.go") ? x.querySelector("a.go").target + " " + x.querySelector("a.go").rel : ""}))')
    assert len(arts) == 5, 'статей не пять: %s' % len(arts)
    assert all(a['href'].startswith('http') for a in arts), 'не у всех статей ссылка: %s' % arts
    assert all(a['tgt'] == '_blank noopener' for a in arts), 'статьи открываются не в новой вкладке: %s' % arts
    assert 'forbes.ru' in arts[0]['href'] and 'apostrophe' in arts[4]['href'], 'порядок статей не тот: %s' % [a['href'] for a in arts]
    print('статьи:', ' | '.join(a['r'] + ' — ' + a['v'][:28] for a in arts))

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.fill('[data-read="v0"]', 'Forbes: как всё начиналось')
    pg.click('#savePage'); pg.wait_for_timeout(700)
    login(pg)
    assert pg.eval_on_selector('#aboutReads .contact .v', 'e => e.textContent') == 'Forbes: как всё начиналось', \
        'правка статьи не долетела до страницы'
    print('HR правит название статьи')

    # ——— документы: правка не должна ронять отметки сотрудника ———
    login(pg)
    pg.click('#docList [data-key="passport"]'); pg.wait_for_timeout(700)
    assert pg.get_attribute('#docList [data-key="passport"]', 'aria-pressed') == 'true', 'отметка не поставилась'
    print('сотрудник отметил паспорт')

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.fill('[data-docreq="t0"]', 'Паспорт (разворот с пропиской)')
    pg.click('#add-docreq'); pg.wait_for_timeout(300)
    n = len(pg.query_selector_all('#pageRows [data-docreq^="t"]')) - 1
    pg.fill('[data-docreq="t%d"]' % n, 'Военно-учётный документ')
    pg.check('[data-docreq="mil%d"]' % n)
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    first = pg.inner_text('#docList .check:first-child .c-t')
    assert 'разворот с пропиской' in first, 'название документа не подменилось: ' + first
    assert pg.get_attribute('#docList [data-key="passport"]', 'aria-pressed') == 'true', 'отметка потерялась при правке списка'
    mil = pg.query_selector_all('#docList .check[data-doc="mil"]')
    assert len(mil) == 2, 'признак «только для мужчин» не сохранился: %s' % len(mil)
    assert all(pg.evaluate('e => e.hidden', el) for el in mil), 'мужской документ показан женщине'
    print('название изменено, отметка цела, новый документ скрыт по полу')

    # ——— план, ценности, карточки «Жизни» ———
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.fill('[data-day="t0"]', 'Встреча с HR и оформление')
    pg.fill('[data-week="t0"]', 'Пройти вводный курс о компании')
    pg.fill('[data-month="t0"]', 'Сверка целей на 30 днях')
    pg.fill('[data-val="t0"]', 'Лидерство')
    pg.fill('[data-cult="k0"]', 'Внутренние события')
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    assert 'Встреча с HR и оформление' in pg.inner_text('#dayList .check:first-child .c-t'), 'план первого дня не обновился'
    assert 'вводный курс' in pg.inner_text('#planWeek li:first-child'), 'список первой недели не обновился'
    assert 'Сверка целей' in pg.inner_text('#planMonths li:first-child'), 'список 30/60/90 не обновился'
    assert pg.inner_text('#aboutValues .val:first-child .v-t') == 'Лидерство', 'ценность не обновилась'
    assert pg.inner_text('#aboutValues .val:first-child .v-i') == 'Ценность 01', 'нумерация ценностей сбилась'
    assert pg.inner_text('#cultureCards .cult:first-child .k') == 'Внутренние события', 'карточка «Жизни» не обновилась'
    print('план, ценности и карточки правятся')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
