# Commons'ta Milli Parklar Servisi'nin (PD-USGov-NPS, kamu malı) geniş taraması:
# park adları ve konular, sorgu başına 40, en az 2600 px. Önceki turlarda
# görülenler ve kataloğa girenler (scout/skip.txt) atlanır. Kolay seviye için
# desensiz eşiği gevşek: düz alan 0.50'ye kadar elenmez, "kolay" işaretlenir.
# Sonuç scout/out/nps/results.json.
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "tool")
import quality

OUT = "scout/out/nps"; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "StillpieceScout/1.0 (https://github.com/Walletude/stillpiece-art)"}
API = "https://commons.wikimedia.org/w/api.php"
PARKS = ["Yellowstone", "Yosemite", "Glacier", "Zion", "Grand Teton", "Acadia", "Arches",
         "Great Smoky", "Denali", "Olympic", "Rocky Mountain", "Bryce", "Grand Canyon",
         "Joshua Tree", "Sequoia", "Everglades", "Mount Rainier", "Shenandoah", "Crater Lake",
         "Canyonlands", "Death Valley", "Katmai", "Glacier Bay", "Kenai Fjords", "Redwood",
         "Capitol Reef", "Big Bend", "Lassen", "North Cascades", "Haleakala", "Hawaii Volcanoes",
         "Badlands", "Saguaro", "Channel Islands", "Great Sand Dunes", "Voyageurs",
         "Isle Royale", "Dry Tortugas", "Cape Hatteras", "Point Reyes"]
TOPICS = ["geyser", "hot spring", "elk", "moose", "bison", "bighorn", "bear", "wolf",
          "wildflowers", "waterfall", "autumn", "sunset", "snow", "lake reflection",
          "sand dunes", "coral", "bird", "butterfly", "aurora", "night sky"]
PER_QUERY = 40
LIMIT = 500
SKIP = set(open("scout/skip.txt").read().split())
BAD_RESTRICTIONS = {"personality", "trademarked", "insignia"}
# Kişi, yapı, tabela, etkinlik ve belge kareleri. Commons araması 300 karakterle
# sınırlı; birkaçı aramada, hepsi başlık ve açıklamada elenir.
NOT = "-ranger -visitor -sign -building -map"
BAD_WORDS = ("ranger", "visitor", "sign", "building", "construction", "staff",
             "superintendent", "ceremony", "meeting", "event", "volunteer", "employee",
             "map", "brochure", "logo", "poster", "museum", "exhibit", "bee inventory",
             "people", "hiker", "crowd", "family", "student", "parking", "road work")
EASY_FLAT = 0.50


def get(url, raw=False):
    for attempt in range(4):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            return b if raw else json.loads(b)
        except Exception as e:
            print("HATA", url[:120], e, flush=True); time.sleep(5 * (attempt + 1))
    return None


def search(term):
    q = f'{term} hastemplate:"PD-USGov-NPS" filetype:bitmap filew:>2600 {NOT}'
    r = get(API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrsearch": q,
        "gsrnamespace": 6, "gsrlimit": PER_QUERY, "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|mime"}))
    if r and "error" in r or len(q) > 300:
        print("ARAMA HATASI", len(q), (r or {}).get("error"), flush=True)
    pages = list(((r or {}).get("query") or {}).get("pages", {}).values())
    return sorted(pages, key=lambda p: p.get("index", 0))


def meta(ii, key):
    return ((ii.get("extmetadata") or {}).get(key) or {}).get("value") or ""


def score(c):
    path = c["file"]
    try:
        r = quality.score(path)
    except Exception as e:
        print("okunamadı", c["title"], e, flush=True); os.remove(path); return None
    w, h = c["size"]
    # Ölçü orijinal boyuta göre; indirilen kopya küçültülmüş olabilir.
    r["width"] = min(w, h * 2 // 3)
    why = [x for x in r["why"] if x not in ("küçük", "desensiz")]
    if r["width"] < quality.MIN_WIDTH:
        why.append("küçük")
    if r["flat"] > EASY_FLAT:
        why.append("desensiz")
    r["why"] = why
    r["easy"] = quality.MAX_FLAT < r["flat"] <= EASY_FLAT
    subprocess.run(["sips", "-Z", "500", path], capture_output=True)
    r.pop("grid", None)
    r.update(c)
    r["size"] = f"{w}x{h}"
    print(f"{os.path.basename(path)} {'GEÇTİ' if not why else ','.join(why):20} {c['title'][:70]}", flush=True)
    return r


def main():
    queries = [p + " National Park" for p in PARKS] + TOPICS
    per_query = []
    for term in queries:
        pages = search(term)
        print(term, len(pages), flush=True)
        per_query.append((term, pages))
        time.sleep(1)

    # Sorgular arasında sırayla al ki ilk sorgular sınırı doldurmasın.
    seen, cands = set(), []
    for i in range(PER_QUERY):
        for term, pages in per_query:
            if i >= len(pages) or len(cands) >= LIMIT:
                continue
            p = pages[i]
            key = p["title"][5:].replace(" ", "_")
            if key in SKIP or key in seen or not p.get("imageinfo"):
                continue
            seen.add(key)
            ii = p["imageinfo"][0]
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff"):
                continue
            restr = set(meta(ii, "Restrictions").split("|")) & BAD_RESTRICTIONS
            lic = meta(ii, "LicenseShortName")
        text = (p["title"] + " " + meta(ii, "ImageDescription")).lower()
        if re.search(r"\b(" + "|".join(BAD_WORDS) + r")s?\b", text):
            print("  kişi/yapı:", p["title"]); continue
            if restr or "public domain" not in lic.lower():
                print("  lisans/kısıt:", p["title"], lic, restr); continue
            cands.append(dict(title=p["title"], query=term, page=ii["descriptionurl"],
                              size=[ii["width"], ii["height"]], license=lic,
                              artist=meta(ii, "Artist")[:200], desc=meta(ii, "ImageDescription")[:300]))
    print("aday", len(cands), flush=True)

    results, jobs = [], []
    with ProcessPoolExecutor(3) as pool:
        for k, c in enumerate(cands):
            w, h = c["size"]
            # Ölçüm için yeterli boyut: 2:3 kırpınca 1686 genişlik kalacak kadar.
            need = min(w, max(1800, round(2600 * w / h)))
            url = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                   + urllib.parse.quote(c["title"][5:]) + f"?width={need}")
            data = get(url, raw=True)
            if not data:
                continue
            c["file"] = f"{OUT}/{k:03}.jpg"
            open(c["file"], "wb").write(data)
            jobs.append(pool.submit(score, c))
            time.sleep(0.5)
        results = [r for r in (j.result() for j in jobs) if r]

    results.sort(key=lambda r: (bool(r["why"]), r["flat"]))
    json.dump(results, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)
    ok = [r for r in results if not r["why"]]
    print(f"{len(ok)}/{len(results)} geçti, {sum(r['easy'] for r in ok)} kolay adayı")


# Alt süreçler (macOS spawn) dosyayı yeniden içe aktarır; tarama yalnızca ana süreçte.
if __name__ == "__main__":
    main()
