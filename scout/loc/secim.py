# Tarama sonucundan seçim sayfası: eşikleri geçenler, tanınabilir yüzü olanlar
# ve neredeyse aynı kareler çıkarılmış. Tıklayarak işaretlenir, "Seçilenleri
# kopyala" numara listesini panoya alır. Kullanım: python3 secim.py
import html, json, os, sys
sys.path.insert(0, "/Users/k.ab200062/Documents/Projeler/Kisisel/stillpiece-art/tool")
import quality
D = os.path.dirname(os.path.abspath(__file__))
res = list(json.load(open(f"{D}/results.json")).values())
def why(r):
    w = []
    if r["color"] < 25: w.append("soluk")
    if r["sharp"] < 55: w.append("bulanık")
    if r["flat"] > 0.50: w.append("desensiz")
    if r["face"] >= 0.05: w.append("kişi")
    return w
ok = [r for r in res if not why(r)]
# Neredeyse aynı kareler (aynı sahnenin art arda çekimleri): 9x8 fark özeti,
# en renklisi kalır.
def dhash(r):
    _, _, rows = quality.load_rgb(f"{D}/crop/{r['pk']}.jpg", 9, 8)
    l = quality.luma(rows)
    return [l[y][x] > l[y][x + 1] for y in range(8) for x in range(8)]
ok.sort(key=lambda r: -r["color"])
kept, hs, dup = [], [], 0
for r in ok:
    h = dhash(r)
    if any(sum(a != b for a, b in zip(h, o)) <= 8 for o in hs):
        dup += 1; continue
    hs.append(h); kept.append(r)
for r in kept:
    r["easy"] = r["flat"] > 0.30
kept.sort(key=lambda r: (r["easy"], r["flat"] if r["easy"] else -r["color"]))
cells = []
for n, r in enumerate(kept, 1):
    r["n"] = n
    tag = "<em>Başlangıç adayı</em>" if r["easy"] else ""
    cells.append(
        f"<label class=f><input type=checkbox value={n}><div class=im>"
        f"<img loading=lazy src='crop/{r['pk']}.jpg'>{tag}</div>"
        f"<span class=n>{n}</span> <a href='{html.escape(r['link'])}' target=_blank>"
        f"{html.escape((r['title'] or '')[:60])}</a><br><small>renk {r['color']} · netlik {r['sharp']}"
        f" · düz {r['flat']}</small></label>")
easy = sum(r["easy"] for r in kept)
gone = {k: sum(k in why(r) for r in res) for k in ("soluk", "bulanık", "desensiz", "kişi")}
page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><title>LoC adayları</title>
<style>body{{font:13px system-ui;margin:16px;background:#fff;color:#222}}.w{{display:flex;flex-wrap:wrap;gap:12px}}
.f{{width:200px;cursor:pointer}}.im{{position:relative;width:200px;height:300px;background:#eee;outline:4px solid transparent;opacity:.55}}
.im img{{width:100%;height:100%;object-fit:cover;display:block}}input{{display:none}}input:checked+.im{{outline-color:#1a7f37;opacity:1}}
.im em{{position:absolute;top:6px;left:6px;background:#1a7f37;color:#fff;font:600 11px system-ui;padding:2px 6px;border-radius:4px}}
.n{{font-weight:700}}#bar{{position:sticky;top:0;background:#fff;padding:8px 0;z-index:1}}</style>
<div id=bar><b>{len(kept)} aday</b> ({len(res)} taranan; elenen: {', '.join(f'{v} {k}' for k, v in gone.items())}, {dup} benzer kare;
{easy} "Başlangıç adayı": düz alan 0.30–0.50). Kareler 2:3 kırpılmış gibi gösteriliyor. Tıklayarak seç, sonra
<button onclick="let v=[...document.querySelectorAll('input:checked')].map(e=>e.value).join(',');navigator.clipboard.writeText(v);this.textContent='Kopyalandı ('+(v?v.split(',').length:0)+')'">Seçilenleri kopyala</button></div>
<div class=w>{''.join(cells)}</div>"""
open(f"{D}/secim.html", "w", encoding="utf-8").write(page)
json.dump(kept, open(f"{D}/secim.json", "w"), ensure_ascii=False, indent=1)
print(f"secim.html: {len(kept)} aday, {easy} kolay, {dup} benzer, elenen {gone}")
