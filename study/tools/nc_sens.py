"""Does the corpus verdict depend on the n_crit 9 convention? Rerun a stratified
sample of drag blocks at n_crit 7 and 11 and compare error medians."""
import csv, json, os
import numpy as np
import aerosandbox as asb

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))
rows = [r for r in csv.DictReader(open(os.path.join(BASE, "lsat-corpus.csv")))
        if r["config"] == "clean" and (r["source"] + "|" + r["airfoil"]) in GEO
        and GEO[r["source"] + "|" + r["airfoil"]]["config"] == "clean"]
blocks = {}
for r in rows:
    blocks.setdefault((r["source"] + "|" + r["airfoil"], float(r["Re"])), []).append(r)
keys = sorted(blocks)[::5]  # every 5th block: ~200 of 1000, stratified by sort order
print(f"sampling {len(keys)} blocks", flush=True)

def load_pts(path):
    pts = []
    for L in open(os.path.join(BASE, path), errors="replace").read().splitlines()[1:]:
        p = L.split()
        if len(p) >= 2:
            try:
                x, y = float(p[0]), float(p[1])
            except ValueError:
                continue
            if -0.5 <= x <= 1.5 and -0.6 <= y <= 0.6:
                pts.append([x, y])
    a = np.array(pts); a[:, 0] -= a[:, 0].min()
    return a / a[:, 0].max()

errs = {7: [], 9: [], 11: []}
af_cache = {}
for i, (key, Re) in enumerate(keys):
    try:
        if key not in af_cache:
            af_cache[key] = asb.Airfoil(coordinates=load_pts(GEO[key]["path"])).to_kulfan_airfoil()
    except Exception:
        continue
    af = af_cache[key]
    pts = blocks[(key[0], key[1])] if False else blocks[(key, Re)] if False else blocks[(key, Re)]
    pts = blocks[(key, Re)]
    alphas = np.array([float(p["alpha"]) for p in pts])
    meas = np.array([float(p["CD"]) for p in pts])
    for nc in (7, 9, 11):
        try:
            preds = [np.atleast_1d(af.get_aero_from_neuralfoil(alpha=alphas, Re=Re, mach=0.0,
                                                               model_size=s, n_crit=nc)["CD"]) for s in SIZES]
            m8 = np.mean(preds, axis=0)
            errs[nc] += list(np.abs(m8 - meas) * 1e4)
        except Exception:
            pass
    if (i + 1) % 40 == 0:
        print(f"{i+1}/{len(keys)}", flush=True)
print("\nN_CRIT SENSITIVITY (sampled clean drag blocks, mean-of-8, counts):")
for nc in (7, 9, 11):
    v = np.array(errs[nc])
    print(f"  n_crit {nc:2d}: n {len(v):5d}  median {np.median(v):6.1f}  MAE {v.mean():6.1f}")
