#!/usr/bin/env python3
"""Сборка для Yandex Cloud: архив функции со страницей (cloud/dist/function.zip)."""
import pathlib, zipfile

ROOT = pathlib.Path(__file__).resolve().parent
FN = ROOT / 'function'
# страница — как есть; документ и флаг облачного режима добавляет index.js
(FN / 'static').mkdir(exist_ok=True)
(FN / 'static' / 'page.html').write_text((ROOT.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8'), encoding='utf-8')

dist = ROOT / 'dist'; dist.mkdir(exist_ok=True)
with zipfile.ZipFile(dist / 'function.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in ['index.js', 'acl.js', 'auth.js', 'store.js', 'package.json', 'package-lock.json', 'static/page.html']:
        z.write(FN / name, name)   # зависимости (ydb-sdk) облако ставит само по package.json
print('собрано:', dist / 'function.zip', round((dist / 'function.zip').stat().st_size / 1024), 'КБ')
