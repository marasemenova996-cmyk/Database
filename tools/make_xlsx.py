"""Собирает scores.csv и evidence.csv в один Excel-файл database.xlsx (листы «Сводка», «Таблица», «Цитаты»)."""
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

csv.field_size_limit(10**9)
F = Font(name="Arial", size=10)
H = Font(name="Arial", size=10, bold=True)
HF = PatternFill("solid", fgColor="DDE4EE")
WRAP = Alignment(wrap_text=True, vertical="top")

def sheet(ws, rows, widths, numeric_from=None, numeric_to=None):
    head = list(rows[0].keys())
    ws.append(head)
    for r in rows:
        vals = []
        for i, k in enumerate(head):
            v = r[k]
            if numeric_from is not None and numeric_from <= i <= numeric_to and v.lstrip("-").isdigit():
                v = int(v)
            vals.append(v)
        ws.append(vals)
    for c in ws[1]:
        c.font, c.fill, c.alignment = H, HF, Alignment(wrap_text=True, vertical="center")
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font, c.alignment = F, WRAP
    for i, w in enumerate(widths(head), 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 75
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    return head

scores = list(csv.DictReader(open("scores.csv", encoding="utf-8")))
evidence = list(csv.DictReader(open("evidence.csv", encoding="utf-8")))

wb = Workbook()
summ = wb.active
summ.title = "Сводка"
ws = wb.create_sheet("Таблица")
head = sheet(ws, scores, lambda h: [45, 12, 16, 22, 16, 11, 26, 11] + [12] * 15 + [40], 8, 22)
ev = wb.create_sheet("Цитаты")
sheet(ev, evidence, lambda h: [45] + [40] * (len(h) - 1))

n = len(scores) + 1
summ["A1"] = "База позиций США по внешнеполитическим темам"; summ["A1"].font = Font(name="Arial", size=14, bold=True)
summ["A2"] = "Шкала оценок: от −3 (резко негативно) до +3 (резко позитивно); пустая клетка — тема в документе не затронута. Цитаты-основания — на листе «Цитаты»."
summ["A4"] = "Сайт"; summ["B4"] = "Документов в таблице"
sites = [("Белый дом", "*whitehouse.gov*"), ("Госдеп", "*state.gov*"), ("Минобороны", "*war.gov*")]
for i, (name, pat) in enumerate(sites, 5):
    summ[f"A{i}"] = name
    summ[f"B{i}"] = f'=COUNTIF(Таблица!$A$2:$A${n},"{pat}")' + (f'+COUNTIF(Таблица!$A$2:$A${n},"*defense.gov*")' if name == "Минобороны" else "")
summ["A8"] = "Всего"; summ["B8"] = "=SUM(B5:B7)"
summ["A10"] = "Тема"; summ["B10"] = "Документов с оценкой"; summ["C10"] = "Средняя оценка"
for j, col in enumerate(range(9, 24)):          # колонки I..W листа «Таблица»
    L = get_column_letter(col); r = 11 + j
    summ[f"A{r}"] = f"=Таблица!{L}1"
    summ[f"B{r}"] = f"=COUNT(Таблица!{L}$2:{L}${n})"
    summ[f"C{r}"] = f'=IF(B{r}=0,"",AVERAGE(Таблица!{L}$2:{L}${n}))'
    summ[f"C{r}"].number_format = "+0.00;-0.00;0.00"
for row in summ.iter_rows():
    for c in row:
        if c.row != 1: c.font = H if c.row in (4, 10) or (c.row == 8) else F
for c in ("A4", "B4", "A10", "B10", "C10"): summ[c].fill = HF
summ.column_dimensions["A"].width = 60; summ.column_dimensions["B"].width = 22; summ.column_dimensions["C"].width = 16
summ["A2"].alignment = WRAP; summ.merge_cells("A2:C2"); summ.row_dimensions[2].height = 45
wb.calculation.fullCalcOnLoad = True   # Excel и Google Таблицы пересчитают формулы при открытии
wb.save("database.xlsx")
print("database.xlsx:", len(scores), "строк,", len(evidence), "цитат")
