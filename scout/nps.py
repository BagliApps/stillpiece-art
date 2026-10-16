# Commons'ta Milli Parklar Servisi'nin (PD-USGov-NPS, kamu malı) geniş taraması:
# park adları ve konular, sorgu başına 40, en az 2600 px. Önceki turlarda
# görülenler ve kataloğa girenler (scout/skip.txt) atlanır. Kolay seviye için
# desensiz eşiği gevşek: düz alan 0.50'ye kadar elenmez, "kolay" işaretlenir.
# Sonuç scout/out/nps/results.json; workflow 5 dakikada bir dala commit'ler, yeniden
# başlayan tarama orada olanları atlar.
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "tool")
import quality

OUT = "scout/out/nps"; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "StillpieceScout/1.0 (https://github.com/BagliApps/stillpiece-art)"}
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


def get(url, raw=False, tries=4):
    for attempt in range(tries):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
            return b if raw else json.loads(b)
        except Exception as e:
            print("HATA", url[:120], e, flush=True); time.sleep(5 * (attempt + 1))
    return None


def search(term):
    q = f'{term} hastemplate:"PD-USGov-NPS" filetype:bitmap filew:>2600 {NOT}'
    r = get(API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "list": "search", "srsearch": q,
        "srnamespace": 6, "srlimit": PER_QUERY}))
    if not r or "error" in r or len(q) > 300:
        print("ARAMA HATASI", len(q), (r or {}).get("error"), flush=True)
    return [x["title"] for x in ((r or {}).get("query") or {}).get("search", [])]


def info(titles):
    """Dosya bilgileri 10'arlı gruplarla: extmetadata büyük, tek yanıta sığmıyor."""
    out = {}
    for i in range(0, len(titles), 10):
        r = get(API + "?" + urllib.parse.urlencode({
            "action": "query", "format": "json", "titles": "|".join(titles[i:i + 10]),
            "prop": "imageinfo", "iiprop": "url|size|extmetadata|mime",
            # Standart küçük kopya: hazır üretilmiş, kısıtlamaya takılmaz.
            "iiurlwidth": 1920}))
        for p in ((r or {}).get("query") or {}).get("pages", {}).values():
            if p.get("imageinfo"):
                out[p["title"]] = p["imageinfo"][0]
        time.sleep(0.3)
    return out


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


def save(results):
    results = sorted((r for r in results if r), key=lambda r: (bool(r["why"]), r["flat"]))
    json.dump(results, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)


def main():
    queries = [p + " National Park" for p in PARKS] + TOPICS
    per_query = []
    for term in queries:
        titles = search(term)
        print(term, len(titles), flush=True)
        per_query.append((term, titles))
        time.sleep(1)

    # Sorgular arasında sırayla al ki ilk sorgular sınırı doldurmasın.
    seen, order = set(), []
    for i in range(PER_QUERY):
        for term, titles in per_query:
            if i < len(titles):
                key = titles[i][5:].replace(" ", "_")
                if key not in SKIP and key not in seen:
                    seen.add(key)
                    order.append((term, titles[i]))
    print("yeni dosya", len(order), "atlanan önceki", sum(len(t) for _, t in per_query) - len(order), flush=True)
    infos = info([t for _, t in order])
    cands, drop = [], {}
    for term, title in order:
        if len(cands) >= LIMIT:
            break
        ii = infos.get(title)
        lic = meta(ii, "LicenseShortName") if ii else ""
        restr = set(meta(ii, "Restrictions").split("|")) & BAD_RESTRICTIONS if ii else set()
        text = (title + " " + meta(ii, "ImageDescription")).lower() if ii else ""
        reason = ("bilgi yok" if not ii else
                  "biçim" if ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff") else
                  "lisans/kısıt" if restr or "public domain" not in lic.lower() else
                  "kişi/yapı" if re.search(r"\b(" + "|".join(BAD_WORDS) + r")s?\b", text) else None)
        if reason:
            drop[reason] = drop.get(reason, 0) + 1
            continue
        cands.append(dict(title=title, query=term, page=ii["descriptionurl"], thumb=ii.get("thumburl"),
                          size=[ii["width"], ii["height"]], license=lic,
                          artist=meta(ii, "Artist")[:200], desc=meta(ii, "ImageDescription")[:300]))
    print("elenen", drop, flush=True)
    print("aday", len(cands), flush=True)

    # Yarıda kalan bir turun sonuçları dalda durur; bakılanlar yeniden indirilmez.
    path = f"{OUT}/results.json"
    done = json.load(open(path)) if os.path.exists(path) else []
    have = {r["title"] for r in done}
    k = max((int(r["file"][-7:-4]) for r in done), default=-1)
    print("önceki kayıttan", len(done), flush=True)

    results, jobs = [], []
    with ProcessPoolExecutor(3) as pool:
        for c in cands:
            if c["title"] in have:
                continue
            k += 1
            thumb = c.pop("thumb")
            data = thumb and get(thumb, raw=True, tries=2)
            if not data:
                continue
            c["file"] = f"{OUT}/{k:03}.jpg"
            open(c["file"], "wb").write(data)
            jobs.append(pool.submit(score, c))
            if k % 25 == 24:
                print("indirilen", k + 1, flush=True)
                save(done + [j.result() for j in jobs if j.done()])
            time.sleep(0.2)
        results = done + [r for r in (j.result() for j in jobs) if r]

    save(results)
    ok = [r for r in results if not r["why"]]
    print(f"{len(ok)}/{len(results)} geçti, {sum(r['easy'] for r in ok)} kolay adayı")


# Alt süreçler (macOS spawn) dosyayı yeniden içe aktarır; tarama yalnızca ana süreçte.
if __name__ == "__main__":
    main()
