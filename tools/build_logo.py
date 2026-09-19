#!/usr/bin/env python3
"""Готовит логотип i'way для портала и письма.

Вход  — исходник логотипа (JPEG/PNG на белом фоне).
Выход — прозрачные PNG в фирменных цветах гайдбука:

  logo-dark.png       полноразмерный, Pantone 447 C + Hexachrome Green C
  logo-light.png      полноразмерный, моно-белый (для тёмных подложек)
  logo-dark-q.png     480 px, 32 цвета  — вшивается в страницу как data URI
  logo-light-q.png    480 px, 32 цвета  — то же, инверсный вариант
  mail-logo-small.png 260 px            — шапка письма
  mail-logo-white.png 320 px            — белый вариант для письма

Запуск:  python3 tools/build_logo.py <исходник> [каталог-назначения]
Зависимость: pillow
"""
import sys
import pathlib
from PIL import Image

GREEN = (0, 150, 52)    # Pantone Hexachrome Green C
OLIVE = (72, 78, 65)    # Pantone 447 C


def luminance(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def cut_white(src):
    """Убирает белый фон, сохраняя сглаживание краёв, и красит в цвета гайдбука."""
    img = src.convert('RGB')
    w, h = img.size
    px = img.load()
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    op = out.load()
    lo, lg = luminance(OLIVE), luminance(GREEN)
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if r > 247 and g > 247 and b > 247:
                continue
            is_green = g > r + 30 and g > b + 30
            ink, li = (GREEN, lg) if is_green else (OLIVE, lo)
            alpha = (255 - luminance((r, g, b))) / (255 - li)
            alpha = max(0.0, min(1.0, alpha))
            op[x, y] = (ink[0], ink[1], ink[2], int(round(alpha * 255)))
    return out.crop(out.getbbox())


def to_white(img):
    mono = img.copy()
    mp = mono.load()
    for y in range(mono.size[1]):
        for x in range(mono.size[0]):
            r, g, b, a = mp[x, y]
            if a:
                mp[x, y] = (255, 255, 255, a)
    return mono


def save(img, path, width, colors=None):
    scaled = img.resize((width, round(img.size[1] * width / img.size[0])), Image.LANCZOS)
    if colors:
        scaled = scaled.quantize(colors=colors, method=Image.FASTOCTREE)
    scaled.save(path, optimize=True)
    print('%-22s %5d KB' % (pathlib.Path(path).name, len(open(path, 'rb').read()) // 1024))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = Image.open(sys.argv[1])
    dst = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else 'assets')
    dst.mkdir(parents=True, exist_ok=True)

    dark = cut_white(src)
    light = to_white(dark)
    dark.save(dst / 'logo-dark.png')
    light.save(dst / 'logo-light.png')
    save(dark, dst / 'logo-dark-q.png', 480, 32)
    save(light, dst / 'logo-light-q.png', 480, 32)
    save(dark, dst / 'mail-logo-small.png', 260, 16)
    save(light, dst / 'mail-logo-white.png', 320, 16)
    print('\nГотово. Base64 этих файлов вшит в src/iway-welcome.html:')
    print('  --logo / --logo-inv        — токены CSS (logo-dark-q / logo-light-q)')
    print('  buildEmail()               — шапка письма (mail-logo-small)')


if __name__ == '__main__':
    main()
