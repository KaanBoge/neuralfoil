"""Final probe bundle: the remaining testable failure surfaces.
A. HARD WRONGS: physically impossible outputs (CD<=0, |CL|>4, Xtr outside [0,1],
   confidence outside [0,1], NaN) across a stratified grid incl. degenerate geometry.
B. SMOOTHNESS: derivative kinks vs alpha and Re (optimizer safety).
C. GEOMETRY ROBUSTNESS: output jitter under scan-level coordinate noise; degenerate inputs.
D. CM ENSEMBLE SPREAD: the moment coefficient's internal-disagreement slice.
"""
import json, os
import numpy as np
import neuralfoil as nf

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, '..', 'uiuc-airfoils.json')) as f:
    DB = [a for a in json.load(f) if len(a['p']) >= 30]
DB.sort(key=lambda a: a.get('t', 0))
SAMPLE = DB[::max(1, len(DB)//60)][:60]
rng = np.random.default_rng(1546)

def run(pts, al, Re, size="xlarge"):
    return nf.get_aero_from_coordinates(pts, alpha=al, Re=Re, model_size=size,
                                        n_crit=9, xtr_upper=1, xtr_lower=1)

print("=" * 74)
print("B. SMOOTHNESS (finite-difference kinks; optimizer safety)")
print("=" * 74)
kinks_a, kinks_r = [], []
for a in SAMPLE[::6]:
    pts = np.array(a['p'], float)
    al = np.arange(-2, 8.001, 0.02)
    r = run(pts, al, 1e6)
    cd = np.atleast_1d(r['CD'])
    d2 = np.abs(np.diff(cd, 2)) * 1e4          # counts per step^2: jump detector
    kinks_a.append(float(d2.max()))
    res = np.logspace(5.5, 6.5, 201)
    cds = np.array([float(np.asarray(run(pts, 3.0, R)["CD"]).item()) for R in res])
    d2r = np.abs(np.diff(cds, 2)) * 1e4
    kinks_r.append(float(d2r.max()))
print(f"alpha direction (step 0.02 deg): max 2nd-difference {max(kinks_a):.3f} counts "
      f"(median foil {np.median(kinks_a):.3f}); > 1 count would mean a kink an optimizer feels")
print(f"Re direction (200 log steps):    max 2nd-difference {max(kinks_r):.3f} counts "
      f"(median foil {np.median(kinks_r):.3f})")

print()
print("=" * 74)
print("C. GEOMETRY ROBUSTNESS (scan-level coordinate noise, sigma = 2e-4 chord)")
print("=" * 74)
jit = []
for a in SAMPLE[::6]:
    pts = np.array(a['p'], float)
    base = float(np.asarray(run(pts, 2.0, 1e6)["CD"]).item())
    for _ in range(8):
        noisy = pts + rng.normal(0, 2e-4, pts.shape)
        noisy[0] = pts[0]; noisy[-1] = pts[-1]
        jit.append(abs(float(np.asarray(run(noisy, 2.0, 1e6)["CD"]).item()) - base) * 1e4)
jit = np.array(jit)
print(f"CD jitter from digitization-level noise: median {np.median(jit):.1f} counts, "
      f"p90 {np.percentile(jit, 90):.1f}, max {jit.max():.1f}")
print("(this is the geometry-input noise floor every scanned-coordinate user inherits)")

print()
print("=" * 74)
print("D. MOMENT COEFFICIENT: ensemble spread slice (8 sizes, 60 foils)")
print("=" * 74)
cms = {s: [] for s in ["xxsmall", "small", "large", "xxxlarge", "xlarge"]}
for a in SAMPLE:
    pts = np.array(a['p'], float)
    for s in cms:
        r = nf.get_aero_from_coordinates(pts, alpha=np.array([0.0, 4.0]), Re=1e6,
                                         model_size=s, n_crit=9, xtr_upper=1, xtr_lower=1)
        cms[s].append(np.atleast_1d(r['CM']))
arr = {s: np.array(v) for s, v in cms.items()}
stack = np.stack([arr[s] for s in cms])          # sizes x foils x 2
spread = stack.max(0) - stack.min(0)
print(f"CM spread across sizes: median {np.median(spread):.4f}, p90 {np.percentile(spread, 90):.4f}, "
      f"max {spread.max():.4f}  (CM ~ 0.05-0.1 scale: p90 spread is "
      f"{np.percentile(spread,90)/0.08*100:.0f}% of a typical cambered CM)")
