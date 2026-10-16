# Commons'ta Balık ve Yaban Hayatı Servisi'nin (PD-USGov-FWS, kamu malı) taraması:
# hayvan ve doğa konuları, sorgu başına 40, en az 2600 px. skip.txt'dekiler atlanır.
# Seviye iki ölçüden: düz alan (quality.flat) ve benzer parça (Usta ızgarasında
# birbirine çok benzeyen parça oranı). Düz alan seviyeyi verir, benzer parça
# tavanı; çim, kar, gün batımı gibi tekdüze dokular üst seviyelere çıkmaz.
# Sonuç scout/out/fws/results.json; workflow 5 dakikada bir dala commit'ler.
import json, os, re, subprocess, statistics, sys, time, urllib.parse
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "scout"); sys.path.insert(0, "tool")
from nps import get, info, meta, API, SKIP, BAD_RESTRICTIONS, BAD_WORDS
import quality

OUT = "scout/out/fws"; os.makedirs(OUT, exist_ok=True)
TOPICS = ["bald eagle", "sandhill crane", "whooping crane", "snow geese", "pelican", "heron",
          "egret", "spoonbill", "owl", "hummingbird", "warbler", "bluebird", "puffin", "loon",
          "swan", "wood duck", "hawk", "osprey", "elk", "bison", "moose", "pronghorn", "bighorn",
          "mountain goat", "fox", "bear", "wolf", "deer", "otter", "beaver", "alligator",
          "manatee", "butterfly", "monarch", "bee flower", "dragonfly", "frog", "turtle",
          "wildflowers", "autumn refuge", "sunrise refuge", "marsh", "prairie", "tundra",
          "waterfall", "snow refuge", "Alaska refuge", "lake reflection"]
PER_QUERY, LIMIT = 40, int(os.environ.get("LIMIT") or 600)
EXTRA = ("biologist", "hunter", "hunting", "angler", "fishing", "kid", "child", "truck",
         "banding", "workshop", "award", "director", "secretary", "intern", "drawing",
         "illustration", "line art", "specimen", "dead", "carcass")
BAD = re.compile(r"\b(" + "|".join(BAD_WORDS + EXTRA) + r")s?\b")
LEVELS = ["baslangic", "kolay", "orta", "zor", "uzman", "usta", "buyukUsta"]

# Benzer parça: Usta ızgarasında (14x21) hücrenin ortalama rengi ve dokusu;
# en az 8 çok benzer hücresi olan hücrelerin oranı.
C, R, K = 14, 21, 8


def twin_share(path, T=14, N=8):
    w, h = quality.size(path)
    H = R * K; W = max(C * K, round(H * w / h))
    bw, bh, rows = quality.load_rgb(path, W, H)
    x0 = (bw - C * K) // 2
    cs = []
    for cy in range(R):
        for cx in range(C):
            px = [(rows[y][0][x], rows[y][1][x], rows[y][2][x])
                  for y in range(cy * K, cy * K + K) for x in range(x0 + cx * K, x0 + cx * K + K)]
            m = [sum(p[i] for p in px) / len(px) for i in range(3)]
            cs.append((*m, statistics.pstdev(0.3 * p[0] + 0.59 * p[1] + 0.11 * p[2] for p in px)))
    n = 0
    for i, a in enumerate(cs):
        c = sum(1 for j, b in enumerate(cs) if j != i and (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 +
                (a[2] - b[2]) ** 2 + (2 * (a[3] - b[3])) ** 2 < T * T)
        n += c >= N
    return n / len(cs)


def level(flat, twin, width):
    by_flat = 0 if flat >= 0.30 else 1 if flat >= 0.15 else 2 if flat >= 0.06 else 3
    cap = 0 if twin >= 0.80 else 1 if twin >= 0.60 else 2 if twin >= 0.45 else 4 if twin >= 0.30 else 6
    if by_flat == 3:
        by_flat = (6 if twin < 0.20 and width >= 2400 else
                   5 if twin < 0.30 and width >= 2000 else
                   4 if twin < 0.40 else 3)
    return LEVELS[min(by_flat, cap)]


def score(c):
    path = c["file"]
    try:
        r = quality.score(path)
        r["twin"] = round(twin_share(path), 2)
    except Exception as e:
        print("okunamadı", c["title"], e, flush=True); os.remove(path); return None
    w, h = c["size"]
    r["width"] = min(w, h * 2 // 3)
    why = [x for x in r["why"] if x not in ("küçük", "desensiz")]
    if r["width"] < quality.MIN_WIDTH:
        why.append("küçük")
    if r["flat"] > 0.50:
        why.append("desensiz")
    r["why"] = why
    r["level"] = level(r["flat"], r["twin"], r["width"])
    subprocess.run(["sips", "-Z", "500", path], capture_output=True)
    r.pop("grid", None)
    r.update(c)
    r["size"] = f"{w}x{h}"
    print(f"{os.path.basename(path)} {'GEÇTİ ' + r['level'] if not why else ','.join(why):20} {c['title'][:60]}", flush=True)
    return r


def search(term):
    q = f'{term} hastemplate:"PD-USGov-FWS" filetype:bitmap filew:>2600 -ranger -visitor -sign -map'
    r = get(API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "list": "search", "srsearch": q,
        "srnamespace": 6, "srlimit": PER_QUERY}))
    return [x["title"] for x in ((r or {}).get("query") or {}).get("search", [])]


