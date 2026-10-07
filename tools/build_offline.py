#!/usr/bin/env python3
"""Собирает офлайн-версию игры «Миссия выполнима» — один HTML, который открывается
двойным щелчком на ПК, без claude.ai и без интернета.

Отличия от опубликованной страницы:
  * общая база артефакта заменена хранилищем браузера (localStorage этого ПК),
    стартовые данные берутся из снимка базы;
  * сохранение картинки рейтинга — обычная загрузка файла браузером;
  * шрифт Russo One и звук «Кота в мешке» вшиты внутрь, Google Fonts не нужен.

Запуск:  python3 tools/build_offline.py <каталог-снимка-базы> [выходной.html]
Снимок — каталог вида <коллекция>/<документ>.json (как сохраняет ArtifactData
с out_dir), вложенные коллекции — подкаталогами.
"""
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "mission-game.html"

SHIM = r"""<script>
/* офлайн: база в localStorage этого ПК вместо общей базы claude.ai */
(function () {
  var KEY = "mi-offline-db", SEED = __SEED__, store = null;
  try { store = JSON.parse(localStorage.getItem(KEY)); } catch (e) {}
  if (!store) store = SEED;
  var subs = [];
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(store)); }
    catch (e) { alert("Браузеру не хватает места, чтобы сохранить данные игры."); }
  }
  function copy(o) { return JSON.parse(JSON.stringify(o)); }
  function snap(p) { var d = store[p]; return { id: p.split("/").pop(), exists: !!d, data: function () { return d ? copy(d) : undefined; } }; }
  function query(c) {
    var n = c.split("/").length + 1;
    var docs = Object.keys(store).filter(function (p) { return p.indexOf(c + "/") === 0 && p.split("/").length === n; }).sort().map(snap);
    return { docs: docs, size: docs.length, empty: !docs.length };
  }
  function notify() { subs.slice().forEach(function (s) { s.cb(query(s.c)); }); }
  var db = {
    doc: function (p) { return {
      get: function () { return Promise.resolve(snap(p)); },
      set: function (d) { store[p] = copy(d); save(); notify(); return Promise.resolve(); },
      delete: function () { delete store[p]; save(); notify(); return Promise.resolve(); }
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
  window.claude = { use: function (n) { return Promise.resolve(n === "db" ? db : n === "downloads" ? downloads : null); } };
})();
</script>
"""


def b64(path):
    return base64.b64encode(path.read_bytes()).decode()


def load_snapshot(snap_dir):
    seed = {}
    for f in sorted(snap_dir.rglob("*.json")):
        seed[f.relative_to(snap_dir).with_suffix("").as_posix()] = json.loads(f.read_text(encoding="utf-8"))
    return seed


def build(snap_dir, out):
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

    # подмена базы — перед основным скриптом
    seed = json.dumps(load_snapshot(snap_dir), ensure_ascii=False).replace("</", "<\\/")
    swap("\n<script>\n", "\n" + SHIM.replace("__SEED__", seed) + "<script>\n")

    page = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
            + html + "\n</body>\n</html>\n")
    out.write_text(page, encoding="utf-8")
    print(f"{out}  {out.stat().st_size // 1024} КБ")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    snap = pathlib.Path(sys.argv[1])
    target = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "dist" / "mission-game-offline.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    build(snap, target)
