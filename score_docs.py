"""
Оценка документов по кодбуку (15 тем, -3..3) через Claude API. Формат таблицы как в примере коллеги.
  pip install anthropic gspread
  export ANTHROPIC_API_KEY=...
  python score_docs.py --limit 40                      # пилот
  python score_docs.py                                 # полный прогон (можно перезапускать)
  python score_docs.py --upload SHEET_ID creds.json    # запись в Google Таблицу
Вход: docs.csv (collect_docs.py). Выход: results.jsonl, scores.csv (основная таблица), evidence.csv (цитаты).
"""
import csv, json, time, argparse, os
from datetime import date
import anthropic

MODEL = "claude-sonnet-5-5"     # сверь актуальное имя модели в документации Anthropic
MAX_CHARS = 80000

ISSUE_HEADERS = [
 "Отношение к России", "Отношение к украинскому кризису", "Отношение к Китаю",
 "Позиция об изменении климата", "Позиция о миграции", "Отношение к глобализации",
 "Отношение к НАТО", "Отношение к ЕС", "Отношение к ООН и дочерним организациям",
 "Отношение к международной торговле", "Позиция о демократиях в мире",
 "Отношение к военным интервенциям",
 "Отношение к продвижению либеральной повестки (аборты, экстремисты-ЛГБТ, легализация наркотиков)",
 "Отношение к Израилю", "Отношение к многополярному мировому порядку",
]
HEAD = ["ссылка", "страна", "дата", "кто у власти?", "категория документов", "язык",
        "институция", "директивность"] + ISSUE_HEADERS + ["примечания (п.13 и прочее)"]

SYSTEM = """Ты кодировщик в исследовании внешнеполитического дискурса США. Тебе дают один документ
(стратегический документ, речь, заявление или пресс-релиз). Кодируй ТОЛЬКО то, что сказано в тексте,
без внешних знаний и домыслов. Оценивай позицию автора документа (США), а не свою.

1) category — одно из: "стратегический документ", "речь", "пресс-релиз", "авторская статья",
   "позиция правительства", "другое".
2) institution — ведомство и, если назван, автор/спикер, по-русски, как "Госдепартамент США (Марко Рубио)".
3) directive — 1 для стратегических и программных документов (определяют политику), 0 для речей,
   заявлений и пресс-релизов.
4) eligible — true, если это стратегический документ, речь/заявление министра или лидера, пресс-релиз или
   позиция правительства с позицией/словами министра, лидера или ведомства. false для брифингов
   пресс-секретарей, логистических анонсов, расписаний, технических текстов.
5) По каждой из 15 тем: mentioned (true/false). true, только если из текста извлекается позиция автора.
   Мимолётное перечисление без оценки = false. Если false, score=null.
6) Если mentioned=true — score, целое от -3 до 3. ЕДИНАЯ ШКАЛА «угроза → союзник», применяется к объекту темы:
   -3 главная/экзистенциальная угроза; -2 угроза, но одна из нескольких; -1 оппонент, проблема, но не угроза;
   0 нейтральное отношение; 1 партнёр/польза, в первую очередь экономическая; 2 союзник, важный
   стратегический партнёр / важный приоритет; 3 ближайший союзник, наиважнейший контакт / ключевой приоритет.
   Как применять к темам-явлениям:
   - Украинский кризис: оценка самого кризиса и действий, его порождающих (опасность/угроза = отрицательные).
   - Изменение климата: климатические изменения как угроза = отрицательные значения.
   - Миграция: нелегальная/неконтролируемая миграция как проблема = отрицательные; полезная миграция = положительные.
   - Глобализация, международная торговля, демократии в мире, многополярный порядок: оценка объекта
     (поддержка/польза = положительные, угроза/критика = отрицательные).
   - Военные интервенции: интервенции противников/агрессия осуждаются = отрицательные; применение силы
     США и союзниками как законное = положительные.
   - Либеральная повестка (аборты, права ЛГБТ, легализация наркотиков): одна оценка общей позиции;
     если позиции по подтемам расходятся, поставь оценку по преобладающей и опиши в note_13 как
     "-2 (наркотики); 0 - ЛГБТ".
   Остальные темы-субъекты (Россия, Китай, НАТО, ЕС, ООН, Израиль) — отношение к субъекту.
7) evidence — дословная цитата из документа до 25 слов для каждой упомянутой темы.

Верни СТРОГО JSON без пояснений и markdown:
{"category": "...", "institution": "...", "directive": 0, "eligible": true, "note_13": "",
 "issues": {"1": {"mentioned": true, "score": -2, "evidence": "..."}, ... "15": {...}}}
Ключи issues "1".."15" обязательны."""

MONTHS = ["января","февраля","марта","апреля","мая","июня","июля","августа",
          "сентября","октября","ноября","декабря"]

def ru_date(iso):
    try:
        y, m, d = (int(x) for x in iso[:10].split("-"))
        return f"{d} {MONTHS[m-1]} {y}"
    except Exception:
        return iso

