#!/usr/bin/env python3
"""Собирает офлайн-версию игры «Миссия выполнима» — один HTML, который открывается
двойным щелчком на любом ПК, без claude.ai и без интернета, и носит данные в себе.

Как живут данные:
  * все игры, игроки и результаты вшиты в сам файл (SEED);
  * изменения сразу пишутся в хранилище браузера этого ПК (localStorage);
  * кнопка «Сохранять в файл игры» перезаписывает сам HTML-файл с текущими данными
    (Chrome/Edge: File System Access API, дальше — автоматически после каждого
    изменения); в других браузерах она скачивает обновлённую копию файла.
  * Файл умеет пересобрать себя: в нём лежит его же шаблон (TEMPLATE), куда
    подставляются новые данные. Ту же подстановку делает этот скрипт.

Запуск:  python3 tools/build_offline.py <каталог-снимка-базы> [выходной.html]
Снимок — каталог вида <коллекция>/<документ>.json (как сохраняет ArtifactData
с out_dir), вложенные коллекции — подкаталогами.
"""
import base64
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "mission-game.html"

# __SEED__ и __TEMPLATE__ должны встречаться в шаблоне впервые именно здесь
SHIM = r"""<script>
/* офлайн-версия: данные в самом файле + localStorage этого ПК вместо общей базы claude.ai */
(function () {
  var SEED = __SEED__;
  var TEMPLATE = __TEMPLATE__;
  var KEY = "mi-offline-db", local = null, handle = null, linked = false, error = "", timer = null, subs = [];
  try { local = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}

  function persist() {
    try { localStorage.setItem(KEY, JSON.stringify(local)); error = ""; }
    catch (e) { error = "Браузеру не хватает места на этом ПК. Сохраните игру в файл."; }
  }
  function changed() { if (window.__offlineChanged) window.__offlineChanged(); }
  function copy(o) { return JSON.parse(JSON.stringify(o)); }
  function esc(json) { return json.replace(/</g, "\\u003c"); }
  function makeFile(seed) {
    return TEMPLATE
      .replace("__SEED__", function () { return esc(JSON.stringify(seed)); })
      .replace("__TEMPLATE__", function () { return esc(JSON.stringify(TEMPLATE)); });
  }
  function fmt(t) { return new Date(t).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" }); }

  /* какие данные открыть. Файл и ПК могли разойтись (копию возили на другой ПК):
     этот ПК помнит пути, изменённые после последнего сохранения в файл (local.changed),
     и накладывает их поверх данных более нового файла — ничьи результаты не теряются. */
  var notice = "";
  function fresh() { return { fileStamp: SEED.stamp, dirty: false, changed: [], data: copy(SEED.data) }; }
  function choose() {
    if (!local || !local.data) local = fresh();
    else if (local.fileStamp === SEED.stamp) { /* тот же файл: продолжаем с этого ПК */ }
    else if (SEED.stamp > (local.fileStamp || 0)) {                          // файл новее: берём его + свои несохранённые правки
      try { localStorage.setItem(KEY + "-prev", JSON.stringify(local)); } catch (e) {}
      var mine = local.changed || [], data = copy(SEED.data);
      mine.forEach(function (p) { if (p in local.data) data[p] = local.data[p]; else delete data[p]; });
      local = { fileStamp: SEED.stamp, dirty: mine.length > 0, changed: mine, changedAt: local.changedAt, data: data };
      notice = mine.length ? "Открыт файл от " + fmt(SEED.stamp) + ", к нему добавлены несохранённые изменения этого ПК." : "";
    } else notice = "Это старая копия файла. Показаны более новые данные этого ПК.";
    local.changed = local.changed || [];
    persist();
    return Promise.resolve();
  }

  /* запоминаем выбранный файл между запусками (Chrome/Edge) */
  function idb(mode, val) {
    return new Promise(function (ok) {
      try {
        var r = indexedDB.open("mi-offline", 1);
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
  var canLink = typeof window.showSaveFilePicker === "function";
  if (canLink) idb("readonly").then(function (h) {
    if (!h) return;
    handle = h;
    h.queryPermission({ mode: "readwrite" }).then(function (p) { linked = p === "granted"; changed(); }, function () {});
  });

  function writeFile() {
    var stamp = Date.now(), html = makeFile({ stamp: stamp, data: local.data });
    return handle.createWritable().then(function (w) { return w.write(html).then(function () { return w.close(); }); }).then(function () {
      local.fileStamp = stamp; local.savedAt = stamp; local.dirty = false; local.changed = []; notice = ""; persist(); changed();
    }, function (e) { linked = false; error = "Не удалось записать файл. Нажмите, чтобы выбрать его снова."; changed(); throw e; });
  }
  function schedule() {
    if (!linked) return;
    clearTimeout(timer); timer = setTimeout(function () { writeFile().catch(function () {}); }, 1200);
  }
  function save() {
    error = "";
    if (!canLink) {                                                         // другие браузеры: скачать копию с данными
      var stamp = Date.now(), url = URL.createObjectURL(new Blob([makeFile({ stamp: stamp, data: local.data })], { type: "text/html" }));
      var a = document.createElement("a"); a.href = url; a.download = "Миссия выполнима.html"; document.body.append(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      local.fileStamp = stamp; local.savedAt = stamp; local.dirty = false; local.changed = []; notice = ""; persist(); changed();
      return Promise.resolve();
    }
    var pick = handle
      ? handle.requestPermission({ mode: "readwrite" }).then(function (p) { if (p !== "granted") throw new Error("denied"); })
      : window.showSaveFilePicker({ suggestedName: "Миссия выполнима.html", types: [{ description: "Игра", accept: { "text/html": [".html"] } }] })
          .then(function (h) { handle = h; return idb("readwrite", h); });
    return pick.then(function () { linked = true; return writeFile(); });
  }

  var ready = choose();
  function snap(p) { var d = local.data[p]; return { id: p.split("/").pop(), exists: !!d, data: function () { return d ? copy(d) : undefined; } }; }
  function query(c) {
    var n = c.split("/").length + 1;
    var docs = Object.keys(local.data).filter(function (p) { return p.indexOf(c + "/") === 0 && p.split("/").length === n; }).sort().map(snap);
    return { docs: docs, size: docs.length, empty: !docs.length };
  }
  function write(p, d) {
    if (d === undefined) delete local.data[p]; else local.data[p] = copy(d);
    if (local.changed.indexOf(p) < 0) local.changed.push(p);
    local.dirty = true; local.changedAt = Date.now(); persist();
    subs.slice().forEach(function (s) { s.cb(query(s.c)); });
    changed(); schedule();
    return Promise.resolve();
  }
  var db = {
    doc: function (p) { return {
      get: function () { return Promise.resolve(snap(p)); },
      set: function (d) { return write(p, d); },
      delete: function () { return write(p, undefined); }
    }; },
    collection: function (c) { return {
      get: function () { return Promise.resolve(query(c)); },
      onSnapshot: function (cb) { var s = { c: c, cb: cb }; subs.push(s); setTimeout(function () { cb(query(c)); }); return function () { subs.splice(subs.indexOf(s), 1); }; }
    }; }
  };
  var downloads = { save: function (r) {
    var url = URL.createObjectURL(r.data instanceof Blob ? r.data : new Blob([r.data]));
    var a = document.createElement("a"); a.href = url; a.download = r.filename; document.body.append(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    return Promise.resolve({ status: "saved" });
  } };

  window.__offline = {
    save: save,
    status: function () { return { linked: linked, canLink: canLink, hasHandle: !!handle, dirty: !!(local && local.dirty), savedAt: local && (local.savedAt || local.fileStamp), error: error || notice }; }
  };
  window.claude = { use: function (n) { return ready.then(function () { return n === "db" ? db : n === "downloads" ? downloads : null; }); } };
})();
</script>
"""


