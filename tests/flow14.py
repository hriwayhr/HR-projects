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
seed={'employees/IW-P':{'code':'IW-P','login':'аня','firstName':'Анна','lastName':'Иванова','gender':'f',
      'dept':'Клиентский сервис','email':'','personalEmail':'x@ex.com','startDate':'2026-10-05','startTime':'10:00',
      'createdAt':'2026-09-18','openedAt':'','sentAt':'','salt':salt,'hash':h,'progress':{}},
      'config/departments':{'list':[{'name':'Клиентский сервис','head':'М. Соколова','senior':'И. Ли','chat':''}]}}
errs=[]

def login(pg):
    pg.evaluate("location.hash='#exit'"); pg.wait_for_timeout(500)
    pg.fill('#gateLogin','аня'); pg.fill('#gatePass','тест')
    pg.click('#gateForm button'); pg.wait_for_timeout(1400)

with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
    pg=b.new_page(viewport={'width':1280,'height':1000})
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(path=base+'mockdb.js')
    pg.add_init_script('window.__seed='+json.dumps(seed, ensure_ascii=False)+'; Object.assign(window.__store, window.__seed);')
    pg.goto(url+'#admin'); pg.wait_for_timeout(1000)

    pg.click('#tabPage'); pg.wait_for_timeout(400)
    rows = pg.query_selector_all('#pageRows .pg-row')
    assert len(rows) >= 7, 'блоки страницы не отрисованы: %d' % len(rows)
    print('блоков в настройке:', len(rows))

    # исходный текст подсказан в поле — по нему потом сверим сброс
    default_title = pg.get_attribute('[data-field="docs.title"]', 'placeholder')
    assert default_title, 'в поле нет подсказки с текстом по умолчанию'
    print('текст по умолчанию:', default_title)

    # правим текст и скрываем «Жизнь»
    pg.fill('[data-field="docs.title"]', 'Документы к первому дню')
    pg.fill('[data-field="docs.lead"]', 'Короткий список — остальное разберём на месте.')
    pg.uncheck('[data-section="culture"]')
    pg.click('#savePage'); pg.wait_for_timeout(700)
    assert pg.is_visible('#pageSaved'), 'сохранение не подтверждено'
    print('настройки сохранены')

    login(pg)
    assert pg.inner_text('#docs h2') == 'Документы к первому дню', 'заголовок не подменён: ' + pg.inner_text('#docs h2')
    assert 'Короткий список' in pg.inner_text('#docs .lead'), 'подзаголовок не подменён'
    assert not pg.is_visible('#culture'), 'скрытый раздел всё равно виден'
    assert pg.get_attribute('.hero .nav a[href="#culture"]', 'hidden') is not None, 'ссылка на скрытый раздел осталась в навигации'
    assert pg.is_visible('#team'), 'нетронутый раздел пропал'
    print('у сотрудника: текст подменён, «Жизнь» скрыта, навигация без неё')

    # пустое поле = вернуть текст из вёрстки
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.fill('[data-field="docs.title"]', '')
    pg.check('[data-section="culture"]')
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    assert pg.inner_text('#docs h2') == default_title, 'пустое поле не вернуло исходный заголовок'
    assert pg.is_visible('#culture'), 'раздел не вернулся'
    print('пустое поле вернуло исходный текст, раздел вернулся')

    # ——— вопросы: правка, добавление, удаление, возврат исходных ———
    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    base_q = pg.eval_on_selector_all('#pageRows [data-faq^="q"]', 'e => e.map(x => x.value)')
    assert len(base_q) >= 5, 'вопросы не подставились в редактор: %d' % len(base_q)
    print('вопросов в редакторе:', len(base_q))

    pg.fill('[data-faq="q0"]', 'Во сколько приходить в первый день?')
    pg.fill('[data-faq="a0"]', 'К 10:00, точный адрес пришлёт HR-партнёр.')
    pg.click('#addFaq'); pg.wait_for_timeout(300)
    last = len(base_q)
    pg.fill('[data-faq="q%d"]' % last, 'Есть ли парковка?')
    pg.fill('[data-faq="a%d"]' % last, 'Да, по пропуску <b>оформим</b> в первый день.')
    pg.click('#savePage'); pg.wait_for_timeout(700)

    login(pg)
    qs = pg.eval_on_selector_all('#faq details summary', 'e => e.map(x => x.textContent)')
    assert qs[0] == 'Во сколько приходить в первый день?', 'правка вопроса не доехала: ' + qs[0]
    assert 'Есть ли парковка?' in qs, 'добавленный вопрос не появился'
    assert len(qs) == len(base_q) + 1, 'не то число вопросов: %d' % len(qs)
    print('у сотрудника вопросов:', len(qs), '| первый:', qs[0])
    # HR пишет текст, а не разметку: теги не должны исполняться
    marked = pg.eval_on_selector_all('#faq details .a', 'e => e.map(x => x.innerHTML)')
    hit = [x for x in marked if 'оформим' in x]
    assert hit and '<b>' not in hit[0], 'разметка из поля HR попала в страницу: ' + (hit[0] if hit else 'нет ответа')
    print('разметка в ответе экранирована')

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.click('[data-faq-del="0"]'); pg.wait_for_timeout(300)
    pg.click('#savePage'); pg.wait_for_timeout(700)
    login(pg)
    assert len(pg.query_selector_all('#faq details')) == len(base_q), 'удаление вопроса не доехало'
    print('после удаления вопросов:', len(base_q))

    pg.evaluate("location.hash='#admin'"); pg.wait_for_timeout(800)
    pg.click('#tabPage'); pg.wait_for_timeout(400)
    pg.click('#resetFaq'); pg.wait_for_timeout(300)
    pg.click('#savePage'); pg.wait_for_timeout(700)
    login(pg)
    qs2 = pg.eval_on_selector_all('#faq details summary', 'e => e.map(x => x.textContent)')
    assert qs2 == base_q, 'исходные вопросы не вернулись'
    print('«Вернуть исходные» восстановил список из вёрстки')
    b.close()
assert not errs, errs
print('ОШИБКИ:', errs or 'нет')
