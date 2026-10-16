# Kıyas için küçük örnek: Commons'ta FWS, NOAA ve DOCUMERICA (EPA, 1971-77)
# fotoğraflarından kaynak başına 40 aday puanlanır; geçme oranı ve geçenlerden
# 12'şer küçük kopya scout/out/ornek/ altına yazılır. skip.txt'dekiler atlanır.
import json, os, re, subprocess, sys, time, urllib.parse
sys.path.insert(0, "scout"); sys.path.insert(0, "tool")
from nps import get, info, meta, API, SKIP, BAD_RESTRICTIONS, BAD_WORDS
import quality

OUT = "scout/out/ornek"; os.makedirs(OUT, exist_ok=True)
SOURCES = {
    "fws": ('hastemplate:"PD-USGov-FWS"', ["bird", "elk", "wildflowers", "refuge sunset", "butterfly",
                                          "fox", "owl", "marsh", "salmon", "wetland"]),
    "noaa": ('hastemplate:"PD-USGov-NOAA"', ["coral reef", "sea turtle", "whale", "ship", "coast",
                                            "fish", "lighthouse", "sea lion", "storm clouds", "reef"]),
    "documerica": ('DOCUMERICA', ["", "park", "beach", "city", "farm", "river", "street", "lake",
                                  "autumn", "boat"]),
}
PER_SOURCE, KEEP = 40, 12


def search(base, term, n=8):
    q = f'{term} {base} filetype:bitmap filew:>1800 -ranger -visitor -sign -map'.strip()
    r = get(API + "?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "list": "search", "srsearch": q,
        "srnamespace": 6, "srlimit": n}))
    return [x["title"] for x in ((r or {}).get("query") or {}).get("search", [])]


def main():
    summary = {}
    for name, (base, terms) in SOURCES.items():
        titles, seen = [], set()
        for t in terms:
            for x in search(base, t):
                key = x[5:].replace(" ", "_")
                if key not in SKIP and x not in seen:
                    seen.add(x); titles.append(x)
            time.sleep(1)
        infos = info(titles)
        rows, k = [], 0
        for title in titles:
            if len(rows) >= PER_SOURCE:
                break
            ii = infos.get(title)
            if not ii:
                continue
            lic = meta(ii, "LicenseShortName")
            restr = set(meta(ii, "Restrictions").split("|")) & BAD_RESTRICTIONS
            text = (title + " " + meta(ii, "ImageDescription")).lower()
            if restr or "public domain" not in lic.lower() or \
                    re.search(r"\b(" + "|".join(BAD_WORDS) + r")s?\b", text):
                continue
            data = ii.get("thumburl") and get(ii["thumburl"], raw=True, tries=2)
            if not data:
                continue
            path = f"{OUT}/{name}_{k:02}.jpg"; k += 1
            open(path, "wb").write(data)
            try:
                r = quality.score(path)
            except Exception as e:
                print("okunamadı", title, e); os.remove(path); continue
            r.pop("grid", None)
            r.update(title=title, page=ii["descriptionurl"], orig=f'{ii["width"]}x{ii["height"]}',
                     desc=re.sub("<[^>]+>", "", meta(ii, "ImageDescription"))[:200])
            r["width"] = min(ii["width"], ii["height"] * 2 // 3)
            r["why"] = [x for x in r["why"] if x != "küçük"] + (["küçük"] if r["width"] < quality.MIN_WIDTH else [])
            rows.append(r)
            print(name, os.path.basename(path), ",".join(r["why"]) or "GEÇTİ", title[:70], flush=True)
            time.sleep(0.2)
        ok = [r for r in rows if not r["why"]]
        keep = (ok + [r for r in rows if r["why"]])[:KEEP]
        for r in rows:
            if r in keep:
                subprocess.run(["sips", "-Z", "800", r["file"]], capture_output=True)
            else:
                os.remove(r["file"])
        summary[name] = dict(bakilan=len(rows), gecen=len(ok), ornek=keep)
        print(name, f"{len(ok)}/{len(rows)} geçti", flush=True)
    json.dump(summary, open(f"{OUT}/ornek.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
