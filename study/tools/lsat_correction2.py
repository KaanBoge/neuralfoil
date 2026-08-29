"""Correction v2: gradient-boosted measured-residual models for drag AND lift.
DECLARED BEFORE FITTING, no tuning afterward:
  model: sklearn GradientBoostingRegressor(n_estimators=300, learning_rate=0.06,
         max_depth=3, min_samples_leaf=40, subsample=0.7, random_state=824)
  targets: CD: clip(log(CD_meas/CD_mean8), +-1.5); CL: clip(CL_meas-CL_mean8, +-0.5)
  features (16, all computable in the page at inference): alpha, log10 Re,
         stats2-thickness, its position, stats2-camber, its position, LE radius,
         TE angle (all from an exact python port of the page's foilStats2, on the
         same coordinates the NF runs used), log CD_mean8, CL_mean8, log spread,
         xlarge confidence, top/bottom transition (xlarge), size trend
         log(CD_xxsmall)-log(CD_xxxlarge), CM_mean8
  ship rule (per output): airfoil-disjoint 5-fold CV mean MAE must improve AND
         both cross-facility transfers must improve. Domain as v1.
Exports correction-cd2.json (+cl) with raw trees, a numeric export check, and
reference vectors for the in-page self-test. Also writes out-of-fold
predictions (oof2.csv) for the honest head-to-head."""
import csv, json, os
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))
CT = 1e4

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

def foil_stats2(pts):
    """Exact python port of the page function foilStats2."""
    le = int(np.argmin([p[0] for p in pts]))
    up, lo = pts[:le + 1], pts[le:]
    def interp(seg, x):
        for k in range(len(seg) - 1):
            a, b = seg[k], seg[k + 1]
            if (x - a[0]) * (x - b[0]) <= 0 and abs(b[0] - a[0]) > 1e-9:
                return a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
        return 0.0
    t = tx = c = cx = 0.0
    for k in range(1, 100):
        x = 0.5 * (1 - np.cos(np.pi * k / 100))
        yu, yl = interp(up, x), interp(lo, x)
        th, cm = yu - yl, (yu + yl) / 2
        if th > t:
            t, tx = th, x
        if abs(cm) > abs(c):
            c, cx = cm, x
    A = pts[max(0, le - 1)]
    B = pts[le]
    Cp = pts[min(len(pts) - 1, le + 1)]
    a2 = np.hypot(B[0] - Cp[0], B[1] - Cp[1])
    b3 = np.hypot(A[0] - Cp[0], A[1] - Cp[1])
    c3 = np.hypot(A[0] - B[0], A[1] - B[1])
    s2 = (a2 + b3 + c3) / 2
    tri = np.sqrt(max(1e-18, s2 * (s2 - a2) * (s2 - b3) * (s2 - c3)))
    leR = a2 * b3 * c3 / (4 * tri)
    v1 = [pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]]
    v2 = [pts[-2][0] - pts[-1][0], pts[-2][1] - pts[-1][1]]
    den = np.hypot(*v1) * np.hypot(*v2)
    if den == 0:
        den = 1e-9
    teA = np.degrees(np.arccos(np.clip((v1[0] * v2[0] + v1[1] * v2[1]) / den, -1, 1)))
    return dict(t=t, tx=tx, c=c, cx=cx, leR=min(leR, 0.2), teA=teA)

S2 = {}
for key, g in GEO.items():
    try:
        S2[key] = foil_stats2([list(p) for p in load_pts(g["path"])])
    except Exception:
        pass

FEATS = ["alpha", "lre", "t2", "tx2", "c2", "cx2", "leR", "teA", "lcd8", "cl8", "lsp",
         "conf", "topxtr", "botxtr", "dsize", "cm8"]
X, yCD, yCL, af_l, src_l, meta = [], [], [], [], [], []
for r in csv.DictReader(open(os.path.join(BASE, "lsat-nf2.csv"))):
    if r["config"] != "clean":
        continue
    key = r["source"] + "|" + r["airfoil"]
    s2 = S2.get(key)
    if not s2:
        continue
    a, Re = float(r["alpha"]), float(r["Re"])
    if not (Re <= 6e5 and abs(a) <= 12 and 0.05 <= s2["t"] <= 0.20):
        continue
    cds = np.array([float(r["CD_" + s]) for s in SIZES])
    cls = np.array([float(r["CL_" + s]) for s in SIZES])
    cd8, cl8 = cds.mean(), cls.mean()
    meas, clm = float(r["CD_meas"]), float(r["CL_meas"])
    if meas <= 0 or cd8 <= 0:
        continue
    spread = max(np.percentile(cds, 90) - np.percentile(cds, 10), 1e-6)
    X.append([a, np.log10(Re), s2["t"], s2["tx"], s2["c"], s2["cx"], s2["leR"], s2["teA"],
              np.log(cd8), cl8, np.log(spread), float(r["conf_xlarge"]),
              float(r["topxtr"]), float(r["botxtr"]),
              np.log(cds[0]) - np.log(cds[7]), float(r["cm8"])])
    yCD.append(np.clip(np.log(meas / cd8), -1.5, 1.5))
    yCL.append(np.clip(clm - cl8, -0.5, 0.5))
    af_l.append(r["airfoil"])
    src_l.append(r["source"])
    meta.append((key, round(Re), round(a, 2), meas, cd8, clm, cl8))
