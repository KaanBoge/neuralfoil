"""XFOIL 6.99 (the field's de facto standard tool, and NeuralFoil's teacher)
run over the same measured LSAT corpus: every clean drag block, at its measured
alphas, viscous, n_crit 9 (XFOIL default), free transition.
Output lsat-xfoil.csv: entry, Re, alpha, CL_xf, CD_xf. Non-converged points are
simply absent, and the convergence rate is part of the result."""
import csv, json, os, subprocess, tempfile
import numpy as np
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
XFOIL = os.path.expanduser("~/Xfoil/bin/xfoil")
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))
rows = [r for r in csv.DictReader(open(os.path.join(BASE, "lsat-corpus.csv")))
        if r["config"] == "clean" and (r["source"] + "|" + r["airfoil"]) in GEO
        and GEO[r["source"] + "|" + r["airfoil"]]["config"] == "clean"]
blocks = {}
for r in rows:
    blocks.setdefault((r["source"] + "|" + r["airfoil"], float(r["Re"])), []).append(float(r["alpha"]))

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

def run_block(job):
    key, Re, alphas = job
    try:
        pts = load_pts(GEO[key]["path"])
    except Exception:
        return (key, Re, [])
    with tempfile.TemporaryDirectory() as td:
        dat, pol = os.path.join(td, "a.dat"), os.path.join(td, "p.txt")
        with open(dat, "w") as f:
            f.write("af\n")
            for x, y in pts:
                f.write(f" {x:.6f} {y:.6f}\n")
        cmds = (f"PLOP\nG\n\nLOAD {dat}\nPANE\nOPER\nVISC {Re:.0f}\nITER 200\nPACC\n{pol}\n\n"
                + "\n".join(f"ALFA {a:.2f}" for a in sorted(alphas)) + "\nPACC\n\nQUIT\n")
        try:
            subprocess.run([XFOIL], input=cmds.encode(), timeout=180,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return (key, Re, [])
        out = []
        if os.path.exists(pol):
            for L in open(pol).read().splitlines():
                p = L.split()
                if len(p) >= 3:
                    try:
                        a, cl, cd = float(p[0]), float(p[1]), float(p[2])
                        if -25 < a < 30 and 0 < cd < 1:
                            out.append((a, cl, cd))
                    except ValueError:
                        pass
        return (key, Re, out)

jobs = [(k, Re, al) for (k, Re), al in sorted(blocks.items())]
print(f"{len(jobs)} XFOIL blocks", flush=True)
with ThreadPoolExecutor(10) as pool:
    with open(os.path.join(BASE, "lsat-xfoil.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entry", "Re", "alpha", "CL_xf", "CD_xf"])
        done = 0
        for key, Re, out in pool.map(run_block, jobs):
            for a, cl, cd in out:
                w.writerow([key, Re, f"{a:.2f}", f"{cl:.4f}", f"{cd:.6f}"])
            done += 1
            if done % 50 == 0:
                print(f"{done}/{len(jobs)}", flush=True)
print("DONE", flush=True)
