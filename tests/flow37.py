# Дашборд: период (вкладки год → день, окошко выбора), плитки команды, «По рекрутерам» по людям с подкраской отклонений,
# панель по дням по клику на имя, «Нужно сделать» и «Главное за период». «Сегодня» — 21.10.2026.
from playwright.sync_api import sync_playwright
import pathlib, json
HERE = pathlib.Path(__file__).resolve().parent
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
def month(days, f):   # будни месяца → цифры дня
    out = {}
    for d in days: out[d] = f(d)
    return out
SEP = ['2026-09-%02d' % d for d in range(1, 22) if d not in (5, 6, 12, 13, 19, 20)]
OCT = ['2026-10-%02d' % d for d in range(1, 22) if d not in (3, 4, 10, 11, 17, 18)]
seed = {
  'config/team': {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'hash': 'h', 'admin': True, 'recruiter': True, 'order': 1, 'since': '2026-09-01'},
                             'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'a', 'hash': 'h', 'recruiter': True, 'order': 2, 'since': '2026-09-01'}}},
  'months/yulia_2026-09': {'person': 'yulia', 'month': '2026-09', 'days': month(SEP, lambda d: {'int_planned': 5, 'int_done': 4, 'calls': 10})},
  'months/yulia_2026-10': {'person': 'yulia', 'month': '2026-10', 'days': month(OCT, lambda d: {'int_planned': 5, 'int_done': 4, 'calls': 10, 'hires': 1 if d == '2026-10-09' else 0})},
  'months/anna_2026-09': {'person': 'anna', 'month': '2026-09', 'days': month(SEP, lambda d: {'int_planned': 5, 'int_done': 5, 'calls': 9})},
  # октябрь у Анны: доходимость ниже (2 из 5), 15.10 — 35 звонков, 16.10 — 0, 20.10 не внесён
  'months/anna_2026-10': {'person': 'anna', 'month': '2026-10', 'days': month([d for d in OCT if d != '2026-10-20'],
      lambda d: {'int_planned': 5, 'int_done': 2, 'calls': 35 if d == '2026-10-15' else 0 if d == '2026-10-16' else 9})},
}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width': 1300, 'height': 1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time('2026-10-21T18:05:00')
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('if(!sessionStorage.seeded){ sessionStorage.seeded = 1; window.__store = ' + json.dumps(seed) + '; } localStorage.setItem("hrSession", JSON.stringify({id: "yulia"}));')
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)

    # месяц: вкладка открывает окошко, Esc — закрывает; плитки — команда, таблица — люди (без столбца «Команда»)
    pg.click('#dModes [data-mode=month]'); assert pg.is_visible('#dPop'); pg.keyboard.press('Escape'); assert pg.is_hidden('#dPop')
    assert pg.inner_text('#dayTitle') == 'Октябрь 2026' and 'идёт — по 21.10' in pg.inner_text('#dayPrev')
    head = pg.inner_text('#dTable thead'); assert 'Команда' not in head and '15 из 15 дней' in head and '14 из 15 дней' in head, head
    tiles = pg.inner_text('#dTiles'); assert 'Собеседования прошли' in tiles, tiles
    # заметное падение у Анны подкрашено, необычные дни отмечены точкой
    assert 'bad' in pg.get_attribute('#dTable tr:has-text("Собеседования") td:nth-child(3)', 'class')
    assert pg.locator('#dTable tr:has-text("Звонки") td:nth-child(3) .odd').count() == 1 and pg.locator('#dTable tr:has-text("Звонки") td:nth-child(2) .odd').count() == 0
    # «Главное за октябрь»: сначала плохое, потом что проверить
    now = pg.inner_text('#dNow')
    assert now.startswith('Главное за октябрь') and 'Анна: доходимость 40%' in now and 'было 100%' in now and 'Проверьте данные' in now and 'Анна, 15.10: 35 звонков' in now, now
    assert now.index('доходимость') < now.index('Проверьте данные')
    # «Нужно сделать»: подсвечено, пропуск Анны 20.10 — с кнопкой
    assert 'calm' not in pg.get_attribute('#dTodo', 'class') and pg.query_selector('#dTodo button.miss[data-p=anna][data-d="2026-10-20"]')

    # панель по дням: строки — показатели, столбцы — даты; 35 звонков — красным, 20.10 — пропуск; ✎ → «Внести день»
    pg.click('#dTable .who[data-days=anna]'); pg.wait_for_selector('#dDays .ddrawer')
    assert '20.10' in pg.inner_text('#dDays thead') and 'не внесено: 20.10' in pg.inner_text('#dDays header')
    assert pg.locator('#dDays td.out', has_text='35').count() == 1 and pg.locator('#dDays td.out', has_text='0').count() >= 1
    pg.keyboard.press('Escape'); assert not pg.query_selector('#dDays')
    pg.click('#dTable .who[data-days=anna]'); pg.click('#dDays [data-ed="2026-10-15"]'); pg.wait_for_timeout(100)
    assert pg.is_visible('#viewEntry') and pg.input_value('#fDate') == '2026-10-15' and pg.input_value('#m_calls') == '35'
    pg.fill('#m_calls', '9'); pg.click('#fSave'); pg.wait_for_timeout(300)

    # день: окошко — календарь; «внесено в 18:05» у только что сохранённого дня
    pg.click('#tab_day'); pg.click('#dModes [data-mode=day]'); assert pg.is_visible('#dPop .pcal')
    assert pg.is_disabled('#dPop .pcal button:has-text("18")')   # воскресенье
    pg.click('#dPop [data-pick="2026-10-15"]'); pg.wait_for_timeout(100)
    assert pg.inner_text('#dayTitle').startswith('15 октября') and 'внесено в 18:05' in pg.inner_text('#dTable thead'), pg.inner_text('#dTable thead')
    # неделя: окошко со строками-неделями, листается по месяцам; будущее недоступно
    pg.click('#dModes [data-mode=week]'); pg.click('#dPop [data-pview="2026-09-01"]')
    assert 'Сентябрь 2026' in pg.inner_text('#dPop') and pg.is_disabled('#dPop [data-pview][aria-label="Вперёд"]') is False
    pg.click('#dPop [data-pick="2026-09-07"]'); pg.wait_for_timeout(100)
    assert pg.inner_text('#dayTitle').startswith('Неделя 37'), pg.inner_text('#dayTitle')
    assert pg.is_disabled('#dNext') is False
    pg.click('#dModes [data-mode=year]'); assert pg.is_disabled('#dPop [data-pick="2027-01-01"]') if pg.query_selector('#dPop [data-pick="2027-01-01"]') else True
    pg.keyboard.press('Escape'); assert pg.inner_text('#dayTitle') == '2026 год' and pg.is_disabled('#dNext')
    b.close()
assert not errs, errs
print('flow37 ok')
