"""Aday görselleri yapboza uygunluk için puanlar ve eler (fotoğraf taraması).

Dört ölçü:
- genişlik: 2:3 kırpılınca kalan genişlik (uygulama en çok 1686 px kullanır)
- renk:     renk canlılığı (Hasan-Süsstrunk); soluk ve gri kareler düşük
- netlik:   konunun (en belirgin kenarların) keskinliği, uygulamadaki boyutta
- düz:      desensiz (gökyüzü, durgun su, düz duvar gibi) en büyük bitişik
            alanın görsele oranı; bu alanın parçaları birbirinden ayrılmaz

Yalnızca macOS'un sips komutunu kullanır (Pillow/numpy gerekmez).

Kullanım: python3 tool/quality.py [--html sayfa.html] görsel...
"""

import html
import os
import struct
import subprocess
import sys
import tempfile

MIN_WIDTH = 1686
MIN_COLOR = 25
MIN_SHARP = 55
MAX_FLAT = 0.30

# Düz alan ızgarası: 24x36 hücre (her biri ~70 px, kabaca bir yapboz parçası
# kadar, 1686 px genişlikte).
GRID_W, GRID_H = 24, 36
CELL = 10  # hücre başına 10x10 piksel ölçülür
# Bir hücre, komşu pikseller arası ortalama parlaklık farkı bunun altındaysa
# düz sayılır (0-255 ölçeğinde).
FLAT_EDGE = 2.5
# Rengi de çevresinden ayrılmıyorsa düz: hücrenin renk sapması bunun altında.
FLAT_SPREAD = 6.0


def size(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                         capture_output=True, text=True, check=True).stdout
    vals = {}
    for line in out.splitlines():
        k, _, v = line.strip().partition(": ")
        if k in ("pixelWidth", "pixelHeight"):
            vals[k] = int(v)
    return vals["pixelWidth"], vals["pixelHeight"]


def load_rgb(path, w, h):
    """Görseli w x h'ye küçültüp satır satır (r, g, b) bayt dizisi döndürür."""
    with tempfile.TemporaryDirectory() as tmp:
        bmp = os.path.join(tmp, "x.bmp")
        subprocess.run(["sips", "-s", "format", "bmp", "-z", str(h), str(w), path, "--out", bmp],
                       capture_output=True, check=True)
        data = open(bmp, "rb").read()
    off = struct.unpack_from("<I", data, 10)[0]
    bw, bh = struct.unpack_from("<ii", data, 18)
    bpp = struct.unpack_from("<H", data, 28)[0] // 8
    stride = (bw * bpp + 3) & ~3
    rows = []
    for y in range(abs(bh)):
        sy = abs(bh) - 1 - y if bh > 0 else y  # BMP alttan üste
        row = data[off + sy * stride: off + sy * stride + bw * bpp]
        # BMP sırası BGR(A)
        rows.append((row[2::bpp], row[1::bpp], row[0::bpp]))
    return bw, abs(bh), rows


def luma(rows):
    return [[(77 * r + 150 * g + 29 * b) >> 8 for r, g, b in zip(*row)] for row in rows]


def colorfulness(rows):
    n = s_rg = s_yb = q_rg = q_yb = 0
    for rs, gs, bs in rows:
        for r, g, b in zip(rs, gs, bs):
            rg = r - g
            yb = (r + g) / 2 - b
            s_rg += rg; s_yb += yb; q_rg += rg * rg; q_yb += yb * yb; n += 1
    m_rg, m_yb = s_rg / n, s_yb / n
    sd = (max(0, q_rg / n - m_rg ** 2) + max(0, q_yb / n - m_yb ** 2)) ** 0.5
    return sd + 0.3 * (m_rg ** 2 + m_yb ** 2) ** 0.5


