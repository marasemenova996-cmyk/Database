"""Переводит ручные оценки (codes/*.tsv) в results.jsonl, совместимый с score_docs.export_csv().

Номера документов в codes/X.tsv относятся к снимку codes/X.snap.csv (idx, url, date, title),
поэтому пересборка docs.csv не сбивает уже сделанные оценки.

Формат строки (через TAB):
  idx  category  institution  directive(0/1)  eligible(0/1)  note_13  issues
issues: "1=-2~цитата;;3=-3~цитата" (номер темы = оценка ~ дословная цитата); пусто — ничего не упомянуто.
"""
import csv, glob, json, sys
csv.field_size_limit(sys.maxsize)
out = []
for path in sorted(glob.glob("codes/*.tsv")):
    snap = {int(r["idx"]): r for r in csv.DictReader(open(path[:-4] + ".snap.csv", encoding="utf-8"))}
    coded = {}
    for n, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"): continue
        parts = line.split("\t")
        parts += [""] * (7 - len(parts))
        idx, cat, inst, dire, elig, note, iss = parts[:7]
        issues = {str(k): {"mentioned": False, "score": None, "evidence": ""} for k in range(1, 16)}
        for item in filter(None, iss.split(";;")):
            k, rest = item.split("=", 1)
            sc, _, ev = rest.partition("~")
            issues[k.strip()] = {"mentioned": True, "score": int(sc), "evidence": ev.strip()}
        coded[int(idx)] = {"category": cat, "institution": inst, "directive": int(dire or 0),
                           "eligible": elig.strip() == "1", "note_13": note, "issues": issues}
    for i in sorted(coded):
        r = snap[i]
        out.append({"url": r["url"], "date": r["date"], "title": r["title"], "result": coded[i]})
    print(f"{path}: оценено {len(coded)} из {len(snap)}")
with open("results.jsonl", "w", encoding="utf-8") as f:
    for r in out: f.write(json.dumps(r, ensure_ascii=False) + "\n")
