"""DOUBLE-CLEAN RE-ANALYSIS. The export audit (2026-09-06) found that the
geometry matcher classified configurations from airfoil NAMES only, so rows
whose Comment field marks trips, tapes, flaps or other modifications entered
the 'clean' validation set and the correction training. This script repeats
the whole low-Reynolds analysis on rows that are clean by BOTH name and
comment, with the identical declared protocols, and writes everything under a
dc- prefix. No original file is modified.
"""
import csv, json, os
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
CT = 1e4
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))
rep = open(os.path.join(BASE, "dc-report.txt"), "w")
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); rep.write(s + "\n")

# ---------------- double-clean row set ----------------
cfg = {}
for r in csv.DictReader(open(os.path.join(BASE, "lsat-corpus.csv"))):
    cfg[(r["source"], r["airfoil"], round(float(r["Re"])), round(float(r["alpha"]), 2))] = r["config"]
def key_of(r):
    return (r["source"], r["airfoil"], round(float(r["Re"])), round(float(r["alpha"]), 2))
R2 = [r for r in csv.DictReader(open(os.path.join(BASE, "lsat-nf2.csv")))
      if r["config"] == "clean" and cfg.get(key_of(r)) == "clean"]
P("=" * 76)
P(f"DOUBLE-CLEAN CORPUS: {len(R2)} rows, {len(set(r['source']+'|'+r['airfoil'] for r in R2))} airfoil entries "
  f"(clean by name AND by comment; previous analyses used {sum(1 for _ in csv.DictReader(open(os.path.join(BASE, 'lsat-nf.csv'))) if _['config']=='clean')} name-clean rows)")
P("=" * 76)

pts = []
for r in R2:
    cds = np.array([float(r["CD_" + s]) for s in SIZES]); cls = np.array([float(r["CL_" + s]) for s in SIZES])
    pts.append(dict(af=r["source"] + "|" + r["airfoil"], src=r["source"], Re=float(r["Re"]), a=float(r["alpha"]),
                    tc=float(r["tc"]), conf=float(r["conf_xlarge"]), cdm=float(r["CD_meas"]), clm=float(r["CL_meas"]),
                    cd8=cds.mean(), cdx=float(r["CD_xlarge"]), cl8=cls.mean(), clx=float(r["CL_xlarge"]),
                    spread=(np.percentile(cds, 90) - np.percentile(cds, 10)) * CT, u=float(r["u_cd_span"]) if r["u_cd_span"] else np.nan))
e8 = np.array([abs(p["cd8"] - p["cdm"]) for p in pts]) * CT
ex = np.array([abs(p["cdx"] - p["cdm"]) for p in pts]) * CT
l8 = np.array([abs(p["cl8"] - p["clm"]) for p in pts]); lx = np.array([abs(p["clx"] - p["clm"]) for p in pts])
P(f"\nCORE RETEST: CD MAE mean-of-8 {e8.mean():.1f} vs xlarge {ex.mean():.1f} ({(1-e8.mean()/ex.mean())*100:+.1f}%); "
  f"median {np.median(e8):.1f} vs {np.median(ex):.1f}; better on {np.mean(e8<ex)*100:.0f}% of points; "
  f"CL MAE {l8.mean():.4f} vs {lx.mean():.4f}; measurement spanwise half-spread median {np.nanmedian([p['u'] for p in pts])*CT:.1f}")
P("\nERROR MAP BY RE (mean-of-8, counts): band n median p90 MAE")
for lo, hi in [(0, 45e3), (45e3, 75e3), (75e3, 15e4), (15e4, 25e4), (25e4, 35e4), (35e4, 6e5)]:
    sel = [i for i, p in enumerate(pts) if lo <= p["Re"] < hi]
    if sel:
        v = e8[sel]; P(f"  {int(lo/1e3):>3d}k-{int(hi/1e3):<3d}k {len(sel):5d} {np.median(v):6.1f} {np.percentile(v,90):6.1f} {v.mean():6.1f}")
P("BY ALPHA:")
for lo, hi in [(-10, -4), (-4, 0), (0, 4), (4, 8), (8, 12), (12, 18)]:
    sel = [i for i, p in enumerate(pts) if lo <= p["a"] < hi]
    if sel: P(f"  {lo:+3d}..{hi:+3d} n {len(sel):5d} median {np.median(e8[sel]):6.1f} p90 {np.percentile(e8[sel],90):6.1f}")
P("BY THICKNESS:")
for lo, hi in [(0, 0.07), (0.07, 0.09), (0.09, 0.12), (0.12, 0.15), (0.15, 0.30)]:
    sel = [i for i, p in enumerate(pts) if lo <= p["tc"] < hi]
    if sel: P(f"  {lo:.2f}-{hi:.2f} n {len(sel):5d} median {np.median(e8[sel]):6.1f} p90 {np.percentile(e8[sel],90):6.1f}")
