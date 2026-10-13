# Commons'tan ABD federal kurumlarının (kamu malı) doğa fotoğrafları. İlk tur
# (scout/out/commons) yalnızca editörlerin seçtiklerini aldı; bu tur tüm havuzu
# konu konu tarar (en az 2600 px). Her biri tool/quality.py ile puanlanır,
# sonuç scout/out/commons2/index.html.
import json, os, subprocess, sys, time, urllib.parse, urllib.request
sys.path.insert(0, "tool")
import quality

OUT = "scout/out/commons2"; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "StillpieceScout/1.0 (https://github.com/Walletude/stillpiece-art)"}
API = "https://commons.wikimedia.org/w/api.php"
AGENCIES = ["PD-USGov-NPS", "PD-USGov-FWS", "PD-USGov-NOAA", "PD-USGov-USGS",
            "PD-USGov-USDA-FS", "PD-USGov-BLM"]
TOPICS = ["wildlife", "bird", "landscape", "mountain", "lake", "waterfall", "flowers",
          "forest", "canyon", "coral reef", "autumn", "fox", "bear", "butterfly"]
PER_QUERY = 6
LIMIT = 220
# Kişilik hakkı / marka uyarısı olanlar alınmaz.
BAD_RESTRICTIONS = {"personality", "trademarked", "insignia"}


def get(url, raw=False):
    for attempt in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            return b if raw else json.loads(b)
        except Exception as e:
            print("HATA", url[:120], e, flush=True); time.sleep(3 * (attempt + 1))
    return None


def search(agency, topic):
    # Böcek laboratuvarının yakın çekimleri yapboz için itici; dışarıda kalsın.
    q = f'{topic} hastemplate:"{agency}" filetype:bitmap filew:>2600 -"Bee Inventory"'
    r = get(API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q,
        "gsrnamespace": 6, "gsrlimit": PER_QUERY, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|mime"}))
    return list(((r or {}).get("query") or {}).get("pages", {}).values())


def meta(ii, key):
    return ((ii.get("extmetadata") or {}).get(key) or {}).get("value") or ""


seen, cands = set(), []
for agency in AGENCIES:
    for topic in TOPICS:
        pages = search(agency, topic)
        print(agency, topic, len(pages), flush=True)
        for p in pages:
            if p["title"] in seen or not p.get("imageinfo"):
                continue
            seen.add(p["title"])
            ii = p["imageinfo"][0]
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff"):
                continue
            restr = set(meta(ii, "Restrictions").split("|")) & BAD_RESTRICTIONS
            lic = meta(ii, "LicenseShortName")
            if restr or "public domain" not in lic.lower():
                print("  lisans/kısıt:", p["title"], lic, restr); continue
            cands.append(dict(title=p["title"], agency=agency, topic=topic,
                              page=ii["descriptionurl"], size=[ii["width"], ii["height"]],
                              license=lic, artist=meta(ii, "Artist")[:200],
                              desc=meta(ii, "ImageDescription")[:300]))
        time.sleep(1)
cands = cands[:LIMIT]
print("aday", len(cands), flush=True)

results = []
for k, c in enumerate(cands):
    w, h = c["size"]
    # Ölçüm için yeterli boyut: 2:3 kırpınca 1686 genişlik kalacak kadar.
    need = min(w, max(1800, round(2600 * w / h)))
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(c["title"][5:]) + f"?width={need}"
    data = get(url, raw=True)
    if not data:
        continue
    path = f"{OUT}/{k:03}.jpg"
    open(path, "wb").write(data)
    try:
        r = quality.score(path)
    except Exception as e:
        print("okunamadı", c["title"], e); os.remove(path); continue
    # Ölçü orijinal boyuta göre; indirilen kopya küçültülmüş olabilir.
    r["width"] = min(w, h * 2 // 3)
    r["why"] = [x for x in r["why"] if x != "küçük"] + (["küçük"] if r["width"] < quality.MIN_WIDTH else [])
    # Sayfa için küçük kopya yeter (depoyu şişirmesin).
    subprocess.run(["sips", "-Z", "600", path], capture_output=True)
    r.update(c)
    r["file"] = path
    r["size"] = f"{w}x{h}"
    results.append(r)
    print(f"{k:03} {'GEÇTİ' if not r['why'] else ','.join(r['why']):20} {c['title'][:70]}", flush=True)
    time.sleep(0.5)

results.sort(key=lambda r: (bool(r["why"]), r["flat"]))
quality.write_html(results, f"{OUT}/index.html")
for r in results:
    r.pop("grid", None)
json.dump(results, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)
print(f"{sum(1 for r in results if not r['why'])}/{len(results)} geçti")
