"""Диагностика: структура страниц Госдепа и доступность war.gov."""
import re, sys
sys.path.insert(0, ".")
import requests
from bs4 import BeautifulSoup
import collect_docs as cd

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/128.0.0.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}

def chain(el):
    out = []
    while el is not None and getattr(el, "name", None) not in (None, "[document]"):
        out.append(el.name + ("#" + el.get("id") if el.get("id") else "") +
                   ("." + ".".join(el.get("class", [])[:2]) if el.get("class") else ""))
        el = el.parent
    return " < ".join(out[:8])

print("=== StateDept structure")
url = "https://www.state.gov/releases/office-of-the-spokesman/2026/07/secretary-of-state-marco-rubio-remarks-to-the-press-13/"
html = requests.get(url, headers=H, timeout=30).text
for parser in ["lxml", "html.parser"]:
    soup = BeautifulSoup(html, parser)
    body = soup.body
    print(parser, "body text len:", len(body.get_text(" ", strip=True)) if body else None)
    blocks = sorted(soup.find_all(["div", "section", "article", "main"]),
                    key=lambda e: len(e.find_all("p", recursive=False)), reverse=True)[:3]
    for b in blocks:
        print("  p-children", len(b.find_all("p", recursive=False)), "|", chain(b))
    for tag in ["header", "nav", "footer", "aside"]:
        big = [t for t in soup.find_all(tag) if len(t.get_text(" ", strip=True)) > 2000]
        for t in big: print(f"  BIG <{tag}> len={len(t.get_text(' ', strip=True))} | {chain(t)}")
for cls in ["entry-content", "article", "post", "content"]:
    print(cls, "in html:", cls in html)

print("=== war.gov")
for u in ["https://www.war.gov/robots.txt", "https://www.war.gov/News/Speeches/",
          "https://www.war.gov/News/Releases/", "https://www.war.gov/sitemap.xml",
          "https://media.defense.gov/", "https://www.defense.gov/"]:
    try:
        r = requests.get(u, headers=H, timeout=30)
        print(u, "->", r.status_code, r.url, len(r.text), r.text[:150].replace("\n", " "))
    except Exception as e:
        print(u, "->", type(e).__name__, e)
try:
    maps = cd.sitemap_urls("https://www.war.gov")
    print("war.gov sitemap urls:", len(maps))
    import collections
    print(collections.Counter("/".join(u.split("/")[3:5]) for u, _ in maps).most_common(20))
except Exception as e:
    print("sitemap error", e)
