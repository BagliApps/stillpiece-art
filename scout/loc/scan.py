# LoC FSA/OWI renkli: önizlemeyi (1024 px) indirir, film kenarını keser,
# renk/netlik/düz alan ve en büyük yüzü ölçer. results.json'a 20'de bir yazar,
# yeniden başlatınca ölçülmüşleri atlar.
import json, os, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/Users/k.ab200062/Documents/Projeler/Kisisel/stillpiece-art/tool")
import quality
items = json.load(open(sys.argv[1]))
RES = f"{D}/results.json"
res = json.load(open(RES)) if os.path.exists(RES) else {}
LIMIT = int(os.environ.get("LIMIT", "0")) or len(items)

def src(img):
    u = img if img.startswith("http") else "https:" + img
    u = u.replace("cdn.loc.gov/service", "tile.loc.gov/storage-services/service")
    return u.rsplit(".", 1)[0][:-1] + "v.jpg"

def one(it):
    pk = str(it["pk"]); f = f"{D}/img/{pk}.jpg"; c = f"{D}/crop/{pk}.jpg"
    try:
        if not os.path.exists(f):
            b = urllib.request.urlopen(urllib.request.Request(src(it["img"]), headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
            open(f + ".part", "wb").write(b); os.replace(f + ".part", f)
        w, h = quality.size(f)
        subprocess.run(["sips", "-c", str(h * 88 // 100), str(w * 88 // 100), f, "--out", c], capture_output=True, check=True)
        r = quality.score(c); r.pop("grid", None); r.pop("why", None); r.pop("file", None)
        out = subprocess.run([f"{D}/faces", c], capture_output=True, text=True).stdout.split("\t")
        r["face"], r["faces"] = float(out[1]), int(out[2])
        r.update(pk=pk, title=it["title"], creator=it.get("creator"), link=it.get("link"), src=src(it["img"]))
        return pk, r
    except Exception as e:
        print("HATA", pk, e, flush=True); return pk, None

todo = [it for it in items[:LIMIT] if it.get("img") and str(it["pk"]) not in res]
print(len(todo), "ölçülecek", flush=True)
with ThreadPoolExecutor(6) as ex:
    for k, (pk, r) in enumerate(ex.map(one, todo), 1):
        if r: res[pk] = r
        if k % 20 == 0 or k == len(todo):
            json.dump(res, open(RES + ".tmp", "w"), ensure_ascii=False); os.replace(RES + ".tmp", RES)
            print(k, "/", len(todo), flush=True)
