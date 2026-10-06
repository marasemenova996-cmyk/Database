"""
Сбор ~1000 свежих документов (2026 и назад) с правительственных сайтов США.
Запуск:  pip install requests beautifulsoup4 lxml
         python collect_docs.py
Результат: docs.csv (source, url, date, title, text)
"""
import csv, re, sys, time, gzip
from datetime import datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (research project; contact: your@email)"}
PAUSE = 1.5          # секунд между запросами
MAX_TOTAL = 1000

# quota: сколько документов брать; include: подстроки URL, которые нужны.
# ПОДПРАВЬ include после первого запуска, если документов мало или они не те.
SOURCES = [
    {"name": "WhiteHouse+NSC", "root": "https://www.whitehouse.gov", "quota": 400,
     "include": ["/remarks/", "/briefings-statements/", "/nsc/", "/fact-sheets/", "strategy"]},
    {"name": "StateDept", "root": "https://www.state.gov", "quota": 350,
     "include": ["/remarks", "/speeches", "/secretary", "/strategy"]},
    # defense.gov / war.gov закрыты для облачных серверов (Akamai 403), поэтому страницы Пентагона
    # берём из копий в Wayback Machine. Транскрипты (в основном брифинги) не берём.
    {"name": "DoD", "quota": 250,
     "wayback": ["war.gov/News/Speeches/Speech/Article/", "war.gov/News/Releases/Release/Article/",
                 "defense.gov/News/Speeches/Speech/Article/", "defense.gov/News/Releases/Release/Article/"]},
]

# Грубый префильтр на «упомянут хотя бы один поляризующий вопрос».
# Нарочно широкий: точное решение принимает этап оценки. Документы без единого
# совпадения отбрасываются до оценки, чтобы не тратить на них API.
KEYWORDS = ["russia", "ukrain", "china", "chinese", "climate", "migra", "immigra",
            "border", "globaliz", "nato", "european union", "united nations",
            " u.n.", "trade", "tariff", "democra", "intervention", "abortion",
            "lgbt", "gender", "israel", "multipolar", "world order"]

def mentions_issue(text):
    t = text.lower()
    return any(k in t for k in KEYWORDS)

DATE_FORMATS = ["%B %d, %Y", "%b %d, %Y", "%b. %d, %Y", "%d %B %Y", "%d %b %Y",
                "%m/%d/%Y", "%Y/%m/%d", "%Y%m%d"]

def norm_date(s):
    """Приводит дату к YYYY-MM-DD; если не удалось распознать — пустая строка."""
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m: return m.group(0)
    s = re.sub(r"\s+", " ", s.replace("Sept.", "Sep."))
    for fmt in DATE_FORMATS:
        try: return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError: pass
    m = re.search(r"[A-Z][a-z]+\.? \d{1,2}, \d{4}", s)   # дата внутри более длинного текста
    return norm_date(m.group(0)) if m and m.group(0) != s else ""

def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    r.raise_for_status()
    return r

def sitemap_urls(root):
    """Находит sitemap через robots.txt, рекурсивно раскрывает индексы."""
    try:
        robots = get(urljoin(root, "/robots.txt")).text
        maps = re.findall(r"(?im)^sitemap:\s*(\S+)", robots)
    except Exception:
        maps = []
    if not maps:
        maps = [urljoin(root, "/sitemap.xml")]
    found, queue = [], list(maps)
    while queue:
        sm = queue.pop()
        try:
            time.sleep(PAUSE)
            r = get(sm)
            data = gzip.decompress(r.content) if sm.endswith(".gz") else r.content
            soup = BeautifulSoup(data, "xml")
        except Exception as e:
            print("  sitemap fail", sm, e)
            continue
        for s in soup.find_all("sitemap"):
            queue.append(s.loc.text.strip())
        for u in soup.find_all("url"):
            lm = u.find("lastmod")
            found.append((u.loc.text.strip(), norm_date(lm.text) if lm else ""))
    return found

