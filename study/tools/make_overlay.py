"""Build nfb-measured.json: Studio airfoil-file id -> measured LSAT drag-polar
blocks [[Re, [[alpha, CL, CD], ...]], ...] (clean configs only), so the site can
overlay real wind-tunnel points on the prediction charts."""
import csv, json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))
dat_ids = set()
for root, _, files in os.walk(os.path.join(BASE, "coords")):
    for f in files:
        if f.lower().endswith(".dat"):
            dat_ids.add(f[:-4].lower())

def file_id(entry, g):
    p = os.path.basename(g["path"]).lower()
    if p.endswith(".dat"):
        return p[:-4]
    base = re.sub(r"[^a-z0-9]", "", p[:-4].lower())  # stec8 .COR name
    for cand in (base, base[:-1] if len(base) > 3 and base[-1].isalpha() else base):
        if cand in dat_ids:
            return cand
    return None

out = {}
n = 0
for r in csv.DictReader(open(os.path.join(BASE, "lsat-corpus.csv"))):
    key = r["source"] + "|" + r["airfoil"]
    g = GEO.get(key)
    if not g or g["config"] != "clean":
        continue
    fid = file_id(key, g)
    if not fid:
        continue
    blocks = out.setdefault(fid, {})
    b = blocks.setdefault(str(int(float(r["Re"]))), {"src": r["source"], "pts": []})
    b["pts"].append([round(float(r["alpha"]), 2), round(float(r["CL"]), 3),
                     round(float(r["CD"]), 5)])
    n += 1
json.dump(out, open(os.path.join(BASE, "nfb-measured.json"), "w"), separators=(",", ":"))
print(f"{n} points across {len(out)} airfoil ids; "
      f"size {os.path.getsize(os.path.join(BASE, 'nfb-measured.json'))/1e3:.0f} KB")
print("sample ids:", sorted(out)[:10])