P("SPREAD DECILES -> median true error:")
qs = np.percentile([p["spread"] for p in pts], np.arange(0, 101, 10))
for i in range(10):
    sel = [j for j, p in enumerate(pts) if qs[i] <= p["spread"] <= qs[i+1] + (1e-9 if i == 9 else 0)]
    if sel: P(f"  {qs[i]:6.1f}-{qs[i+1]:6.1f}: {np.median(e8[sel]):6.1f} (n {len(sel)})")
hi_conf = [i for i, p in enumerate(pts) if p["conf"] > 0.9]
P(f"CONFIDENCE BLINDSPOT: conf>0.90 on {len(hi_conf)}; with true error >20 counts: "
  f"{sum(1 for i in hi_conf if e8[i] > 20)} ({100*sum(1 for i in hi_conf if e8[i] > 20)/max(len(hi_conf),1):.1f}%)")

# ---------------- corrections, declared protocols unchanged ----------------
import zipfile
_ZC = zipfile.ZipFile(os.path.join(BASE, "coord_seligFmt.zip")); _ZS = zipfile.ZipFile(os.path.join(BASE, "Stec8.zip"))
def read_geom_text(path):
    """Original file if still on disk, else the identical bytes streamed from the original archive (never extracted)."""
    full = os.path.join(BASE, path)
    if os.path.exists(full):
        return open(full, errors="replace").read()
    if path.startswith("coords/"):
        return _ZC.read(path[len("coords/"):]).decode("latin-1")
    if path.startswith("stec8/"):
        return _ZS.read(path[len("stec8/"):]).decode("latin-1")
    raise FileNotFoundError(path)
def load_pts(path):
    out = []
    for L in read_geom_text(path).splitlines()[1:]:
        p = L.split()
        if len(p) >= 2:
            try: x, y = float(p[0]), float(p[1])
            except ValueError: continue
            if -0.5 <= x <= 1.5 and -0.6 <= y <= 0.6: out.append([x, y])
    a = np.array(out); a[:, 0] -= a[:, 0].min(); return a / a[:, 0].max()

def foil_stats2(pts_):
    le = int(np.argmin([p[0] for p in pts_])); up, lo = pts_[:le+1], pts_[le:]
    def interp(seg, x):
        for k in range(len(seg)-1):
            a, b = seg[k], seg[k+1]
            if (x-a[0])*(x-b[0]) <= 0 and abs(b[0]-a[0]) > 1e-9: return a[1] + (b[1]-a[1])*(x-a[0])/(b[0]-a[0])
        return 0.0
    t = tx = c = cx = 0.0
    for k in range(1, 100):
        x = 0.5*(1-np.cos(np.pi*k/100)); yu, yl = interp(up, x), interp(lo, x); th, cm = yu-yl, (yu+yl)/2
        if th > t: t, tx = th, x
        if abs(cm) > abs(c): c, cx = cm, x
    A = pts_[max(0, le-1)]; B = pts_[le]; Cp = pts_[min(len(pts_)-1, le+1)]
    a2 = np.hypot(B[0]-Cp[0], B[1]-Cp[1]); b3 = np.hypot(A[0]-Cp[0], A[1]-Cp[1]); c3 = np.hypot(A[0]-B[0], A[1]-B[1])
    s2 = (a2+b3+c3)/2; tri = np.sqrt(max(1e-18, s2*(s2-a2)*(s2-b3)*(s2-c3))); leR = a2*b3*c3/(4*tri)
    v1 = [pts_[1][0]-pts_[0][0], pts_[1][1]-pts_[0][1]]; v2 = [pts_[-2][0]-pts_[-1][0], pts_[-2][1]-pts_[-1][1]]
    den = np.hypot(*v1)*np.hypot(*v2) or 1e-9
    teA = np.degrees(np.arccos(np.clip((v1[0]*v2[0]+v1[1]*v2[1])/den, -1, 1)))
    return dict(t=t, tx=tx, c=c, cx=cx, leR=min(leR, 0.2), teA=teA)
S2 = {}
for k, g in GEO.items():
    try: S2[k] = foil_stats2([list(p) for p in load_pts(g["path"])])
    except Exception: pass
P(f"\ngeometry stats available for {len(S2)} entries (extracted geometry files were deleted after the runs; "
  f"entries without on-disk geometry cannot be featured and are dropped from correction training here)")

