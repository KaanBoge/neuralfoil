"""Match every LSAT corpus airfoil entry to a geometry file, and classify
configuration modifiers that SoarTech-8 embeds in the airfoil NAME itself.
stec8: own profiler-measured .COR (public). Volumes: public UIUC coordinate
database (nominal geometry; COORD0x.TXT is not public-licensed and unused;
the geometry-noise probe bounds nominal-vs-built at median 0.4, worst 11 counts).
Writes lsat-geometry.json: entry -> {kind, path, config} plus a miss list.
"""
import csv, json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
entries = sorted(set((r["source"], r["airfoil"]) for r in
                     csv.DictReader(open(os.path.join(BASE, "lsat-corpus.csv")))))
dats = {}
for root, _, files in os.walk(os.path.join(BASE, "coords")):
    for f in files:
        if f.lower().endswith(".dat"):
            dats[f[:-4].lower()] = os.path.relpath(os.path.join(root, f), BASE)
cors = {}
for f in os.listdir(os.path.join(BASE, "stec8")):
    if f.upper().endswith(".COR"):
        cors[f[:-4].lower()] = os.path.join("stec8", f)

MOD_TOKENS = ("ust", "lst", "trip", "tape", "bump", "clay", "blowing", "rough",
              "turbulence", "thick t.e.", "modified", "gap", "repeat", "nf3",
              "nf6", "pf3", "f0,", " at 200k", "upside")
def split_name(raw):
    """-> (base airfoil token, config: clean|modified|flap|plate)."""
    s = raw.lower()
    if "flat plate" in s:
        return None, "plate"
    cfg = "modified" if any(t in s for t in MOD_TOKENS) else "clean"
    base = s.split(",")[0]
    for t in ("ust", "lst", "trip", "bump", "clay", "blowing", "high turbulence",
              "repeat", "thick t.e.", "modified", "nf3", "nf6", "pf3", "f0"):
        base = base.split(" " + t)[0]
    base = re.sub(r"\(.*?\)", "", base)
    base = re.sub(r"[^a-z0-9]", "", base)
    return base, cfg

def find_geo(src, base):
    pools = ([("profiler", cors), ("nominal", dats)] if src == "stec8"
             else [("nominal", dats)])
    for kind, pool in pools:
        keys = {re.sub(r"[^a-z0-9]", "", k): v for k, v in pool.items()}
        stem = base[:-1] if len(base) > 3 and base[-1].isalpha() else base
        cands = [base, stem, base + "sm", stem + "sm"]
        if base.startswith("naca"):
            cands += [base.replace("naca", "n", 1), base.replace("naca", "n", 1) + "sm"]
        for cand in cands:
            if cand in keys:
                return kind, keys[cand]
    return None

out, misses = {}, []
for src, af in entries:
    base, cfg = split_name(af)
    if cfg == "plate":
        misses.append(src + "|" + af + "  (flat plate: excluded by design)"); continue
    hit = find_geo(src, base)
    if hit:
        out[src + "|" + af] = {"kind": hit[0], "path": hit[1], "config": cfg}
    else:
        misses.append(src + "|" + af + "  (base '" + base + "')")
json.dump(out, open(os.path.join(BASE, "lsat-geometry.json"), "w"), indent=0)
n_clean = sum(1 for v in out.values() if v["config"] == "clean")
print(f"matched {len(out)}/{len(entries)}  (clean-config entries: {n_clean})")
print("misses:", len(misses))
for m in misses: print("  ", m)