def sharpness(path, w, h):
    """Netlik, görselin uygulamadaki boyutunda (Crete yeniden bulanıklaştırma
    ölçüsü): görsel 9 px'lik ortalamayla bulanıklaştırılınca komşu piksel
    farklarının ne kadarı kaybolur. Net görselde çoğu kaybolur, zaten bulanık
    olanda az. İçerikten büyük ölçüde bağımsız; 0-100, yüksek net. En belirgin
    kenarlı karelerin (konu) ortancası; arka planın bulanık olması sorun değil."""
    tw = min(w, MIN_WIDTH)
    th = round(h * tw / w)
    bw, bh, rows = load_rgb(path, tw, th)
    g = luma(rows)
    tiles = {}

    def add(k, d, v):
        t = tiles.get(k)
        if t is None:
            tiles[k] = [d, v]
        else:
            t[0] += d; t[1] += v

    # Yatay: her ikinci satırda, kayan 9'luk ortalamayla.
    for y in range(0, bh, 2):
        row = g[y]
        acc = sum(row[:9])
        prev_b = acc / 9
        for x in range(5, bw - 4):
            acc += row[x + 4] - row[x - 5]
            bx = acc / 9
            d = abs(row[x] - row[x - 1])
            add((y // 64, x // 64), d, max(0, d - abs(bx - prev_b)))
            prev_b = bx
    # Dikey: her ikinci sütunda.
    for x in range(0, bw, 2):
        col = [g[y][x] for y in range(bh)]
        acc = sum(col[:9])
        prev_b = acc / 9
        for y in range(5, bh - 4):
            acc += col[y + 4] - col[y - 5]
            by = acc / 9
            d = abs(col[y] - col[y - 1])
            add((y // 64, x // 64), d, max(0, d - abs(by - prev_b)))
            prev_b = by
    edged = sorted(tiles.values(), key=lambda t: t[0], reverse=True)
    top = edged[:max(1, len(edged) // 4)]
    vals = sorted(v / d for d, v in top if d)
    return 100 * vals[len(vals) // 2] if vals else 0


def flat_share(rows, cols, lines):
    """Düz hücrelerden oluşan en büyük bitişik alanın oranı ve düz hücre ızgarası."""
    g = luma(rows)
    flat = [[False] * cols for _ in range(lines)]
    for cy in range(lines):
        for cx in range(cols):
            edge = n = 0
            sr = sg = sb = qr = qg = qb = 0
            for y in range(cy * CELL, cy * CELL + CELL):
                gr = g[y]
                rs, gs, bs = rows[y]
                for x in range(cx * CELL, cx * CELL + CELL):
                    if x + 1 < len(gr):
                        edge += abs(gr[x + 1] - gr[x])
                    if y + 1 < len(g):
                        edge += abs(g[y + 1][x] - gr[x])
                    r, gg, b = rs[x], gs[x], bs[x]
                    sr += r; sg += gg; sb += b; qr += r * r; qg += gg * gg; qb += b * b
                    n += 1
            spread = sum(max(0, q / n - (s / n) ** 2) for s, q in ((sr, qr), (sg, qg), (sb, qb))) ** 0.5
            flat[cy][cx] = edge / (2 * n) < FLAT_EDGE and spread < FLAT_SPREAD
    seen = [[False] * cols for _ in range(lines)]
    best = 0
    for sy in range(lines):
        for sx in range(cols):
            if not flat[sy][sx] or seen[sy][sx]:
                continue
            stack, count = [(sy, sx)], 0
            seen[sy][sx] = True
            while stack:
                y, x = stack.pop()
                count += 1
                for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if 0 <= ny < lines and 0 <= nx < cols and flat[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            best = max(best, count)
    return best / (cols * lines), flat


def score(path):
    w, h = size(path)
    portrait = h >= w
    # Izgara görselin yönüne göre (yatayda 36x24); kırpma yeri henüz belli değil.
    crop_w = min(w, h * 2 // 3)
    gw, gh = (GRID_W * CELL, GRID_H * CELL) if portrait else (GRID_H * CELL, GRID_W * CELL)
    _, _, rows = load_rgb(path, gw, gh)
    flat, grid = flat_share(rows, gw // CELL, gh // CELL)
    r = {
        "file": path,
        "size": f"{w}x{h}",
        "width": crop_w,
        "color": round(colorfulness(rows), 1),
        "sharp": round(sharpness(path, w, h), 1),
        "flat": round(flat, 2),
        "grid": grid,
    }
    why = []
    if crop_w < MIN_WIDTH:
        why.append("küçük")
    if r["color"] < MIN_COLOR:
        why.append("soluk")
    if r["sharp"] < MIN_SHARP:
        why.append("bulanık")
    if r["flat"] > MAX_FLAT:
        why.append("desensiz")
    r["why"] = why
    return r


def write_html(results, out):
    rows = []
    for r in results:
        cols = len(r["grid"][0])
        cells = "".join(
            "<i style='background:%s'></i>" % ("rgba(255,0,0,.45)" if f else "transparent")
            for line in r["grid"] for f in line)
        ok = not r["why"]
        name = f"<b>{html.escape(r.get('title') or os.path.basename(r['file']))}</b>"
        if r.get("page"):
            name = f"<a href='{html.escape(r['page'])}' target=_blank>{name}</a>"
        rows.append(
            f"<figure class='{'ok' if ok else 'no'}'><div class='im' style='aspect-ratio:{r['size'].replace('x', '/')}'>"
            f"<img src='{html.escape(os.path.relpath(r['file'], os.path.dirname(out) or '.'))}'>"
            f"<div class='g' style='grid-template-columns:repeat({cols},1fr)'>{cells}</div></div><figcaption>{name}<br>"
            f"{r['size']} · renk {r['color']} · netlik {r['sharp']} · düz {r['flat']}<br>"
            f"<span>{'geçti' if ok else ', '.join(r['why'])}</span></figcaption></figure>")
    page = f"""<!doctype html><meta charset=utf-8><title>Kalite taraması</title>
<style>body{{font:13px system-ui;margin:16px;background:#fff;color:#222}}
.wrap{{display:flex;flex-wrap:wrap;gap:12px}}figure{{margin:0;width:200px}}
.im{{position:relative;width:200px;background:#eee}}
.im img{{display:block;width:100%;height:100%}}
.g{{position:absolute;inset:0;display:none}}
body.show .g{{display:grid}}.g i{{display:block}}
.no span{{color:#c00;font-weight:600}}.ok span{{color:#080;font-weight:600}}</style>
<label><input type=checkbox onchange="document.body.classList.toggle('show',this.checked)">
Düz bölgeleri göster (kırmızı)</label>
<p>Eşikler: genişlik ≥ {MIN_WIDTH}, renk ≥ {MIN_COLOR}, netlik ≥ {MIN_SHARP}, düz ≤ {MAX_FLAT}</p>
<div class=wrap>{''.join(rows)}</div>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    args = sys.argv[1:]
    out = None
    if args[:1] == ["--html"]:
        out, args = args[1], args[2:]
    if not args:
        sys.exit(__doc__)
    results = []
    for p in args:
        try:
            r = score(p)
        except (ValueError, KeyError, subprocess.CalledProcessError, struct.error):
            print(f"OKUNAMADI {os.path.basename(p)}")
            continue
        results.append(r)
        print(f"{'GEÇTİ' if not r['why'] else 'ELENDİ':7} {os.path.basename(p):40} {r['size']:>10} "
              f"renk {r['color']:5} netlik {r['sharp']:5} düz {r['flat']:4}  {', '.join(r['why'])}")
    if out:
        write_html(results, out)
        print(f"Sayfa: {out}")
    print(f"{sum(1 for r in results if not r['why'])}/{len(args)} geçti")


if __name__ == "__main__":
    main()