def party(iso):
    """Партия президента США на дату документа."""
    try:
        y, m, d = (int(x) for x in iso[:10].split("-")); dt = date(y, m, d)
    except Exception:
        return ""
    if dt >= date(2025, 1, 20): return "Республиканская партия (администрация Д. Трампа)"
    if dt >= date(2021, 1, 20): return "Демократическая партия (администрация Дж. Байдена)"
    if dt >= date(2017, 1, 20): return "Республиканская партия (администрация Д. Трампа)"
    if dt >= date(2009, 1, 20): return "Демократическая партия (администрация Б. Обамы)"
    if dt >= date(2001, 1, 20): return "Республиканская партия (администрация Дж. Буша-мл.)"
    if dt >= date(1993, 1, 20): return "Демократическая партия (администрация Б. Клинтона)"
    return ""

def score_one(client, doc):
    user = (f"Заголовок: {doc['title']}\nДата: {doc['date']}\nИсточник: {doc['url']}\n\n"
            f"ТЕКСТ:\n{doc['text'][:MAX_CHARS]}")
    for attempt in range(5):
        try:
            r = client.messages.create(model=MODEL, max_tokens=4000, temperature=0,
                                       system=SYSTEM, messages=[{"role": "user", "content": user}])
            raw = r.content[0].text.strip().replace("```json", "").replace("```", "").strip()
            out = json.loads(raw)
            assert "issues" in out
            return out
        except Exception as e:
            print("  retry", attempt + 1, type(e).__name__, e)
            time.sleep(2 ** attempt * 2)
    return None

def run(limit):
    client = anthropic.Anthropic()
    docs = list(csv.DictReader(open("docs.csv", encoding="utf-8")))
    done = set()
    if os.path.exists("results.jsonl"):
        # неудачные попытки (result = null) не считаются сделанными и будут повторены
        for l in open("results.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r.get("result"): done.add(r["url"])
    todo = [d for d in docs if d["url"] not in done]
    if limit: todo = todo[:limit]
    with open("results.jsonl", "a", encoding="utf-8") as f:
        for i, d in enumerate(todo, 1):
            res = score_one(client, d)
            f.write(json.dumps({"url": d["url"], "date": d["date"], "title": d["title"],
                                "result": res}, ensure_ascii=False) + "\n"); f.flush()
            if i % 10 == 0: print(f"{i}/{len(todo)}")
    export_csv()

def valid_score(v):
    return isinstance(v, int) and not isinstance(v, bool) and -3 <= v <= 3

def export_csv():
    """Берёт eligible-документы, где упомянута >=1 тема. Пустая ячейка = не упомянуто."""
    # по каждому url берём последнюю успешную запись (после перезапуска могут быть повторы)
    latest = {}
    for l in open("results.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r.get("result") or r["url"] not in latest: latest[r["url"]] = r
    main_rows, ev_rows = [], []
    for r in latest.values():
        res = r["result"]
        if not res or not res.get("eligible"): continue
        iss = res["issues"]
        ment = []
        for k in range(1, 16):
            it = iss.get(str(k)) or {}
            ok = bool(it.get("mentioned")) and valid_score(it.get("score"))
            if it.get("mentioned") and not ok:
                print(f"  некорректная оценка, тема {k} считается неупомянутой:", r["url"], it.get("score"))
            ment.append(ok)
        if not any(ment): continue
        scores = [iss[str(k)]["score"] if ment[k-1] else "" for k in range(1, 16)]
        evid = [iss[str(k)].get("evidence", "") if ment[k-1] else "" for k in range(1, 16)]
        main_rows.append([r["url"], "Соединённые Штаты Америки", ru_date(r["date"]), party(r["date"]),
                          res.get("category", ""), "английский", res.get("institution", ""),
                          res.get("directive", ""), *scores, res.get("note_13", "")])
        ev_rows.append([r["url"], *evid])
    with open("scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(HEAD); w.writerows(main_rows)
    with open("evidence.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["ссылка"] + ISSUE_HEADERS); w.writerows(ev_rows)
    print("scores.csv:", len(main_rows), "документов")

def upload(sheet_id, creds):
    import gspread
    sh = gspread.service_account(filename=creds).open_by_key(sheet_id)
    ws = sh.sheet1
    ws.clear(); ws.update(values=list(csv.reader(open("scores.csv", encoding="utf-8"))), range_name="A1")
    try: ev = sh.worksheet("evidence")
    except Exception: ev = sh.add_worksheet("evidence", rows=1200, cols=20)
    ev.clear(); ev.update(values=list(csv.reader(open("evidence.csv", encoding="utf-8"))), range_name="A1")
    print("Записано в таблицу.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--upload", nargs=2, metavar=("SHEET_ID", "CREDS_JSON"))
    a = ap.parse_args()
    if a.upload: export_csv(); upload(*a.upload)
    else: run(a.limit)
