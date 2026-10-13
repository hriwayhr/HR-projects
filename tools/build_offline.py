#!/usr/bin/env python3
"""Собирает версию HR-метрик для ПК — один HTML, который открывается двойным щелчком
без claude.ai и без интернета и носит данные в себе. Принцип — как у офлайн-версии
«Миссии выполнимой» (ветка claude/brave-goodall-su1lxt, tools/build_offline.py).

Как живут данные:
  * команда, метрики, вакансии, отпуска и отказы вшиты в сам файл (SEED);
  * изменения сразу пишутся в хранилище браузера этого ПК (localStorage);
  * «Подключить файл» (Chrome/Edge, File System Access API): дальше страница сама записывает
    изменения в файл и каждые несколько секунд перечитывает его, сливая правки коллег по полям —
    так с одним файлом в общей папке могут работать несколько человек одновременно;
    в других браузерах скачивается обновлённая копия файла.
  * Файл умеет пересобрать себя: в нём лежит его же шаблон (TEMPLATE).

Запуск:  python3 tools/build_offline.py <каталог-снимка-базы> [выходной.html]
         python3 tools/build_offline.py --update [выходной.html]   — обновление программы без данных:
         открыть его и «Подключить файл» с рабочим файлом — данные берутся из рабочего файла, программа
         в нём заменяется на новую (VERSION — время сборки; файл новее открытой вкладки не перезаписывается).
Снимок — каталог вида <коллекция>/<документ>.json (как сохраняет ArtifactData с out_dir).
"""
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "hr-metrics.html"

