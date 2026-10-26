# HR-метрики: первый администратор, команда и пароли, свои метрики, ввод за рекрутера,
# кабинет рекрутера, вакансии и скорость закрытия, архив пользователя с историей, админ-рекрутер, телефон
from playwright.sync_api import sync_playwright
import pathlib, json, datetime as dt
HERE = pathlib.Path(__file__).resolve().parent
(HERE / 'shots').mkdir(exist_ok=True)
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
ago = lambda n: (dt.date.today() - dt.timedelta(days=n)).isoformat()
seed = {
  'config/team': {'people': {'yulia': {'name': 'Юля', 'surname': 'Немчинова', 'order': 1}, 'anna': {'name': 'Анна', 'order': 2}}},
  'months/yulia_2026-09': {'person': 'yulia', 'month': '2026-09', 'days': {
     '2026-09-30': {'vac_end': 3, 'int_planned': 2, 'int_done': 1},
     '2026-10-01': {'vac_start': 9}}},
  'months/anna_2026-10': {'person': 'anna', 'month': '2026-10', 'days': {
     '2026-10-01': {'vac_start': 4, 'vac_end': 5, 'int_planned': 4, 'int_done': 3, 'chats': 2, 'chats_first': 1, 'hires': 1}}},
  'vacancies/v1': {'title': 'Логист', 'status': 'выход сотрудника', 'manager': 'Немчинова', 'publishedAt': ago(40), 'closedAt': ago(10)},  # 30 дн.
  'vacancies/v2': {'title': 'Бухгалтер', 'status': 'архив', 'manager': 'Шулятицкая', 'publishedAt': ago(70), 'startAt': ago(20)},     # 50 дн.
  'vacancies/v3': {'title': 'Аналитик', 'status': 'активна', 'manager': 'Немчинова', 'rate': 2, 'publishedAt': ago(5), 'link': 'https://hh.ru/vacancy/1'},
  'vacancies/v4': {'title': 'BDM', 'status': 'не актуальна', 'manager': 'Немчинова', 'publishedAt': ago(90), 'closedAt': ago(1)},     # не в скорости
}
errs = []
def page(b, **kw):
    pg = b.new_page(**kw)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('window.__store = ' + json.dumps(seed) + ';')
    return pg
def secret(pg):
    s = pg.query_selector_all('#tStat .secret'); return s[0].inner_text(), s[1].inner_text()