X16, X9, yCD, yCL, af_l, src_l, meta = [], [], [], [], [], [], []
for r in R2:
    key = r["source"] + "|" + r["airfoil"]; s2 = S2.get(key)
    if not s2: continue
    a, Re = float(r["alpha"]), float(r["Re"])
    if not (Re <= 6e5 and abs(a) <= 12 and 0.05 <= s2["t"] <= 0.20): continue
    cds = np.array([float(r["CD_" + s]) for s in SIZES]); cls = np.array([float(r["CL_" + s]) for s in SIZES])
    cd8, cl8 = cds.mean(), cls.mean(); meas, clm = float(r["CD_meas"]), float(r["CL_meas"])
    if meas <= 0 or cd8 <= 0: continue
    spread = max(np.percentile(cds, 90) - np.percentile(cds, 10), 1e-6)
    lre, lcd, lsp = np.log10(Re), np.log(cd8), np.log(spread)
    tx_, bx_ = float(r["topxtr"]), float(r["botxtr"])
    X16.append([a, lre, s2["t"], s2["tx"], s2["c"], s2["cx"], s2["leR"], s2["teA"], lcd, cl8, lsp,
                float(r["conf_xlarge"]), tx_, bx_, np.log(cds[0]) - np.log(cds[7]), float(r["cm8"])])
    X9.append([a, lre, s2["t"], s2["c"], lcd, cl8, lsp, tx_, bx_])
    yCD.append(np.clip(np.log(meas / cd8), -1.5, 1.5)); yCL.append(np.clip(clm - cl8, -0.5, 0.5))
    af_l.append(r["airfoil"]); src_l.append(r["source"]); meta.append((key_of(r), meas, cd8, clm, cl8))
X16, X9, yCD, yCL = map(np.array, (X16, X9, yCD, yCL)); af = np.array(af_l); src = np.array(src_l)
MEAS_CD = np.array([m[1] for m in meta]); BASE_CD = np.array([m[2] for m in meta])
MEAS_CL = np.array([m[3] for m in meta]); BASE_CL = np.array([m[4] for m in meta])
P(f"in-domain training rows {len(yCD)}, airfoils {len(set(af_l))}")
rng = np.random.default_rng(824); foils = sorted(set(af_l)); rng.shuffle(foils); folds = [set(foils[i::5]) for i in range(5)]

def errs(kind, sel, pred):
    if kind == "CD":
        return (np.abs(BASE_CD[sel]-MEAS_CD[sel])*CT, np.abs(BASE_CD[sel]*np.exp(np.clip(pred, np.log(0.5), np.log(2)))-MEAS_CD[sel])*CT)
    return (np.abs(BASE_CL[sel]-MEAS_CL[sel]), np.abs(BASE_CL[sel]+np.clip(pred, -0.5, 0.5)-MEAS_CL[sel]))
def protocol(X, y, kind, mk):
    oof = np.zeros(len(y)); P(f"\n[{kind}] GROUPED 5-FOLD CV (airfoil-disjoint):"); raws, cors = [], []
    for i, hold in enumerate(folds):
        te = np.isin(af, list(hold)); m = mk().fit(X[~te], y[~te]); oof[te] = m.predict(X[te])
        e_r, e_c = errs(kind, te, oof[te]); raws.append(e_r.mean()); cors.append(e_c.mean())
        P(f"  fold {i}: {e_r.mean():.4g} -> {e_c.mean():.4g}")
    P(f"  MEAN: {np.mean(raws):.4g} -> {np.mean(cors):.4g} ({(1-np.mean(cors)/np.mean(raws))*100:+.1f}%)")
    ok = np.mean(cors) < np.mean(raws); P(f"[{kind}] CROSS-SOURCE:")
    for name in ("stec8", "vols"):
        te = (src == "stec8") if name == "stec8" else (src != "stec8")
        if te.sum() == 0 or (~te).sum() == 0: P(f"  test {name}: not possible (one side empty)"); continue
        m = mk().fit(X[~te], y[~te]); e_r, e_c = errs(kind, te, m.predict(X[te]))
        P(f"  test {name:5s}: {e_r.mean():.4g} -> {e_c.mean():.4g}"); ok = ok and (e_c.mean() < e_r.mean())
    P(f"[{kind}] SHIP: {ok}"); return ok, oof
gCD = lambda: GradientBoostingRegressor(n_estimators=150, learning_rate=0.06, max_depth=2, min_samples_leaf=80, subsample=0.7, random_state=824)
gCL = lambda: GradientBoostingRegressor(n_estimators=300, learning_rate=0.06, max_depth=3, min_samples_leaf=40, subsample=0.7, random_state=824)
okCD, oofCD = protocol(X9, yCD, "CD", gCD)
okCL, oofCL = protocol(X16, yCL, "CL", gCL)

