"""Analysis of the full-corpus run: the measured ground-truth upgrade.
1. Core retest at scale: mean-of-8 vs classic xlarge on every clean measured point.
2. Measured error maps by Re, alpha, thickness: these replace the atlas-proxy
   verdict thresholds with wind-tunnel truth.
3. Spread-vs-measured-error: does 8-net disagreement rank true error?
4. Confidence blindspot measured against truth, not proxy.
Writes lsat-report.txt, lsat-thresholds.json, lsat-by-airfoil.csv.
"""
import csv, json, os
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
R = [r for r in csv.DictReader(open(os.path.join(BASE, "lsat-nf.csv")))]
CT = 1e4

pts = []
for r in R:
    if r["config"] != "clean":
        continue
    cds = np.array([float(r["CD_" + s]) for s in SIZES])
    cls = np.array([float(r["CL_" + s]) for s in SIZES])
    pts.append(dict(
        af=r["source"] + "|" + r["airfoil"], src=r["source"], Re=float(r["Re"]),
        a=float(r["alpha"]), tc=float(r["tc"]), conf=float(r["conf_xlarge"]),
        cdm=float(r["CD_meas"]), clm=float(r["CL_meas"]),
        u=float(r["u_cd_span"]) if r["u_cd_span"] else np.nan,
        cd8=cds.mean(), cdx=float(r["CD_xlarge"]),
        cl8=cls.mean(), clx=float(r["CL_xlarge"]),
        spread=(np.percentile(cds, 90) - np.percentile(cds, 10)) * CT))
N = len(pts)
rep = open(os.path.join(BASE, "lsat-report.txt"), "w")
def P(*a):
    print(*a); rep.write(" ".join(str(x) for x in a) + "\n")

P("=" * 76)
P(f"FULL-CORPUS VALIDATION: {N} clean measured points, "
  f"{len(set(p['af'] for p in pts))} airfoil entries, "
  f"Re {min(p['Re'] for p in pts):.0f} to {max(p['Re'] for p in pts):.0f}")
P("=" * 76)
e8 = np.array([abs(p.cd8 - p.cdm) if False else abs(p["cd8"] - p["cdm"]) for p in pts]) * CT
ex = np.array([abs(p["cdx"] - p["cdm"]) for p in pts]) * CT
l8 = np.array([abs(p["cl8"] - p["clm"]) for p in pts])
lx = np.array([abs(p["clx"] - p["clm"]) for p in pts])
uspan = np.nanmedian([p["u"] for p in pts]) * CT
P(f"\nCORE RETEST AT SCALE (drag counts; measurement's own spanwise half-spread median {uspan:.1f}):")
P(f"  CD MAE: mean-of-8 {e8.mean():.1f}  vs xlarge {ex.mean():.1f}   "
  f"({(1 - e8.mean()/ex.mean())*100:+.1f}% for mean-of-8)")
P(f"  CD median |err|: mean-of-8 {np.median(e8):.1f}  vs xlarge {np.median(ex):.1f}")
P(f"  CL MAE: mean-of-8 {l8.mean():.4f}  vs xlarge {lx.mean():.4f}")
P(f"  mean-of-8 better on {np.mean(e8 < ex)*100:.0f}% of points (CD)")

P("\nMEASURED ERROR MAP BY REYNOLDS (clean, drag counts, mean-of-8):")
P(f"{'Re band':>16s} {'n':>6s} {'median':>8s} {'p90':>8s} {'MAE':>8s}")
bands = [(0, 45e3), (45e3, 75e3), (75e3, 15e4), (15e4, 25e4), (25e4, 35e4), (35e4, 6e5)]
th_re = {}
for lo, hi in bands:
    sel = [i for i, p in enumerate(pts) if lo <= p["Re"] < hi]
    if not sel: continue
    v = e8[sel]
    th_re[f"{int(lo/1000)}k-{int(hi/1000)}k"] = dict(n=len(sel), med=float(np.median(v)),
                                                     p90=float(np.percentile(v, 90)), mae=float(v.mean()))
    P(f"{int(lo/1e3):>7d}k-{int(hi/1e3):<6d}k {len(sel):>6d} {np.median(v):>8.1f} "
      f"{np.percentile(v, 90):>8.1f} {v.mean():>8.1f}")

