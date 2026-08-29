"""A measured-residual drag correction for NeuralFoil at low Reynolds numbers,
with the validation protocol DECLARED BEFORE FITTING:
  target: clipped log(CD_meas / CD_mean8), clip [-1.5, 1.5]
  basis:  fixed 21-term polynomial in (log10 Re, alpha, t/c, log CD_pred,
          log spread, conf, CL_pred); ridge lambda FIXED at 3e-2 on
          standardized features; no tuning of any kind after this line.
  tests:  (1) 5-fold cross-validation GROUPED BY AIRFOIL (an airfoil never
          appears in both train and test), (2) cross-source transfer both ways
          (vols 1-3 <-> SoarTech 8). SHIP only if MAE improves in grouped CV
          AND in BOTH transfer directions.
  domain: Re <= 600k, |alpha| <= 12, 0.05 <= t/c <= 0.20, mach < 0.3; the
          shipped correction fades to zero outside (structural no-harm).
"""
import csv, json, os
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
R = [r for r in csv.DictReader(open(os.path.join(BASE, "lsat-nf.csv"))) if r["config"] == "clean"]
CT = 1e4

X, y, af, src, keep = [], [], [], [], []
for r in R:
    a, tc, Re = float(r["alpha"]), float(r["tc"]), float(r["Re"])
    if not (Re <= 6e5 and abs(a) <= 12 and 0.05 <= tc <= 0.20):
        continue
    cds = np.array([float(r["CD_" + s]) for s in SIZES])
    cls = np.array([float(r["CL_" + s]) for s in SIZES])
    cd8, cl8 = cds.mean(), cls.mean()
    meas = float(r["CD_meas"])
    if meas <= 0 or cd8 <= 0:
        continue
    spread = max(np.percentile(cds, 90) - np.percentile(cds, 10), 1e-6)
    lre, lcd, lsp, cf = np.log10(Re), np.log(cd8), np.log(spread), float(r["conf_xlarge"])
    X.append([1, lre, lre**2, a, a**2, a**3, tc, tc**2, lcd, lsp, cf, cl8, cl8**2,
              lre*a, lre*tc, a*tc, lre*lcd, a*cl8, lre*cl8, lsp*lre, lcd*a])
    y.append(np.clip(np.log(meas / cd8), -1.5, 1.5))
    af.append(r["airfoil"]); src.append(r["source"])
    keep.append((meas, cd8))
X = np.array(X); y = np.array(y)
af = np.array(af); src = np.array(src)
meas_v = np.array([k[0] for k in keep]); cd8_v = np.array([k[1] for k in keep])
print(f"{len(y)} in-domain points, {len(set(af))} airfoils")

mu, sd = X.mean(0), X.std(0); sd[sd == 0] = 1; mu[0], sd[0] = 0, 1
Xs = (X - mu) / sd
LAM = 3e-2

def fit(idx):
    A = Xs[idx]; b = y[idx]
    return np.linalg.solve(A.T @ A + LAM * len(idx) * np.eye(A.shape[1]), A.T @ b)

def score(idx, w):
    corr = cd8_v[idx] * np.exp(np.clip(Xs[idx] @ w, np.log(0.5), np.log(2.0)))
    e_cor = np.abs(corr - meas_v[idx]) * CT
    e_raw = np.abs(cd8_v[idx] - meas_v[idx]) * CT
    return e_raw.mean(), e_cor.mean(), np.median(e_raw), np.median(e_cor)

rng = np.random.default_rng(824)
foils = sorted(set(af)); rng.shuffle(foils)
folds = [foils[i::5] for i in range(5)]
print("\nGROUPED 5-FOLD CV (airfoil-disjoint):")
agg = []
for i, hold in enumerate(folds):
    te = np.isin(af, hold); tr = ~te
    w = fit(np.where(tr)[0])
    mr, mc, dr, dc = score(np.where(te)[0], w)
    agg.append((mr, mc))
    print(f"  fold {i}: MAE raw {mr:6.1f} -> corrected {mc:6.1f}  (median {dr:.1f} -> {dc:.1f})")
mr = np.mean([a[0] for a in agg]); mc = np.mean([a[1] for a in agg])
print(f"  MEAN: {mr:.1f} -> {mc:.1f} counts ({(1-mc/mr)*100:+.1f}%)")

print("\nCROSS-SOURCE TRANSFER:")
ok = True
for a_, b_ in (("vols", "stec8"), ("stec8", "vols")):
    tr = (src != "stec8") if a_ == "vols" else (src == "stec8")
    w = fit(np.where(tr)[0])
    mr2, mc2, dr2, dc2 = score(np.where(~tr)[0], w)
    print(f"  train {a_:5s} -> test {b_:5s}: MAE {mr2:6.1f} -> {mc2:6.1f}  (median {dr2:.1f} -> {dc2:.1f})")
    ok = ok and (mc2 < mr2)
ok = ok and (mc < mr)
print(f"\nSHIP DECISION per declared rule: {'SHIP' if ok else 'DO NOT SHIP'}")
if ok:
    w = fit(np.arange(len(y)))
    mrF, mcF, drF, dcF = score(np.arange(len(y)), w)
    print(f"  final in-sample (reference only): {mrF:.1f} -> {mcF:.1f}")
    json.dump({"terms": ["1","lre","lre2","a","a2","a3","tc","tc2","lcd","lsp","conf","cl","cl2",
                         "lre*a","lre*tc","a*tc","lre*lcd","a*cl","lre*cl","lsp*lre","lcd*a"],
               "mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(),
               "clip_ratio": [0.5, 2.0], "domain": {"re_max": 6e5, "alpha_abs_max": 12,
               "tc": [0.05, 0.20], "mach_max": 0.3}, "lambda": LAM,
               "cv_mae_raw": mr, "cv_mae_corrected": mc},
              open(os.path.join(BASE, "correction-cd.json"), "w"), indent=1)
    print("wrote correction-cd.json")
