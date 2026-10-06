"""Диагностика Госдепа с текущим collect_docs.parse()."""
import sys, collections
sys.path.insert(0, ".")
import collect_docs as cd
src = [s for s in cd.SOURCES if s["name"] == "StateDept"][0]
maps = cd.sitemap_urls(src["root"])
print("sitemap urls:", len(maps))
urls = [(u, d) for u, d in maps if any(p.lower() in u.lower() for p in src["include"])]
urls.sort(key=lambda x: x[1], reverse=True)
print("candidates:", len(urls), urls[:3])
reasons = collections.Counter()
for u, d in urls[:25]:
    try:
        t, dt, x = cd.parse(u)
    except Exception as e:
        print("ERR", u, e); reasons["error"] += 1; continue
    r = "short" if len(x) < 600 else ("noissue" if not cd.mentions_issue(x) else "ok")
    reasons[r] += 1
    print(r, len(x), dt, t[:70], "|", x[:120])
print(reasons)
