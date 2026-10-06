"""Диагностика: что отдают сайты Госдепа и Пентагона скрипту сбора (статус, длина текста, начало текста)."""
import re, sys
sys.path.insert(0, ".")
import requests
from bs4 import BeautifulSoup
import collect_docs as cd

UAS = {
    "script": cd.HEADERS["User-Agent"],
    "chrome": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0.0.0 Safari/537.36",
}
EXTRA = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9"}

def show(url, ua):
    try:
        r = requests.get(url, headers={"User-Agent": UAS[ua], **EXTRA}, timeout=30)
    except Exception as e:
        print(f"[{ua}] {url} -> {type(e).__name__} {e}"); return None
    soup = BeautifulSoup(r.text, "lxml")
    for t in soup(["script", "style", "nav", "header", "footer", "aside"]): t.decompose()
    node = soup.find("main") or soup.find("article") or soup.body
    text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)) if node else ""
    print(f"[{ua}] {url} -> {r.status_code}, html {len(r.text)}, text {len(text)}, "
          f"main={'yes' if soup.find('main') else 'no'}, issue={cd.mentions_issue(text)}")
    print("    ", text[:300].replace("\n", " "))
    return r

print("=== StateDept")
urls = [u for u, _ in cd.sitemap_urls("https://www.state.gov")
        if any(p in u.lower() for p in ["/remarks", "/speeches", "/secretary", "/strategy"])]
print("candidates", len(urls))
import collections
print(collections.Counter(u.split("/")[3] for u in urls).most_common(15))
sample = [u for u in urls if "remarks" in u][:3] + urls[:2]
for u in sample:
    for ua in UAS: show(u, ua)

print("=== DoD")
for u in ["https://www.defense.gov/robots.txt", "https://www.defense.gov/sitemap.xml",
          "https://www.defense.gov/News/Speeches/", "https://www.defense.gov/News/Releases/"]:
    for ua in UAS: show(u, ua)
