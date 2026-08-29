"""The accuracy answer: measured truth vs XFOIL vs classic NeuralFoil vs the new
NeuralFoil (mean-of-8) vs new + measured correction, on identical points.
Corrections are OUT-OF-FOLD (refit with each airfoil held out of its own
correction) so the corrected column never sees its own test airfoil.
XFOIL is scored only where it converged; its convergence rate is reported as
part of the result, because refusing to answer is a real cost."""
import csv, json, os
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
CT = 1e4
NF = {}
for r in csv.DictReader(open(os.path.join(BASE, "lsat-nf.csv"))):
    if r["config"] != "clean":
        continue
    key = (r["source"] + "|" + r["airfoil"], round(float(r["Re"])), round(float(r["alpha"]), 2))
    NF[key] = r
XF = {}
for r in csv.DictReader(open(os.path.join(BASE, "lsat-xfoil.csv"))):
    XF[(r["entry"], round(float(r["Re"])), round(float(r["alpha"]), 2))] = (float(r["CL_xf"]), float(r["CD_xf"]))

# ---- rebuild the correction design exactly as declared, get OOF corrections ----
feats, tgt, af_l, keys = [], [], [], []
for key, r in NF.items():
    a, tc, Re = float(r["alpha"]), float(r["tc"]), float(r["Re"])
    cds = np.array([float(r["CD_" + s]) for s in SIZES])
    cls = np.array([float(r["CL_" + s]) for s in SIZES])
    cd8, cl8 = cds.mean(), cls.mean()
    meas = float(r["CD_meas"])
    if meas <= 0 or cd8 <= 0:
        continue
    indom = (Re <= 6e5 and abs(a) <= 12 and 0.05 <= tc <= 0.20)
    spread = max(np.percentile(cds, 90) - np.percentile(cds, 10), 1e-6)
    lre, lcd, lsp, cf = np.log10(Re), np.log(cd8), np.log(spread), float(r["conf_xlarge"])
    feats.append([1, lre, lre**2, a, a**2, a**3, tc, tc**2, lcd, lsp, cf, cl8, cl8**2,
                  lre*a, lre*tc, a*tc, lre*lcd, a*cl8, lre*cl8, lsp*lre, lcd*a])
    tgt.append(np.clip(np.log(meas / cd8), -1.5, 1.5) if indom else 0.0)
    af_l.append((r["airfoil"], indom))
    keys.append((key, meas, cd8, cl8, float(r["CD_xlarge"]), float(r["CL_xlarge"]), float(r["CL_meas"])))
X = np.array(feats); y = np.array(tgt)
mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1; mu[0], sd[0] = 0, 1
Xs = (X - mu) / sd
LAM = 3e-2
rng = np.random.default_rng(824)
foils = sorted(set(a for a, _ in af_l)); rng.shuffle(foils)
folds = [set(foils[i::5]) for i in range(5)]
oof = np.zeros(len(y))
afarr = np.array([a for a, _ in af_l]); indomarr = np.array([d for _, d in af_l])
for hold in folds:
    te = np.isin(afarr, list(hold)); tr = ~te & indomarr
    A = Xs[tr]
    w = np.linalg.solve(A.T @ A + LAM * tr.sum() * np.eye(A.shape[1]), A.T @ y[tr])
    oof[te] = Xs[te] @ w
oof = np.clip(oof, np.log(0.5), np.log(2.0))

rows = []
for i, (key, meas, cd8, cl8, cdx, clx, clm) in enumerate(keys):
    xf = XF.get(key)
    rows.append(dict(meas=meas, cd8=cd8, cdx=cdx, clm=clm, cl8=cl8, clx=clx,
                     corr=cd8 * np.exp(oof[i]) if indomarr[i] else cd8,
                     xf=xf, Re=key[1]))
n_all = len(rows)
conv = [r for r in rows if r["xf"]]
print(f"points with NF: {n_all}; XFOIL converged on {len(conv)} ({100*len(conv)/n_all:.1f}%)")
print("\nHEAD TO HEAD on the XFOIL-converged common points (drag counts):")
for name, f in (("XFOIL 6.99          ", lambda r: r["xf"][1]),
                ("classic NF (xlarge) ", lambda r: r["cdx"]),
                ("new NF (mean-of-8)  ", lambda r: r["cd8"]),
                ("new NF + correction ", lambda r: r["corr"])):
    e = np.array([abs(f(r) - r["meas"]) for r in conv]) * CT
    print(f"  {name}: MAE {e.mean():6.1f}  median {np.median(e):6.1f}")
print("\nCL on the same points:")
for name, f in (("XFOIL 6.99          ", lambda r: r["xf"][0]),
                ("classic NF (xlarge) ", lambda r: r["clx"]),
                ("new NF (mean-of-8)  ", lambda r: r["cl8"])):
    e = np.array([abs(f(r) - r["clm"]) for r in conv])
    print(f"  {name}: MAE {e.mean():.4f}  median {np.median(e):.4f}")
print("\nALL measured points (XFOIL scored as absent where it diverged):")
e8 = np.array([abs(r["cd8"] - r["meas"]) for r in rows]) * CT
ec = np.array([abs(r["corr"] - r["meas"]) for r in rows]) * CT
print(f"  new NF: MAE {e8.mean():.1f} -> with correction {ec.mean():.1f} "
      f"(medians {np.median(e8):.1f} -> {np.median(ec):.1f})")
print("\nby Re band, corrected new NF vs XFOIL (MAE counts, common points):")
for lo, hi in ((0, 75e3), (75e3, 15e4), (15e4, 25e4), (25e4, 6e5)):
    sel = [r for r in conv if lo <= r["Re"] < hi]
    if not sel: continue
    exf = np.mean([abs(r["xf"][1] - r["meas"]) for r in sel]) * CT
    eco = np.mean([abs(r["corr"] - r["meas"]) for r in sel]) * CT
    print(f"  Re {int(lo/1e3):>3d}k-{int(hi/1e3):<3d}k: XFOIL {exf:6.1f} | new+corr {eco:6.1f}  (n {len(sel)})")
