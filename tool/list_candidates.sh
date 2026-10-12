#!/bin/sh
# Müzedeki kamu malı (CC0) ve yüksek çözünürlüklü tüm eserleri aday listesi
# olarak tool/aic_candidates.json'a yazar. Yüksek çözünürlük: 2:3 dikey
# kırpılınca genişliği en az 1686 px kalan görsel (build.py büyük seviyelerde
# bu boyda indiriyor). Veri build.py ile aynı S3 dosyasından gelir.
# Liste yalnızca künye bilgisi taşır; görsel indirmez. sources.tsv'ye eser
# seçerken bakmak için.
# Kullanım: proje kökünde  sh tool/list_candidates.sh [artic-api-data.tar.bz2]
set -e

URL="https://artic-api-data.s3.amazonaws.com/artic-api-data.tar.bz2"
CACHE="${TMPDIR:-/tmp}/stillpiece-aic"
DUMP="${1:-$CACHE/artic-api-data.tar.bz2}"
mkdir -p "$CACHE"

if [ -z "$1" ] && [ -z "$(find "$DUMP" -mtime -7 2>/dev/null)" ]; then
  echo "Müze verisi indiriliyor (~130 MB)..."
  curl -fsSL "$URL" -o "$DUMP.tmp"
  mv "$DUMP.tmp" "$DUMP"
fi

OUT="$CACHE/all"
rm -rf "$OUT"
mkdir -p "$OUT"
echo "Eser kayıtları açılıyor (~140 bin dosya, bir iki dakika sürer)..."
tar -xjf "$DUMP" -C "$OUT" 'artic-api-data/json/artworks/'

python3 - "$OUT/artic-api-data/json/artworks" tool/aic_candidates.json <<'EOF'
import collections, json, os, sys
root, dest = sys.argv[1], sys.argv[2]
rows = []
for name in os.listdir(root):
    try:
        d = json.load(open(os.path.join(root, name)))
    except ValueError:
        continue
    t = d.get("thumbnail") or {}
    w, h = t.get("width") or 0, t.get("height") or 0
    if d.get("is_public_domain") is not True or not d.get("image_id"):
        continue
    if min(w, h * 2 / 3) < 1686:
        continue
    rows.append({
        "id": d["id"],
        "image_id": d["image_id"],
        "title": d.get("title"),
        "artist": d.get("artist_title"),
        "date": d.get("date_display"),
        "type": d.get("artwork_type_title"),
        "w": w,
        "h": h,
        "subjects": d.get("subject_titles") or [],
        "boost": d.get("boost_rank"),
    })
# Önce müzenin öne çıkardıkları (boost_rank küçük = popüler), sonra numara.
rows.sort(key=lambda r: (r["boost"] is None, r["boost"] or 0, r["id"]))
with open(dest, "w") as f:
    f.write("[\n")
    f.write(",\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    f.write("\n]\n")
print("%d aday -> %s" % (len(rows), dest))
for kind, n in collections.Counter(r["type"] for r in rows).most_common(10):
    print("  %6d  %s" % (n, kind))
EOF
rm -rf "$OUT"
