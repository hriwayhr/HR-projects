#!/usr/bin/env python3
"""Архив для своего сервера: dist/hr-metrics-selectel.zip — всё, что нужно для server/setup.sh, без данных и секретов."""
import pathlib, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ['src/hr-metrics.html', 'README.md', 'docs/session-history.md',
         'cloud/function/index.js', 'cloud/function/acl.js', 'cloud/function/auth.js', 'cloud/function/store.js',
         'cloud/function/test/server.test.js', 'cloud/function/test/store.test.js', 'cloud/README.md',
         'server/server.js', 'server/test.js', 'server/Dockerfile', 'server/docker-compose.yml', 'server/Caddyfile',
         'server/.env.example', 'server/setup.sh', 'server/README.md']
out = ROOT / 'dist' / 'hr-metrics-selectel.zip'
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in FILES:
        info = zipfile.ZipInfo.from_file(ROOT / f, f)
        if f.endswith('.sh'): info.external_attr = 0o100755 << 16
        z.writestr(info, (ROOT / f).read_bytes(), zipfile.ZIP_DEFLATED)
print('собрано:', out, round(out.stat().st_size / 1024), 'КБ,', len(FILES), 'файлов')
