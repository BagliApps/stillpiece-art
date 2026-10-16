"""Stillpiece eser deposunu kurar: sources.tsv'deki eserleri Art Institute of
Chicago'dan, fotoğrafları Wikimedia Commons'tan (ABD federal kurumlarının
kamu malı işleri) indirir, 2:3 kırpar, ölçer, seviyelere dağıtır ve
catalog.json'u yazar. Yalnızca eksik görselleri indirir; var olanların
seviyesi değişmez.

Kullanım: python3 build.py <artic-api-data.tar.bz2>
Müze verisi (kamu malı denetimi ve künye için):
https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2
"""

import hashlib
import io
import json
import os
import sys
import tarfile
import time
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image

LEVELS = ["baslangic", "kolay", "orta", "zor", "uzman", "usta", "buyukUsta", "efsane"]
# Küçük seviyelerde ~1000 px yeter; büyüklerde müzenin izin verdiği en büyük
# genişlik (kamu malı eserde 1686).
WIDTH = {l: 1000 if i < 4 else 1686 for i, l in enumerate(LEVELS)}
THUMB_WIDTH = 300
CATEGORIES = {"doga", "deniz", "sehir", "naturmort", "hayvan"}
IIIF = "https://www.artic.edu/iiif/2"
COMMONS = "https://commons.wikimedia.org"
# Kamu malı sayılan Commons şablonları ve künyede yazılacak kurum adı.
AGENCIES = {
    "PD-USGov-NPS": "National Park Service",
    "PD-USGov-FWS": "U.S. Fish and Wildlife Service",
    "PD-USGov-NOAA": "NOAA",
    "PD-USGov-USGS": "U.S. Geological Survey",
    "PD-USGov-USDA-FS": "U.S. Forest Service",
    "PD-USGov-BLM": "Bureau of Land Management",
}
# Commons'ta kişilik hakkı ya da marka uyarısı olan görsel alınmaz.
BAD_RESTRICTIONS = {"personality", "trademarked", "insignia"}
# Müze AIC-User-Agent başlığını rica ediyor; Python'un varsayılan
# "Python-urllib" kimliği ise 403 alıyor.
UA = {
    "AIC-User-Agent": "Stillpiece (yapboz uygulamasi; github.com/BagliApps/stillpiece-art)",
    "User-Agent": "Stillpiece/1.0 (+https://github.com/BagliApps/stillpiece-art)",
}


