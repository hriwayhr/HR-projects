# Импорт Workload.xlsx: даты в шапке формулой «=F3+7» и забытые копии столбцов из шаблона
import datetime as dt, pathlib, sys
import openpyxl
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'tools'))
from import_workload import parse_sheet

wb = openpyxl.Workbook(); ws = wb.active
ws.append([2026])
# B — забытая копия «4.09 ЧТ» (4.09.2026 — пятница); C — пт 11.09; D = C+3 → пн 14.09; E = C+7 → пт 18.09
ws.append(['Сентябрь', 4.09, dt.datetime(2026, 9, 11), '=C2+3', '=C2+7'])
ws.append([None, 'ЧТ', 'пт', 'пн', 'пт'])
ws.append(['Количество собеседований (назначенных)', 9, 1, 2, 3])
ws.append(['Колчество отказов', 9, 'о', 5, 6])
off = set()
out = parse_sheet(ws, off)
assert out == {'2026-09-11': {'int_planned': 1}, '2026-09-14': {'int_planned': 2, 'rejections': 5},
               '2026-09-18': {'int_planned': 3, 'rejections': 6}}, out
assert off == {'2026-09-11'}, off
print('ok')
