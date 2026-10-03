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
    assert pg.inner_text('#meRole') == 'администратор' and pg.is_visible('#tab_team')
    st = [u for u in pg.evaluate("window.__store['config/team'].people").values() if u.get('login') == 'admin'][0]
    assert st['hash'] and st['admin'] and st['recruiter'] is False and 'secret1' not in json.dumps(st), st
    assert 'Юлия Немчинова' not in pg.inner_text('#dTable')   # администратор без метрик — не в таблице рекрутеров

    # 2. дашборд дня по команде
    pg.fill('#dDate', '2026-10-01'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(100)
    tiles = pg.inner_text('#dTiles')
    for want in ('3 из 4', '+25 п.п.', 'Открытые вакансии\n14', '+11', 'Чаты\n3'): assert want in tiles, (want, tiles)

    # 2a. пропуски: будни с 28.09 без цифр подсвечены, клик ведёт в форму на этот день
    todo = pg.inner_text('#dTodo')
    assert 'Нужно внести' in todo and '28.09 пн' in todo and '30.09 ср' in todo, todo
    assert pg.evaluate("dayStatus('yulia', '2026-09-30')") == 'ok' and pg.evaluate("dayStatus('yulia', '2026-09-25')") == 'vac'   # до недели перехода — отпуск
    assert pg.evaluate("dayStatus('yulia', '2026-09-27')") == 'off'   # воскресенье
    pg.click('#dTodo button.miss[data-p=anna][data-d="2026-09-28"]'); pg.wait_for_timeout(200)
    assert pg.is_visible('#viewEntry') and pg.input_value('#fPerson') == 'anna' and pg.input_value('#fDate') == '2026-09-28'
    pg.screenshot(path=str(HERE / 'shots' / 'hr-todo-entry.png'))
    pg.click('#tab_day'); pg.wait_for_timeout(100)
    pg.screenshot(path=str(HERE / 'shots' / 'hr-day-todo.png'), full_page=True)

    # 3. команда: логин Анне, пароль; новый рекрутер
    pg.click('#tab_team')
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
    pg.click('#tab_metrics'); pg.fill('#mName', 'Отклики hh'); pg.click('#mForm button[type=submit]'); pg.wait_for_timeout(300)
    pg.click('#mTable button[data-i="4"]'); pg.wait_for_timeout(300)   # «Звонки» убираем из формы
    # 5. админ вносит день за Анну
    pg.click('#tab_entry'); pg.select_option('#fPerson', 'anna'); pg.fill('#fDate', '2026-10-02'); pg.dispatch_event('#fDate', 'change')
    assert pg.input_value('#m_vac_start') == '5' and not pg.query_selector('#m_calls')
    custom = pg.get_attribute('#fGroups input[id^=m_c_]', 'data-k')
    pg.fill('#m_int_planned', '2'); pg.fill('#m_int_done', '2'); pg.fill('#m_' + custom, '7'); pg.click('#fSave'); pg.wait_for_timeout(300)
    day = pg.evaluate("window.__store['months/anna_2026-10'].days['2026-10-02']")
    assert day == {'vac_start': 5, 'int_planned': 2, 'int_done': 2, custom: 7}, day
    # 5a. сводка: блок месяца по неделям, неделя 28.09–2.10 — в октябре (четверг 1.10), sum и CV %
    pg.click('#tab_sum'); pg.wait_for_timeout(100)
    blk = pg.inner_text('#sBlocks')
    assert blk.startswith('Октябрь 2026') and '40\n28.09–2.10' in blk, blk[:200]
    assert 'Назначенных собеседований\t8\t8' in blk and 'Собеседований (факт)\t6\t6' in blk, blk
    assert 'Вакантных мест (на пятницу)\t—' in blk and 'Отклики hh\t7\t7' in blk, blk
    assert '75%' in blk and '16,7%' in blk, blk
    assert 'Отказов' not in blk   # отказы в сводке не нужны
    # копирование для отчёта: в буфер уходят HTML-таблица и текст через табуляцию
    pg.evaluate("""window.__clip = null; Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {write: function(items){
      return Promise.all(['text/html', 'text/plain'].map(function(t){ return items[0].getType(t).then(function(b){ return b.text(); }); }))
        .then(function(v){ window.__clip = v; }); }}});""")
    pg.click('#sBlocks button[data-copy="2026-10"]'); pg.wait_for_timeout(200)
    html_, text_ = pg.evaluate('window.__clip')
    assert '<table' in html_ and 'Неделя 40<br>' in html_ and '28.09–2.10' in html_ and 'Итого' in html_, html_[:300]
    assert text_.startswith('HR-метрики: Октябрь 2026 — вся команда') and 'Неделя 40 (28.09–2.10' in text_ and 'Назначенных собеседований\t8\t8' in text_ and 'Доходимость: 75%' in text_, text_
    assert 'Скопировано' in pg.inner_text('#sBlocks')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-sum.png'), full_page=True)

    # 6. вакансии: в работе 1 (нужно 2 человека), скорость (30+50)/2 = 40
    pg.click('#tab_vac'); pg.wait_for_timeout(200)
    vt = pg.inner_text('#vTiles')
    assert 'В работе\n1' in vt and 'Нужно людей\n2' in vt and 'Скорость закрытия\n40' in vt and 'медиана 40' in vt, vt
    pg.click('#vAdd'); pg.fill('#v_title', 'Тестировщик'); pg.fill('#v_manager', 'Шулятицкая'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert 'В работе\n2' in pg.inner_text('#vTiles')
    # «Шулятицкая» и «Катя Шулятицкая» — один ответственный: строка по пользователю, а не по тексту
    pg.click('#vAdd'); pg.fill('#v_title', 'Логист 2'); pg.fill('#v_manager', 'Катя Шулятицкая'); pg.click('#vSave'); pg.wait_for_timeout(300)
    bm = pg.inner_text('#vByMgr')
    assert 'Катя Шулятицкая\t2\t1' in bm and 'Юля Немчинова' in bm and '\nШулятицкая' not in bm, bm
    assert 'Катя Шулятицкая' in pg.inner_text('#vManager')
    # фильтр по умолчанию — активные: закрытых в таблице нет, пока не выбрать «Все статусы»
    assert pg.input_value('#vStatus') == 'активна' and 'Логист\t' not in pg.inner_text('#vTable') and 'Аналитик' in pg.inner_text('#vTable')
    pg.select_option('#vStatus', ''); pg.wait_for_timeout(100); assert 'Бухгалтер' in pg.inner_text('#vTable')
    # «Скопировать для отчёта»: только активные, по ответственным, фильтр «Все статусы» не влияет
    pg.click('#vCopy'); pg.wait_for_timeout(200)
    html_, text_ = pg.evaluate('window.__clip')
    assert text_.startswith('Текущий найм на ') and 'В работе 3 вакансии, нужно 4 человека.' in text_, text_
    assert 'Катя Шулятицкая — 2, нужно 2' in text_ and 'Юля Немчинова — 1, нужно 2' in text_, text_
    assert 'Логист\t' not in text_ and 'Бухгалтер' not in text_ and 'Аналитик\t—\t—\t2\t' in text_, text_
    assert '<table' in html_ and 'Скопировано' in pg.inner_text('#vCopyStat')
    # несколько публикаций и заказчик: старая ссылка подхватывается, сохраняется списком
    pg.select_option('#vStatus', 'активна'); pg.click('#vTable tr[data-id=v3] td:nth-child(2)'); pg.wait_for_timeout(100)
    assert pg.input_value('#vLinks .v-link') == 'https://hh.ru/vacancy/1'
    pg.click('#vLinkAdd'); pg.fill('#vLinks .link-row:nth-child(2) .v-link', 'https://hh.ru/vacancy/2')
    pg.click('#vLinkAdd'); pg.fill('#vLinks .link-row:nth-child(3) .v-link', 'https://hh.ru/vacancy/3')
    pg.click('#vLinks .link-row:nth-child(3) [data-del-link]')
    pg.fill('#v_customer', 'Дмитрий Васильевич'); pg.click('#vSave'); pg.wait_for_timeout(300)
    v3 = pg.evaluate("window.__store['vacancies/v3']")
    assert v3['links'] == ['https://hh.ru/vacancy/1', 'https://hh.ru/vacancy/2'] and 'link' not in v3 and v3['customer'] == 'Дмитрий Васильевич', v3
    row = pg.inner_text('#vTable tr[data-id=v3]'); assert 'hh 1' in row and 'hh 2' in row and 'Дмитрий Васильевич' in row, row
    pg.fill('#vSearch', 'дмитрий'); pg.dispatch_event('#vSearch', 'input'); assert 'Аналитик' in pg.inner_text('#vTable') and 'Тестировщик' not in pg.inner_text('#vTable')
    pg.fill('#vSearch', ''); pg.dispatch_event('#vSearch', 'input')
    pg.click('#vCopy'); pg.wait_for_timeout(200)
    html_, text_ = pg.evaluate('window.__clip')
    assert 'Заказчик' in text_ and 'Дмитрий Васильевич' in text_ and 'hh 2</a>' in html_, text_
    # несколько ставок: «Бронирование 2/2» — единица на поиск, «+1» от руководителя, выход по единице
    pg.click('#vAdd'); pg.fill('#v_title', 'Менеджер отдела бронирования 2/2'); pg.fill('#v_manager', 'Немчинова')
    pg.fill('#v_publishedAt', ago(30)); pg.check('#v_multi'); pg.wait_for_timeout(100)
    assert pg.is_visible('#vSeatsBox') and not pg.is_visible('#vRateWrap')
    assert pg.input_value('#vSeats .s-req') == ago(30), pg.input_value('#vSeats .s-req')
    pg.click('#vSeatAdd'); pg.click('#vSeatAdd')                       # руководитель попросил ещё двоих
    assert 'Всего 3, в поиске 3' in pg.inner_text('#vSeatSum')
    pg.fill('#vSeats tbody tr:nth-child(1) .s-start', ago(10)); pg.fill('#vSeats tbody tr:nth-child(1) .s-person', 'Иванова')
    pg.click('#vSeats tbody tr:nth-child(3) [data-del-seat]')          # одну «+1» отменили
    pg.dispatch_event('#vSeats tbody tr:nth-child(1) .s-start', 'change')
    assert 'Всего 2, в поиске 1, закрыто 1' in pg.inner_text('#vSeatSum'), pg.inner_text('#vSeatSum')
    pg.click('#vSave'); pg.wait_for_timeout(300)
    vid = [k for k, v in pg.evaluate('window.__store').items() if k.startswith('vacancies/') and v.get('title', '').startswith('Менеджер отдела бронирования')][0]
    v = pg.evaluate("window.__store['%s']" % vid)
    assert v['multi'] and v['rate'] == 1 and v['status'] == 'активна' and v['seats'][0] == {'requestedAt': ago(30), 'startAt': ago(10), 'person': 'Иванова'} and v['seats'][1] == {'requestedAt': dt.date.today().isoformat()}, v
    row = pg.inner_text('#vTable tr[data-id=%s]' % vid.split('/')[1]); assert '1 из 2' in row, row
    vt = pg.inner_text('#vTiles')
    assert 'Скорость закрытия\n33' in vt and 'закрыто 3' in vt, vt                # (30 + 50 + 20) / 3: единица считается отдельно
    # вторая единица закрыта — вакансия сама уходит в «выход сотрудника»; новая «+1» — снова «активна»
    pg.fill('#vSeats tbody tr:nth-child(2) .s-start', dt.date.today().isoformat()); pg.click('#vSave'); pg.wait_for_timeout(300)
    v = pg.evaluate("window.__store['%s']" % vid)
    assert v['status'] == 'выход сотрудника' and v['rate'] == 0 and v['closedAt'] == dt.date.today().isoformat(), v
    pg.click('#vSeatAdd'); pg.click('#vSave'); pg.wait_for_timeout(300)
    v = pg.evaluate("window.__store['%s']" % vid)
    assert v['status'] == 'активна' and v['rate'] == 1 and 'closedAt' not in v and len(v['seats']) == 3, v
    pg.click('#vCancel')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-vac.png'), full_page=True)
    pg.click('#tab_metrics'); pg.screenshot(path=str(HERE / 'shots' / 'hr-metrics-admin.png'), full_page=True)

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
    pg.click('#tab_day'); pg.fill('#dDate', '2026-10-01'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(100)
    t = pg.inner_text('#dTiles'); assert 'Открытые вакансии\n5' in t, t   # только Анна, без Юли
    assert pg.inner_text('#dChips') == ''
    pg.click('#tab_vac'); pg.wait_for_timeout(100)
    assert 'Вакансий нет' in pg.inner_text('#vTable')
    # «Мой отпуск»: отпуск убирает дни из пропусков и ставит статус
    pg.click('#tab_vacation'); assert not pg.is_visible('#oPerson')
    pg.fill('#oFrom', '2026-09-28'); pg.fill('#oTo', '2030-01-01'); pg.click('#oForm button[type=submit]'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacations/anna'].list") == [{'from': '2026-09-28', 'to': '2030-01-01'}]
    assert 'в отпуске' in pg.inner_text('#meRole') and 'идёт' in pg.inner_text('#oTable')
    pg.click('#tab_day'); pg.wait_for_timeout(100)
    assert 'Все рабочие дни внесены' in pg.inner_text('#dTodo'), pg.inner_text('#dTodo')
    pg.click('#tab_vacation'); pg.click('#oTable button[data-i="0"]'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacations/anna'].list") == []   # у Анны нет фамилии — в «Ответственном» её нет

    # 8. администратор отправляет Анну в архив — её сессия закрывается, история остаётся с пометкой
    pg.click('#logout'); pg.fill('#lLogin', 'admin'); pg.fill('#lPass', 'secret1'); pg.click('#lSubmit'); pg.wait_for_timeout(300)
    pg.click('#tab_team'); pg.click('#tUsers button[data-act=archive][data-p=anna]'); pg.wait_for_timeout(300)
    assert 'Анна' in pg.inner_text('#tArchive') and 'Анна' not in pg.inner_text('#tUsers')
    assert pg.evaluate("window.__store['config/team'].people.anna.archivedAt")
    pg.click('#tab_day'); pg.fill('#dDate', '2026-10-01'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(100)
    t = pg.inner_text('#dTable'); assert 'Анна (архив)' in t, t
    assert 'Открытые вакансии\n14' in pg.inner_text('#dTiles')   # её цифры в итогах команды
    pg.fill('#dDate', '2026-10-06'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(100)
    assert 'Анна' not in pg.inner_text('#dTable') and 'Анна' not in pg.inner_text('#dChips')   # на новых днях её нет
    pg.click('#tab_sum'); assert 'Анна (архив)' in pg.inner_text('#sPerson')
    pg.select_option('#sPerson', 'anna'); pg.wait_for_timeout(100); assert 'Пока нет' not in pg.inner_text('#sBlocks')
    pg.click('#tab_entry'); assert 'Анна (архив)' in pg.inner_text('#fPerson')
    # Катя в архиве — в отчётах по вакансиям её имя с пометкой «(архив)»
    pg.click('#tab_team'); pg.click('#tUsers button[data-act=archive]:not([data-p=yulia])'); pg.wait_for_timeout(300)
    pg.click('#tab_vac'); pg.select_option('#vStatus', ''); pg.wait_for_timeout(100)
    assert 'Катя Шулятицкая (архив)' in pg.inner_text('#vByMgr') and 'Катя Шулятицкая (архив)' in pg.inner_text('#vTable'), pg.inner_text('#vByMgr')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-entry-admin.png'), full_page=True)
    pg.click('#tab_team'); pg.screenshot(path=str(HERE / 'shots' / 'hr-team.png'), full_page=True)
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
