# Кто уволился: в единице вакансии с причиной «увольнение сотрудника» и в метриках дня — имя подсвечивается плашкой.
from playwright.sync_api import sync_playwright
import pathlib, json
HERE = pathlib.Path(__file__).resolve().parent
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
seed = {
  'config/team': {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'hash': 'h', 'admin': True, 'order': 1},
                             'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'hash': 'h', 'order': 2}}},
  'vacancies/v1': {'title': 'Логист', 'status': 'активна', 'manager': 'Шулятицкая', 'multi': True, 'rate': 1, 'seats': [{'requestedAt': '2026-10-01'}]},
  'vacancies/v2': {'title': 'Бухгалтер', 'status': 'активна', 'manager': 'Шулятицкая', 'multi': True, 'rate': 1, 'seats': [{'requestedAt': '2026-10-02'}]},
}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width': 1280, 'height': 1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time('2026-10-21T12:00:00')
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('if(!sessionStorage.seeded){ sessionStorage.seeded = 1; window.__store = ' + json.dumps(seed) + '; } localStorage.setItem("hrSession", JSON.stringify({id: "yulia"}));')
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)

    # вакансия: поле «Кто уволился» — только при причине «увольнение сотрудника»
    pg.click('#tab_vac'); pg.evaluate("setVacStatus([])"); pg.click('#vTable tr[data-id=v1] td:nth-child(2)'); pg.wait_for_timeout(200)
    assert pg.is_hidden('#vSeats .s-leaver')
    pg.select_option('#vSeats .s-reason', 'увольнение сотрудника'); assert pg.is_visible('#vSeats .s-leaver')
    pg.fill('#vSeats .s-leaver', 'Петров Пётр'); pg.click('#vSave'); pg.wait_for_timeout(300)
    row = pg.inner_text('#vTable tr[data-id=v1]'); assert 'вместо: Петров Пётр' in row, row
    assert pg.locator('#vTable tr[data-id=v1] .pill.leaver').count() == 1
    pg.fill('#vSearch', 'петров'); pg.wait_for_timeout(200)
    assert pg.locator('#vTable tr[data-id=v1]').count() == 1 and pg.locator('#vTable tr[data-id=v2]').count() == 0
    pg.fill('#vSearch', ''); pg.wait_for_timeout(100)
    # сменили причину — имя не остаётся висеть
    pg.click('#vTable tr[data-id=v1] td:nth-child(2)'); pg.wait_for_timeout(200)
    assert pg.input_value('#vSeats .s-leaver') == 'Петров Пётр'
    pg.select_option('#vSeats .s-reason', 'новая ставка'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert 'вместо' not in pg.inner_text('#vTable tr[data-id=v1]')
    assert 'leaver' not in json.dumps(pg.evaluate("window.__store['vacancies/v1']"))

    # метрики дня: «Кто уволился» рядом с числом увольнений → имена на плитке «Увольнения»
    pg.click('#tab_entry'); pg.wait_for_timeout(200)
    pg.select_option('#fPerson', 'anna'); pg.fill('#fDate', '2026-10-20'); pg.dispatch_event('#fDate', 'change'); pg.wait_for_timeout(100)
    pg.fill('#m_dismissals', '2'); pg.fill('#m_dismissed_names', 'Иванова Ольга, Сидоров Иван'); pg.click('#fSave'); pg.wait_for_timeout(300)
    day = pg.evaluate("window.__store['months/anna_2026-10'].days['2026-10-20']")
    assert day['dismissals'] == 2 and day['dismissed_names'] == 'Иванова Ольга, Сидоров Иван', day
    pg.fill('#fDate', '2026-10-19'); pg.dispatch_event('#fDate', 'change'); pg.wait_for_timeout(100)
    assert pg.input_value('#m_dismissed_names') == ''
    pg.fill('#fDate', '2026-10-20'); pg.dispatch_event('#fDate', 'change'); pg.wait_for_timeout(100)
    assert pg.input_value('#m_dismissed_names') == 'Иванова Ольга, Сидоров Иван'
    pg.click('#tab_day'); pg.wait_for_timeout(300)
    prob = pg.inner_text('#dProb')
    assert pg.locator('#dProb .pill.leaver').count() == 2 and 'Иванова Ольга' in prob and 'Сидоров Иван' in prob, prob
    b.close()
assert not errs, errs
print('flow36 ok')
