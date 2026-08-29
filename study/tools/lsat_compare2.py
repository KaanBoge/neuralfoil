"""Final head-to-head using the SHIPPED corrections, out-of-fold:
CD from v3 (oof3.csv), CL from v2 (oof2.csv)."""
import csv, os
import numpy as np
BASE = os.path.dirname(os.path.abspath(__file__))
CT = 1e4
OCD = {}
for r in csv.DictReader(open(os.path.join(BASE, "oof3.csv"))):
    OCD[(r["entry"], int(r["Re"]), float(r["alpha"]))] = float(r["zCD_oof"])
OCL = {}
for r in csv.DictReader(open(os.path.join(BASE, "oof2.csv"))):
    OCL[(r["entry"], int(r["Re"]), float(r["alpha"]))] = float(r["dCL_oof"])
SIZES = ["xxsmall","xsmall","small","medium","large","xlarge","xxlarge","xxxlarge"]
NF = {}
for r in csv.DictReader(open(os.path.join(BASE, "lsat-nf.csv"))):
    if r["config"] != "clean": continue
    NF[(r["source"] + "|" + r["airfoil"], round(float(r["Re"])), round(float(r["alpha"]), 2))] = r
XF = {}
for r in csv.DictReader(open(os.path.join(BASE, "lsat-xfoil.csv"))):
    XF[(r["entry"], round(float(r["Re"])), round(float(r["alpha"]), 2))] = (float(r["CL_xf"]), float(r["CD_xf"]))
rows = []
for key, r in NF.items():
    cds = np.array([float(r["CD_" + s]) for s in SIZES]); cls = np.array([float(r["CL_" + s]) for s in SIZES])
    cd8, cl8 = cds.mean(), cls.mean()
    z = OCD.get(key, 0.0); dcl = OCL.get(key, 0.0)
    rows.append(dict(meas=float(r["CD_meas"]), clm=float(r["CL_meas"]),
                     cd8=cd8, cl8=cl8, cdx=float(r["CD_xlarge"]), clx=float(r["CL_xlarge"]),
                     cdc=cd8 * np.exp(np.clip(z, np.log(0.5), np.log(2))),
                     clc=cl8 + np.clip(dcl, -0.5, 0.5),
                     xf=XF.get(key), Re=key[1]))
conv = [r for r in rows if r["xf"]]
print(f"common XFOIL-converged points: {len(conv)} of {len(rows)} ({100*len(conv)/len(rows):.1f}%)")
print("\nDRAG (counts):")
for name, f in (("XFOIL 6.99", lambda r: r["xf"][1]), ("classic NF xlarge", lambda r: r["cdx"]),
                ("new NF mean-of-8", lambda r: r["cd8"]), ("new NF + corrections", lambda r: r["cdc"])):
    e = np.array([abs(f(r) - r["meas"]) for r in conv]) * CT
    print(f"  {name:22s} MAE {e.mean():6.1f}  median {np.median(e):6.1f}")
print("LIFT:")
for name, f in (("XFOIL 6.99", lambda r: r["xf"][0]), ("classic NF xlarge", lambda r: r["clx"]),
                ("new NF mean-of-8", lambda r: r["cl8"]), ("new NF + corrections", lambda r: r["clc"])):
    e = np.array([abs(f(r) - r["clm"]) for r in conv])
    print(f"  {name:22s} MAE {e.mean():.4f}  median {np.median(e):.4f}")
print("\nby Re band, corrected vs XFOIL (drag MAE counts):")
for lo, hi in ((0, 75e3), (75e3, 15e4), (15e4, 25e4), (25e4, 6e5)):
    sel = [r for r in conv if lo <= r["Re"] < hi]
    if not sel: continue
    exf = np.mean([abs(r["xf"][1] - r["meas"]) for r in sel]) * CT
    eco = np.mean([abs(r["cdc"] - r["meas"]) for r in sel]) * CT
    print(f"  Re {int(lo/1e3):>3d}k-{int(hi/1e3):<3d}k: XFOIL {exf:6.1f} | new {eco:6.1f}  (n {len(sel)})")
e8 = np.array([abs(r["cd8"] - r["meas"]) for r in rows]) * CT
ec = np.array([abs(r["cdc"] - r["meas"]) for r in rows]) * CT
l8 = np.array([abs(r["cl8"] - r["clm"]) for r in rows])
lc = np.array([abs(r["clc"] - r["clm"]) for r in rows])
print(f"\nALL points: drag {e8.mean():.1f} -> {ec.mean():.1f}; lift {l8.mean():.4f} -> {lc.mean():.4f}")
