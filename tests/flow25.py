# Синхронизация «Вакансий» с ежедневными метриками: с SYNC_FROM (5.10.2026) «вакансии» = публикации hh.ru,
# «кандидаты» = сколько человек нужно, «новые вакансии» = публикации, открытые в этот день. «Сегодня» — 7.10.2026.
from playwright.sync_api import sync_playwright
import pathlib, json
HERE = pathlib.Path(__file__).resolve().parent
html = (HERE.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
prev = HERE / 'preview-hr.html'
prev.write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + html + '</body></html>', encoding='utf-8')
seed = {
  'config/team': {'people': {'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'y', 'hash': 'h', 'admin': True}}},
  'months/yulia_2026-10': {'person': 'yulia', 'month': '2026-10', 'days': {'2026-10-02': {'vac_start': 40, 'cand_start': 50, 'int_planned': 1}}},
  # A: две публикации (вторая открыта 6.10), нужно 2
  'vacancies/a': {'title': 'A', 'status': 'активна', 'manager': 'Немчинова', 'publishedAt': '2026-10-01', 'rate': 2,
                  'links': [{'url': 'https://hh.ru/1', 'at': '2026-10-01'}, {'url': 'https://hh.ru/2', 'at': '2026-10-06'}]},
  # B: несколько ставок — первая единица вышла 6.10, вторую запросили 6.10; старая ссылка строкой
  'vacancies/b': {'title': 'B', 'status': 'активна', 'manager': 'Немчинова', 'publishedAt': '2026-09-20', 'link': 'https://hh.ru/3',
                  'multi': True, 'rate': 1, 'seats': [{'requestedAt': '2026-09-20', 'startAt': '2026-10-06'}, {'requestedAt': '2026-10-06'}]},
  # C: закрыта 6.10
  'vacancies/c': {'title': 'C', 'status': 'выход сотрудника', 'manager': 'Немчинова', 'publishedAt': '2026-09-01', 'closedAt': '2026-10-06', 'link': 'https://hh.ru/4', 'rate': 1},
}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg = b.new_page(viewport={'width': 1280, 'height': 1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time('2026-10-07T12:00:00')
    pg.add_init_script(path=str(HERE / 'mockdb.js'))
    pg.add_init_script('window.__store = ' + json.dumps(seed) + '; localStorage.setItem("hrSession", JSON.stringify({id: "yulia"}));')
    pg.goto('file://' + str(prev)); pg.wait_for_timeout(500)
    r = pg.evaluate("registryDay('yulia', '2026-10-06')")
    assert r == {'vac_start': 3, 'cand_start': 4, 'vac_end': 3, 'cand_end': 3, 'vac_published': 1}, r
    # до SYNC_FROM — как вносили; с него — из реестра, даже если день ещё не внесён
    assert pg.evaluate("byDate['2026-10-02'].yulia.vac_start") == 40
    assert pg.evaluate("byDate['2026-10-05'].yulia.vac_end") == 3 and pg.evaluate("dayStatus('yulia', '2026-10-05')") == 'missing'
    # форма: синхронные поля только для чтения, в базу не пишутся
    pg.click('#tab_entry'); pg.select_option('#fPerson', 'yulia'); pg.fill('#fDate', '2026-10-06'); pg.dispatch_event('#fDate', 'change')
    assert pg.input_value('#m_vac_end') == '3' and pg.input_value('#m_cand_start') == '4' and pg.input_value('#m_vac_published') == '1'
    assert pg.evaluate("$('m_vac_end').readOnly") and not pg.evaluate("$('m_int_planned').readOnly")
    assert 'из «Вакансий»' in pg.inner_text('#fStatus')
    pg.fill('#m_int_planned', '3'); pg.click('#fSave'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['months/yulia_2026-10'].days['2026-10-06']") == {'int_planned': 3}
    pg.click('#tab_day'); pg.fill('#dDate', '2026-10-06'); pg.dispatch_event('#dDate', 'change'); pg.wait_for_timeout(100)
    t = pg.inner_text('#dTiles'); assert 'Открытые вакансии\n3' in t and 'Кандидаты на вакансию\n3' in t, t
    # новая вакансия сегодня — сразу в ячейках сегодняшнего дня
    pg.click('#tab_vac'); pg.click('#vAdd'); pg.fill('#v_title', 'D'); pg.fill('#v_manager', 'Юлия Немчинова')
    pg.fill('#vLinks .v-link', 'https://hh.ru/5'); assert pg.input_value('#vLinks .v-link-at') == '2026-10-07'
    pg.click('#vSave'); pg.wait_for_timeout(300)
    d = [v for k, v in pg.evaluate('window.__store').items() if k.startswith('vacancies/') and v.get('title') == 'D'][0]
    assert d['links'] == [{'url': 'https://hh.ru/5', 'at': '2026-10-07'}], d
    assert pg.evaluate("byDate['2026-10-07'].yulia") == {'vac_start': 3, 'cand_start': 3, 'vac_end': 4, 'cand_end': 4, 'vac_published': 1}, pg.evaluate("byDate['2026-10-07'].yulia")
    # снятая публикация перестаёт считаться со дня снятия
    pg.click('#vTable tr[data-id=a] td:nth-child(2)'); pg.fill('#vLinks .link-row:nth-child(1) .v-link-closed', '2026-10-07'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert pg.evaluate("byDate['2026-10-07'].yulia.vac_end") == 3
    # сводка: неделя 41 — вакантных мест (кандидаты) на последний день, новые вакансии — сумма за неделю
    pg.click('#tab_sum'); pg.wait_for_timeout(100)
    blk = pg.inner_text('#sBlocks')
    assert 'Вакантных мест (на пятницу)\t50\t4' in blk and 'Новых вакансий\t0\t2\t2' in blk, blk[:600]
    b.close()
print('ОШИБКИ:', errs or 'нет')
assert not errs
