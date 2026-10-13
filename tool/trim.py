"""Tablo ve baskılarda eserin çevresindeki düz kenarı (kâğıt payı, paspartu,
düz renkli şerit) bulur. Kenardan içeri doğru, satır/sütun tekdüze ve rengi
en dıştakine yakın oldukça ilerler; ince çizgileri (çerçeve çizgisi, leke)
atlayıp arkasında düz kenar sürüyorsa devam eder. Sonuç oranlarla
(sol, üst, sağ, alt) verilir; sources.tsv'nin 8. sütununa yazılır, build.py
kırpmadan önce bunları keser.

Yalnızca macOS'un sips komutunu kullanır.

Kullanım: python3 tool/trim.py görsel...
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quality

SIDE = 300        # ölçüm, uzun kenarı bu boyda küçültülmüş görselde
LINE_NEAR = 40.0  # düz satırda piksel ortanca renge en çok bu uzaklıkta (0-255)
LINE_SHARE = 0.85 # ... ve piksellerin en az bu kadarı öyle
NEAR = 18.0       # en dıştaki çizginin rengine uzaklık üst sınırı
SKIP = 0.025      # atlanabilecek ince çizgi kalınlığı (boyuta oran)
MAX = 0.25        # bir kenardan en çok kesilen oran
FRAME_NEAR = 30.0 # çerçeve bandı başka kenarlarda bu renk uzaklığında aranır
PAD = 0.006       # bulunan sınırın biraz içinden kes (çizgi kalıntısı kalmasın)
# Kenarın bittiği yerde eser, çizginin orta yarısının en az bu kadarında
# başlamalı. Portrenin koyu fonu ya da botanik baskının kâğıt zemini böyle
# değil (konu çizginin ortasında küçük bir yerde başlar); onlar kesilmez.
EDGE_COVER = 0.6


def _stats(px):
    """Satırın ortanca rengi ve ona yakın piksellerin oranı (toz, leke ve
    kâğıt dokusu oranı az düşürür)."""
    med = [sorted(p[i] for p in px)[len(px) // 2] for i in range(3)]
    near = sum(1 for p in px if _dist(p, med) <= LINE_NEAR)
    return med, near / len(px)


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _bands(lines):
    """Dıştan içe ardışık düz bantlar (fon, bordür, paspartu): her biri
    (bittiği derinlik, rengi). Bir bant yalnızca eser alanı çizgi boyunca
    başlıyorsa ya da arkasından yeni bir düz bant geliyorsa sayılır."""
    limit = int(len(lines) * MAX)
    skip = max(1, int(len(lines) * SKIP))
    bands, i = [], 0
    while i < limit:
        # Bantlar arasında yırtık kâğıt kenarı ya da gölge olabilir: sonraki
        # düz satır biraz içeride başlayabilir.
        start = i
        while i < min(limit, start + 2 * skip):
            ref, share = _stats(lines[i])
            if share >= LINE_SHARE:
                break
            i += 1
        else:
            break
        edge, gap, j = i + 1, 0, i + 1
        while j < limit:
            m, share = _stats(lines[j])
            if share >= LINE_SHARE and _dist(m, ref) <= NEAR:
                edge, gap = j + 1, 0
                ref = [0.9 * a + 0.1 * b for a, b in zip(ref, m)]  # kâğıt tonu yavaşça değişebilir
            else:
                gap += 1
                if gap > skip:
                    break
            j += 1
        if edge >= limit:
            break
        bands.append((edge, ref))
        i = edge
    # En içteki bandın ardında eser çizgi boyunca başlamıyorsa (portre fonu,
    # botanik baskının zemini) o bant kenar değildir.
    while bands:
        edge, ref = bands[-1]
        inside = lines[edge:edge + 3]
        n = len(inside[0])
        mid = [px for line in inside for px in line[n // 4: n - n // 4]]
        diff = sum(1 for px in mid if sum((a - b) ** 2 for a, b in zip(px, ref)) ** 0.5 > NEAR)
        if diff >= EDGE_COVER * len(mid):
            break
        bands.pop()
    return bands


def find(path):
    w, h = quality.size(path)
    s = SIDE / max(w, h)
    bw, bh, rows = quality.load_rgb(path, max(1, round(w * s)), max(1, round(h * s)))
    grid = [list(zip(*row)) for row in rows]  # grid[y][x] = (r, g, b)
    cols = [[grid[y][x] for y in range(bh)] for x in range(bw)]
    sides = [_bands(cols), _bands(grid), _bands(cols[::-1]), _bands(grid[::-1])]
    sizes = [bw, bh, bw, bh]
    fr = []
    for k, bands in enumerate(sides):
        # Çerçeve en az üç kenarda aynı renkte olur; tek kenardaki düz bant
        # (gökyüzü, deniz) resmin parçasıdır, kesilmez.
        depth = 0
        for edge, ref in bands:
            same = sum(1 for o, other in enumerate(sides) if o != k and any(
                sum((a - b) ** 2 for a, b in zip(ref, r2)) ** 0.5 <= FRAME_NEAR for _, r2 in other))
            if same < 2:
                break
            depth = edge
        fr.append(depth / sizes[k])
    return [round(min(MAX, f + PAD), 3) if f else 0.0 for f in fr]


def crop_box(w, h, trim):
    """Oranlardan piksel kutusu (x0, y0, x1, y1)."""
    l, t, r, b = trim
    return round(w * l), round(h * t), round(w * (1 - r)), round(h * (1 - b))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        print(os.path.basename(p), ",".join(f"{v:g}" for v in find(p)))
