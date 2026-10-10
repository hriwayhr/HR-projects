#!/usr/bin/env python3
"""Сборка для Yandex Cloud: страница в облачном режиме + архив функции (cloud/dist/function.zip)."""
import pathlib, zipfile

ROOT = pathlib.Path(__file__).resolve().parent
FN = ROOT / 'function'
page = (ROOT.parent / 'src' / 'hr-metrics.html').read_text(encoding='utf-8')
html = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>'
        '<script>window.HR_CLOUD = true;</script>' + page + '</body></html>')
(FN / 'static').mkdir(exist_ok=True)
(FN / 'static' / 'index.html').write_text(html, encoding='utf-8')

dist = ROOT / 'dist'; dist.mkdir(exist_ok=True)
with zipfile.ZipFile(dist / 'function.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for name in ['index.js', 'acl.js', 'auth.js', 'store.js', 'package.json', 'package-lock.json', 'static/index.html']:
        z.write(FN / name, name)   # зависимости (ydb-sdk) облако ставит само по package.json
print('собрано:', dist / 'function.zip', round((dist / 'function.zip').stat().st_size / 1024), 'КБ')
