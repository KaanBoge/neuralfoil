"""Measured LIFT corpus: parse LIFT01/02/03.TXT + SoarTech-8 per-Re lift files,
run all 8 NeuralFoil sizes (mach 0, n_crit 9), and score:
  1. CL error by alpha regime (pre-stall, near-stall, post-stall),
  2. per-sweep CLmax and stall-angle error (predicted on a fine grid),
  3. mean-of-8 vs xlarge on lift at scale.
Geometry from lsat-geometry.json (same matching as the drag corpus).
Writes lsat-lift-report.txt and lsat-clmax.csv.
"""
import csv, json, os, re
import numpy as np
import aerosandbox as asb

BASE = os.path.dirname(os.path.abspath(__file__))
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
GEO = json.load(open(os.path.join(BASE, "lsat-geometry.json")))

def ffloat(s):
    return float(re.sub(r"[^0-9eE+.\-]", "", s))

sweeps = {}  # (entrykey, Re) -> list of (alpha, cl)
def parse_lift_txt(path, source):
    txt = open(path, errors="replace").read().splitlines()
    i, n = 0, len(txt)
    af, comment = None, ""
    while i < n:
        L = txt[i].strip()
        if L.startswith("Airfoil:"):
            af = L.split(":", 1)[1].strip(); comment = ""
        elif L.startswith("Comment:"):
            comment = L.split(":", 1)[1].strip()
        elif L.startswith("Average Reynolds #"):
            i += 1
            Re = ffloat(txt[i])
            while not txt[i].strip().startswith("Number of angles"):
                i += 1
            i += 1
            cnt = int(txt[i].strip())
            while "alpha" not in txt[i]:
                i += 1
            key = source + "|" + af
            if key in GEO and GEO[key]["config"] == "clean" and not any(
                    t in comment.lower() for t in ("trip", "tape", "flap", "rough", "turbulator")):
                for k in range(cnt):
                    i += 1
                    p = txt[i].split()
                    try:
                        sweeps.setdefault((key, Re), []).append((ffloat(p[0]), ffloat(p[1])))
                    except (ValueError, IndexError):
                        pass
            else:
                i += cnt
        i += 1

for v, d in (("vol1", "volume01/volume01/LIFT01.TXT"),
             ("vol2", "volume02/volume02/LIFT02.TXT"),
             ("vol3", "volume03/volume03/LIFT03.TXT")):
    parse_lift_txt(os.path.join(BASE, d), v)
# stec8 per-Re lift files: NAME.06 etc, Re on line 4
for f in os.listdir(os.path.join(BASE, "stec8")):
    if not re.match(r".+\.\d\d$", f):
        continue
    lines = open(os.path.join(BASE, "stec8", f), errors="replace").read().splitlines()
    try:
        af = lines[1].strip()
        Re = ffloat(lines[3].split()[-1])
    except (IndexError, ValueError):
        continue
    key = "stec8|" + af
    if key not in GEO or GEO[key]["config"] != "clean":
        continue
    for L in lines[5:]:
        p = L.split()
        if len(p) >= 2:
            try:
                sweeps.setdefault((key, Re), []).append((ffloat(p[0]), ffloat(p[1])))
            except ValueError:
                pass
print(f"lift corpus: {sum(len(v) for v in sweeps.values())} points, "
      f"{len(set(k for k, _ in sweeps))} entries, {len(sweeps)} sweeps", flush=True)

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