X = np.array(X)
yCD = np.array(yCD)
yCL = np.array(yCL)
af = np.array(af_l)
src = np.array(src_l)
print(f"{len(X)} in-domain points, {len(set(af_l))} airfoils")

def gbr():
    return GradientBoostingRegressor(n_estimators=300, learning_rate=0.06, max_depth=3,
                                     min_samples_leaf=40, subsample=0.7, random_state=824)

rng = np.random.default_rng(824)
foils = sorted(set(af_l))
rng.shuffle(foils)
folds = [set(foils[i::5]) for i in range(5)]

MEAS_CD = np.array([m[3] for m in meta]); BASE_CD = np.array([m[4] for m in meta])
MEAS_CL = np.array([m[5] for m in meta]); BASE_CL = np.array([m[6] for m in meta])

def errs(kind, sel, pred):
    if kind == "CD":
        e_r = np.abs(BASE_CD[sel] - MEAS_CD[sel]) * CT
        e_c = np.abs(BASE_CD[sel] * np.exp(np.clip(pred, np.log(0.5), np.log(2))) - MEAS_CD[sel]) * CT
    else:
        e_r = np.abs(BASE_CL[sel] - MEAS_CL[sel])
        e_c = np.abs(BASE_CL[sel] + np.clip(pred, -0.5, 0.5) - MEAS_CL[sel])
    return e_r, e_c

def run_protocol(y, kind):
    oof = np.zeros(len(y))
    print(f"\n[{kind}] GROUPED 5-FOLD CV:")
    raws, cors = [], []
    for i, hold in enumerate(folds):
        te = np.isin(af, list(hold))
        m = gbr().fit(X[~te], y[~te])
        oof[te] = m.predict(X[te])
        e_r, e_c = errs(kind, te, oof[te])
        raws.append(e_r.mean())
        cors.append(e_c.mean())
        print(f"  fold {i}: {e_r.mean():.4g} -> {e_c.mean():.4g}")
    print(f"  MEAN: {np.mean(raws):.4g} -> {np.mean(cors):.4g} ({(1 - np.mean(cors) / np.mean(raws)) * 100:+.1f}%)")
    ok = np.mean(cors) < np.mean(raws)
    print(f"[{kind}] CROSS-SOURCE:")
    for name in ("stec8", "vols"):
        te = (src == "stec8") if name == "stec8" else (src != "stec8")
        m = gbr().fit(X[~te], y[~te])
        e_r, e_c = errs(kind, te, m.predict(X[te]))
        print(f"  test {name:5s}: {e_r.mean():.4g} -> {e_c.mean():.4g}")
        ok = ok and (e_c.mean() < e_r.mean())
    print(f"[{kind}] SHIP: {ok}")
    return ok, oof

okCD, oofCD = run_protocol(yCD, "CD")
okCL, oofCL = run_protocol(yCL, "CL")

def export(model, path, extra):
    trees = []
    for est in model.estimators_[:, 0]:
        t = est.tree_
        trees.append({"f": t.feature.tolist(), "th": t.threshold.tolist(),
                      "l": t.children_left.tolist(), "r": t.children_right.tolist(),
                      "v": t.value[:, 0, 0].tolist()})
    b0 = float(model.init_.constant_[0][0])
    def js_predict(row):
        s = b0
        for tr_ in trees:
            n = 0
            while tr_["f"][n] >= 0:
                n = tr_["l"][n] if row[tr_["f"][n]] <= tr_["th"][n] else tr_["r"][n]
            s += 0.06 * tr_["v"][n]
        return s
    idx = rng.choice(len(X), 50, replace=False)
    diff = max(abs(js_predict(X[i]) - model.predict(X[i:i + 1])[0]) for i in idx)
    print(f"  export check max |diff| = {diff:.2e}")
    assert diff < 1e-8
    refs = [{"x": X[i].tolist(), "y": float(model.predict(X[i:i + 1])[0])} for i in idx[:5]]
    json.dump({"feats": FEATS, "lr": 0.06, "b0": b0, "trees": trees, "refs": refs, **extra},
              open(os.path.join(BASE, path), "w"))
    print(f"  wrote {path} ({os.path.getsize(os.path.join(BASE, path)) / 1e3:.0f} KB)")

if okCD:
    export(gbr().fit(X, yCD), "correction-cd2.json", {"kind": "logratio", "clip": 1.5})
if okCL:
    export(gbr().fit(X, yCL), "correction-cl2.json", {"kind": "additive", "clip": 0.5})
with open(os.path.join(BASE, "oof2.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["entry", "Re", "alpha", "zCD_oof", "dCL_oof"])
    for i, mm in enumerate(meta):
        w.writerow([mm[0], mm[1], mm[2], f"{oofCD[i]:.5f}", f"{oofCL[i]:.5f}"])
print("wrote oof2.csv")
