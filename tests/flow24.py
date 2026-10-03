# HR-метрики: первый администратор, команда и пароли, свои метрики, ввод за рекрутера,
# кабинет рекрутера, вакансии и скорость закрытия, отключение рекрутера, телефон
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
  'vacancies/v3': {'title': 'Аналитик', 'status': 'активна', 'manager': 'Немчинова', 'rate': 2, 'publishedAt': ago(5)},
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
    st = pg.evaluate("window.__store['config/admins'].list.admin")
    assert st['hash'] and 'secret1' not in json.dumps(st), st

    # 2. дашборд дня по команде
    pg.fill('#dDate', '2026-10-01'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(100)
    tiles = pg.inner_text('#dTiles')
    for want in ('3 из 4', '+25 п.п.', 'Открытые вакансии\n14', '+11', 'Чаты\n3'): assert want in tiles, (want, tiles)

    # 3. команда: логин Анне, пароль; новый рекрутер
    pg.click('#tab_team')
    pg.fill('#tRec input[data-p=anna][data-f=login]', 'yulia_x'); pg.dispatch_event('#tRec input[data-p=anna][data-f=login]', 'change'); pg.wait_for_timeout(200)
    pg.fill('#tRec input[data-p=anna][data-f=login]', 'admin'); pg.dispatch_event('#tRec input[data-p=anna][data-f=login]', 'change'); pg.wait_for_timeout(200)
    assert 'занят' in pg.inner_text('#tStat'), pg.inner_text('#tStat')
    assert pg.evaluate("window.__store['config/team'].people.anna.login") == 'yulia_x'
    pg.click('#tRec button[data-act=reset][data-p=anna]'); pg.wait_for_timeout(300)
    anna_login, anna_pw = secret(pg)
    pg.fill('#tName', 'Катя'); pg.fill('#tSurname', 'Шулятицкая'); pg.fill('#tLogin', 'katya'); pg.click('#tRecForm button[type=submit]'); pg.wait_for_timeout(300)
    assert secret(pg)[0] == 'katya' and 'Катя' in pg.inner_text('#tRec')

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

    # 6. вакансии: в работе 1 (нужно 2 человека), скорость (30+50)/2 = 40
    pg.click('#tab_vac'); pg.wait_for_timeout(200)
    vt = pg.inner_text('#vTiles')
    assert 'В работе\n1' in vt and 'Нужно людей\n2' in vt and 'Скорость закрытия\n40' in vt and 'медиана 40' in vt, vt
    pg.click('#vAdd'); pg.fill('#v_title', 'Тестировщик'); pg.fill('#v_manager', 'Шулятицкая'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert 'В работе\n2' in pg.inner_text('#vTiles')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-vac.png'), full_page=True)
    pg.click('#tab_team'); pg.screenshot(path=str(HERE / 'shots' / 'hr-team.png'), full_page=True)
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
    assert 'Вакансий нет' in pg.inner_text('#vTable')   # у Анны нет фамилии — в «Ответственном» её нет

    # 8. администратор отключает Анну — её сессия закрывается
    pg.evaluate("var t = window.__store['config/team']; t.people.anna.archived = true; window.__notify()"); pg.wait_for_timeout(300)
    assert pg.is_visible('#loginForm') and not pg.is_visible('#me')
    pg.fill('#lLogin', anna_login); pg.fill('#lPass', anna_pw); pg.click('#lSubmit'); pg.wait_for_timeout(200)
    assert 'отключена' in pg.inner_text('#lErr')
    pg.close()

    # 9. Юля по логину видит свои вакансии по фамилии; телефон и тёмная тема
    pg = page(b, viewport={'width': 390, 'height': 900}, color_scheme='dark')
    pg.add_init_script("window.__store['config/admins'] = {list: {boss: {name: 'Босс', salt: 's', hash: 'x'}}};")
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(300)
    assert pg.is_visible('#loginForm') and not pg.is_visible('#bootForm')
    # сохранённая сессия рекрутера с паролем открывает кабинет сразу
    pg.add_init_script("window.__store['config/team'].people.yulia.hash = 'h'; localStorage.setItem('hrSession', JSON.stringify({role:'rec', id:'yulia'}));")
    pg.reload(); pg.wait_for_timeout(400)
    assert pg.inner_text('#meName') == 'Юля'
    pg.click('#tab_vac'); pg.wait_for_timeout(100)
    vt = pg.inner_text('#vTable'); assert 'Аналитик' in vt and 'Бухгалтер' not in vt, vt
    assert pg.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'горизонтальный скролл на телефоне'
    pg.screenshot(path=str(HERE / 'shots' / 'hr-rec-phone.png'), full_page=True)
    b.close()
print('ОШИБКИ:', errs or 'нет')
assert not errs
