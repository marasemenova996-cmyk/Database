"""Находит настоящие даты публикации старых статей Пентагона из dod_old.csv.

При первом сборе им проставились даты архивных копий (2025–2026). Здесь для каждой статьи берём
1) самую раннюю копию в Wayback Machine (по номеру статьи на defense.gov и war.gov) и
2) дату со страницы (meta/time/JSON-LD/«Month D, YYYY» в начале статьи).
Результат: dod_old_dates.csv (url, cdx_date, page_date, date)."""
import csv, re, sys, time
sys.path.insert(0, ".")
from collect_docs import get, norm_date

csv.field_size_limit(10**9)
rows = list(csv.DictReader(open("dod_old.csv", encoding="utf-8")))
DATE_RE = re.compile(r"(Jan|Feb|Mar|Apr|May|June?|July?|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, (19|20)\d\d")

def earliest(url):
    m = re.search(r"/(News/[^/]+/[^/]+/Article/\d+)/", url + "/", re.I)
    best = ""
    for dom in ("defense.gov", "war.gov"):
        q = (f"https://web.archive.org/cdx/search/cdx?url={dom}/{m.group(1)}/&matchType=prefix"
             "&filter=statuscode:200&fl=timestamp,original&limit=1&output=json")
        for attempt in range(3):
            try:
                time.sleep(2)
                d = get(q).json()[1:]
                if d and (not best or d[0][0] < best[0]): best = d[0]
                break
            except Exception as e:
                print("  cdx fail", e)
    return best

def page_date(ts, orig):
    html = get(f"https://web.archive.org/web/{ts}id_/{orig}").text
    for pat in [r'"datePublished"\s*:\s*"([^"]+)"', r'article:published_time"\s+content="([^"]+)"',
                r'<time[^>]*datetime="([^"]+)"', r'class="date"[^>]*>\s*([^<]+)<']:
        m = re.search(pat, html)
        if m and norm_date(m.group(1)): return norm_date(m.group(1))
    body = re.sub(r"<[^>]+>", " ", html)
    m = DATE_RE.search(body)
    return norm_date(m.group(0)) if m else ""

out = open("dod_old_dates.csv", "w", newline="", encoding="utf-8")
w = csv.writer(out); w.writerow(["url", "cdx_date", "page_date", "date"])
for i, r in enumerate(rows):
    e = earliest(r["url"])
    cdx = f"{e[0][:4]}-{e[0][4:6]}-{e[0][6:8]}" if e else ""
    pd = ""
    if e:
        try: pd = page_date(*e)
        except Exception as ex: print("  page fail", r["url"], ex)
    date = pd or cdx
    w.writerow([r["url"], cdx, pd, date]); out.flush()
    print(i, cdx, pd, r["title"][:60])
out.close()