FINE = np.arange(-5, 20.01, 0.25)
af_cache, rows_cl, rows_max = {}, [], []
done = 0
for (key, Re), pts in sorted(sweeps.items()):
    try:
        if key not in af_cache:
            af_cache[key] = asb.Airfoil(name=key.split("|")[1],
                                        coordinates=load_pts(GEO[key]["path"])).to_kulfan_airfoil()
        af = af_cache[key]
        alphas = np.array([p[0] for p in pts])
        meas = np.array([p[1] for p in pts])
        pred = {}
        for s in SIZES:
            o = af.get_aero_from_neuralfoil(alpha=alphas, Re=Re, mach=0.0, model_size=s, n_crit=9)
            pred[s] = np.atleast_1d(o["CL"])
        m8 = np.mean([pred[s] for s in SIZES], axis=0)
        for i in range(len(pts)):
            rows_cl.append((key, Re, alphas[i], meas[i], m8[i], pred["xlarge"][i]))
        # CLmax: only when the measured sweep actually captures a peak (a decrease after max)
        im = int(np.argmax(meas))
        if 0 < im < len(meas) - 1 and meas[im] > meas[-1] + 0.02 and alphas[im] > 4:
            fine = {}
            for s in ("xlarge",):
                o = af.get_aero_from_neuralfoil(alpha=FINE, Re=Re, mach=0.0, model_size=s, n_crit=9)
                fine[s] = np.atleast_1d(o["CL"])
            o8 = [np.atleast_1d(af.get_aero_from_neuralfoil(alpha=FINE, Re=Re, mach=0.0,
                                                            model_size=s, n_crit=9)["CL"]) for s in SIZES]
            f8 = np.mean(o8, axis=0)
            rows_max.append((key, Re, meas[im], alphas[im],
                             float(f8.max()), float(FINE[int(np.argmax(f8))]),
                             float(fine["xlarge"].max()), float(FINE[int(np.argmax(fine["xlarge"]))])))
    except Exception as e:
        print("FAIL", key, Re, repr(e), flush=True)
    done += 1
    if done % 50 == 0:
        print(f"{done}/{len(sweeps)} sweeps", flush=True)

rep = open(os.path.join(BASE, "lsat-lift-report.txt"), "w")
def P(*a):
    print(*a, flush=True); rep.write(" ".join(str(x) for x in a) + "\n")
A = np.array([(r[2], r[3], r[4], r[5]) for r in rows_cl])
P("=" * 70)
P(f"MEASURED LIFT VALIDATION: {len(rows_cl)} points, {len(set(r[0] for r in rows_cl))} airfoils")
P("=" * 70)
for name, lo, hi in (("pre-stall (-5..+8)", -5, 8), ("near-stall (+8..+12)", 8, 12),
                     ("stall/post (+12..+20)", 12, 20), ("negative (-10..-5)", -10, -5)):
    sel = (A[:, 0] >= lo) & (A[:, 0] < hi)
    if sel.sum() == 0: continue
    e8 = np.abs(A[sel, 2] - A[sel, 1]); ex = np.abs(A[sel, 3] - A[sel, 1])
    P(f"  {name:22s} n {sel.sum():5d}  CL MAE mean8 {e8.mean():.4f} | xlarge {ex.mean():.4f}  median {np.median(e8):.4f}")
M = np.array([(r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows_max])
if len(M):
    P(f"\nCLMAX ({len(M)} sweeps with a captured measured peak):")
    P(f"  CLmax error mean8: mean {np.mean(M[:,2]-M[:,0]):+.3f}, MAE {np.mean(np.abs(M[:,2]-M[:,0])):.3f}"
      f" | xlarge MAE {np.mean(np.abs(M[:,4]-M[:,0])):.3f}")
    P(f"  stall-alpha error mean8: mean {np.mean(M[:,3]-M[:,1]):+.2f} deg, MAE {np.mean(np.abs(M[:,3]-M[:,1])):.2f} deg")
    P(f"  CLmax overpredicted on {np.mean(M[:,2]>M[:,0])*100:.0f}% of sweeps (mean8)")
with open(os.path.join(BASE, "lsat-clmax.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["entry", "Re", "clmax_meas", "astall_meas", "clmax_mean8", "astall_mean8", "clmax_xlarge", "astall_xlarge"])
    w.writerows(rows_max)
rep.close()
print("wrote lsat-lift-report.txt, lsat-clmax.csv")
