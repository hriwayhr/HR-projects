#!/usr/bin/env python3
"""Готовит корпоративный шрифт Fedra Sans Pro для вшивания в страницу.

Берёт .otf, отрезает всё лишнее (оставляет латиницу, кириллицу, пунктуацию,
цифры), конвертирует в woff2 и печатает base64 — его и вшиваем в @font-face
внутри src/iway-welcome.html.

Файлы шрифта НЕ лежат в репозитории: Fedra Sans Pro лицензионный.
Положите .otf рядом и укажите каталог аргументом.

Ожидаемые имена (можно поправить в FACES):
  FedraSansPro-Book.otf   — 400
  FedraSansPro-Demi.otf   — 600
  FedraSansPro-Bold.otf   — 700

Запуск:  python3 tools/build_fonts.py <каталог-с-otf> [каталог-назначения]
Зависимости: fonttools, brotli
"""
import sys
import base64
import pathlib
from fontTools import subset

FACES = {
    'book': ('FedraSansPro-Book.otf', 400),
    'demi': ('FedraSansPro-Demi.otf', 600),
    'bold': ('FedraSansPro-Bold.otf', 700),
}

# латиница + кириллица + типографика + валюты + стрелки
UNICODES = (
    'U+0020-007E,U+00A0,U+00A9,U+00AB,U+00B0,U+00B7,U+00BB,U+00D7,'
    'U+0400-045F,U+0490-0491,'
    'U+2010-2015,U+2018-201A,U+201C-201E,U+2020-2022,U+2026,U+2030,'
    'U+2039-203A,U+2044,U+2116,U+20AC,U+20BD,U+2190-2193,U+2212,U+25CF'
)
FEATURES = 'kern,liga,clig,calt,locl,tnum,lnum,case,ccmp,mark,mkmk'


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = pathlib.Path(sys.argv[1])
    dst = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'build/fonts')
    dst.mkdir(parents=True, exist_ok=True)

    css = []
    for key, (filename, weight) in FACES.items():
        path = src / filename
        if not path.exists():
            print('нет файла:', path)
            continue
        out = dst / ('fedra-%s.woff2' % key)
        subset.main([
            str(path),
            '--unicodes=' + UNICODES,
            '--layout-features=' + FEATURES,
            '--flavor=woff2', '--desubroutinize', '--no-hinting',
            '--name-IDs=1,2,3,4,6', '--drop-tables+=DSIG',
            '--output-file=' + str(out),
        ])
        raw = out.read_bytes()
        b64 = base64.b64encode(raw).decode()
        print('%-12s %3d KB woff2 → %3d KB base64' % (key, len(raw) // 1024, len(b64) // 1024))
        css.append(
            "  @font-face{font-family:'Fedra Sans Pro';font-style:normal;font-weight:%d;"
            "font-display:swap;src:url(data:font/woff2;base64,%s) format('woff2');}" % (weight, b64)
        )

    if css:
        face_css = dst / 'fontface.css'
        face_css.write_text('\n'.join(css), encoding='utf-8')
        print('\n@font-face с base64:', face_css)
        print('Вставьте содержимое в начало <style> в src/iway-welcome.html.')


if __name__ == '__main__':
    main()
