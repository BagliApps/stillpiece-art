# Met Open Access'ten aday tarar: kamu malı, dikey, renkli ve desenli eserler.
# Çıktı: scout/out/cands.json ve numaralı paftalar (sheet_*.jpg).
import io, json, os, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageStat, ImageFilter

API = "https://collectionapi.metmuseum.org/public/collection/v1"
Q = [("Hiroshige", "japon"), ("Hokusai", "japon"), ("Kuniyoshi", "japon"), ("Utamaro", "japon"), ("Kunisada", "japon"),
     ("Shahnama", "minyatur"), ("Mughal painting", "minyatur"), ("Persian miniature", "minyatur"), ("Rajput painting", "minyatur"),
     ("Klimt", "modern"), ("Mucha", "modern"), ("Kandinsky", "modern"), ("Franz Marc", "modern"), ("Macke", "modern"), ("Matisse", "modern"),
     ("Tiffany window", "dekor"), ("Iznik", "dekor"),
     ("Redouté", "doga"), ("Audubon", "doga"), ("flower still life", "doga"), ("Jacob Marrel", "doga")]
PER = int(os.environ.get("PER", "60"))
OUT = "scout/out"; os.makedirs(OUT, exist_ok=True)

def get(url, raw=False):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "stillpiece-scout/1.0"})
            b = urllib.request.urlopen(req, timeout=60).read()
            return b if raw else json.loads(b)
        except Exception as e:
            err = e; time.sleep(2 + 3 * i)
    print("HATA", url, err, file=sys.stderr); return None

def score(img):
    # renk doygunluğu, aydınlık ve ayrıntı (kenar yoğunluğu); 0..1 arası
    s = ImageStat.Stat(img.convert("HSV")).mean[1] / 255
    g = img.convert("L")
    b = ImageStat.Stat(g).mean[0] / 255
    d = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0] / 255
    return round(s, 3), round(b, 3), round(d, 3)

cands, seen = [], set()
for q, cat in Q:
    r = get(f"{API.replace('/v1', '/v1.1')}/search?" + urllib.parse.urlencode({"q": q, "hasImages": "true", "isPublicDomain": "true", "limit": PER}))
    if r and not r.get("objectIDs"): print(q, "yanıt:", str(r)[:300], file=sys.stderr)
    ids = (r or {}).get("objectIDs") or []
    n = 0
    for oid in ids[:PER]:
        if oid in seen: continue
        seen.add(oid)
        o = get(f"{API}/objects/{oid}")
        if not o or not o.get("isPublicDomain") or not o.get("primaryImageSmall"): continue
        end = o.get("artistEndDate") or ""
        try:
            if end and int(end[:4]) > 1955: continue  # TR/AB: ölümden 70 yıl
        except ValueError: pass
        b = get(o["primaryImageSmall"], raw=True)
        if not b: continue
        try: img = Image.open(io.BytesIO(b)).convert("RGB")
        except Exception: continue
        w, h = img.size
        if not 0.5 <= w / h <= 0.85: continue
        s, br, d = score(img)
        cands.append(dict(id=oid, q=q, cat=cat, title=o.get("title"), artist=o.get("artistDisplayName"),
                          date=o.get("objectDate"), cls=o.get("classification"), sat=s, bright=br, detail=d,
                          small=o["primaryImageSmall"], full=o.get("primaryImage"), url=o.get("objectURL")))
        n += 1
        time.sleep(0.05)
    print(q, len(ids), "uygun:", n, file=sys.stderr)

# soluk ya da desensizleri ele, kalanları puanla
keep = [c for c in cands if c["sat"] >= 0.18 and c["detail"] >= 0.06 and 0.2 <= c["bright"] <= 0.85]
for c in keep: c["score"] = round(c["sat"] + 2 * c["detail"], 3)
keep.sort(key=lambda c: (c["cat"], c["q"], -c["score"]))
# her aramadan en iyi 10
out, per = [], {}
for c in keep:
    if per.get(c["q"], 0) < 10: out.append(c); per[c["q"]] = per.get(c["q"], 0) + 1
for i, c in enumerate(out, 1): c["no"] = i
json.dump(out, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
print("toplam", len(cands), "elenmeden sonra", len(keep), "paftada", len(out), file=sys.stderr)

# paftalar: 10x4, 2:3 kırpılmış, numaralı
TW, TH, COLS, ROWS = 200, 300, 10, 4
for p in range(0, len(out), COLS * ROWS):
    page = out[p:p + COLS * ROWS]
    sheet = Image.new("RGB", (COLS * (TW + 6), ((len(page) + COLS - 1) // COLS) * (TH + 6)), "white")
    dr = ImageDraw.Draw(sheet)
    for k, c in enumerate(page):
        img = Image.open(io.BytesIO(get(c["small"], raw=True))).convert("RGB")
        w, h = img.size
        cw, ch = min(w, h * 2 / 3), min(h, w * 3 / 2)
        img = img.crop((int((w - cw) / 2), int((h - ch) / 2), int((w + cw) / 2), int((h + ch) / 2))).resize((TW, TH))
        x, y = (k % COLS) * (TW + 6), (k // COLS) * (TH + 6)
        sheet.paste(img, (x, y))
        dr.rectangle((x, y, x + 34, y + 22), fill="black")
        dr.text((x + 4, y + 4), str(c["no"]), fill="white")
    sheet.save(f"{OUT}/sheet_{p // (COLS * ROWS) + 1}.jpg", quality=85)
