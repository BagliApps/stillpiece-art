# LoC FSA/OWI renkli (Kodachrome) fotoğraflar: fabrika, uçak, demiryolu. "No known restrictions".
import io, json, os, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw
OUT = "scout/out"; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 stillpiece-scout"}
def get(url, raw=False):
    try:
        b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
        return b if raw else json.loads(b)
    except Exception as e:
        print("HATA", url, e, flush=True); return None
out = []
for q in ["factory", "aircraft", "railroad", "steel", "welding", "machine shop"]:
    r = get("https://www.loc.gov/pictures/search/?" + urllib.parse.urlencode({"q": q, "co": "fsac", "fo": "json", "c": 8}))
    res = (r or {}).get("results") or []
    print(q, len(res), flush=True)
    for it in res:
        img = it.get("image") or {}
        u = img.get("full") or img.get("square")
        if u and u.startswith("//"): u = "https:" + u
        out.append(dict(q=q, title=it.get("title"), url=u, link=it.get("links", {}).get("item"), thumb=img.get("thumb")))
json.dump(out, open(f"{OUT}/loc.json", "w"), ensure_ascii=False, indent=1)
TW, TH, COLS = 200, 300, 8
sheet = Image.new("RGB", (COLS * (TW + 6), ((len(out) + COLS - 1) // COLS) * (TH + 6)), "white")
dr = ImageDraw.Draw(sheet)
for k, c in enumerate(out):
    c["no"] = k + 1
    b = get(c["url"], raw=True) if c["url"] else None
    if not b: continue
    im = Image.open(io.BytesIO(b)).convert("RGB"); w, h = im.size
    cw, ch = min(w, h * 2 / 3), min(h, w * 3 / 2)
    im = im.crop((int((w - cw) / 2), int((h - ch) / 2), int((w + cw) / 2), int((h + ch) / 2))).resize((TW, TH))
    x, y = (k % COLS) * (TW + 6), (k // COLS) * (TH + 6)
    sheet.paste(im, (x, y)); dr.rectangle((x, y, x + 34, y + 22), fill="black"); dr.text((x + 4, y + 4), str(k + 1), fill="white")
    c["size"] = [w, h]
sheet.save(f"{OUT}/loc_sheet.jpg", quality=85)
json.dump(out, open(f"{OUT}/loc.json", "w"), ensure_ascii=False, indent=1)