# __SEED__ и __TEMPLATE__ должны встречаться в шаблоне впервые именно здесь
SHIM = r"""<script>
/* версия для ПК: данные в самом файле + localStorage этого ПК вместо общей базы claude.ai.
   Совместная работа: файл лежит в общей папке, каждый подключает его (Chrome/Edge). Страница раз в
   несколько секунд перечитывает файл, сливает чужие изменения со своими по полям и записывает результат. */
(function () {
  var SEED = __SEED__;
  var TEMPLATE = __TEMPLATE__;
  var VERSION = __VERSION__;                                  // время сборки программы
  var KEY = "hr-offline-db", POLL = window.__hrPoll || 5000;
  var local = null, handle = null, linked = false, error = "", timer = null, busy = null, subs = [];
  try { local = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}

  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(local)); }
    catch (e) { error = "Браузеру не хватает места на этом ПК. Подключите файл, чтобы сохранить изменения."; }
  }
  function changed() { bar(); }
  function copy(o) { return o === undefined ? undefined : JSON.parse(JSON.stringify(o)); }
  function isObj(o) { return o !== null && typeof o === "object" && !Array.isArray(o); }
  // сравнение без учёта порядка ключей
  function canon(o) { return isObj(o) ? "{" + Object.keys(o).sort().map(function (k) { return JSON.stringify(k) + ":" + canon(o[k]); }).join(",") + "}" : Array.isArray(o) ? "[" + o.map(canon).join(",") + "]" : JSON.stringify(o === undefined ? null : o); }
  function same(a, b) { return canon(a) === canon(b); }
  function esc(json) { return json.replace(/</g, "\\u003c"); }
  function makeFile(seed) {
    return TEMPLATE
      .replace("__SEED__", function () { return esc(JSON.stringify(seed)); })
      .replace("__TEMPLATE__", function () { return esc(JSON.stringify(TEMPLATE)); });
  }
  function readSeed(text) {
    var a = text.indexOf("var SEED = "), z = text.indexOf(";\n  var TEMPLATE = ");
    if (a < 0 || z < 0) throw { bad: true };
    return JSON.parse(text.slice(a + 11, z));
  }
  // файл обновления: программа без данных — данные придут из подключённого рабочего файла
  function isUpdate() { return !local.data["config/team"]; }
  var UPDATE_HINT = "Это обновление программы, данных в нём нет. Нажмите «Подключить файл» и выберите ваш рабочий файл с данными — данные появятся здесь, а программа в рабочем файле обновится.";
  function fmt(t) { return new Date(t).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }); }

  /* слияние трёх версий: base — как было до моей правки, mine — моя, theirs — сейчас в файле.
     Поменял только я — берём моё, только коллега — его, оба разные поля — оба.
     Одно и то же поле: побеждает более поздняя правка — моя, пока она не записана (tw = false),
     и чужая, если моя уже была в файле и её поменяли после (tw = true). */
  function merge3(b, m, t, tw) {
    if (same(m, b)) return copy(t);
    if (same(t, b) || same(t, m)) return copy(m);
    if (isObj(m) && isObj(t)) {
      var bo = isObj(b) ? b : {}, out = {}, keys = {};
      [bo, m, t].forEach(function (o) { Object.keys(o).forEach(function (k) { keys[k] = 1; }); });
      Object.keys(keys).forEach(function (k) { var v = merge3(bo[k], m[k], t[k], tw); if (v !== undefined) out[k] = v; });
      return out;
    }
    return copy(tw ? t : m);
  }
  /* мои правки: pending — путь → {base, mid?, mine}. base — документ до моих правок, mid — то, что я уже
     записал в файл (ещё не подтверждено чтением), mine — текущее. Записанный слой (base → mid) при конфликте
     уступает более поздней чужой правке, а если его затёрли одновременной записью — возвращается;
     незаписанный (mid → mine) побеждает. */
  function written(x) { return "mid" in x; }
  function mergeOne(x, t) {
    if (!written(x)) return merge3(x.base, x.mine, t, false);
    return merge3(x.mid, x.mine, merge3(x.base, x.mid, t, true), false);
  }
  function applyPending(theirs) {
    var out = copy(theirs);
    Object.keys(local.pending).forEach(function (p) { var v = mergeOne(local.pending[p], theirs[p]); if (v === undefined) delete out[p]; else out[p] = v; });
    return out;
  }
  function diff(a, b) { var ks = {}; Object.keys(a).concat(Object.keys(b)).forEach(function (k) { ks[k] = 1; }); return Object.keys(ks).filter(function (k) { return !same(a[k], b[k]); }); }

  if (!local || !local.data) local = { pending: {} };
  if (local.changed && !local.pending) {                     // правки из прежней версии файла для ПК
    local.pending = {};
    local.changed.forEach(function (p) { local.pending[p] = { base: copy(SEED.data[p]), mine: copy(local.data[p]) }; });
  }
  local.pending = local.pending || {}; delete local.changed; delete local.fileStamp; delete local.dirty;
  local.data = applyPending(SEED.data);
  persist();
  var ready = Promise.resolve();

  /* подключённый файл запоминается между запусками (Chrome/Edge) */
  function idb(mode, val) {
    return new Promise(function (ok) {
      try {
        var r = indexedDB.open("hr-offline", 1);
        r.onupgradeneeded = function () { r.result.createObjectStore("h"); };
        r.onsuccess = function () {
          try { var st = r.result.transaction("h", mode).objectStore("h"); var q = mode === "readonly" ? st.get("file") : st.put(val, "file"); }
          catch (e) { ok(null); return; }
          q.onsuccess = function () { ok(q.result); }; q.onerror = function () { ok(null); };
        };
        r.onerror = function () { ok(null); };
      } catch (e) { ok(null); }
    });
  }
  var canLink = typeof window.showOpenFilePicker === "function";
  if (canLink) idb("readonly").then(function (h) {
    if (!h) return;
    handle = h;
    h.queryPermission({ mode: "readwrite" }).then(function (p) { if (p === "granted") start(); else changed(); }, function () {});
  });

  function writeData(data) {
    var html = makeFile({ stamp: Date.now(), data: data });
    return handle.createWritable().then(function (w) { return w.write(html).then(function () { return w.close(); }); });
  }
  // прочитать файл → слить → записать, если в нём не хватает моих правок → показать чужие
  function sync() {
    if (!linked) return Promise.resolve();
    if (busy) return busy;
    busy = handle.getFile().then(function (f) { return f.text(); }).then(function (text) {
      var fileVer = +((text.match(/var VERSION = (\d+);/) || [])[1] || 0);
      if (fileVer > VERSION) {                                 // файл уже записан более новой программой — не откатываем
        clearInterval(poller); linked = false; error = "Файл обновлён до новой версии программы — перезагрузите страницу (F5)."; changed();
        return;
      }
      var theirs = readSeed(text).data, merged = applyPending(theirs);
      // записанный слой, который файл уже содержит (или который после поменяли), больше не ждёт
      Object.keys(local.pending).forEach(function (p) {
        var x = local.pending[p];
        if (!written(x) || !same(merge3(x.base, x.mid, theirs[p], true), theirs[p])) return;
        if (same(x.mine, x.mid)) delete local.pending[p]; else { x.base = x.mid; delete x.mid; }
      });
      var sent = {}; Object.keys(local.pending).forEach(function (p) { sent[p] = canon(local.pending[p].mine); });
      return (same(merged, theirs) && fileVer === VERSION ? Promise.resolve() : writeData(merged)).then(function () {
        // отмечаем записанное; удалим, когда следующее чтение покажет его в файле — если коллега затёр его
        // одновременной записью, оно вернётся
        Object.keys(sent).forEach(function (p) { var x = local.pending[p]; if (x && canon(x.mine) === sent[p]) x.mid = copy(x.mine); });
        var view = applyPending(merged), ch = diff(local.data, view);
        local.data = view; local.syncedAt = Date.now(); error = ""; persist();
        if (ch.length) notify(ch);
        changed();
      });
    }).catch(function (e) {
      linked = false; clearInterval(poller);
      if (e && e.bad) { handle = null; error = "Выбран не тот файл: нужен рабочий файл HR-метрик с данными (HTML-файл, в котором вы работаете)."; }
      else error = "Нет доступа к файлу — нажмите «Подключить файл» и разрешите изменение.";
      changed();
    }).then(function () { busy = null; });
    return busy;
  }
  var poller = null;
  function start() { linked = true; error = ""; clearInterval(poller); poller = setInterval(sync, POLL); return sync(); }
  var NO_ACCESS = "Браузер не даёт этой странице работать с файлами. Откройте файл двойным щелчком в Chrome или Edge (не внутри другого приложения) — или обновите через «Загрузить рабочий файл».";
  function link() {
    error = ""; note = "Открываю выбор файла…"; changed();
    var stored = !!handle, pick;
    try {
      pick = stored
        ? handle.requestPermission({ mode: "readwrite" }).then(function (p) { if (p !== "granted") throw new Error("denied"); })
        : window.showOpenFilePicker({ types: [{ description: "HR-метрики", accept: { "text/html": [".html"] } }] })
            .then(function (hs) { handle = hs[0]; return handle.requestPermission({ mode: "readwrite" }); })
            .then(function (p) { if (p !== "granted") throw new Error("denied"); return idb("readwrite", handle); });
    } catch (e) { pick = Promise.reject({ blocked: true }); }                 // открыт внутри другого приложения, доступ к файлам выключен политикой
    return pick.then(function () { note = ""; return start(); }, function (e) {
      note = "";
      if (stored) handle = null;                                 // запомненный файл недоступен (перенесли, удалили) — выбрать заново
      if (!(e && e.name === "AbortError")) error = e && e.blocked ? NO_ACCESS : stored ? "Не удалось открыть прежний файл. Нажмите «Подключить файл» ещё раз и выберите рабочий файл."
        : e && e.name === "SecurityError" && window.top === window ? "Браузер не открывает файлы из этой папки. Перенесите рабочий файл, например, в «Документы» или на общий диск и подключите снова."
        : e && /denied/.test(e.message || "") ? "Браузер не дал доступ к файлу. Нажмите «Подключить файл» ещё раз и разрешите изменение файла."
        : NO_ACCESS;
      changed();
    });
  }
  /* запасной путь без доступа к файлам: прочитать рабочий файл обычной загрузкой и скачать
     новый файл — программа отсюда, данные оттуда плюс несохранённое с этого ПК */
  var note = "";
  function loadWork(f) {
    error = "";
    return f.text().then(function (text) {
      var merged = applyPending(readSeed(text).data);
      if (!merged["config/team"]) throw { bad: true };
      var url = URL.createObjectURL(new Blob([makeFile({ stamp: Date.now(), data: merged })], { type: "text/html" }));
      var a = document.createElement("a"); a.href = url; a.download = "HR-метрики.html"; document.body.append(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      var ch = diff(local.data, merged); local.data = merged; persist(); if (ch.length) notify(ch);
      note = "Готово: скачан файл «HR-метрики.html» с вашими данными и новой программой. Замените им рабочий файл (старый сохраните как копию).";
      changed();
    }).catch(function () { error = "Выбран не тот файл: нужен рабочий файл HR-метрик с данными."; changed(); });
  }
  function download() {                                      // браузеры без доступа к файлам: скачать копию с данными
    var url = URL.createObjectURL(new Blob([makeFile({ stamp: Date.now(), data: local.data })], { type: "text/html" }));
    var a = document.createElement("a"); a.href = url; a.download = "HR-метрики.html"; document.body.append(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    local.pending = {}; persist(); changed();
  }
  function save() { return canLink ? (linked ? sync() : link()) : (download(), Promise.resolve()); }
  function schedule() { if (!linked) return; clearTimeout(timer); timer = setTimeout(sync, 800); }

  function snap(p) { var d = local.data[p]; return { id: p.split("/").pop(), exists: !!d, data: function () { return d ? copy(d) : undefined; } }; }
  function query(c) {
    var n = c.split("/").length + 1;
    var docs = Object.keys(local.data).filter(function (p) { return p.indexOf(c + "/") === 0 && p.split("/").length === n; }).sort().map(snap);
    return { docs: docs, size: docs.length, empty: !docs.length };
  }
  function fire(s) { s.cb(s.p ? snap(s.p) : query(s.c)); }
  function notify(paths) { subs.slice().forEach(function (s) { if (paths.some(function (p) { return s.p ? s.p === p : p.indexOf(s.c + "/") === 0; })) fire(s); }); }
  function write(p, d) {
    if (!(p in local.pending)) local.pending[p] = { base: copy(local.data[p]) };
    local.pending[p].mine = copy(d);
    if (d === undefined) delete local.data[p]; else local.data[p] = copy(d);
    persist(); notify([p]); changed(); schedule();
    return Promise.resolve();
  }
  function listen(s) { subs.push(s); ready.then(function () { setTimeout(function () { fire(s); }); }); return function () { subs.splice(subs.indexOf(s), 1); }; }
  function doc(p) { return {
    id: p.split("/").pop(),
    get: function () { return Promise.resolve(snap(p)); },
    set: function (d) { return write(p, d); },
    update: function (d) { return local.data[p] ? write(p, Object.assign({}, local.data[p], copy(d))) : Promise.reject({ code: "not_found" }); },
    delete: function () { return write(p, undefined); },
    onSnapshot: function (cb) { return listen({ p: p, cb: cb }); }
  }; }
  var db = {
    doc: doc,
    collection: function (c) { return {
      doc: function (id) { return doc(c + "/" + (id || "v" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8))); },
      get: function () { return Promise.resolve(query(c)); },
      onSnapshot: function (cb) { return listen({ c: c, cb: cb }); }
    }; }
  };
  var downloads = { save: function (r) {
    var url = URL.createObjectURL(r.data instanceof Blob ? r.data : new Blob([r.data]));
    var a = document.createElement("a"); a.href = url; a.download = r.filename; document.body.append(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    return Promise.resolve({ status: "saved" });
  } };

  /* плашка внизу: файл не подключён / есть несохранённое / ошибка; Ctrl+S; вопрос при закрытии с несохранённым */
  var barEl = null;
  function pending() { return Object.keys(local.pending).length; }
  function bar() {
    if (!document.body) return;
    var show = !linked && (canLink || pending() > 0 || isUpdate()) || !!error || !!note;
    if (!barEl) {
      barEl = document.createElement("div"); barEl.id = "offlineBar"; barEl.setAttribute("role", "status");
      barEl.style.cssText = "position:fixed;left:0;right:0;bottom:0;z-index:30;display:flex;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;" +
        "padding:10px 16px calc(env(safe-area-inset-bottom,0px) + 10px);background:var(--surface);color:var(--ink);border-top:2px solid var(--accent);box-shadow:0 -6px 20px #0003;font-size:14px";
      barEl.addEventListener("click", function (e) {
        var btn = e.target.closest("button"); if (!btn) return;
        if (btn.dataset.load) { var inp = document.createElement("input"); inp.type = "file"; inp.accept = ".html,text/html"; inp.onchange = function () { if (inp.files[0]) loadWork(inp.files[0]); }; inp.click(); return; }
        save().catch(function () {});
      });
      document.body.append(barEl);
    }
    barEl.hidden = !show;
    document.documentElement.style.paddingBottom = show ? "64px" : "";
    if (!show) return;
    var loadBtn = isUpdate() || error ? "<button class=\"btn ghost\" type=\"button\" data-load=\"1\">Загрузить рабочий файл</button>" : "";
    if (note) { barEl.innerHTML = "<span><b>" + note + "</b></span>" + (/^Готово/.test(note) ? "" : loadBtn); return; }
    barEl.innerHTML = error ? "<span>" + error + "</span>" + (canLink ? "<button class=\"btn\" type=\"button\">Подключить файл</button>" : "") + loadBtn
      : canLink ? "<span>" + (isUpdate() ? "<b>" + UPDATE_HINT + "</b>" : (pending() ? "<b>Есть несохранённые изменения.</b> " : "") + "Подключите этот файл, чтобы сохранять изменения и видеть правки коллег.") + "</span>" +
          "<button class=\"btn\" type=\"button\">Подключить файл</button>" + loadBtn + "<small style=\"opacity:.7\">Ctrl+S</small>"
      : isUpdate() ? "<span><b>Это обновление программы.</b> Выберите ваш рабочий файл — скачается он же с новой программой.</span>" + loadBtn
      : "<span><b>Есть несохранённые изменения.</b> Этот браузер не умеет сохранять в файл — скачайте копию (совместная работа — в Chrome или Edge).</span>" +
          "<button class=\"btn\" type=\"button\">Скачать файл с данными</button>";
  }
  window.addEventListener("DOMContentLoaded", function () {
    var w = document.getElementById("bootWait");                // вместо «Администраторов ещё нет»
    if (w && isUpdate()) w.textContent = canLink ? UPDATE_HINT + " Если кнопка не срабатывает — «Загрузить рабочий файл»: скачается обновлённый файл, им заменить рабочий."
      : "Это обновление программы. Нажмите «Загрузить рабочий файл» внизу и выберите ваш рабочий файл — скачается он же с новой программой; замените им рабочий.";
    bar();
  });
  window.addEventListener("beforeunload", function (e) { if (pending()) { if (linked) sync(); e.preventDefault(); e.returnValue = ""; } });
  window.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "ы" || e.code === "KeyS")) { e.preventDefault(); save().catch(function () {}); }
  });

  window.__offline = {
    save: save, sync: sync,
    status: function () { return { linked: linked, canLink: canLink, pending: pending(), syncedAt: local.syncedAt || null, error: error }; }
  };
  window.claude = { use: function (n) { return ready.then(function () { return n === "db" ? db : n === "downloads" ? downloads : null; }); } };
})();
</script>
"""


