# Cleveland adaylarını puanlar: küçük görseli indirir, quality.score ile
# renk, netlik, düz alan ölçer. 25'te bir results.json'a yazar; yeniden
# başlayınca puanlanmışları atlar. Actions'ta çalışır (.github/workflows/cma.yml);
# kullanım: python3 scout/cma/scout.py [adet]
import json, os, subprocess, sys
sys.path.insert(0, "tool")
import quality

D = os.path.dirname(os.path.abspath(__file__))
IMG = "/tmp/cma-img"  # görseller commit edilmez (~1,4 GB)
os.makedirs(IMG, exist_ok=True)
OUT = os.path.join(D, "results.json")
sel = json.load(open(os.path.join(D, "sel.json")))
limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(sel)
done = json.load(open(OUT)) if os.path.exists(OUT) else []
have = {r["id"] for r in done}


def save():
    tmp = OUT + ".tmp"
    json.dump(done, open(tmp, "w"), ensure_ascii=False)
    os.replace(tmp, OUT)


def work(a):
    im = a["images"]
    url = (im.get("web") or {}).get("url")
    pr = im["print"]
    path = os.path.join(IMG, f"{a['id']}.jpg")
    r = {"id": a["id"], "title": a.get("title"), "dept": a.get("department"),
         "artist": ((a.get("creators") or [{}])[0].get("description") or ""),
         "date": a.get("creation_date"), "tech": a.get("technique"),
         "size": [int(pr["width"]), int(pr["height"])]}
    try:
        if not os.path.exists(path):
            subprocess.run(["curl", "-fsS", "--max-time", "30", url, "-o", path], check=True)
        q = quality.score(path)
        r.update(color=q["color"], sharp=q["sharp"], flat=q["flat"])
    except Exception as e:
        r["error"] = str(e)[:100]
    return r


from concurrent.futures import ThreadPoolExecutor
todo = [a for a in sel[:limit] if a["id"] not in have]
with ThreadPoolExecutor(8) as pool:
    for n, r in enumerate(pool.map(work, todo), 1):
        done.append(r)
        if n % 25 == 0:
            save()
            print(len(done), flush=True)
save()
print("bitti", len(done), flush=True)
