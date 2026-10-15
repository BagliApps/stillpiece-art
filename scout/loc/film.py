# Kodachrome taramalarının film çerçevesini bulur: her kenardan içeri, çizginin
# orta %60'ı çoğunlukla çok koyu (ya da en dıştaki ince beyaz şerit) oldukça
# ilerler. Sonuç oranlarla (sol, üst, sağ, alt); sources.tsv 8. sütunu.
import sys
sys.path.insert(0, "/Users/k.ab200062/Documents/Projeler/Kisisel/stillpiece-art/tool")
import quality
SIDE, DARK, SHARE, MAX, PAD = 400, 45, 0.6, 0.16, 0.02

def trim(path):
    w, h = quality.size(path)
    gw, gh = (SIDE, round(SIDE * h / w)) if w >= h else (round(SIDE * w / h), SIDE)
    _, _, rows = quality.load_rgb(path, gw, gh)
    L = quality.luma(rows)
    cols = [[L[y][x] for y in range(gh)] for x in range(gw)]
    def side(lines):
        n = len(lines); lim = int(n * MAX); d = 0
        for i in range(lim):
            ln = lines[i]; m = len(ln); seg = ln[m // 5: m - m // 5]
            dark = sum(v < DARK for v in seg) / len(seg)
            bright = sum(v > 215 for v in seg) / len(seg)
            if dark >= SHARE or (i < n * 0.03 and bright >= SHARE):
                d = i + 1
            elif i - d > n * 0.01:
                break
        return round(d / n + PAD, 3) if d else 0.0
    return (side(cols), side(L), side(cols[::-1]), side(L[::-1]))

if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p.split("/")[-1], ",".join(str(v) for v in trim(p)))
