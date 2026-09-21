# -*- coding: utf-8 -*-
# Этапы кабинета: панель слева, открытие по сроку, испытательный срок из оффера,
# закрытый этап не открывается, нумерация шагов пересчитывается.
from playwright.sync_api import sync_playwright
import pathlib, json, hashlib
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
base = str(HERE) + '/'
SRC = str(ROOT / 'src' / 'iway-welcome.html')
html = pathlib.Path(SRC).read_text(encoding='utf-8')
pathlib.Path(base+'preview.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font:14px system-ui}[hidden]{display:none!important}</style></head><body>'+html+'</body></html>', encoding='utf-8')
url='file://'+base+'preview.html'
salt='s1'; h=hashlib.sha256((salt+'::'+'тест').encode()).hexdigest()

def emp(start, probation=None):
    rec={'code':'IW-S','login':'аня','firstName':'Анна','lastName':'Иванова','gender':'f',
         'dept':'Клиентский сервис','email':'','personalEmail':'x@ex.com','startDate':start,'startTime':'10:00',
         'createdAt':'2026-08-01','openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}}
    if probation: rec['offer']={'probation':probation}
    return {'employees/IW-S':rec,
            'config/departments':{'list':[{'name':'Клиентский сервис','head':'М. Соколова','senior':'И. Ли','chat':''}]}}

errs=[]
def open_page(b, seed):
    pg=b.new_page(viewport={'width':1280,'height':900})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url); pg.wait_for_timeout(700)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    return pg

def notes(pg):
    return pg.eval_on_selector_all('.st', 'els => els.map(e => e.querySelector(".st-s").textContent)')

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')

    # ——— новичок: открыт только «до выхода», сроки остальных посчитаны
    pg = open_page(b, emp('2026-10-05', '2 месяца'))     # сегодня 19.09.2026
    assert pg.inner_text('#tbStage') == 'До выхода', 'открылся не тот этап: ' + pg.inner_text('#tbStage')
    assert not pg.is_visible('#stageDay'), 'закрытый этап показан'
    dis = pg.eval_on_selector_all('.st', 'els => els.map(e => e.getAttribute("aria-disabled"))')
    assert dis == ['false','true','true','true','true'], 'не те этапы закрыты: %s' % dis
    assert notes(pg) == ['открыт', 'с 5 октября', 'с 12 октября', 'с 4 ноября', 'с 5 декабря'], \
        'сроки этапов посчитаны не так: %s' % notes(pg)
    print('новичок:', ' | '.join(notes(pg)))

    # закрытый этап не открывается
    pg.click('.st[data-stage="day"]', force=True); pg.wait_for_timeout(500)
    assert pg.inner_text('#tbStage') == 'До выхода', 'закрытый этап всё-таки открылся'
    assert pg.is_visible('#stagePre'), 'этап «до выхода» пропал'
    print('клик по закрытому этапу ничего не меняет')

    # содержание закрытых этапов лежит в DOM, но не видно; отметки считаются
    assert pg.inner_text('#hpDocs') == '0 из 4', 'плитка документов сбилась: ' + pg.inner_text('#hpDocs')
    assert pg.eval_on_selector_all('#dayList .check', 'els => els.length') == 5, 'план первого дня потерялся'
    for sec in ['plan', 'week', 'month', 'prob']:
        assert not pg.is_visible('#' + sec), 'этап «%s» виден до срока' % sec
    print('этапы до срока скрыты, план первого дня на месте')
    pg.close()

    # ——— вышел месяц назад: открыты «1-й день» и «неделя», срок ИС — 2 месяца
    pg = open_page(b, emp('2026-09-01', '2 месяца'))
    n = notes(pg)
    assert n[1].startswith('открыт') and n[2].startswith('открыт'), 'этапы не открылись по сроку: %s' % n
    assert n[3] == 'с 1 октября' and n[4] == 'с 1 ноября', 'сроки месяца и ИС посчитаны не так: %s' % n
    print('вышел месяц назад:', ' | '.join(n))

    # по умолчанию — последний доступный этап
    assert pg.inner_text('#tbStage') == 'Первая неделя', 'открылся не последний доступный этап: ' + pg.inner_text('#tbStage')
    assert pg.is_visible('#week') and not pg.is_visible('#plan'), 'показан не тот этап'
    assert pg.eval_on_selector('#week .stage-when', 'e => e.textContent') == 'Этап с 8 сентября', \
        'срок первой недели в карточке не тот: ' + pg.eval_on_selector('#week .stage-when', 'e => e.textContent')
    print('по умолчанию открыт последний доступный этап, срок в карточке на месте')

    pg.click('.st[data-stage="day"]'); pg.wait_for_timeout(700)
    assert pg.inner_text('#tbStage') == '1-й день', 'этап не переключился'
    assert pg.is_visible('#plan') and not pg.is_visible('#week'), 'панели этапов не переключились'
    assert pg.eval_on_selector_all('#dayList .check', 'els => els.length') == 5, 'план первого дня потерялся'
    print('переключение этапов работает')

    # содержание разнесено по этапам: неделя, месяц, 60–90
    parts = pg.evaluate("""() => {
      const at = id => {
        const box = document.querySelector(id);
        return box ? {n: box.querySelectorAll('li').length, stage: box.closest('.stage').id} : null;
      };
      return {week: at('#planWeek'), month: at('#planMonths'), prob: at('#planProb')};
    }""")
    for key, stage in [('week', 'stageWeek'), ('month', 'stageMonth'), ('prob', 'stageProb')]:
        got = parts[key]
        assert got, 'список «%s» пропал со страницы' % key
        assert got['stage'] == stage, 'список «%s» лежит в этапе %s, а не %s' % (key, got['stage'], stage)
        assert got['n'], 'список «%s» пуст' % key
    print('списки по этапам: неделя %s · месяц %s · 60–90 %s'
          % (parts['week']['n'], parts['month']['n'], parts['prob']['n']))
    pg.close()

    # ——— срок не указан — считаем стандартные три месяца
    pg = open_page(b, emp('2026-09-01'))
    assert notes(pg)[4] == 'с 1 декабря', 'без срока в оффере ИС посчитан не как 3 месяца: %s' % notes(pg)[4]
    print('без срока в оффере: испытательный срок 3 месяца —', notes(pg)[4])
    pg.close()

    # ——— HR скрыл шаг: нумерация пересчитывается без дырки
    pg = open_page(b, emp('2026-10-05'))
    nums = pg.eval_on_selector_all('#stagePre section[data-step] .s-num', 'els => els.map(e => e.textContent)')
    assert nums == ['01','02','03','04','05','06'], 'нумерация до правки: %s' % nums
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(900)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.uncheck('[data-section="dress"]'); pg.click('#savePage'); pg.wait_for_timeout(700)
    pg.evaluate("location.hash='#exit'"); pg.wait_for_timeout(500)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест'); pg.click('#gateForm button'); pg.wait_for_timeout(1400)
    assert not pg.is_visible('#dress'), 'скрытый шаг остался виден'
    vis = pg.eval_on_selector_all('#stagePre section[data-step]:not([hidden]) .s-num', 'els => els.map(e => e.textContent)')
    assert vis == ['01','02','03','04','05'], 'нумерация не пересчиталась: %s' % vis
    print('скрытый шаг: нумерация', ' · '.join(vis))
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
