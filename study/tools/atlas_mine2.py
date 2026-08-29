"""Coverage closure 2 and 3: lift-spread mining, and the transition-handling probe.

Part A mines the CL spread already recorded in the atlas (the lift analogue of the
drag analysis). Part B probes the trip inputs on a stratified airfoil sample:
n_crit sensitivity and forced-transition behavior, including the consistency
requirement that tripping at the natural transition point should approximately
reproduce the free solution, and that trip location should move drag monotonically.
Violations are internal-inconsistency failures no experiment is needed to see."""
import os, csv, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'atlas-out')

# ---------- Part A: lift spread ----------
rows = []
for fn in os.listdir(OUT):
    if not fn.endswith('.csv'):
        continue
    with open(os.path.join(OUT, fn)) as f:
        for r in csv.DictReader(f):
            rows.append((fn[:-4], float(r['Re']), float(r['alpha']),
                         float(r['CL_xl']), float(r['conf_xl']), float(r['CL_std8'])))
re_a = np.array([r[1] for r in rows]); al_a = np.array([r[2] for r in rows])
cl_a = np.array([r[3] for r in rows]); cf_a = np.array([r[4] for r in rows])
cls_a = np.array([r[5] for r in rows])

print("=" * 74)
print("A. LIFT: spread of CL across the eight model sizes (std, lift counts of 0.001)")
print("=" * 74)
print(f"{'Re':>8s} {'median':>8s} {'p90':>8s} {'share>0.02':>11s} {'share>0.05':>11s}")
for Re in sorted(set(re_a)):
    m = re_a == Re
    print(f"{Re:8.0e} {np.median(cls_a[m]):8.4f} {np.percentile(cls_a[m],90):8.4f} "
          f"{np.mean(cls_a[m]>0.02)*100:10.1f}% {np.mean(cls_a[m]>0.05)*100:10.1f}%")
mtr = (re_a >= 2e5) & (re_a <= 5e6)
print()
print("alpha profile (training-band Re):")
for al in [-10, -6, -2, 0, 2, 6, 10, 13, 16]:
    m = mtr & (al_a == al)
    print(f"  alpha {al:+3d}: median {np.median(cls_a[m]):.4f}  p90 {np.percentile(cls_a[m],90):.4f}  "
          f"share>0.05 {np.mean(cls_a[m]>0.05)*100:.1f}%")
hh = (cf_a > 0.9) & (cls_a > 0.05)
print(f"\nhigh-confidence lift failures (conf>0.90, CL spread>0.05): "
      f"{hh.sum():,} of {len(rows):,} ({hh.mean()*100:.2f}%)")

# ---------- Part B: transition-handling probe ----------
print()
print("=" * 74)
print("B. TRANSITION HANDLING (stratified 40-airfoil sample, alpha 2, Re 1e6)")
print("=" * 74)
import neuralfoil as nf
UIUC = os.path.join(HERE, '..', 'uiuc-airfoils.json')
with open(UIUC) as f:
    db = [a for a in json.load(f) if len(a['p']) >= 20]
db.sort(key=lambda a: a.get('t', 0))
sample = db[::max(1, len(db)//40)][:40]

viol_nonmono = []   # trip location fails to move drag monotonically
viol_freetrip = []  # tripping AT the natural transition point does not reproduce free
ncrit_range = []    # cd(ncrit 4) - cd(ncrit 12): the tunnel-turbulence lever arm
for a in sample:
    pts = np.array(a['p'], dtype=float)
    try:
        free = nf.get_aero_from_coordinates(pts, alpha=2.0, Re=1e6, model_size="xlarge",
                                            n_crit=9, xtr_upper=1, xtr_lower=1)
        cd_free = float(np.asarray(free['CD']).item())
        xt_u = float(np.asarray(free['Top_Xtr']).item())
        xt_l = float(np.asarray(free['Bot_Xtr']).item())
        # consistency 1: trip at the natural transition points ~ free solution
        att = nf.get_aero_from_coordinates(pts, alpha=2.0, Re=1e6, model_size="xlarge",
                                           n_crit=9, xtr_upper=xt_u, xtr_lower=xt_l)
        d_at = abs(float(np.asarray(att['CD']).item()) - cd_free) * 1e4
        viol_freetrip.append((a['f'], d_at))
        # consistency 2: monotonicity in trip location (earlier trip -> more turbulent -> higher cd)
        cds = []
        for x in (0.05, 0.15, 0.30, 0.50, 0.70):
            r = nf.get_aero_from_coordinates(pts, alpha=2.0, Re=1e6, model_size="xlarge",
                                             n_crit=9, xtr_upper=x, xtr_lower=x)
            cds.append(float(np.asarray(r['CD']).item()))
        diffs = np.diff(cds)
        worst_up = max(0.0, float(diffs.max())) * 1e4  # any INCREASE with later trip = violation
        viol_nonmono.append((a['f'], worst_up, cds[0]*1e4, cds[-1]*1e4))
        # lever arm
        c4 = nf.get_aero_from_coordinates(pts, alpha=2.0, Re=1e6, model_size="xlarge",
                                          n_crit=4, xtr_upper=1, xtr_lower=1)
        c12 = nf.get_aero_from_coordinates(pts, alpha=2.0, Re=1e6, model_size="xlarge",
                                           n_crit=12, xtr_upper=1, xtr_lower=1)
        ncrit_range.append((float(np.asarray(c4['CD']).item()) -
                            float(np.asarray(c12['CD']).item())) * 1e4)
    except Exception:
        continue

d_at = np.array([v[1] for v in viol_freetrip])
print(f"trip-at-natural-transition vs free (should be ~equal): "
      f"median |dCD| {np.median(d_at):.1f} counts, p90 {np.percentile(d_at,90):.1f}, max {d_at.max():.1f}")
worst = sorted(viol_freetrip, key=lambda v: -v[1])[:3]
for n, d in worst:
    print(f"    worst: {n} {d:.1f} counts")
up = np.array([v[1] for v in viol_nonmono])
print(f"trip-location monotonicity (drag must fall as trip moves aft): "
      f"violations > 2 counts on {np.mean(up>2)*100:.0f}% of sample, max violation {up.max():.1f} counts")
nr = np.array(ncrit_range)
print(f"n_crit lever arm (cd at n_crit 4 minus 12): median {np.median(nr):.1f} counts "
      f"(the tunnel-turbulence convention uncertainty a user inherits)")