def esc(obj):
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def load_snapshot(snap_dir):
    seed = {}
    for f in sorted(snap_dir.rglob("*.json")):
        seed[f.relative_to(snap_dir).with_suffix("").as_posix()] = json.loads(f.read_text(encoding="utf-8"))
    return seed


def template():
    html = SRC.read_text(encoding="utf-8")   # шрифты и логотип уже внутри страницы

    def swap(old, new):
        nonlocal html
        assert html.count(old) == 1, f"не найдено ровно одно вхождение: {old[:60]}"
        html = html.replace(old, new)

    swap("<title>HR-метрики i’way</title>", "<title>HR-метрики i’way — на ПК</title>")
    assert "__SEED__" not in html and "__TEMPLATE__" not in html
    swap("\n<script>\n", "\n" + SHIM.replace("__VERSION__", str(int(time.time() * 1000))) + "<script>\n")      # подмена базы — перед основным скриптом
    return ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
            + html + "\n</body>\n</html>\n")


def make_file(tpl, seed):
    # то же, что makeFile() в странице: сначала данные, потом сам шаблон
    return tpl.replace("__SEED__", esc(seed), 1).replace("__TEMPLATE__", esc(tpl), 1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    update = sys.argv[1] == "--update"
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / ("HR-метрики (обновление).html" if update else "HR-метрики.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {} if update else load_snapshot(pathlib.Path(sys.argv[1]))
    out.write_text(make_file(template(), {"stamp": int(time.time() * 1000), "data": data}), encoding="utf-8")
    print(f"{out}  {out.stat().st_size // 1024} КБ")
