"""Собирает scores.csv и evidence.csv в один Excel-файл database.xlsx (листы «Сводка», «Таблица», «Цитаты»)."""
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

csv.field_size_limit(10**9)
F = Font(name="Arial", size=10)
H = Font(name="Arial", size=10, bold=True)
LINK = Font(name="Arial", size=10, color="0563C1", underline="single")
HF = PatternFill("solid", fgColor="DDE4EE")
LF = PatternFill("solid", fgColor="F3F5F8")
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

TOPIC_RULES = [
    ("Россия", "−: Россия как противник, агрессор, санкции против неё; +: переговоры, жесты сближения"),
    ("Украинский кризис", "+: поддержка Украины, помощь, мирное урегулирование; −: давление на Украину"),
    ("Китай", "−2: угроза/противник; −1: конкурент; +1: партнёр по сделке, переговоры"),
    ("Изменение климата", "всегда 0, позиция описывается словами в примечании (напр. «выход из Парижского соглашения»)"),
    ("Миграция", "−3: «вторжение», чрезвычайное положение; −2: нелегальная миграция как угроза; −1: мягкое упоминание; +1: полезная легальная миграция"),
    ("Глобализация", "−: критика «глобализма», международных обязательств; +: поддержка"),
    ("НАТО", "+2: поддержка, похвала; +1: требование делить расходы; −1: «они нам не нужны»"),
    ("ЕС", "+: партнёрство; −: критика"),
    ("ООН", "−2: выход из организаций, резкая критика; −1: критика; +1: работа в органах ООН"),
    ("Международная торговля", "−1: пошлины, «нечестная торговля», дефицит; +1: торговые сделки, открытие рынков"),
    ("Демократии в мире", "+: продвижение демократии и свобод за рубежом; −: отказ от этого"),
    ("Военные интервенции", "+2: одобрение операций и ударов США; −: отказ, сворачивание"),
    ("Либеральная повестка", "−2: против абортов, «гендерной идеологии», DEI; +: поддержка (с примечанием)"),
    ("Израиль", "+2: поддержка; +3: посольство в Иерусалиме; +1: участие в мирной сделке"),
    ("Многополярный мир", "+: признание баланса сил/многополярности; −: отрицание"),
]

def write_table(ws, rows, start, widths, numeric=(), links=True):
    head = list(rows[0].keys())
    for j, k in enumerate(head, 1):
        c = ws.cell(start, j, k)
        c.font, c.fill, c.alignment = H, HF, CENTER
    for i, r in enumerate(rows, start + 1):
        for j, k in enumerate(head, 1):
            v = r[k]
            if j - 1 in numeric and v.lstrip("-").isdigit(): v = int(v)
            c = ws.cell(i, j, v)
            c.font = F
            c.alignment = CENTER if j - 1 in numeric else WRAP
            if links and j == 1 and v.startswith("http"):
                c.hyperlink = v; c.font = LINK
    for j, w in enumerate(widths(head), 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[start].height = 75
    ws.auto_filter.ref = f"A{start}:{get_column_letter(len(head))}{start + len(rows)}"
    return head

scores = list(csv.DictReader(open("scores.csv", encoding="utf-8")))
evidence = list(csv.DictReader(open("evidence.csv", encoding="utf-8")))

wb = Workbook()
summ = wb.active
summ.title = "Сводка"
ws = wb.create_sheet("Таблица")

# Легенда над таблицей: шкала, критерии по темам, прочие колонки
legend = [("Как читать таблицу", None),
          ("Шкала оценок", "от −3 до +3: −3 резко негативно, −2 негативно, −1 скорее негативно, 0 нейтрально/упомянуто без оценки, "
                           "+1 скорее позитивно, +2 позитивно, +3 резко позитивно. Пустая клетка — тема в документе не затронута."),
          ("Основание", "к каждой оценке есть дословная цитата из документа — лист «Цитаты» (строки совпадают по ссылке)."),
          ("Директивность", "1 — указ, прокламация, меморандум, директива, соглашение, стратегия; 0 — заявления, речи, релизы."),
          ("Отбор", "в таблицу входят только документы, где оценена хотя бы одна тема."),
          ("Критерии по темам", None)] + TOPIC_RULES
r = 1
for name, text in legend:
    a = ws.cell(r, 1, name); a.font = H if text is None or r == 1 else F
    if text is None:
        a.font = Font(name="Arial", size=12 if r == 1 else 10, bold=True)
    else:
        a.font = H
        b = ws.cell(r, 2, text); b.font = F; b.alignment = WRAP
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=12)
        ws.row_dimensions[r].height = 28 if len(text) > 110 else 15
        for cc in range(1, 13): ws.cell(r, cc).fill = LF
    r += 1
start = r + 1
head = write_table(ws, scores, start, lambda h: [45, 12, 16, 22, 16, 11, 26, 12] + [12] * 15 + [40],
                   numeric=set(range(7, 23)) | {2})
ws.freeze_panes = ws.cell(start + 1, 2)

ev = wb.create_sheet("Цитаты")
write_table(ev, evidence, 1, lambda h: [45] + [40] * (len(h) - 1))
ev.freeze_panes = "B2"

first, last = start + 1, start + len(scores)
rng = lambda L: f"Таблица!${L}${first}:${L}${last}"
summ["A1"] = "База позиций США по внешнеполитическим темам"; summ["A1"].font = Font(name="Arial", size=14, bold=True)
summ["A2"] = "Шкала оценок: от −3 (резко негативно) до +3 (резко позитивно); пустая клетка — тема не затронута. Критерии — над таблицей на листе «Таблица», цитаты — на листе «Цитаты»."
summ["A4"] = "Сайт"; summ["B4"] = "Документов в таблице"
sites = [("Белый дом", ["*whitehouse.gov*"]), ("Госдеп", ["*state.gov*"]), ("Минобороны", ["*war.gov*", "*defense.gov*"])]
for i, (name, pats) in enumerate(sites, 5):
    summ[f"A{i}"] = name
    summ[f"B{i}"] = "=" + "+".join(f'COUNTIF({rng("A")},"{p}")' for p in pats)
summ["A8"] = "Всего"; summ["B8"] = "=SUM(B5:B7)"
summ["A10"] = "Тема"; summ["B10"] = "Документов с оценкой"; summ["C10"] = "Средняя оценка"
for j, col in enumerate(range(9, 24)):          # колонки I..W листа «Таблица»
    L = get_column_letter(col); rr = 11 + j
    summ[f"A{rr}"] = f"=Таблица!{L}{start}"
    summ[f"B{rr}"] = f"=COUNT({rng(L)})"
    summ[f"C{rr}"] = f'=IF(B{rr}=0,"",AVERAGE({rng(L)}))'
    summ[f"C{rr}"].number_format = "+0.00;-0.00;0.00"
for row in summ.iter_rows():
    for c in row:
        if c.row != 1: c.font = H if c.row in (4, 8, 10) else F
        if c.column > 1 and c.row > 3: c.alignment = CENTER
for c in ("A4", "B4", "A10", "B10", "C10"): summ[c].fill = HF
summ.column_dimensions["A"].width = 60; summ.column_dimensions["B"].width = 22; summ.column_dimensions["C"].width = 16
summ["A2"].alignment = WRAP; summ.merge_cells("A2:C2"); summ.row_dimensions[2].height = 45
wb.calculation.fullCalcOnLoad = True   # Excel и Google Таблицы пересчитают формулы при открытии
wb.save("database.xlsx")
print("database.xlsx:", len(scores), "строк,", len(evidence), "цитат; таблица с строки", start)
