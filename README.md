# stillpiece-art

Stillpiece yapboz uygulamasının eser görselleri, GitHub Pages ile sunulur:
`https://walletude.github.io/stillpiece-art/catalog.json` (yedek:
`https://cdn.jsdelivr.net/gh/Walletude/stillpiece-art@main/catalog.json`).

- `sources.tsv`: elle seçilen eserler (müze numarası, slug, kategori, Türkçe ad). Slug değişmez; uygulamadaki kayıtlar ona bağlı.
- `build.py`: kamu malı denetimi, indirme, 2:3 kırpma, ölçüm ve seviye dağıtımı; `catalog.json`'u yazar. Yalnızca eksik görselleri indirir.
- Seviye ölçülerek verilir: aydınlık ve ayrıntı (kenar yoğunluğu) arttıkça daha yüksek seviye. Bir kez verilen seviye değişmez.
- `art/<slug>.jpg`: Başlangıç–Zor 1000 px, Uzman ve üstü 1686 px genişlik. `thumb/<slug>.jpg`: 300 px.

Eser eklemek: `sources.tsv`'ye satır ekle, push'la; workflow gerisini yapar.

Görseller The Art Institute of Chicago'nun açık arşivinden, CC0.
