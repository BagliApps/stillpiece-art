# Tarama sonucundan seçim sayfası: geçenler (kolay adayları etiketli), tıklayarak
# işaretlenir, "Seçilenleri kopyala" numara listesini panoya alır.
# Kullanım: python3 scout/secim.py scout/out/nps
import html, json, os, sys

out = sys.argv[1]
res = json.load(open(f"{out}/results.json"))
ok = [r for r in res if not r["why"]]
# Kolay adayları sonda, düz alana göre; geri kalanlar sorguya göre gruplu.
ok.sort(key=lambda r: (r["easy"], r["flat"] if r["easy"] else 0, r["query"]))
cells = []
for n, r in enumerate(ok, 1):
    r["n"] = n
    tag = "<em>Kolay adayı</em>" if r["easy"] else ""
    cells.append(
        f"<label class=f><input type=checkbox value={n}><div class=im>"
        f"<img loading=lazy src='{html.escape(os.path.basename(r['file']))}'>{tag}</div>"
        f"<span class=n>{n}</span> <a href='{html.escape(r['page'])}' target=_blank>"
        f"{html.escape(r['title'][5:60])}</a><br><small>{html.escape(r['query'])} · {r['size']}"
        f" · renk {r['color']} · netlik {r['sharp']} · düz {r['flat']}</small></label>")
easy = sum(r["easy"] for r in ok)
page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><title>NPS adayları</title>
<style>body{{font:13px system-ui;margin:16px;background:#fff;color:#222}}.w{{display:flex;flex-wrap:wrap;gap:12px}}
.f{{width:200px;cursor:pointer}}.im{{position:relative;width:200px;height:300px;background:#eee;outline:4px solid transparent;opacity:.55}}
.im img{{width:100%;height:100%;object-fit:cover;display:block}}input{{display:none}}input:checked+.im{{outline-color:#1a7f37;opacity:1}}
.im em{{position:absolute;top:6px;left:6px;background:#1a7f37;color:#fff;font:600 11px system-ui;padding:2px 6px;border-radius:4px}}
.n{{font-weight:700}}#bar{{position:sticky;top:0;background:#fff;padding:8px 0;z-index:1}}</style>
<div id=bar><b>{len(ok)} aday</b> ({len(res)} taranan; {easy} "Kolay adayı": düz alan 0.30–0.50, Başlangıç/Kolay için).
Kareler 2:3 kırpılmış gibi gösteriliyor. Tıklayarak seç, sonra
<button onclick="let v=[...document.querySelectorAll('input:checked')].map(e=>e.value).join(',');navigator.clipboard.writeText(v);this.textContent='Kopyalandı ('+(v?v.split(',').length:0)+')'">Seçilenleri kopyala</button></div>
<div class=w>{''.join(cells)}</div>"""
open(f"{out}/secim.html", "w", encoding="utf-8").write(page)
json.dump(ok, open(f"{out}/secim.json", "w"), ensure_ascii=False, indent=1)
print(f"{out}/secim.html: {len(ok)} aday, {easy} kolay")