def save(results):
    results = sorted((r for r in results if r), key=lambda r: (bool(r["why"]), r.get("level", "")))
    json.dump(results, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)


def main():
    per_query = []
    for term in TOPICS:
        titles = search(term)
        print(term, len(titles), flush=True)
        per_query.append((term, titles))
        time.sleep(1)
    seen, order = set(), []
    for i in range(PER_QUERY):
        for term, titles in per_query:
            if i < len(titles):
                key = titles[i][5:].replace(" ", "_")
                if key not in SKIP and key not in seen:
                    seen.add(key); order.append((term, titles[i]))
    json.dump([t for _, t in order], open(f"{OUT}/titles.json", "w"), ensure_ascii=False)
    print("yeni dosya", len(order), flush=True)
    infos = info([t for _, t in order[:LIMIT * 2]])
    cands, drop = [], {}
    for term, title in order:
        if len(cands) >= LIMIT:
            break
        ii = infos.get(title)
        if not ii:
            continue
        lic = meta(ii, "LicenseShortName")
        restr = set(meta(ii, "Restrictions").split("|")) & BAD_RESTRICTIONS
        text = (title + " " + meta(ii, "ImageDescription")).lower()
        reason = ("biçim" if ii.get("mime") not in ("image/jpeg", "image/png", "image/tiff") else
                  "lisans/kısıt" if restr or "public domain" not in lic.lower() else
                  "kişi/yapı" if BAD.search(text) else None)
        if reason:
            drop[reason] = drop.get(reason, 0) + 1
            continue
        cands.append(dict(title=title, query=term, page=ii["descriptionurl"], thumb=ii.get("thumburl"),
                          size=[ii["width"], ii["height"]], license=lic,
                          artist=meta(ii, "Artist")[:200], desc=re.sub("<[^>]+>", "", meta(ii, "ImageDescription"))[:300]))
    print("elenen", drop, "aday", len(cands), flush=True)

    path = f"{OUT}/results.json"
    done = json.load(open(path)) if os.path.exists(path) else []
    have = {r["title"] for r in done}
    k = max((int(r["file"][-7:-4]) for r in done), default=-1)
    jobs = []
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
                save(done + [j.result() for j in jobs if j.done()])
            time.sleep(0.2)
        results = done + [r for r in (j.result() for j in jobs) if r]
    save(results)
    ok = [r for r in results if not r["why"]]
    print(f"{len(ok)}/{len(results)} geçti", {l: sum(r["level"] == l for r in ok) for l in LEVELS})


if __name__ == "__main__":
    main()
