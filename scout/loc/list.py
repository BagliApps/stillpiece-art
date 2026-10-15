# LoC FSA/OWI renkli koleksiyonunun tam listesi (kurumsal ağda loc.gov kapalı,
# yalnızca Actions'ta çalışır). Görseller tile.loc.gov'dan yerelde indirilir.
import json, sys, time, urllib.parse, urllib.request
OUT = "scout/loc/list.json"
UA = {"User-Agent": "Mozilla/5.0 stillpiece-scout"}
def get(url):
    for i in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception as e:
            print("HATA", url, e, flush=True); time.sleep(5 * (i + 1))
items, page = [], 1
while True:
    r = get("https://www.loc.gov/pictures/search/?" + urllib.parse.urlencode({"co": "fsac", "fo": "json", "c": 100, "sp": page}))
    if r is None:
        sys.exit("liste alınamadı")
    for it in r.get("results") or []:
        img = it.get("image") or {}
        items.append(dict(pk=it.get("pk"), title=it.get("title"), creator=it.get("creator"),
                          date=it.get("created_published_date"), img=img.get("full") or img.get("square"),
                          link=(it.get("links") or {}).get("item")))
    pages = r.get("pages") or {}
    print(page, len(items), pages.get("total"), flush=True)
    json.dump(items, open(OUT, "w"), ensure_ascii=False, indent=0)
    if not pages.get("next") or page >= int(pages.get("total") or 0):
        break
    page += 1; time.sleep(1)
if not items:
    sys.exit("0 sonuç")
