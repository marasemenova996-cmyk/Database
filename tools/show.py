"""Печатает документы из docs.csv для ручной оценки.
  python tools/show.py START END          — фрагменты: предложения с темами кодбука (+ соседние)
  python tools/show.py START END full     — полный текст
"""
import csv, re, sys
csv.field_size_limit(sys.maxsize)
TOPIC = re.compile(r"russia|putin|moscow|kremlin|ukrain|zelensk|kyiv|china|chinese|beijing|\bxi\b|\bccp\b|"
    r"climate|carbon emission|green new|paris agreement|migra|immigra|illegal alien|border|deport|asylum|"
    r"globali|nato\b|alliance|our allies|european union|\beu\b|brussels|united nations|\bu\.n\.|world health|"
    r"unesco|unrwa|trade deal|trade agreement|trade deficit|free trade|fair trade|tariff|reciproc|\bwto\b|"
    r"democra|authoritarian|dictator|intervention|invasion|airstrike|military action|use of force|"
    r"abortion|pro-life|lgbt|transgender|gender ideology|drug legaliz|illicit drug|narco|fentanyl|marijuana|"
    r"cannabis|israel|gaza|hamas|iran\b|multipolar|world order|brics|venezuela|maduro|cartel|terrorist org|"
    r"sanction|ceasefire|peace deal|peace agreement", re.I)
start, end = int(sys.argv[1]), int(sys.argv[2])
full = len(sys.argv) > 3 and sys.argv[3] == "full"
import os
rows = list(csv.DictReader(open(os.environ.get("DOCS", "docs.csv"), encoding="utf-8")))
for i in range(start, min(end, len(rows))):
    r = rows[i]; t = r["text"]
    if full or len(t) < 1500:
        body = t[:20000]
    else:
        sents = re.split(r"(?<=[.!?])\s+", t)
        keep = set()
        for j, s in enumerate(sents):
            if TOPIC.search(s): keep.update({j - 1, j, j + 1})
        parts, prev = [], -2
        for j in sorted(k for k in keep if 0 <= k < len(sents)):
            parts.append(("" if j == prev + 1 else "… ") + sents[j]); prev = j
        body = " ".join(parts)
        if len(body) > 3500: body = body[:3500] + " …[ещё фрагменты]"
        if not body: body = "(тем кодбука нет) " + t[:300]
    print(f"##### [{i}] {r['date']} | {r['title'][:150]}\n{body}\n")
