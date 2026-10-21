# Аналитика дашборда: воронка, тренд 12 месяцев, испытательный срок, нагрузка и прогноз выходов,
# сроки закрытия по этапам, причины отказов из выгрузки Talantix (CSV и Excel). «Сегодня» — 7.10.2026.
from playwright.sync_api import sync_playwright
import pathlib, json, datetime, openpyxl
HERE = pathlib.Path(__file__).resolve().parent
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
cache = HERE / '.cache'; cache.mkdir(exist_ok=True)
csv = cache / 'talantix.csv'
csv.write_text('Выгрузка из Talantix\nФИО;Ответственный;Дата отказа;Причина отказа\n'
               'А;Немчинова Юлия;01.10.2026 15:30;Не устроила зарплата\nБ;Немчинова Юлия;02.10.2026;"Не устроила зарплата"\nВ;Шулятицкая;02.10.2026;Нет опыта\nГ;;;\n', encoding='utf-8')
wb = openpyxl.Workbook(); ws = wb.active
ws.append(['Кандидаты']); ws.append([]); ws.append(['ФИО', 'Ответственный', 'Дата отказа', 'Причина отказа'])
ws.append(['А', 'Немчинова Юлия', datetime.datetime(2026, 10, 1, 15, 30), 'Не устроила зарплата'])
ws.append(['Б', 'Шулятицкая', datetime.datetime(2026, 10, 2), 'Нет опыта'])
ws.append(['В', 'Шулятицкая', None, 'Нет опыта'])
xl = cache / 'talantix.xlsx'; wb.save(xl)