def read_sources():
    rows = []
    for line in open("sources.tsv", encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        if len(p) < 5:
            sys.exit(f"HATA: eksik sütun: {line!r}")
        if p[2] not in CATEGORIES:
            sys.exit(f"HATA: bilinmeyen kategori {p[2]} ({p[1]})")
        level = p[6] if len(p) > 6 and p[6] else None
        if level and level not in LEVELS:
            sys.exit(f"HATA: bilinmeyen seviye {level} ({p[1]})")
        commons = p[0][len("commons:"):] if p[0].startswith("commons:") else None
        rows.append({
            "aicId": 0 if commons else int(p[0]),
            "file": commons,
            "slug": p[1],
            "category": p[2],
            "focusX": float(p[3]),
            "title": p[4],
            "titleEn": p[5] if len(p) > 5 and p[5] else None,
            "level": level,
        })
    slugs = [r["slug"] for r in rows]
    if len(set(slugs)) != len(slugs):
        sys.exit("HATA: aynı slug iki kez")
    return rows


def read_museum(dump, ids):
    """Müze kayıtları, yalnızca listedeki eserler."""
    want = {f"artic-api-data/json/artworks/{i}.json": i for i in ids}
    found = {}
    with tarfile.open(dump, "r:bz2") as tar:
        for m in tar:
            i = want.get(m.name)
            if i is not None:
                found[i] = json.load(tar.extractfile(m))
                if len(found) == len(want):
                    break
    return found


def get(url):
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            time.sleep(1)  # müze istekler arasında 1 sn bekleme rica ediyor
            return data
        except Exception as e:
            print(f"  tekrar ({attempt + 1}): {url}: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"indirilemedi: {url}")


def fetch_master(image_id, focus_x):
    """Eserin 2:3 kısmını sunucuda kesip en büyük genişlikte indirir."""
    info = json.loads(get(f"{IIIF}/{image_id}/info.json"))
    w, h = info["width"], info["height"]
    if w * 3 > h * 2:
        cw, ch = h * 2 // 3, h
        x, y = int((w - cw) * focus_x), 0
    else:
        cw, ch = w, w * 3 // 2
        x, y = 0, (h - ch) // 2
    out = min(1686, cw)
    data = get(f"{IIIF}/{image_id}/{x},{y},{cw},{ch}/{out},/0/default.jpg")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return to_ratio(img)


def read_commons(files):
    """Commons kayıtları: boyut ve kamu malı denetimi için şablonlar, lisans."""
    found = {}
    for i in range(0, len(files), 40):
        batch = files[i:i + 40]
        q = urllib.parse.urlencode({
            "action": "query", "format": "json", "formatversion": 2,
            "titles": "|".join("File:" + f for f in batch),
            "prop": "imageinfo|templates", "iiprop": "size|extmetadata",
            "tltemplates": "|".join("Template:" + t for t in AGENCIES), "tllimit": "max"})
        data = json.loads(get(f"{COMMONS}/w/api.php?{q}"))
        norm = {n["to"]: n["from"] for n in data["query"].get("normalized", [])}
        for page in data["query"]["pages"]:
            name = norm.get(page["title"], page["title"])[len("File:"):]
            if page.get("missing") or not page.get("imageinfo"):
                continue
            ii = page["imageinfo"][0]
            meta = ii.get("extmetadata") or {}
            agencies = [AGENCIES[t["title"][len("Template:"):]] for t in page.get("templates", [])]
            found[name] = {
                "width": ii["width"],
                "height": ii["height"],
                "license": (meta.get("LicenseShortName") or {}).get("value", ""),
                "restrictions": set(filter(None, (meta.get("Restrictions") or {}).get("value", "").split("|"))),
                "agency": agencies[0] if agencies else None,
            }
    return found


def fetch_commons(name, w, h, focus_x):
    """Görseli 2:3 kırpılınca en çok 1686 genişlik kalacak boyutta indirir,
    kırpmayı burada yapar (Commons sunucuda kesmiyor)."""
    crop_w = min(w, h * 2 // 3)
    scale = min(1, 1686 / crop_w)
    width = max(1, round(w * scale))
    url = f"{COMMONS}/wiki/Special:FilePath/{urllib.parse.quote(name)}?width={width}"
    img = Image.open(io.BytesIO(get(url))).convert("RGB")
    w, h = img.size
    if w * 3 > h * 2:
        cw = h * 2 // 3
        x = int((w - cw) * focus_x)
        img = img.crop((x, 0, x + cw, h))
    return to_ratio(img)


def to_ratio(img):
    """Tam 2:3 olsun; sunucunun yuvarlamasından kalan birkaç pikseli keser."""
    w, h = img.size
    if w * 3 > h * 2:
        cw = h * 2 // 3
        return img.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    ch = w * 3 // 2
    return img.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))


def measure(img):
    """Aydınlık (ortalama parlaklık) ve ayrıntı (kenar yoğunluğu), 0-1."""
    g = np.asarray(img.convert("L").resize((400, 600), Image.LANCZOS), dtype=np.float32) / 255
    gx = np.abs(np.diff(g, axis=1))[:-1, :]
    gy = np.abs(np.diff(g, axis=0))[:, :-1]
    edges = np.hypot(gx, gy)
    return round(float(g.mean()), 4), round(float((edges > 0.06).mean()), 4)


def save_jpeg(img, width, path, quality):
    height = width * 3 // 2
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    data = buf.getvalue()
    with open(path, "wb") as f:
        f.write(data)
    return data


def sha(data):
    return hashlib.sha256(data).hexdigest()


def assign_levels(entries):
    """Yeni eserlere seviye verir: aydınlık ve ayrıntı sıralamasının
    ortalamasına göre, tüm eserler arasında eşit dilimlere. Seviyesi olanlar
    yerinde kalır, yeni eser eklenince eskiler kaymaz."""
    n = len(entries)
    def pct(key):
        order = sorted(range(n), key=lambda i: entries[i][key])
        r = [0] * n
        for pos, i in enumerate(order):
            r[i] = pos / max(1, n - 1)
        return r
    pb, pd = pct("bright"), pct("detail")
    score = [(pb[i] + pd[i]) / 2 for i in range(n)]
    order = sorted(range(n), key=lambda i: score[i])
    for pos, i in enumerate(order):
        if not entries[i].get("level"):
            entries[i]["level"] = LEVELS[min(len(LEVELS) - 1, pos * len(LEVELS) // n)]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sources = read_sources()
    museum = read_museum(sys.argv[1], [s["aicId"] for s in sources if not s["file"]])
    commons = read_commons([s["file"] for s in sources if s["file"]])

    # Kamu malı denetimi: biri bile geçmezse hiçbir şey yazılmaz.
    bad = 0
    for s in sources:
        if s["file"]:
            c = commons.get(s["file"])
            if c is None:
                print(f"HATA:  {s['slug']} Commons'ta yok"); bad += 1
            elif not c["agency"] or "public domain" not in c["license"].lower():
                print(f"HATA:  {s['slug']} ABD federal kamu malı değil ({c['license']})"); bad += 1
            elif c["restrictions"] & BAD_RESTRICTIONS:
                print(f"HATA:  {s['slug']} kısıtlı: {c['restrictions']}"); bad += 1
            continue
        d = museum.get(s["aicId"])
        if d is None:
            print(f"HATA:  {s['slug']} ({s['aicId']}) müzede kayıt yok"); bad += 1
        elif d.get("is_public_domain") is not True:
            print(f"HATA:  {s['slug']} kamu malı değil"); bad += 1
        elif not d.get("image_id"):
            print(f"HATA:  {s['slug']} görseli yok"); bad += 1
    if bad:
        sys.exit(f"{bad} eserde sorun var, hiçbir şey değişmedi.")

    old = {}
    if os.path.exists("catalog.json"):
        old = {a["slug"]: a for a in json.load(open("catalog.json", encoding="utf-8"))["art"]}
    os.makedirs("art", exist_ok=True)
    os.makedirs("thumb", exist_ok=True)
    os.makedirs("work", exist_ok=True)

    entries, masters = [], {}
    for s in sources:
        if s["file"]:
            c = commons[s["file"]]
            e = {
                "slug": s["slug"],
                "level": None,
                "category": s["category"],
                "title": s["title"],
                "titleEn": s["titleEn"] or s["title"],
                "artist": c["agency"],
                "source": "commons",
                "imageId": s["file"],
            }
        else:
            d = museum[s["aicId"]]
            artist = d.get("artist_title") or (d.get("artist_display") or "").split("\n")[0]
            e = {
                "slug": s["slug"],
                "level": None,
                "category": s["category"],
                "title": s["title"],
                "titleEn": s["titleEn"] or d["title"],
                "artist": artist,
                "aicId": s["aicId"],
                "imageId": d["image_id"],
            }
        prev = old.get(s["slug"])
        art_path, thumb_path = f"art/{s['slug']}.jpg", f"thumb/{s['slug']}.jpg"
        if prev and prev["imageId"] == e["imageId"] and os.path.exists(art_path) and os.path.exists(thumb_path):
            for k in ("level", "bright", "detail", "sha256", "bytes", "thumbSha256"):
                e[k] = prev[k]
        else:
            print(f"indiriliyor: {s['slug']}")
            if s["file"]:
                c = commons[s["file"]]
                img = fetch_commons(s["file"], c["width"], c["height"], s["focusX"])
            else:
                img = fetch_master(e["imageId"], s["focusX"])
            e["bright"], e["detail"] = measure(img)
            if prev and prev.get("level"):
                e["level"] = prev["level"]
            # Hepsini bellekte tutmak ~2 GB eder; seviye belli olana kadar diskte.
            masters[s["slug"]] = f"work/{s['slug']}.jpg"
            img.save(masters[s["slug"]], "JPEG", quality=97)
        # Listede sabitlenen seviye her zaman geçerli.
        if s["level"]:
            e["level"] = s["level"]
        entries.append(e)

    assign_levels(entries)

    for e in entries:
        master = masters.get(e["slug"])
        if master is None:
            continue
        img = Image.open(master).convert("RGB")
        width = min(WIDTH[e["level"]], img.size[0])
        data = save_jpeg(img, width, f"art/{e['slug']}.jpg", 86)
        thumb = save_jpeg(img, THUMB_WIDTH, f"thumb/{e['slug']}.jpg", 80)
        e["sha256"], e["bytes"], e["thumbSha256"] = sha(data), len(data), sha(thumb)
        print(f"  {e['slug']}: {e['level']} {width}px {len(data) // 1024} KB "
              f"aydınlık {e['bright']} ayrıntı {e['detail']}")

    # Listeden çıkarılan eserlerin dosyaları da gitsin.
    keep = {e["slug"] for e in entries}
    for folder in ("art", "thumb"):
        for f in os.listdir(folder):
            if f.endswith(".jpg") and f[:-4] not in keep:
                os.remove(os.path.join(folder, f))
                print(f"silindi: {folder}/{f}")

    with open("catalog.json", "w", encoding="utf-8") as f:
        json.dump({"schema": 1, "art": entries}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    counts = {l: sum(1 for e in entries if e["level"] == l) for l in LEVELS}
    total = sum(e["bytes"] for e in entries) / 1e6
    print(f"Tamam: {len(entries)} eser, {total:.0f} MB. Seviyeler: {counts}")


if __name__ == "__main__":
    main()
