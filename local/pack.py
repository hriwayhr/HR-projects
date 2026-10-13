#!/usr/bin/env python3
"""Архив локальной версии для Windows: dist/HR-метрики-локально.zip.

Внутри — папка «HR-метрики»: «Запустить HR-метрики.cmd», «Как пользоваться.txt» и program/
(node.exe с nodejs.org с проверкой SHA-256, local.js, сервер из cloud/function, страница).
Папки data в архиве нет — она появляется при первом запуске; обновление = заменить только program.
"""
import hashlib, pathlib, urllib.request, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
NODE_VER, NODE_SHA = 'v22.23.3', '9c9245166b4a8e182e0b797da9c20136117ff24368eaff1fec8343a123c8db0e'   # SHASUMS256.txt с nodejs.org
cache = ROOT / 'dist' / '.cache' / f'node-{NODE_VER}-win-x64.exe'
if not cache.exists() or hashlib.sha256(cache.read_bytes()).hexdigest() != NODE_SHA:
    cache.parent.mkdir(parents=True, exist_ok=True)
    data = urllib.request.urlopen(f'https://nodejs.org/dist/{NODE_VER}/win-x64/node.exe').read()
    assert hashlib.sha256(data).hexdigest() == NODE_SHA, 'node.exe: контрольная сумма не совпала'
    cache.write_bytes(data)

FILES = {
    'Запустить HR-метрики.cmd': ROOT / 'local' / 'start.cmd',
    'Как пользоваться.txt': ROOT / 'local' / 'README.txt',
    'program/node.exe': cache,
    'program/local.js': ROOT / 'local' / 'local.js',
    'program/app/index.js': ROOT / 'cloud' / 'function' / 'index.js',
    'program/app/acl.js': ROOT / 'cloud' / 'function' / 'acl.js',
    'program/app/auth.js': ROOT / 'cloud' / 'function' / 'auth.js',
    'program/app/store.js': ROOT / 'cloud' / 'function' / 'store.js',
    'program/app/static/page.html': ROOT / 'src' / 'hr-metrics.html',
}
out = ROOT / 'dist' / 'HR-метрики-локально.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, src in FILES.items():
        data = src.read_bytes()
        if name.endswith('.txt'): data = b'\xef\xbb\xbf' + data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')   # Блокнот: UTF-8 с BOM, CRLF
        z.writestr('HR-метрики/' + name, data)
print(out, round(out.stat().st_size / 1024 / 1024, 1), 'МБ')