seed = {
  'config/team': {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'hash': 'h', 'admin': True, 'order': 1},
                             'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'hash': 'h', 'order': 2}}},
  'months/yulia_2026-10': {'person': 'yulia', 'month': '2026-10', 'days': {
      '2026-10-01': {'chats': 20, 'int_planned': 5, 'int_done': 4, 'hires': 1, 'dismissals': 1},
      '2026-10-02': {'chats': 10, 'int_planned': 5, 'int_done': 2, 'rejections': 3}}},
  'months/yulia_2026-09': {'person': 'yulia', 'month': '2026-09', 'days': {'2026-09-15': {'chats': 30, 'int_planned': 6, 'int_done': 3, 'hires': 1}}},
  'months/yulia_2025-10': {'person': 'yulia', 'month': '2025-10', 'days': {'2025-10-01': {'int_done': 7}}},
  'vacancies/a': {'title': 'Логист', 'status': 'активна', 'manager': 'Немчинова', 'dept': 'Логистика', 'requestedAt': '2026-08-25', 'publishedAt': '2026-09-01', 'rate': 2},
  'vacancies/b': {'title': 'Диспетчер', 'status': 'выход сотрудника', 'manager': 'Шулятицкая', 'dept': 'Логистика', 'customer': 'Петров',
                  'requestedAt': '2026-08-01', 'publishedAt': '2026-08-05', 'closedAt': '2026-08-20', 'startAt': '2026-08-20', 'person': 'Иванов Иван', 'rate': 1},
  'vacancies/c': {'title': 'Менеджер', 'status': 'активна', 'manager': 'Немчинова', 'dept': 'Продажи', 'publishedAt': '2026-08-01', 'multi': True, 'rate': 0,
                  'seats': [{'requestedAt': '2026-07-25', 'startAt': '2026-08-03', 'person': 'Петрова'}, {'requestedAt': '2026-09-01', 'startAt': '2026-10-20', 'person': 'Сидоров',
                  'offers': [{'candidate': 'Орлов', 'sentAt': '2026-10-01', 'result': 'declined', 'answerAt': '2026-10-02', 'reason': 'зарплата'},
                             {'candidate': 'Сидоров', 'sentAt': '2026-10-03', 'result': 'accepted', 'answerAt': '2026-10-05'}]}]},
}
errs = []
def start(b, who):
    pg = b.new_page(viewport={'width': 1280, 'height': 1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time('2026-10-07T12:00:00')
    pg.route('**/*', lambda r: r.abort() if r.request.url.startswith('http') else r.continue_())   # внешних загрузок нет
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('if(!sessionStorage.seeded){ sessionStorage.seeded = 1; window.__store = ' + json.dumps(seed) + '; } localStorage.setItem("hrSession", JSON.stringify({id: "' + who + '"})); localStorage.setItem("hrMode", JSON.stringify("month"));')
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)
    return pg
def txt(pg, sel): return pg.inner_text(sel).replace(' ', ' ')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = start(b, 'yulia')
    assert pg.inner_text('#dayTitle').startswith('Октябрь 2026'), (pg.inner_text('#dayTitle'), errs)
    # офферы считаем с 20.10.26: в октябре до этой даты их нет — «—», а не 2, и пометка «с 20.10»
    f = txt(pg, '#dFunnel')
    assert 'Офферы отправлены · с 20.10.26\n—' in f and 'Нет данных за период' not in f, f
    pg.evaluate("sinceOver = {offers: '2026-09-01'}; render()"); pg.wait_for_timeout(100)   # как если бы офферы вносили с сентября
    # воронка: 30 чатов → 10 назначено (33%) → 6 прошло (60%) → 2 оффера (33%) → 1 принят (50%) → 1 выход (100%) → ИС
    f = txt(pg, '#dFunnel')
    assert 'Чаты\n30' in f and '↓ 33%' in f and '↓ 60%' in f and 'Офферы отправлены\n2' in f and '↓ 50%' in f and 'Офферы приняты\n1' in f and '↓ 100%' in f, f
    assert 'Прошли испытательный срок' in f and 'На 1 выход: 30 чатов · 10 назначенных · 6 прошедших собеседований · 2 офферов' in f, f
    assert 'Принимают оффер: 50% — 1 из 2 ответивших' in f and 'Отказались: зарплата — 1' in f, f
    # старые офферы (две даты в единице) — первым оффером; при пересохранении карточки переходят в список и не теряются
    assert pg.evaluate("seatOffers({offerSentAt: '2026-07-30', offerAcceptedAt: '2026-08-01'})") == [{'sentAt': '2026-07-30', 'result': 'accepted', 'answerAt': '2026-08-01'}]
    pg.evaluate("window.__store['vacancies/c'].seats[0].offerSentAt = '2026-07-28'; window.__store['vacancies/c'].seats[0].offerAcceptedAt = '2026-07-29'; window.__notify();"); pg.wait_for_timeout(200)
    pg.click('#tab_vac'); pg.evaluate("setVacStatus([])"); pg.click('#vTable tr[data-id=c] td:nth-child(2)'); pg.wait_for_timeout(200)
    assert pg.input_value('#vSeats .seat:nth-child(1) .o-sent') == '2026-07-28' and pg.input_value('#vSeats .seat:nth-child(1) .o-res') == 'accepted'
    pg.click('#vSave'); pg.wait_for_timeout(300)
    s0 = pg.evaluate("window.__store['vacancies/c'].seats[0]")
    # закрытая раньше единица: выход переехал в принятый оффер с отметкой «вышел»
    assert s0['offers'] == [{'result': 'accepted', 'candidate': 'Петрова', 'sentAt': '2026-07-28', 'answerAt': '2026-07-29', 'startAt': '2026-08-03', 'started': True}] and s0['startAt'] == '2026-08-03' and 'probMonths' not in s0 and 'offerSentAt' not in s0, s0
    # у второй единицы дата выхода 20.10 ещё впереди — после пересохранения она не закрыта, а ждёт выхода
    s1 = pg.evaluate("window.__store['vacancies/c'].seats[1]"); assert 'startAt' not in s1 and s1['offers'][1]['startAt'] == '2026-10-20' and not s1['offers'][1].get('started'), s1
    assert '2 из 3' in pg.inner_text('#vTable tr[data-id=c]')   # колонка «Офферы»: принято 2 из 3
    pg.click('#tab_day'); pg.wait_for_timeout(200)
    # тренд: собеседования за 12 месяцев (ноя 25 – окт 26) = 9, год назад = 7 → +29%
    t = txt(pg, '#dTrend')
    assert 'Ноябрь 2025 – Октябрь 2026' in t and 'Всего за 12 месяцев: 9' in t and 'Год назад: 7 +29%' in t, t
    pg.click('#dTrend [data-trend="4"]'); pg.wait_for_timeout(100)
    assert 'Всего за 12 месяцев: 1' in txt(pg, '#dTrend') and pg.get_attribute('#dTrend [data-trend="4"]', 'aria-pressed') == 'true'
    pg.click('#dTrend [data-trend="2"]'); pg.wait_for_timeout(100)
    assert 'За 12 месяцев: 56%' in txt(pg, '#dTrend'), txt(pg, '#dTrend')   # (3+6) / (6+10)
    # испытательный срок: срок в оффере не указан — не придумываем 2 месяца: «срок не указан», на испытательном никого
    pr = txt(pg, '#dProb')
    assert 'Сейчас на испытательном\n0' in pr and 'срок не указан: 2' in pr and 'У 2 вышедших срок испытательного не указан' in pr and not pg.query_selector('#dProb [data-prob=passed]'), pr
    pg.select_option('#dProb tr:has-text("Петрова") select[data-prob-months]', '2'); pg.wait_for_timeout(300)
    c = pg.evaluate("window.__store['vacancies/c']"); assert c['seats'][0]['probMonths'] == 2, c
    pg.select_option('#dProb tr:has-text("Иванов") select[data-prob-months]', '2'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacancies/b'].probMonths") == 2
    # указали 2 мес.: Петрова (вышла 3.08) — срок закончился 3.10, Иванов (20.08) — до 20.10
    pr = txt(pg, '#dProb')
    assert 'Сейчас на испытательном\n1' in pr and 'ждут итога: 1' in pr and 'закончился 4 дня назад' in pr and 'осталось 13 дней' in pr, pr
    assert pr.index('Петрова') < pr.index('Иванов Иван') and 'Сидоров' not in pr and 'Увольнения\n1' in pr
    pg.click('#dProb tr:has-text("Петрова") [data-prob=passed]'); pg.wait_for_timeout(300)
    c = pg.evaluate("window.__store['vacancies/c']")
    assert c['seats'][0]['probation'] == {'result': 'passed', 'at': '2026-10-03'} and 'probation' not in c['seats'][1], c
    assert 'Прошли испытательный срок\n1' in txt(pg, '#dProb') and 'прошёл' in txt(pg, '#dProb')
    pg.click('#dProb tr:has-text("Иванов") [data-prob=failed]'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacancies/b'].probation") == {'result': 'failed', 'at': '2026-10-07'}
    assert 'Не прошли\n1' in txt(pg, '#dProb') and 'прошли 50% из закончивших' in txt(pg, '#dProb'), txt(pg, '#dProb')
    pg.click('#dProb tr:has-text("Иванов") [data-prob=undo]'); pg.wait_for_timeout(300)
    assert not pg.evaluate("window.__store['vacancies/b'].probation")
    pg.click('#dProb tr:has-text("Иванов") [data-prob=failed]'); pg.wait_for_timeout(300)
    # пересохранение карточек не теряет отметки ИС
    pg.click('#tab_vac'); pg.evaluate("setVacStatus([])")
    for vid in ('b', 'c'):
        pg.click('#vTable tr[data-id=%s] td:nth-child(2)' % vid); pg.click('#vSave'); pg.wait_for_timeout(300); pg.click('#vCancel')
    assert pg.evaluate("window.__store['vacancies/b'].seats[0].probation.result") == 'failed' and pg.evaluate("window.__store['vacancies/b'].seats[0].person") == 'Иванов Иван'
    assert pg.evaluate("window.__store['vacancies/c'].seats[0].probation.result") == 'passed'
    pg.click('#tab_vac'); pg.click('#vTable tr[data-id=a] td:nth-child(2)'); assert len(pg.query_selector_all('#vSeats .seat')) == 2; pg.click('#vCancel')   # старая карточка со ставкой 2 — две единицы
    pg.click('#tab_day'); pg.wait_for_timeout(100)
    # нагрузка и прогноз: у Юлии 1 вакансия (C закрылась при пересохранении — все единицы с датой выхода), нужно 2 человека, ждём 1 выход (Сидоров 20.10)
    ld = txt(pg, '#dLoad')
    # C в работе: вторая единица ждёт выхода 20.10 (дата есть, «кандидат вышел» не отмечен) → 2 вакансии, нужно 3
    assert 'Юлия Немчинова\t2\t3\t36\t36\t1' in ld and ld.split('Юлия Немчинова')[1].split('\n')[0].endswith('\t1'), ld
    assert 'Октябрь по вакансиям: 1 выход (вышли 0, ожидаются 1)' in ld and 'В метриках дня: 1' in ld and '20.10.26\tСидоров\tМенеджер' in ld, ld
    # сроки по этапам — за год: Диспетчер (4 + 15 = 19 дн.), Петрова (7 + 2 = 9 дн.)
    pg.select_option('#dMode', 'year'); pg.wait_for_timeout(100)
    st = txt(pg, '#dStages')
    # выходы — в августе, а сроки считаем с 01.10.26 (раньше их не фиксировали): закрытых за период нет
    assert 'За период закрытых вакансий нет' in st, st
    pg.evaluate("sinceOver = Object.assign({}, sinceOver, {close: '2026-01-01'}); render()"); pg.wait_for_timeout(100)
    st = txt(pg, '#dStages')
    assert 'Логистика\t1\t4 дн.\t15 дн.\t19 дн.' in st and 'Продажи\t1\t7 дн.\t2 дн.\t9 дн.' in st and 'Все\t2\t6 дн.\t9 дн.\t14 дн.' in st, st
    pg.select_option('#dStageBy', 'owner'); pg.wait_for_timeout(100)
    assert 'Анна Шулятицкая\t1' in txt(pg, '#dStages') and pg.input_value('#dStageBy') == 'owner'
    pg.select_option('#dMode', 'month'); pg.wait_for_timeout(100)
    # причины отказов: пусто → загрузка CSV → дашборд
    assert 'Настройки → Talantix' in txt(pg, '#dReasons')
    pg.click('#tab_settings'); pg.click('#sub_talantix'); assert 'Пока ничего не загружено' in txt(pg, '#tTable')
    pg.set_input_files('#tFile', str(csv)); pg.wait_for_timeout(300)
    pv = txt(pg, '#tPreview')
    assert 'Отказов: 3 с 01.10.26 по 02.10.26, причин: 2' in pv and 'Причина — «Причина отказа», Дата — «Дата отказа», Рекрутер — «Ответственный»' in pv, pv
    pg.click('#tSave'); pg.wait_for_timeout(300)
    items = pg.evaluate("window.__store['rejections/2026-10'].items")
    assert sorted((x['d'], x['r'], x.get('w'), x['n']) for x in items) == [('2026-10-01', 'Не устроила зарплата', 'Немчинова Юлия', 1), ('2026-10-02', 'Не устроила зарплата', 'Немчинова Юлия', 1), ('2026-10-02', 'Нет опыта', 'Шулятицкая', 1)], items
    assert 'Октябрь 2026\t3\t2' in txt(pg, '#tTable') and 'Загружено: 3 отказа' in txt(pg, '#tStat')
    pg.click('#tab_day'); pg.wait_for_timeout(100)
    rs = txt(pg, '#dReasons')
    assert 'Не устроила зарплата\n2 67%' in rs and 'Нет опыта\n1 33%' in rs and 'Всего в Talantix: 3' in rs and 'В метриках дня: 3' in rs, rs
    # Excel: заголовок на 3-й строке, дата — ячейкой Excel; повторная загрузка заменяет те же даты
    pg.click('#tab_settings'); pg.click('#sub_talantix')
    pg.set_input_files('#tFile', str(xl)); pg.wait_for_timeout(800)
    assert 'Отказов: 2 с 01.10.26 по 02.10.26, причин: 2, без даты пропущено: 1' in txt(pg, '#tPreview'), txt(pg, '#tPreview') + txt(pg, '#tStat')
    pg.click('#tSave'); pg.wait_for_timeout(300)
    assert len(pg.evaluate("window.__store['rejections/2026-10'].items")) == 2
    pg.set_input_files('#tFile', {'name': 'x.csv', 'mimeType': 'text/csv', 'buffer': 'ФИО;Дата\nА;01.10.2026\n'.encode()}); pg.wait_for_timeout(300)
    assert 'Причина отказа' in txt(pg, '#tStat') and pg.is_hidden('#tSave')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-talantix.png'), full_page=True)
    pg.click('#tab_day'); pg.wait_for_timeout(200)
    pg.screenshot(path=str(HERE / 'shots' / 'hr-analytics.png'), full_page=True)
    store = pg.evaluate('window.__store')
    pg.close()
    # кабинет Анны: только её отказы и её вышедшие
    seed = store
    pg = start(b, 'anna')
    rs = txt(pg, '#dReasons'); assert 'Нет опыта' in rs and 'зарплата' not in rs, rs
    pr = txt(pg, '#dProb'); assert 'Иванов Иван' in pr and 'Петрова' not in pr, pr
    assert 'Анна Шулятицкая' in txt(pg, '#dLoad') and 'Юлия' not in txt(pg, '#dLoad')
    pg.set_viewport_size({'width': 390, 'height': 800}); pg.wait_for_timeout(200)
    assert pg.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'страница едет вбок на телефоне'
    pg.screenshot(path=str(HERE / 'shots' / 'hr-analytics-phone.png'), full_page=True)
    b.close()
print('ОШИБКИ:', errs or 'нет')
assert not errs