P("\nBY ANGLE OF ATTACK (drag counts, mean-of-8):")
th_a = {}
for lo, hi in [(-10, -4), (-4, 0), (0, 4), (4, 8), (8, 12), (12, 18)]:
    sel = [i for i, p in enumerate(pts) if lo <= p["a"] < hi]
    if not sel: continue
    v = e8[sel]
    th_a[f"{lo}..{hi}"] = dict(n=len(sel), med=float(np.median(v)), p90=float(np.percentile(v, 90)))
    P(f"  alpha {lo:+3d}..{hi:+3d}: n {len(sel):5d}  median {np.median(v):6.1f}  p90 {np.percentile(v, 90):7.1f}")

P("\nBY THICKNESS (drag counts, mean-of-8):")
th_t = {}
for lo, hi in [(0, 0.07), (0.07, 0.09), (0.09, 0.12), (0.12, 0.15), (0.15, 0.30)]:
    sel = [i for i, p in enumerate(pts) if lo <= p["tc"] < hi]
    if not sel: continue
    v = e8[sel]
    th_t[f"{lo}-{hi}"] = dict(n=len(sel), med=float(np.median(v)), p90=float(np.percentile(v, 90)))
    P(f"  t/c {lo:.2f}-{hi:.2f}: n {len(sel):5d}  median {np.median(v):6.1f}  p90 {np.percentile(v, 90):7.1f}")

P("\nDOES 8-NET SPREAD RANK TRUE ERROR? (spread decile -> median true error, counts)")
qs = np.percentile([p["spread"] for p in pts], np.arange(0, 101, 10))
th_s = []
for i in range(10):
    sel = [j for j, p in enumerate(pts) if qs[i] <= p["spread"] <= qs[i + 1] + (1e-9 if i == 9 else 0)]
    if not sel: continue
    th_s.append(dict(spread_lo=float(qs[i]), spread_hi=float(qs[i+1]),
                     med_err=float(np.median(e8[sel])), n=len(sel)))
    P(f"  spread {qs[i]:7.1f}-{qs[i+1]:7.1f}: median true err {np.median(e8[sel]):6.1f}  (n {len(sel)})")

hi_conf = [i for i, p in enumerate(pts) if p["conf"] > 0.9]
bl = [i for i in hi_conf if e8[i] > 20]
P(f"\nCONFIDENCE vs TRUTH: conf>0.90 on {len(hi_conf)} points; of those, "
  f"{len(bl)} ({100*len(bl)/max(len(hi_conf),1):.1f}%) have measured error > 20 counts")

by_af = {}
for i, p in enumerate(pts):
    by_af.setdefault(p["af"], []).append(e8[i])
with open(os.path.join(BASE, "lsat-by-airfoil.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["airfoil", "n", "cd_mae_counts", "cd_median"])
    for k in sorted(by_af, key=lambda k: -np.mean(by_af[k])):
        w.writerow([k, len(by_af[k]), f"{np.mean(by_af[k]):.1f}", f"{np.median(by_af[k]):.1f}"])
worst = sorted(by_af.items(), key=lambda kv: -np.mean(kv[1]))[:8]
best = sorted(by_af.items(), key=lambda kv: np.mean(kv[1]))[:5]
P("\nWORST AIRFOILS (CD MAE, counts):")
for k, v in worst: P(f"  {k:34s} {np.mean(v):7.1f}  (n {len(v)})")
P("BEST AIRFOILS:")
for k, v in best: P(f"  {k:34s} {np.mean(v):7.1f}  (n {len(v)})")

json.dump(dict(re=th_re, alpha=th_a, tc=th_t, spread=th_s,
               n=N, u_span_median_counts=float(uspan)),
          open(os.path.join(BASE, "lsat-thresholds.json"), "w"), indent=1)
rep.close()
print("\nwrote lsat-report.txt, lsat-thresholds.json, lsat-by-airfoil.csv")