def export(model, X, path, feats, extra):
    trees = [{"f": e.tree_.feature.tolist(), "th": e.tree_.threshold.tolist(), "l": e.tree_.children_left.tolist(),
              "r": e.tree_.children_right.tolist(), "v": e.tree_.value[:, 0, 0].tolist()} for e in model.estimators_[:, 0]]
    b0 = float(model.init_.constant_[0][0])
    def jsp(row):
        s = b0
        for t in trees:
            n = 0
            while t["f"][n] >= 0: n = t["l"][n] if row[t["f"][n]] <= t["th"][n] else t["r"][n]
            s += 0.06 * t["v"][n]
        return s
    idx = rng.choice(len(X), 50, replace=False)
    d = max(abs(jsp(X[i]) - model.predict(X[i:i+1])[0]) for i in idx); assert d < 1e-8
    refs = [{"x": X[i].tolist(), "y": float(model.predict(X[i:i+1])[0])} for i in idx[:5]]
    json.dump({"feats": feats, "lr": 0.06, "b0": b0, "trees": trees, "refs": refs, **extra}, open(os.path.join(BASE, path), "w"))
    P(f"  wrote {path} (export check {d:.1e})")
F9 = ["alpha","lre","t2","c2","lcd8","cl8","lsp","topxtr","botxtr"]
F16 = ["alpha","lre","t2","tx2","c2","cx2","leR","teA","lcd8","cl8","lsp","conf","topxtr","botxtr","dsize","cm8"]
if okCD: export(gCD().fit(X9, yCD), X9, "dc-correction-cd3.json", F9, {"kind": "logratio", "clip": 1.5})
if okCL: export(gCL().fit(X16, yCL), X16, "dc-correction-cl2.json", F16, {"kind": "additive", "clip": 0.5})

# ---------------- head-to-head on the XFOIL-converged double-clean points ----------------
XF = {}
for r in csv.DictReader(open(os.path.join(BASE, "lsat-xfoil.csv"))):
    XF[(r["entry"], round(float(r["Re"])), round(float(r["alpha"]), 2))] = (float(r["CL_xf"]), float(r["CD_xf"]))
oofmap = {meta[i][0]: (oofCD[i], oofCL[i]) for i in range(len(meta))}
rows = []
for p, r in zip(pts, R2):
    k = key_of(r); kk = (p["af"], k[2], k[3]); z, dcl = oofmap.get(k, (0.0, 0.0))
    rows.append(dict(meas=p["cdm"], clm=p["clm"], cd8=p["cd8"], cdx=p["cdx"], cl8=p["cl8"], clx=p["clx"],
                     cdc=p["cd8"]*np.exp(np.clip(z, np.log(0.5), np.log(2))), clc=p["cl8"]+np.clip(dcl, -0.5, 0.5), xf=XF.get(kk), Re=p["Re"]))
req = len(set((p["af"], key_of(r)[2], key_of(r)[3]) for p, r in zip(pts, R2)))
conv = [r for r in rows if r["xf"]]
P(f"\nXFOIL: double-clean conditions {req}; converged {len(conv)} ({100*len(conv)/req:.1f}%)")
P("HEAD-TO-HEAD on XFOIL-converged double-clean points (corrections out of fold):")
for name, f in (("XFOIL 6.99", lambda r: r["xf"][1]), ("classic NF xlarge", lambda r: r["cdx"]), ("new NF mean-of-8", lambda r: r["cd8"]), ("new NF + corrections", lambda r: r["cdc"])):
    e = np.array([abs(f(r)-r["meas"]) for r in conv])*CT; P(f"  {name:22s} drag MAE {e.mean():6.1f} median {np.median(e):6.1f}")
for name, f in (("XFOIL 6.99", lambda r: r["xf"][0]), ("classic NF xlarge", lambda r: r["clx"]), ("new NF mean-of-8", lambda r: r["cl8"]), ("new NF + corrections", lambda r: r["clc"])):
    e = np.array([abs(f(r)-r["clm"]) for r in conv]); P(f"  {name:22s} lift MAE {e.mean():.4f} median {np.median(e):.4f}")
for lo, hi in ((0, 75e3), (75e3, 15e4), (15e4, 25e4), (25e4, 6e5)):
    sel = [r for r in conv if lo <= r["Re"] < hi]
    if sel: P(f"  Re {int(lo/1e3):>3d}k-{int(hi/1e3):<3d}k: XFOIL {np.mean([abs(r['xf'][1]-r['meas']) for r in sel])*CT:6.1f} | new+corr {np.mean([abs(r['cdc']-r['meas']) for r in sel])*CT:6.1f} (n {len(sel)})")
with open(os.path.join(BASE, "dc-oof.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["entry", "Re", "alpha", "zCD_oof", "dCL_oof"])
    for i, m in enumerate(meta): w.writerow([m[0][0]+"|"+m[0][1], m[0][2], m[0][3], f"{oofCD[i]:.5f}", f"{oofCL[i]:.5f}"])
rep.close(); print("wrote dc-report.txt, dc-oof.csv")