with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = page(b, viewport={'width': 1280, 'height': 1000})
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(400)
    # 1. администраторов нет — владелец создаёт первого
    assert pg.is_visible('#bootForm') and not pg.is_visible('#loginForm'), pg.evaluate('[isOwner, JSON.stringify(admins), teamLoaded, !!db, $("bootForm").hidden, $("loginForm").hidden, $("viewLogin").hidden]')
    pg.fill('#bName', 'Юлия Немчинова'); pg.fill('#bLogin', 'Admin'); pg.fill('#bPass', 'secret1'); pg.click('#bootForm button[type=submit]'); pg.wait_for_timeout(400)
    assert pg.inner_text('#meRole') == 'администратор' and pg.is_visible('#tab_settings') and not pg.query_selector('#tab_team')
    st = [u for u in pg.evaluate("window.__store['config/team'].people").values() if u.get('login') == 'admin'][0]
    assert st['hash'] and st['admin'] and st['recruiter'] is False and 'secret1' not in json.dumps(st), st
    assert 'Юлия Немчинова' not in pg.inner_text('#dTable')   # администратор без метрик — не в таблице рекрутеров

    # 2. дашборд дня по команде
    pg.evaluate("setPeriod('day', '2026-10-01')"); pg.wait_for_timeout(100)
    tiles = pg.inner_text('#dTiles')
    for want in ('3 из 4', '+25 п.п.', 'Вакансии в работе\n14', '+11', 'Чаты\n3'): assert want in tiles, (want, tiles)

    # 2a. пропуски: будни с 28.09 без цифр подсвечены, клик ведёт в форму на этот день
    todo = pg.inner_text('#dTodo')
    assert 'Нужно сделать' in todo and 'внести день' in todo.lower() and 'ещё' in todo, todo   # свежие пропуски — первыми, остальные под «ещё»
    pg.click('#dTodo details summary'); assert '28.09, пн' in pg.inner_text('#dTodo')
    assert pg.query_selector('#dTodo button.miss[data-p=anna][data-d="2026-09-30"]') and 'todo-col' in pg.get_attribute('#dTodo', 'class') and 'calm' not in pg.get_attribute('#dTodo', 'class')
    assert pg.evaluate("dayStatus('yulia', '2026-09-30')") == 'ok' and pg.evaluate("dayStatus('yulia', '2026-09-25')") == 'vac'   # до недели перехода — отпуск
    assert pg.evaluate("dayStatus('yulia', '2026-09-27')") == 'off'   # воскресенье
    pg.click('#dTodo button.miss[data-p=anna][data-d="2026-09-28"]'); pg.wait_for_timeout(200)
    assert pg.is_visible('#viewEntry') and pg.input_value('#fPerson') == 'anna' and pg.input_value('#fDate') == '2026-09-28'
    pg.screenshot(path=str(HERE / 'shots' / 'hr-todo-entry.png'))
    pg.click('#tab_day'); pg.wait_for_timeout(100)
    pg.screenshot(path=str(HERE / 'shots' / 'hr-day-todo.png'), full_page=True)

    # 3. команда: логин Анне, пароль; новый рекрутер
    pg.click('#tab_settings'); pg.click('#sub_team')
    L = '#tUsers input[data-p=anna][data-f=login]'
    pg.fill(L, 'yulia_x'); pg.dispatch_event(L, 'change'); pg.wait_for_timeout(200)
    pg.fill(L, 'admin'); pg.dispatch_event(L, 'change'); pg.wait_for_timeout(200)
    assert 'занят' in pg.inner_text('#tStat'), pg.inner_text('#tStat')
    assert pg.evaluate("window.__store['config/team'].people.anna.login") == 'yulia_x'
    pg.click('#tUsers button[data-act=reset][data-p=anna]'); pg.wait_for_timeout(300)
    anna_login, anna_pw = secret(pg)
    pg.fill('#tName', 'Катя'); pg.fill('#tSurname', 'Шулятицкая'); pg.fill('#tLogin', 'katya'); pg.click('#tUserForm button[type=submit]'); pg.wait_for_timeout(300)
    assert secret(pg)[0] == 'katya' and 'Катя' in pg.inner_text('#tUsers')
    # свои права снять нельзя, кнопки «В архив» у себя нет
    me_id = [k for k, u in pg.evaluate("window.__store['config/team'].people").items() if u.get('login') == 'admin'][0]
    assert pg.is_disabled('#tUsers input[data-p=%s][data-f=admin]' % me_id) and not pg.query_selector('#tUsers button[data-act=archive][data-p=%s]' % me_id)
    # Юля — администратор и рекрутер одновременно
    pg.check('#tUsers input[data-p=yulia][data-f=admin]'); pg.wait_for_timeout(200)
    assert pg.evaluate("window.__store['config/team'].people.yulia.admin") is True

    # 4. своя метрика и убранная встроенная
    # «Настройки»: команда, метрики и отпуска — разделы одной вкладки; раздел запоминается
    pg.click('#tab_vac'); pg.click('#tab_settings'); assert pg.is_visible('#viewTeam') and pg.is_visible('#subTabs')
    pg.click('#sub_vacation'); assert pg.is_visible('#oPerson') and pg.get_attribute('#tab_settings', 'aria-selected') == 'true'
    pg.click('#tab_day'); assert not pg.is_visible('#subTabs'); pg.click('#tab_settings'); assert pg.is_visible('#viewVacation')
    pg.click('#tab_settings'); pg.click('#sub_metrics'); pg.fill('#mName', 'Отклики hh'); pg.click('#mForm button[type=submit]'); pg.wait_for_timeout(300)
    pg.click('#mTable button[data-i="4"]'); pg.wait_for_timeout(300)   # «Звонки» убираем из формы
    # 5. админ вносит день за Анну
    pg.click('#tab_entry'); pg.select_option('#fPerson', 'anna'); pg.fill('#fDate', '2026-10-02'); pg.dispatch_event('#fDate', 'change')
    assert pg.input_value('#m_vac_start') == '5' and not pg.query_selector('#m_calls')
    custom = pg.get_attribute('#fGroups input[id^=m_c_]', 'data-k')
    pg.fill('#m_int_planned', '2'); pg.fill('#m_int_done', '2'); pg.fill('#m_' + custom, '7'); pg.click('#fSave'); pg.wait_for_timeout(300)
    day = pg.evaluate("window.__store['months/anna_2026-10'].days['2026-10-02']")
    assert day.pop('savedAt') and day == {'vac_start': 5, 'int_planned': 2, 'int_done': 2, custom: 7}, day   # плюс время ввода дня
    # 5a. сводка: блок месяца по неделям, неделя 28.09–2.10 — в октябре (четверг 1.10), sum и CV %
    pg.click('#tab_sum'); pg.wait_for_timeout(100)
    blk = pg.inner_text('#sBlocks')
    assert blk.startswith('Октябрь 2026') and '40\n28.09–2.10' in blk, blk[:200]
    assert 'Назначенных собеседований\t8\t' in blk and 'Собеседований (факт)\t6\t' in blk, blk
    assert 'Вакантных мест (на пятницу)\t—' in blk and 'Отклики hh\t7\t' in blk, blk
    assert '75%' in blk and '16,7%' in blk, blk
    assert 'Отказов' not in blk   # отказы в сводке не нужны
    # разбивка года: по месяцам и по кварталам — один блок на год, столбцы-периоды и sum
    pg.select_option('#sGroup', 'month'); pg.wait_for_timeout(100)
    blk = pg.inner_text('#sBlocks')
    assert blk.startswith('2026 год по месяцам') and 'сентябрь' in blk.lower() and 'октябрь' in blk.lower() and 'Вакантных мест (на конец месяца)' in blk, blk[:300]
    assert 'Назначенных собеседований\t2\t6\t8' in blk, blk   # 30.09: 2, октябрь: 6, итого 8
    pg.select_option('#sGroup', 'quarter'); pg.wait_for_timeout(100)
    blk = pg.inner_text('#sBlocks')
    assert blk.startswith('2026 год по кварталам') and '3 квартал' in blk.lower() and '4 квартал' in blk.lower() and 'Назначенных собеседований\t2\t6\t8' in blk, blk[:400]
    assert pg.evaluate("localStorage.getItem('hrSumGroup')") == '"quarter"'
    pg.select_option('#sGroup', 'week'); pg.wait_for_timeout(100)
    # копирование для отчёта: в буфер уходят HTML-таблица и текст через табуляцию
    pg.evaluate("""window.__clip = null; Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {write: function(items){
      return Promise.all(['text/html', 'text/plain'].map(function(t){ return items[0].getType(t).then(function(b){ return b.text(); }); }))
        .then(function(v){ window.__clip = v; }); }}});""")
    pg.click('#sBlocks button[data-copy="2026-10"]'); pg.wait_for_timeout(200)
    html_, text_ = pg.evaluate('window.__clip')
    assert '<table' in html_ and 'Неделя 40<br>' in html_ and '28.09–2.10' in html_ and 'Итого' in html_, html_[:300]
    assert text_.startswith('HR-метрики: Октябрь 2026 — вся команда') and 'Неделя 40 (28.09–2.10' in text_ and 'Назначенных собеседований\t8\t' in text_ and 'Доходимость: 75%' in text_, text_
    assert 'Скопировано' in pg.inner_text('#sBlocks')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-sum.png'), full_page=True)

    # 6. вакансии: в работе 1 (нужно 2 человека); скорость — только выходы (архив не считается), от запроса — с 01.10.26:
    # старые вакансии из таблицы — учёт ставок, не выходов: скорость считаем только с 01.10.26
    pg.click('#tab_vac'); pg.wait_for_timeout(200)
    vt = pg.inner_text('#vTiles')
    assert 'вакансий в работе: 1' in vt and 'План найма\n2' in vt and 'Скорость закрытия\n—' in vt and 'выходов с датой запроса пока нет' in vt and 'публикация' not in vt, vt
    pg.click('#vAdd'); pg.fill('#v_title', 'Тестировщик'); pg.fill('#v_manager', 'Шулятицкая'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert 'вакансий в работе: 2' in pg.inner_text('#vTiles')
    # «Шулятицкая» и «Катя Шулятицкая» — один ответственный: строка по пользователю, а не по тексту
    pg.click('#vAdd'); pg.fill('#v_title', 'Логист 2'); pg.fill('#v_manager', 'Катя Шулятицкая'); pg.click('#vSave'); pg.wait_for_timeout(300)
    bm = pg.inner_text('#vByMgr')
    assert 'Катя Шулятицкая\t2\t0' in bm and ('Юля Немчинова\t1\t1\t—' in bm or 'Юля Немчинова\t1\t0\t—' in bm) and 'Юля Немчинова' in bm and '\nШулятицкая' not in bm, bm
    assert 'Катя Шулятицкая' in pg.inner_text('#vManager')
    # фильтр по умолчанию — активные: закрытых в таблице нет, пока не выбрать «Все статусы»
    assert pg.evaluate('vacStatusSel()') == ['активна'] and pg.inner_text('#vStatusSum') == 'активна' and 'Логист\t' not in pg.inner_text('#vTable') and 'Аналитик' in pg.inner_text('#vTable')
    pg.evaluate("setVacStatus([])"); pg.wait_for_timeout(100); assert 'Бухгалтер' in pg.inner_text('#vTable')
    # «Скопировать для отчёта»: только активные, по ответственным, фильтр «Все статусы» не влияет
    pg.click('#vCopy'); pg.wait_for_timeout(200)
    html_, text_ = pg.evaluate('window.__clip')
    assert text_.startswith('Текущий найм на ') and 'В работе 3 вакансии, нужно 4 человека.' in text_, text_
    assert 'Катя Шулятицкая — 2 вакансии в работе, нужно 2' in text_ and 'Юля Немчинова — 1 вакансия в работе, нужно 2' in text_, text_
    assert 'Логист\t' not in text_ and 'Бухгалтер' not in text_ and 'Аналитик\t—\t—\t2\t' in text_, text_
    assert '<table' in html_ and 'Скопировано' in pg.inner_text('#vCopyStat')
    # несколько публикаций и заказчик: старая ссылка подхватывается, сохраняется списком
    pg.evaluate("setVacStatus(['активна'])"); pg.click('#vTable tr[data-id=v3] td:nth-child(2)'); pg.wait_for_timeout(100)
    assert pg.input_value('#vLinks .v-link') == 'https://hh.ru/vacancy/1'
    pg.click('#vLinkAdd'); pg.fill('#vLinks .link-row:nth-child(2) .v-link', 'https://hh.ru/vacancy/2')
    pg.click('#vLinkAdd'); pg.fill('#vLinks .link-row:nth-child(3) .v-link', 'https://hh.ru/vacancy/3')
    pg.click('#vLinks .link-row:nth-child(3) [data-del-link]')
    pg.fill('#v_customer', 'Дмитрий Васильевич'); pg.click('#vSave'); pg.wait_for_timeout(300)
    v3 = pg.evaluate("window.__store['vacancies/v3']")
    assert v3['links'] == [{'url': 'https://hh.ru/vacancy/1', 'at': ago(5)}, {'url': 'https://hh.ru/vacancy/2', 'at': ago(0), 'closedAt': pg.evaluate("addMonths(today(), 1)")}] and 'link' not in v3 and v3['customer'] == 'Дмитрий Васильевич', v3
    row = pg.inner_text('#vTable tr[data-id=v3]'); assert pg.inner_html('#vTable tr[data-id=v3] .pubs').count('<a ') == 2 and 'hh.ru' not in pg.inner_text('#vTable tr[data-id=v3] .pubs') and 'Дмитрий Васильевич' in row, row
    pg.fill('#vSearch', 'дмитрий'); pg.dispatch_event('#vSearch', 'input'); assert 'Аналитик' in pg.inner_text('#vTable') and 'Тестировщик' not in pg.inner_text('#vTable')
    pg.fill('#vSearch', ''); pg.dispatch_event('#vSearch', 'input')
    pg.click('#vCopy'); pg.wait_for_timeout(200)
    html_, text_ = pg.evaluate('window.__clip')
    assert 'Заказчик' in text_ and 'Дмитрий Васильевич' in text_ and 'https://hh.ru/vacancy/2' in html_, text_
    # единицы найма: «Бронирование 2/2» — по единице на человека, «+1» от руководителя, выход по единице
    pg.click('#vAdd'); pg.fill('#v_title', 'Менеджер отдела бронирования 2/2'); pg.fill('#v_manager', 'Немчинова')
    assert len(pg.query_selector_all('#vSeats .seat')) == 1 and pg.input_value('#vSeats .s-requestedAt') == dt.date.today().isoformat()
    s1 = '#vSeats .seat:nth-child(1) '
    pg.fill(s1 + '.s-requestedAt', ago(30)); assert pg.is_visible(s1 + '.s-publishedAt')
    pg.check(s1 + '.s-pub'); assert pg.is_hidden(s1 + '.s-publishedAt')      # «уже опубликована» — дату не вводим
    pg.uncheck(s1 + '.s-pub'); assert pg.is_visible(s1 + '.s-publishedAt')
    pg.fill(s1 + '.s-publishedAt', ago(25))
    pg.select_option(s1 + '.s-reason', 'увольнение сотрудника'); pg.select_option(s1 + '.s-search', 'активный'); pg.select_option(s1 + '.s-source', 'рекомендация сотрудника')
    # офферы: первый кандидат отказался (зарплата), второй принял; выход — в строке оффера, закрывает только галочка «кандидат вышел»
    pg.click(s1 + '[data-add-offer]'); o1 = s1 + '.offers > .offer:nth-child(2) '
    pg.fill(o1 + '.o-cand', 'Петров'); pg.fill(o1 + '.o-sent', ago(20)); assert pg.is_hidden(o1 + '.o-why')
    pg.select_option(o1 + '.o-res', 'declined'); assert pg.is_visible(o1 + '.o-why'); pg.fill(o1 + '.o-ans', ago(18)); pg.select_option(o1 + '.o-why', 'зарплата')
    pg.click(s1 + '[data-add-offer]'); o2 = s1 + '.offers > .offer:nth-child(3) '
    pg.fill(o2 + '.o-cand', 'Иванова'); pg.fill(o2 + '.o-sent', ago(15)); pg.select_option(o2 + '.o-res', 'accepted'); pg.fill(o2 + '.o-ans', ago(14))
    assert pg.is_hidden(o2 + '.o-why') and pg.is_visible(o2 + '.o-start') and pg.is_hidden(o1 + '.o-start') and not pg.query_selector(s1 + '.s-person')
    pg.click('#vSeatAdd'); pg.click('#vSeatAdd')                       # руководитель попросил ещё двоих
    assert 'Всего 3, в поиске 3' in pg.inner_text('#vSeatSum') and pg.inner_text('#vSeats .seat:nth-child(3) .seat-n') == 'Единица 3'
    pg.fill(o2 + '.o-start', ago(10)); pg.dispatch_event(o2 + '.o-start', 'change')
    assert 'ждём выхода' in pg.inner_text(s1 + '.pill') and 'в поиске 3' in pg.inner_text('#vSeatSum')   # дата выхода ещё не выход
    pg.click('#vSeats .seat:nth-child(3) [data-del-seat]')          # одну «+1» отменили
    pg.check(o2 + '.o-started')
    assert 'Всего 2, в поиске 1, закрыто 1' in pg.inner_text('#vSeatSum') and 'закрыта' in pg.inner_text(s1 + '.pill'), pg.inner_text('#vSeatSum')
    pg.click('#vSave'); pg.wait_for_timeout(300)
    vid = [k for k, v in pg.evaluate('window.__store').items() if k.startswith('vacancies/') and v.get('title', '').startswith('Менеджер отдела бронирования')][0]
    v = pg.evaluate("window.__store['%s']" % vid)
    assert v['multi'] and v['rate'] == 1 and v['status'] == 'активна' and v['publishedAt'] == ago(25) and v['requestedAt'] == ago(30), v
    assert v['seats'][0] == {'requestedAt': ago(30), 'publishedAt': ago(25), 'reason': 'увольнение сотрудника', 'search': 'активный', 'source': 'рекомендация сотрудника', 'person': 'Иванова', 'startAt': ago(10),
        'offers': [{'candidate': 'Петров', 'sentAt': ago(20), 'result': 'declined', 'answerAt': ago(18), 'reason': 'зарплата'},
                   {'candidate': 'Иванова', 'sentAt': ago(15), 'result': 'accepted', 'answerAt': ago(14), 'startAt': ago(10), 'started': True}]}, v['seats'][0]
    assert v['seats'][1] == {'requestedAt': dt.date.today().isoformat()}, v
    row = pg.inner_text('#vTable tr[data-id=%s]' % vid.split('/')[1]); assert '1 из 2' in row, row
    vt = pg.inner_text('#vTiles')
    # единица: запрос 30 дн. назад → выход 10 дн. назад = 20, одна — «мало данных»
    assert 'Скорость закрытия\n20' in vt and 'по 1 выходу — мало данных' in vt, vt
    # вторая единица закрыта — вакансия сама уходит в «выход сотрудника»; новая «+1» — снова «активна»
    s2 = '#vSeats .seat:nth-child(2) '; pg.click(s2 + '[data-add-offer]'); pg.select_option(s2 + '.o-res', 'accepted'); pg.check(s2 + '.o-started')   # без даты — сегодня
    pg.click('#vSave'); pg.wait_for_timeout(300)
    v = pg.evaluate("window.__store['%s']" % vid)
    assert v['status'] == 'выход сотрудника' and v['rate'] == 0 and v['closedAt'] == dt.date.today().isoformat(), v
    pg.click('#vSeatAdd'); pg.click('#vSave'); pg.wait_for_timeout(300)
    v = pg.evaluate("window.__store['%s']" % vid)
    assert v['status'] == 'активна' and v['rate'] == 1 and 'closedAt' not in v and len(v['seats']) == 3, v
    pg.click('#vCancel')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-vac.png'), full_page=True)
    pg.click('#tab_settings'); pg.click('#sub_metrics'); pg.screenshot(path=str(HERE / 'shots' / 'hr-metrics-admin.png'), full_page=True)

    # 7. кабинет рекрутера: Катя видит только себя и свои вакансии
    pg.click('#logout'); pg.wait_for_timeout(100)
    pg.fill('#lLogin', 'katya'); pg.fill('#lPass', 'wrong'); pg.click('#lSubmit'); pg.wait_for_timeout(200)
    assert 'Неверный' in pg.inner_text('#lErr')
    pg.fill('#lLogin', anna_login.upper()); pg.fill('#lPass', anna_pw); pg.click('#lSubmit'); pg.wait_for_timeout(300)
    assert pg.inner_text('#meName') == 'Анна' and pg.inner_text('#meRole') == 'рекрутер'
    tabs = pg.inner_text('#tabs'); assert 'Мой день' in tabs and 'Команда' not in tabs and 'Метрики' not in tabs, tabs
    pg.click('#tab_entry'); assert not pg.is_visible('#fPerson')
    pg.fill('#fDate', '2026-10-05'); pg.dispatch_event('#fDate', 'change'); pg.fill('#m_int_planned', '1'); pg.click('#fSave'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['months/anna_2026-10'].days['2026-10-05'].int_planned") == 1
    pg.click('#tab_day'); pg.evaluate("setPeriod('day', '2026-10-01')"); pg.wait_for_timeout(100)
    t = pg.inner_text('#dTiles'); assert 'Вакансии в работе\n5' in t, t   # только Анна, без Юли
    assert pg.inner_text('#dTable thead').count('дней') + pg.inner_text('#dTable thead').count('внесено') + pg.inner_text('#dTable thead').count('нужно') <= 2 and 'Юлия' not in pg.inner_text('#dTable')   # у рекрутера — только свой столбец
    pg.click('#tab_vac'); pg.wait_for_timeout(100)
    assert 'Вакансий нет' in pg.inner_text('#vTable')
    # «Мой отпуск»: отпуск убирает дни из пропусков и ставит статус
    pg.click('#tab_vacation'); assert not pg.is_visible('#oPerson')
    pg.fill('#oFrom', '2026-09-28'); pg.fill('#oTo', '2030-01-01'); pg.click('#oForm button[type=submit]'); pg.wait_for_timeout(300)
    vl = pg.evaluate("window.__store['vacations/anna'].list"); assert len(vl) == 1 and vl[0]['from'] == '2026-09-28' and vl[0]['to'] == '2030-01-01' and vl[0].get('sub') != 'anna', vl   # вакансии — коллеге
    assert 'в отпуске' in pg.inner_text('#meRole') and 'идёт' in pg.inner_text('#oTable')
    pg.click('#tab_day'); pg.wait_for_timeout(100)
    assert 'Всё сделано' in pg.inner_text('#dTodo') and 'calm' in pg.get_attribute('#dTodo', 'class'), pg.inner_text('#dTodo')
    pg.click('#tab_vacation'); pg.click('#oTable button[data-i="0"]'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacations/anna'].list") == []   # у Анны нет фамилии — в «Ответственном» её нет

    # 8. администратор отправляет Анну в архив — её сессия закрывается, история остаётся с пометкой
    pg.click('#logout'); pg.fill('#lLogin', 'admin'); pg.fill('#lPass', 'secret1'); pg.click('#lSubmit'); pg.wait_for_timeout(300)
    pg.click('#tab_settings'); pg.click('#sub_team'); pg.click('#tUsers button[data-act=archive][data-p=anna]'); pg.wait_for_timeout(300)
    assert 'Анна' in pg.inner_text('#tArchive') and 'Анна' not in pg.inner_text('#tUsers')
    assert pg.evaluate("window.__store['config/team'].people.anna.archivedAt")
    pg.click('#tab_day'); pg.evaluate("setPeriod('day', '2026-10-01')"); pg.wait_for_timeout(100)
    t = pg.inner_text('#dTable'); assert 'Анна (архив)' in t, t
    assert 'Вакансии в работе\n14' in pg.inner_text('#dTiles')   # её цифры в итогах команды
    pg.evaluate("setPeriod('day', today())"); pg.wait_for_timeout(100)
    assert 'Анна' not in pg.inner_text('#dTable')   # с дня архивации её нет
    pg.click('#tab_sum'); assert 'Анна (архив)' in pg.inner_text('#sPerson')
    pg.select_option('#sPerson', 'anna'); pg.wait_for_timeout(100); assert 'Пока нет' not in pg.inner_text('#sBlocks')
    pg.click('#tab_entry'); assert 'Анна (архив)' in pg.inner_text('#fPerson')
    # Катя в архиве — в отчётах по вакансиям её имя с пометкой «(архив)»
    pg.click('#tab_settings'); pg.click('#sub_team'); pg.click('#tUsers button[data-act=archive]:not([data-p=yulia])'); pg.wait_for_timeout(300)
    pg.click('#tab_vac'); pg.evaluate("setVacStatus([])"); pg.wait_for_timeout(100)
    assert 'Катя Шулятицкая (архив)' in pg.inner_text('#vTable') and 'Катя' not in pg.inner_text('#vByMgr'), pg.inner_text('#vByMgr')   # архивных в «По ответственным» нет
    pg.screenshot(path=str(HERE / 'shots' / 'hr-entry-admin.png'), full_page=True)
    pg.click('#tab_settings'); pg.click('#sub_team'); pg.screenshot(path=str(HERE / 'shots' / 'hr-team.png'), full_page=True)
    pg.click('#logout')
    pg.fill('#lLogin', anna_login); pg.fill('#lPass', anna_pw); pg.click('#lSubmit'); pg.wait_for_timeout(200)
    assert 'в архиве' in pg.inner_text('#lErr')
    pg.close()

    # 9. Юля по логину видит свои вакансии по фамилии; телефон и тёмная тема
    pg = page(b, viewport={'width': 390, 'height': 900}, color_scheme='dark')
    pg.add_init_script("window.__store['config/team'].people.boss = {name: 'Босс', login: 'boss', admin: true, recruiter: false, salt: 's', hash: 'x'};")
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(300)
    assert pg.is_visible('#loginForm') and not pg.is_visible('#bootForm')
    # сохранённая сессия рекрутера с паролем открывает кабинет сразу
    pg.add_init_script("window.__store['config/team'].people.yulia.hash = 'h'; localStorage.setItem('hrSession', JSON.stringify({id:'yulia'}));")
    pg.reload(); pg.wait_for_timeout(400)
    assert pg.inner_text('#meName') == 'Юля Немчинова'
    pg.click('#tab_vac'); pg.wait_for_timeout(100)
    vt = pg.inner_text('#vTable'); assert 'Аналитик' in vt and 'Бухгалтер' not in vt, vt
    assert pg.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'горизонтальный скролл на телефоне'
    pg.screenshot(path=str(HERE / 'shots' / 'hr-rec-phone.png'), full_page=True)
    b.close()
print('ОШИБКИ:', errs or 'нет')
assert not errs
