# Отпуск с передачей вакансий: в дни отпуска Анны её вакансии ведёт Юлия, вакансия на паузе не считается в плане найма,
# напоминания о продлении — Юлии; после отпуска всё возвращается само. «Сегодня» — 21.10.2026.
from playwright.sync_api import sync_playwright
import pathlib, json
HERE = pathlib.Path(__file__).resolve().parent
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
seed = {
  'config/team': {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'hash': 'h', 'admin': True, 'order': 1},
                             'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'hash': 'h', 'order': 2}}},
  'vacations/anna': {'list': [{'from': '2026-10-20', 'to': '2026-10-31', 'sub': 'yulia', 'pause': ['v2']}]},
  'vacancies/v1': {'title': 'Логист', 'status': 'активна', 'manager': 'Шулятицкая', 'multi': True, 'rate': 1, 'seats': [{'requestedAt': '2026-10-01'}],
                   'links': [{'url': 'https://hh.ru/1', 'at': '2026-10-01', 'closedAt': '2026-11-01'}]},
  'vacancies/v2': {'title': 'Бухгалтер', 'status': 'активна', 'manager': 'Шулятицкая', 'multi': True, 'rate': 2, 'seats': [{'requestedAt': '2026-10-01'}, {'requestedAt': '2026-10-01'}],
                   'links': [{'url': 'https://hh.ru/2', 'at': '2026-09-23', 'closedAt': '2026-10-23'}]},
  'vacancies/v3': {'title': 'Дизайнер', 'status': 'активна', 'manager': 'Немчинова', 'multi': True, 'rate': 1, 'seats': [{'requestedAt': '2026-10-01'}]},
}
errs = []
def start(b, who, when='2026-10-21T12:00:00'):
    pg = b.new_page(viewport={'width': 1280, 'height': 1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time(when)
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('if(!sessionStorage.seeded){ sessionStorage.seeded = 1; window.__store = ' + json.dumps(seed) + '; } localStorage.setItem("hrSession", JSON.stringify({id: "' + who + '"}));')
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)
    return pg
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = start(b, 'yulia')
    # метрики дня: Логист и Бухгалтер — у Юлии; ставки Бухгалтера на паузе не считаются, его публикация — считается
    assert pg.evaluate("registryDay('yulia', '2026-10-21')") == {'vac_start': 2, 'vac_end': 2, 'cand_start': 2, 'cand_end': 2, 'vac_published': 0}
    assert pg.evaluate("registryDay('anna', '2026-10-21')") == {'vac_start': 0, 'vac_end': 0, 'cand_start': 0, 'cand_end': 0, 'vac_published': 0}
    assert pg.evaluate("registryDay('anna', '2026-10-19')")['cand_end'] == 3   # до отпуска — у Анны
    pg.click('#tab_vac'); pg.wait_for_timeout(200)
    assert 'План найма\n2' in pg.inner_text('#vTiles'), pg.inner_text('#vTiles')   # Логист 1 + Дизайнер 1; Бухгалтер на паузе
    t = pg.inner_text('#vTable')
    assert 'ведёт Юлия Немчинова до 31.10.26 — менеджер в отпуске' in t and 'пауза до 31.10.26 — менеджер в отпуске' in t, t
    assert 'в т. ч. пауза 2 дн. — менеджер в отпуске' in pg.inner_text('#vTable tr[data-id=v2]')
    assert 'Бухгалтер' in pg.inner_text('#vRemind') and 'пауза до 31.10.26' in pg.inner_text('#vRemind')   # продление напоминает Юлии
    pg.click('#tab_day'); pg.wait_for_timeout(200)
    ld = pg.inner_text('#dLoad'); assert 'Юлия Немчинова\t3\t2' in ld and 'Анна Шулятицкая\t0\t0' in ld, ld   # нагрузка — у того, кто ведёт сейчас
    # отпуска: передача и пауза меняются в строке отпуска
    pg.click('#tab_settings'); pg.click('#sub_vacation'); pg.wait_for_timeout(200)
    row = pg.inner_text('#oTable'); assert 'Передаются: Юлия Немчинова, на паузе 1 · 2 вакансии' in row, row
    pg.click('#oTable details.cover summary'); pg.uncheck('#oTable input[data-cover-pause][value=v2]'); pg.wait_for_timeout(300)
    assert 'pause' not in pg.evaluate("window.__store['vacations/anna'].list[0]")
    assert pg.is_visible('#oTable input[data-cover-pause]')   # список остаётся раскрытым после сохранения
    pg.select_option('#oTable select[data-cover-sub]', ''); pg.wait_for_timeout(300)
    assert 'sub' not in pg.evaluate("window.__store['vacations/anna'].list[0]") and pg.evaluate("ownerOn(vacancies.v1, '2026-10-21')") == 'anna'
    pg.select_option('#oTable select[data-cover-sub]', 'yulia'); pg.wait_for_timeout(300)
    # новый отпуск — сразу с передачей единственному коллеге
    pg.select_option('#oPerson', 'anna'); pg.fill('#oFrom', '2026-12-01'); pg.fill('#oTo', '2026-12-10'); pg.click('#oForm button[type=submit]'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacations/anna'].list[1]") == {'from': '2026-12-01', 'to': '2026-12-10', 'sub': 'yulia'}
    assert 'На это время вакансии ведёт Юлия Немчинова' in pg.inner_text('#oStat')
    # Анна в отпуске видит свои вакансии с пометкой, но напоминания о продлении — не ей
    a = start(b, 'anna'); a.click('#tab_vac'); a.wait_for_timeout(200)
    assert 'Логист' in a.inner_text('#vTable') and 'Бухгалтер' not in a.inner_text('#vRemind')
    # после отпуска — всё снова у Анны, пауза снята
    c = start(b, 'yulia', '2026-11-02T12:00:00')
    assert c.evaluate("ownerOn(vacancies.v2, '2026-11-02')") == 'anna' and not c.evaluate("pausedOn(vacancies.v2, '2026-11-02')")
    assert c.evaluate("registryDay('anna', '2026-11-02')")['cand_end'] == 3
    b.close()
assert not errs, errs
print('ok')
