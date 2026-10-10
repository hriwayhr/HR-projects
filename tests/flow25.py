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
  'months/yulia_2026-10': {'person': 'yulia', 'month': '2026-10', 'days': {'2026-10-02': {'vac_start': 40, 'cand_start': 50, 'int_planned': 1},
                                                                         '2026-10-01': {'int_done': 2, 'chats': 5, 'hires': 1}}},
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
    # инфографика недели: 5–9 октября, среда и дальше — «впереди», понедельник без данных — «не внесено»
    assert pg.inner_text('#dChartTitle') == 'Неделя 41 · 5–9 октября'
    svg = pg.inner_html('#dChart svg')
    assert svg.count('впереди') == 2 and 'не внесено' in svg, svg[:300]
    assert 'Назначено\n3' in pg.inner_text('#dChart .wk-tot'), pg.inner_text('#dChart .wk-tot')
    assert not pg.query_selector('#dHero')   # блока прогресса недели нет
    # периоды: неделя / месяц / квартал / год / свой; назначено 1 (2.10) + 3 (6.10)
    def mode(m):
        pg.select_option('#dMode', m); pg.wait_for_timeout(100)
        return pg.inner_text('#dayTitle'), pg.inner_text('#dTable tfoot') if pg.query_selector('#dTable tfoot') else pg.inner_text('#dTable tbody')
    t, row = mode('week'); assert t == 'Неделя 41 · 5–9 октября' and '\t3\t' in row, (t, row)
    assert 'сравнение: неделя 40' in pg.inner_text('#dayPrev') and 'по 30.09' in pg.inner_text('#dayPrev') and 'внесено 1 из 2' in pg.inner_text('#dChips'), pg.inner_text('#dChips')
    t, row = mode('month'); assert t == 'Октябрь 2026' and '\t4\t' in row and pg.is_visible('#dMonth'), (t, row)
    assert 'нед. 40' in pg.inner_html('#dChart svg') and 'нед. 41' in pg.inner_html('#dChart svg')
    pg.click('#dPrev'); pg.wait_for_timeout(100); assert pg.inner_text('#dayTitle') == 'Сентябрь 2026'
    pg.click('#dNext'); pg.wait_for_timeout(100); assert pg.inner_text('#dayTitle') == 'Октябрь 2026' and pg.is_disabled('#dNext')
    t, row = mode('quarter'); assert t == '4 квартал 2026' and '\t4\t' in row, (t, row)
    assert pg.is_visible('#dQuarter') and pg.input_value('#dQuarter') == '2026-10-01' and pg.inner_text('#dQuarter').endswith('3 квартал 2024')
    pg.select_option('#dQuarter', '2025-04-01'); pg.wait_for_timeout(100); assert pg.inner_text('#dayTitle') == '2 квартал 2025'
    pg.select_option('#dQuarter', '2026-10-01'); pg.wait_for_timeout(100)
    t, row = mode('year'); assert t == '2026 год' and pg.inner_html('#dChart svg').count('<rect') == 2, (t, pg.inner_html('#dChart svg').count('<rect'))   # данные только за октябрь: 2 столбика
    t, row = mode('custom'); assert pg.is_visible('#dFrom') and pg.is_visible('#dTo')
    pg.fill('#dFrom', '2026-10-03'); pg.dispatch_event('#dFrom', 'change'); pg.fill('#dTo', '2026-10-06'); pg.dispatch_event('#dTo', 'change'); pg.wait_for_timeout(100)
    assert pg.inner_text('#dayTitle') == '3 октября – 6 октября 2026' and '\t3\t' in pg.inner_text('#dTable tbody'), pg.inner_text('#dTable tbody')
    pg.click('#dPrev'); pg.wait_for_timeout(100); assert pg.inner_text('#dayTitle') == '29 сентября – 2 октября 2026'
    # подробности по плитке: открывается по клику, график по неделям месяца и разбивка по людям, закрывается повторным кликом и «×»
    pg.select_option('#dMode', 'month'); pg.wait_for_timeout(100)
    pg.click('#dTiles [data-detail="Кандидаты на вакансию"]'); pg.wait_for_timeout(100)
    det = pg.inner_text('#dDetail')
    assert det.startswith('Кандидаты на вакансию · Октябрь 2026') and 'Прошлый период' in det and 'Юлия Немчинова' in det, det
    assert pg.inner_html('#dDetail svg').count('<rect') >= 2 and pg.get_attribute('#dTiles [data-detail="Кандидаты на вакансию"]', 'aria-expanded') == 'true'
    pg.click('#dTiles [data-detail="Кандидаты на вакансию"]'); pg.wait_for_timeout(100); assert pg.inner_text('#dDetail') == ''
    pg.focus('#dTiles [data-detail="Звонки"]'); pg.keyboard.press('Enter'); pg.wait_for_timeout(100)
    assert pg.inner_text('#dDetail').startswith('Звонки'); pg.click('#dDetailClose'); pg.wait_for_timeout(100); assert pg.inner_text('#dDetail') == ''
    # пиковые дни недели: сумма по дню недели, пик выделен; в режиме дня — 13 недель
    pk = pg.inner_text('#dPeak')
    assert pk.startswith('Пиковые дни недели · Октябрь 2026') and 'Собеседования — четверг' in pk and pk.index('Чаты') < pk.index('Собеседования') < pk.index('Выходы') and 'Доходимость\t—' in pk and 'Чаты — четверг' in pk and 'Выходы — четверг' in pk, pk
    assert pg.query_selector_all('#dPeak td.peak').__len__() == 3
    pg.select_option('#dMode', 'day'); pg.wait_for_timeout(100)
    assert pg.inner_text('#dPeak').startswith('Пиковые дни недели · 13 недель по '), pg.inner_text('#dPeak')
    # новая вакансия сегодня — сразу в ячейках сегодняшнего дня
    pg.click('#tab_vac'); pg.click('#vAdd'); pg.fill('#v_title', 'D'); pg.fill('#v_manager', 'Юлия Немчинова')
    pg.fill('#vLinks .v-link', 'https://hh.ru/5'); assert pg.input_value('#vLinks .v-link-at') == '2026-10-07'
    pg.click('#vSave'); pg.wait_for_timeout(300)
    d = [v for k, v in pg.evaluate('window.__store').items() if k.startswith('vacancies/') and v.get('title') == 'D'][0]
    assert d['links'] == [{'url': 'https://hh.ru/5', 'at': '2026-10-07', 'closedAt': '2026-11-07'}] and d['archivedAt'] == '2026-11-07', d   # архивация через месяц
    assert pg.evaluate("byDate['2026-10-07'].yulia") == {'vac_start': 3, 'cand_start': 3, 'vac_end': 4, 'cand_end': 4, 'vac_published': 1}, pg.evaluate("byDate['2026-10-07'].yulia")
    # снятая публикация перестаёт считаться со дня снятия
    pg.click('#vTable tr[data-id=a] td:nth-child(2)'); pg.fill('#vLinks .link-row:nth-child(1) .v-link-closed', '2026-10-07'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert pg.evaluate("byDate['2026-10-07'].yulia.vac_end") == 3
    # сводка: неделя 41 — вакантных мест (кандидаты) на последний день, новые вакансии — сумма за неделю
    pg.click('#tab_sum'); pg.wait_for_timeout(100)
    blk = pg.inner_text('#sBlocks')
    assert 'Вакантных мест (на пятницу)\t50\t4' in blk and 'Новых вакансий\t0\t2\t2' in blk, blk[:600]
    # срок публикации и продление: E уходит в архив 10.10 (через 3 дня), у F срок вышел 5.10
    base6 = pg.evaluate("registryDay('yulia', '2026-10-06')"); base7 = pg.evaluate("registryDay('yulia', '2026-10-07')")
    pg.evaluate("""window.__store['vacancies/e'] = {title: 'E', status: 'активна', manager: 'Немчинова', publishedAt: '2026-09-10', rate: 1,
        links: [{url: 'https://hh.ru/6', at: '2026-09-10', closedAt: '2026-10-10'}]};
      window.__store['vacancies/f'] = {title: 'F', status: 'активна', manager: 'Немчинова', publishedAt: '2026-09-05', rate: 1,
        links: [{url: 'https://hh.ru/7', at: '2026-09-05', closedAt: '2026-10-05'}]}; window.__notify();"""); pg.wait_for_timeout(300)
    r6 = pg.evaluate("registryDay('yulia', '2026-10-06')")
    assert r6['vac_end'] == base6['vac_end'] + 1 and r6['cand_end'] == base6['cand_end'] + 2, (base6, r6)   # F в архиве — минус из вакансий, люди нужны
    pg.click('#tab_vac'); pg.wait_for_timeout(100)
    rem = pg.inner_text('#vRemind')
    assert 'в архиве с 05.10.26' in rem and 'осталось 3 дня' in rem and rem.index('F') < rem.index('E'), rem
    pg.click('#tab_day'); pg.wait_for_timeout(100); assert 'осталось 3 дня' in pg.inner_text('#dRemind')
    pg.evaluate("""Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {write: function(items){
      return Promise.all(['text/html', 'text/plain'].map(function(t){ return items[0].getType(t).then(function(b){ return b.text(); }); }))
        .then(function(v){ window.__clip = v; }); }}});""")
    pg.click('#tab_vac'); pg.click('#vCopy'); pg.wait_for_timeout(200)
    clip = pg.evaluate('window.__clip')
    assert '\tв архиве с 05.10.26\t' in clip[1] and '#B4321F' in clip[0], clip[1]   # в отчёте по найму — подсвечено
    # «Не продлеваем»: снятая публикация не напоминает, но остаётся в истории и не считается
    pg.evaluate("""window.__store['vacancies/g'] = {title: 'G', status: 'активна', manager: 'Немчинова', publishedAt: '2026-09-01', rate: 1,
        links: [{url: 'https://hh.ru/8', at: '2026-09-01', closedAt: '2026-10-01'}]}; window.__notify();"""); pg.wait_for_timeout(200)
    pg.click('#vRemind button[data-stop=g]'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacancies/g'].links[0].stopped") is True and 'hh.ru/8' not in pg.inner_html('#vRemind')
    assert 'снята с 01.10.26' in pg.inner_text('#vTable tr[data-id=g]')
    assert 'hh.ru' not in pg.inner_text('#vTable')
    pg.click('#vTable tr[data-id=g] td:nth-child(2)'); pg.click('#vSave'); pg.wait_for_timeout(300)
    assert pg.evaluate("window.__store['vacancies/g'].links[0].stopped") is True   # пересохранение карточки отметку не теряет
    pg.click('#vCancel')
    # продление просроченной из напоминания: с сегодня на месяц, перерыв 5–7.10 не считается
    pg.click('#vRemind button[data-extend=f]'); pg.wait_for_timeout(300)
    f = pg.evaluate("window.__store['vacancies/f']")
    assert f['links'][0] == {'url': 'https://hh.ru/7', 'at': '2026-09-05', 'closedAt': '2026-11-07', 'ext': 1, 'gaps': [['2026-10-05', '2026-10-07']]} and f['extensions'] == 1, f
    assert pg.evaluate("registryDay('yulia', '2026-10-06').vac_end") == r6['vac_end']
    assert pg.evaluate("registryDay('yulia', '2026-10-07').vac_end") == base7['vac_end'] + 2
    # продление в карточке несколько месяцев подряд: 10.10 → 10.11 → 10.12
    pg.click('#vTable tr[data-id=e] td:nth-child(2)'); pg.click('#vLinks [data-extend-link]'); pg.click('#vLinks [data-extend-link]')
    assert pg.input_value('#vLinks .v-link-closed') == '2026-12-10' and 'продлений: 2' in pg.inner_text('#vLinks')
    assert pg.input_value('#v_archivedAt') == '2026-12-10' and pg.input_value('#v_extensions') == '2'
    pg.fill('#vLinks .v-link-cost', '4500')   # стоимость публикации — вручную, вместе с продлениями
    pg.click('#vSave'); pg.wait_for_timeout(300)
    e = pg.evaluate("window.__store['vacancies/e']")
    assert e['links'][0]['cost'] == 4500, e
    sp = lambda sel: pg.inner_text(sel).replace('\u00a0', ' ').replace('\u202f', ' ')   # в суммах — неразрывные пробелы
    assert '4 500 ₽' in sp('#vTable tr[data-id=e]') and 'Потрачено на hh.ru\n4 500 ₽' in sp('#vTiles'), sp('#vTiles')
    assert '4 500 ₽' in sp('#vByMgr')
    pg.click('#vRemind button[data-extend=e]') if pg.query_selector('#vRemind button[data-extend=e]') else None
    assert e['links'][0]['closedAt'] == '2026-12-10' and e['links'][0]['ext'] == 2 and e['extensions'] == 2 and e['archivedAt'] == '2026-12-10', e
    assert 'E' not in pg.inner_text('#vRemind').split('\n')[0:0] and 'осталось' not in pg.inner_text('#vRemind'), pg.inner_text('#vRemind')
    pg.screenshot(path=str(HERE / 'shots' / 'hr-vac-remind.png'), full_page=True)
    b.close()
print('ОШИБКИ:', errs or 'нет')
assert not errs
