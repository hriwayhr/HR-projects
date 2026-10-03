# HR-метрики: дашборд дня считает по команде, ввод дня подставляет начало из вчера и сохраняет
from playwright.sync_api import sync_playwright
import pathlib, json
HERE = pathlib.Path(__file__).resolve().parent
(HERE / 'shots').mkdir(exist_ok=True)
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
seed = {
  'config/team': {'people': {'yulia': {'name': 'Юля', 'order': 1}, 'anna': {'name': 'Анна', 'order': 2}}},
  'months/yulia_2026-09': {'person': 'yulia', 'month': '2026-09', 'days': {
     '2026-09-30': {'vac_end': 3, 'int_planned': 2, 'int_done': 1},
     '2026-10-01': {'vac_start': 9}}},  # чужой месяц в документе не мешает: день берётся по ключу
  'months/anna_2026-10': {'person': 'anna', 'month': '2026-10', 'days': {
     '2026-10-01': {'vac_start': 4, 'vac_end': 5, 'int_planned': 4, 'int_done': 3, 'chats': 2, 'chats_first': 1, 'hires': 1}}},
}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    for theme in ('light', 'dark'):
        pg = b.new_page(viewport={'width': 1280, 'height': 1000}, color_scheme=theme)
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.add_init_script(path=str(HERE / 'mockdb.js'))
        pg.add_init_script('window.__store = ' + json.dumps(seed) + ';')
        pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)
        pg.fill('#dDate', '2026-10-01'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(200)
        tiles = pg.inner_text('#dTiles')
        assert '3 из 4' in tiles, tiles                                  # у Юли 1 октября собесов нет
        assert '+25 п.п.' in tiles, tiles                                # доходимость 75% к 50% накануне
        assert 'Чаты\n3' in tiles, tiles                                 # чаты + первичные
        assert 'Открытые вакансии\n14' in tiles, tiles                   # 5 (конец) + 9 (начало, конца нет)
        assert '+11' in tiles, tiles                                     # вакансии: 14 к 3 накануне
        pg.screenshot(path=str(HERE / 'shots' / f'hr-day-{theme}.png'), full_page=True)
        pg.close()

    pg = b.new_page(viewport={'width': 390, 'height': 900})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('window.__store = ' + json.dumps(seed) + ';')
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)
    assert pg.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'горизонтальный скролл на телефоне'
    pg.click('#tabEntry'); pg.select_option('#fPerson', 'anna'); pg.fill('#fDate', '2026-10-02'); pg.dispatch_event('#fDate', 'change')
    assert pg.input_value('#m_vac_start') == '5', pg.input_value('#m_vac_start')   # из конца 1 октября
    pg.fill('#m_int_planned', '2'); pg.fill('#m_int_done', '2')
    pg.click('#fSave'); pg.wait_for_timeout(300)
    day = pg.evaluate("window.__store['months/anna_2026-10'].days['2026-10-02']")
    assert day == {'vac_start': 5, 'int_planned': 2, 'int_done': 2}, day
    pg.fill('#fNewName', 'Катя'); pg.click('#addPerson'); pg.wait_for_timeout(300)
    assert 'Катя' in pg.inner_text('#fPerson')
    pg.click('#tabSum'); pg.wait_for_timeout(200)
    s = pg.inner_text('#sTable')
    assert '75%' in s, s                     # неделя с 28.09: 6 прошедших из 8 назначенных
    pg.screenshot(path=str(HERE / 'shots' / 'hr-sum-phone.png'), full_page=True)
    b.close()
print('ОШИБКИ:', errs or 'нет')
assert not errs
