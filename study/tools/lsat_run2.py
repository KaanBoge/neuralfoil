"""Run all 8 NeuralFoil sizes over the entire LSAT measured corpus.
Conditions: mach 0, free transition, n_crit 9 (UIUC low-turbulence subsonic
tunnel; the standard comparison value in the LSAT literature; stated as the
convention). Geometry per lsat-geometry.json. One vectorized call per
(entry, Re, size) over that block's measured alphas.
Output lsat-nf2.csv: one row per measured point with per-size CL/CD + xlarge
confidence. Failures are logged, not hidden.
"""
import csv, json, os, sys, traceback
import numpy as np
import aerosandbox as asb

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))
rows = list(csv.DictReader(open(os.path.join(BASE, "lsat-corpus.csv"))))

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
    a = np.array(pts)
    a[:, 0] -= a[:, 0].min()
    c = a[:, 0].max()
    return a / c

blocks = {}
for r in rows:
    key = r["source"] + "|" + r["airfoil"]
    if key not in GEO:
        continue
    blocks.setdefault((key, float(r["Re"])), []).append(r)

out = open(os.path.join(BASE, "lsat-nf2.csv"), "w", newline="")
w = csv.writer(out)
w.writerow(["source", "airfoil", "config", "geom_kind", "Re", "alpha", "CL_meas", "CD_meas", "u_cd_span"]
           + [f"CL_{s}" for s in SIZES] + [f"CD_{s}" for s in SIZES] + ["conf_xlarge", "tc", "topxtr", "botxtr", "cm8"])
af_cache, fails, done = {}, [], 0
for (key, Re), pts in sorted(blocks.items()):
    try:
        g = GEO[key]
        if key not in af_cache:
            coords = load_pts(g["path"])
            af = asb.Airfoil(name=key.split("|")[1], coordinates=coords).to_kulfan_airfoil()
            af_cache[key] = (af, float(af.max_thickness()))
        af, tc = af_cache[key]
        alphas = np.array([float(p["alpha"]) for p in pts])
        res = {}
        xtr = {}
        cms = []
        for s in SIZES:
            o = af.get_aero_from_neuralfoil(alpha=alphas, Re=Re, mach=0.0,
                                            model_size=s, n_crit=9)
            res[s] = (np.atleast_1d(o["CL"]), np.atleast_1d(o["CD"]),
                      np.atleast_1d(o["analysis_confidence"]))
            cms.append(np.atleast_1d(o["CM"]))
            if s == "xlarge":
                xtr[0] = np.atleast_1d(o["Top_Xtr"]); xtr[1] = np.atleast_1d(o["Bot_Xtr"])
        cm8 = np.mean(cms, axis=0)
        for i, p in enumerate(pts):
            w.writerow([p["source"], p["airfoil"], g["config"], g["kind"], Re,
                        p["alpha"], p["CL"], p["CD"], p["u_cd_span"]]
                       + [f"{res[s][0][i]:.5f}" for s in SIZES]
                       + [f"{res[s][1][i]:.6f}" for s in SIZES]
                       + [f"{res['xlarge'][2][i]:.4f}", f"{tc:.4f}",
                          f"{xtr[0][i]:.4f}", f"{xtr[1][i]:.4f}", f"{cm8[i]:.5f}"])
    except Exception as e:
        fails.append((key, Re, repr(e)))
    done += 1
    if done % 50 == 0:
        print(f"{done}/{len(blocks)} blocks", flush=True)
out.close()
print(f"DONE {done} blocks, {len(fails)} failures")
for f in fails[:20]:
    print("FAIL", f)