def wayback_urls(prefixes, since="2025"):
    """Список страниц из индекса Wayback Machine: (исходный url, дата копии, url копии)."""
    found = {}
    for pre in prefixes:
        q = ("https://web.archive.org/cdx/search/cdx?url=" + pre + "&matchType=prefix&from=" + since +
             "&filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey&fl=timestamp,original&output=json")
        try:
            time.sleep(PAUSE)
            data = get(q).json()[1:]
        except Exception as e:
            print("  cdx fail", pre, e); continue
        for ts, orig in data:
            if "?" in orig: continue
            key = re.sub(r"^https?://(www\.)?|:80(?=/)", "", orig).rstrip("/").lower()
            if key not in found or ts > found[key][1]:
                found[key] = ("https://www." + key, ts, f"https://web.archive.org/web/{ts}id_/{orig}")
    return [(u, f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", fetch) for u, ts, fetch in found.values()]

def parse(url):
    soup = BeautifulSoup(get(url).text, "lxml")
    title = (soup.find("h1") or soup.find("title"))
    title = title.get_text(" ", strip=True) if title else ""
    date = ""
    for sel in [("meta", {"property": "article:published_time"}),
                ("meta", {"name": "date"}), ("meta", {"name": "DC.date"})]:
        m = soup.find(*sel)
        if m and m.get("content"):
            date = norm_date(m["content"])
            if date: break
    if not date:
        t = soup.find("time")
        if t: date = norm_date(t.get("datetime") or t.get_text(" ", strip=True))
    # Сначала находим сам текст статьи, потом чистим его. Нельзя удалять <header> во всём документе:
    # на state.gov из-за незакрытого тега статья оказывается внутри <header>.
    node = (soup.select_one("article .entry-content") or soup.select_one("div.body") or
            soup.find("article") or soup.find("main") or soup.body)
    if node:
        for tag in node(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()
    text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""
    return title, date, text

OUT = "docs.csv"

def save(rows):
    rows = sorted(rows, key=lambda r: r[2], reverse=True)[:MAX_TOTAL]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "url", "date", "title", "text"])
        w.writerows(rows)
    return len(rows)

def main():
    import argparse, os
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="собрать только эти источники (через запятую); остальные берутся из docs.csv")
    ap.add_argument("--quota", action="append", default=[], metavar="ИСТОЧНИК=N", help="изменить квоту источника")
    ap.add_argument("--out", default="docs.csv", help="куда записать результат")
    ap.add_argument("--include", action="append", default=[], metavar="ИСТОЧНИК=a,b",
                    help="заменить список разделов URL источника")
    ap.add_argument("--exclude-from", help="CSV с колонкой url: эти документы пропустить (уже собраны)")
    a = ap.parse_args()
    global OUT, MAX_TOTAL
    OUT = a.out
    for q in a.quota:
        name, n = q.rsplit("=", 1)
        for src in SOURCES:
            if src["name"] == name: src["quota"] = int(n)
    for inc in a.include:
        name, parts = inc.split("=", 1)
        for src in SOURCES:
            if src["name"] == name: src["include"] = parts.split(",")
    MAX_TOTAL = max(MAX_TOTAL, sum(s["quota"] for s in SOURCES))
    only = set(a.only.split(",")) if a.only else None
    rows, seen = [], set()
    if only and os.path.exists("docs.csv"):
        rows = [r for r in csv.reader(open("docs.csv", encoding="utf-8"))][1:]
        rows = [r for r in rows if r[0] not in only]
        seen = {r[1] for r in rows}
        print("из docs.csv оставлено:", len(rows))
    if a.exclude_from:
        seen |= {r["url"] for r in csv.DictReader(open(a.exclude_from, encoding="utf-8"))}
        print("исключено как уже собранные:", len(seen))
    for src in SOURCES:
        if only and src["name"] not in only: continue
        print("==", src["name"])
        if "wayback" in src:
            urls = wayback_urls(src["wayback"])
        else:
            urls = [(u, d, u) for u, d in sitemap_urls(src["root"])
                    if any(p.lower() in u.lower() for p in src["include"])]
        urls.sort(key=lambda x: x[1], reverse=True)   # свежие первыми
        print("  кандидатов:", len(urls))
        got = 0
        for u, lastmod, fetch in urls:
            if got >= src["quota"]: break
            if u in seen: continue
            try:
                time.sleep(PAUSE)
                title, date, text = parse(fetch)
            except Exception as e:
                print("  skip", u, e); continue
            slug = u.rstrip("/").split("/")[-1].lower()
            if re.search(r"press briefing|press gaggle|gaggle|briefing with", title, re.I) or "briefing" in slug:
                continue                            # брифинги пресс-секретарей не берём
            if len(text) < 600: continue          # списки и пустышки; короткие релизы (>600 знаков) оставляем
            if not mentions_issue(text): continue  # нет ни одной темы из списка
            seen.add(u)
            rows.append([src["name"], u, date or lastmod, title, text])
            got += 1
            if got % 25 == 0: print("  ", got)
        print("  собрано:", got)
        save(rows)                                  # промежуточное сохранение после каждого сайта
    print("Готово:", save(rows), "документов ->", OUT)

if __name__ == "__main__":
    csv.field_size_limit(sys.maxsize)
    main()
