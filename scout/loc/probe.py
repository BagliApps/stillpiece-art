# Tek eserin loc.gov JSON'u: TIFF bağlantısı ve hak bilgisi nerede?
import json, urllib.request
UA = {"User-Agent": "Mozilla/5.0 stillpiece-scout"}
out = {}
for u in ["https://www.loc.gov/pictures/item/2017877582/?fo=json", "https://www.loc.gov/item/2017877582/?fo=json"]:
    try:
        out[u] = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
    except Exception as e:
        out[u] = str(e)
json.dump(out, open("scout/loc/probe.json", "w"), ensure_ascii=False, indent=1)