def b64(path):
    return base64.b64encode(path.read_bytes()).decode()


def esc(obj):
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c")


def load_snapshot(snap_dir):
    seed = {}
    for f in sorted(snap_dir.rglob("*.json")):
        seed[f.relative_to(snap_dir).with_suffix("").as_posix()] = json.loads(f.read_text(encoding="utf-8"))
    return seed


def template():
    html = SRC.read_text(encoding="utf-8")

    def swap(old, new):
        nonlocal html
        assert html.count(old) == 1, f"не найдено ровно одно вхождение: {old[:60]}"
        html = html.replace(old, new)

    # шрифт заголовков — внутрь, вместо Google Fonts
    fonts = (
        "@font-face{font-family:'Russo One';font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2');"
        "unicode-range:U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116}\n"
        "@font-face{font-family:'Russo One';font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2');"
        "unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+2000-206F,U+20AC,U+2122,U+2212}\n"
    ) % (b64(ROOT / "assets/russo-one-cyrillic.woff2"), b64(ROOT / "assets/russo-one-latin.woff2"))
    swap('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Russo+One&display=swap">\n', "")
    swap("<style>\n", "<style>\n" + fonts)

    # звук «Кота в мешке» — внутрь
    swap("new Audio(`sounds/${name}.mp3`)",
         '(name === "cat" ? new Audio("data:audio/mpeg;base64,%s") : new Audio(`sounds/${name}.mp3`))'
         % b64(ROOT / "src/sounds/cat.mp3"))

    swap("<title>Миссия выполнима</title>", "<title>Миссия выполнима — офлайн</title>")
    assert "__SEED__" not in html and "__TEMPLATE__" not in html
    swap("\n<script>\n", "\n" + SHIM + "<script>\n")      # подмена базы — перед основным скриптом

    return ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
            + html + "\n</body>\n</html>\n")


def make_file(tpl, seed):
    # то же, что makeFile() в странице: сначала данные, потом сам шаблон
    return tpl.replace("__SEED__", esc(seed), 1).replace("__TEMPLATE__", esc(tpl), 1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    snap = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / "mission-game-offline.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(make_file(template(), {"stamp": int(time.time() * 1000), "data": load_snapshot(snap)}), encoding="utf-8")
    print(f"{out}  {out.stat().st_size // 1024} КБ")
