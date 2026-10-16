# Seviyeli tarama sonucundan seçim sayfası: geçenler seviyelere göre gruplu, her
# karede düz alan ve benzer parça. Tıklayınca seçilir; seviye kutusundan değiştirilebilir.
# "Seçilenleri kopyala" numara listesini verir, seviyesi değişenler "12:orta" biçiminde.
# Kullanım: python3 scout/secim_seviye.py scout/out/fws
import html, json, os, sys

LEVELS = [("baslangic", "Başlangıç"), ("kolay", "Kolay"), ("orta", "Orta"), ("zor", "Zor"),
          ("uzman", "Uzman"), ("usta", "Usta"), ("buyukUsta", "Büyük Usta")]
out = sys.argv[1]
res = json.load(open(f"{out}/results.json"))
ok = [r for r in res if not r["why"]]
rank = {k: i for i, (k, _) in enumerate(LEVELS)}
ok.sort(key=lambda r: (rank[r["level"]], r["twin"]))
sections, n = [], 0
for key, name in LEVELS:
    group = [r for r in ok if r["level"] == key]
    cells = []
    for r in group:
        n += 1; r["n"] = n
        opts = "".join(f"<option value={k}{' selected' if k == key else ''}>{v}</option>" for k, v in LEVELS)
        cells.append(
            f"<label class=f><input type=checkbox value={n} data-l={key}><div class=im>"
            f"<img loading=lazy src='{html.escape(os.path.basename(r['file']))}'></div></label>"
            f"<div class=t><span class=n>{n}</span> <select>{opts}</select> "
            f"<a href='{html.escape(r['page'])}' target=_blank>{html.escape(r['title'][5:50])}</a><br>"
            f"<small>düz {r['flat']} · benzer {r['twin']} · netlik {r['sharp']} · {r['size']}</small></div>")
    if group:
        sections.append(f"<h2>{name} <small>({len(group)})</small></h2><div class=w>"
                        + "".join(f"<div>{c}</div>" for c in cells) + "</div>")
counts = " · ".join(f"{v} {sum(r['level'] == k for r in ok)}" for k, v in LEVELS)
page = f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width"><title>FWS adayları</title>
<style>body{{font:13px system-ui;margin:16px;background:#fff;color:#222}}.w{{display:flex;flex-wrap:wrap;gap:12px}}
.w>div{{width:200px}}.f{{cursor:pointer}}.im{{width:200px;height:300px;background:#eee;outline:4px solid transparent;opacity:.55}}
.im img{{width:100%;height:100%;object-fit:cover;display:block}}input{{display:none}}input:checked+.im{{outline-color:#1a7f37;opacity:1}}
.n{{font-weight:700}}h2{{margin:28px 0 8px}}#bar{{position:sticky;top:0;background:#fff;padding:8px 0;z-index:1}}</style>
<div id=bar><b>{len(ok)} aday</b> ({len(res)} taranan) — {counts}<br>
Seviye: düz alan seviyeyi verir, benzer parça tavanı (≥0.80 Başlangıç, ≥0.60 Kolay, ≥0.45 Orta, ≥0.30 Uzman).
Kareler 2:3 kırpılmış gibi. Tıklayarak seç, seviyeyi kutudan değiştir, sonra
<button onclick="let v=[...document.querySelectorAll('input:checked')].map(e=>{{let s=e.closest('.w>div').querySelector('select').value;return s==e.dataset.l?e.value:e.value+':'+s}}).join(',');navigator.clipboard.writeText(v);this.textContent='Kopyalandı ('+(v?v.split(',').length:0)+')'">Seçilenleri kopyala</button></div>
{''.join(sections)}"""
open(f"{out}/secim.html", "w", encoding="utf-8").write(page)
json.dump(ok, open(f"{out}/secim.json", "w"), ensure_ascii=False, indent=1)
print(f"{out}/secim.html: {len(ok)} aday — {counts}")
