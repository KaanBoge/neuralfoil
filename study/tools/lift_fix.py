"""LIFT-BREAK TIMING FIX (exploratory, labeled as such: the registered one-shot
covered the drag layer only and is spent; no confirmatory holdout exists for lift).

Defect being fixed: the shipped buffet factor cuts CL starting at mach_dd + 0.04
(RANS-tuned), but measured lift at alpha +1/+2 (Ferri 2309) is still RISING there;
the measured lift break comes later. Fix form: a single delayed onset,
buffet onset = mach_dd + delta, delta fitted; everything else untouched.

Method: undo the shipped buffet factor exactly (aerosandbox's own np.blend, so the
inversion is machine-exact), reapply with candidate delta. Fit by leave-one-alpha-out
on Ferri (4 folds); the fold-held-out alpha scores the candidate. Then a genuine
cross-source check: apply the Ferri-fitted delta unchanged to the TN 1546 subset.
No-harm is structural: below the onset the factor is 1, so subcritical CL is
bit-identical; verified numerically anyway.
"""
import csv
import numpy as np
import aerosandbox as asb
import aerosandbox.numpy as anp
from fit_definitive import Re_of_M, naca4

def rows(path):
    return list(csv.DictReader([l for l in open(path) if not l.startswith('#')]))

def buffet(m, mdd, delta):
    """The shipped Step-3 buffet factor with movable onset. delta=0.04 = shipped."""
    return anp.blend(50 * (m - (mdd + delta)), anp.blend((m - 1) / 0.1, 1, 0.5), 1)

# ---------- gather every measured lift point with its shipped prediction ----------
pts = []  # (src, alpha, M, cl_meas, CL_shipped, mach_dd)
af29 = asb.Airfoil(name='2309', coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()
for r in rows('ferri-cl.csv'):
    al, m, cl = float(r['alpha']), float(r['M']), float(r['CL'])
    o = af29.get_aero_from_neuralfoil(alpha=al, Re=3.8e5, mach=m, model_size="xlarge", n_crit=6)
    pts.append(('ferri', al, m, cl, float(np.asarray(o['CL']).item()),
                float(np.asarray(o['mach_dd']).item())))

GEOM46 = np.load('tn1546_geom.npy', allow_pickle=True).item()
cache = {}
for r in rows('tn1546-cl.csv'):
    sec, al, m, cl = r['section'], float(r['alpha_test']), float(r['M']), float(r['cl'])
    g = GEOM46.get(sec)
    if g is None:
        continue
    af = cache.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
    o = af.get_aero_from_neuralfoil(alpha=al, Re=Re_of_M(m, c=0.127), mach=m,
                                    model_size="xlarge", n_crit=6)
    pts.append(('tn1546', al, m, cl, float(np.asarray(o['CL']).item()),
                float(np.asarray(o['mach_dd']).item())))

def cl_with_delta(p, delta):
    src, al, m, cl, clship, mdd = p
    return clship / buffet(m, mdd, 0.04) * buffet(m, mdd, delta)

def mae(sel, delta):
    return np.mean([abs(cl_with_delta(p, delta) - p[3]) for p in sel])

DELTAS = np.round(np.arange(0.00, 0.201, 0.005), 3)
fer = [p for p in pts if p[0] == 'ferri']
tn = [p for p in pts if p[0] == 'tn1546']

# ---------- where is the measured lift break vs the shipped onset? ----------
print("=" * 74)
print("MEASURED LIFT-BREAK MACH vs SHIPPED BUFFET ONSET (Ferri 2309)")
print("=" * 74)
for al in sorted(set(p[1] for p in fer)):
    sw = sorted([p for p in fer if p[1] == al], key=lambda p: p[2])
    ms = [p[2] for p in sw]; cs = [p[3] for p in sw]
    i = int(np.argmax(cs))
    mdd = sw[0][5]
    print(f"  alpha {al:+.0f}: measured CL peaks at M {ms[i]:.2f}  |  "
          f"shipped cut starts M {mdd + 0.04:.3f}  ->  early by {ms[i] - mdd - 0.04:+.3f}")

# ---------- LOAO fit on Ferri ----------
print()
print("=" * 74)
print("LEAVE-ONE-ALPHA-OUT FIT OF THE ONSET DELAY delta (shipped delta = 0.04)")
print("=" * 74)
alphas = sorted(set(p[1] for p in fer))
cv_ship, cv_fit, fold_deltas = [], [], []
for hold in alphas:
    train = [p for p in fer if p[1] != hold]
    test = [p for p in fer if p[1] == hold]
    d_star = DELTAS[int(np.argmin([mae(train, d) for d in DELTAS]))]
    fold_deltas.append(d_star)
    cv_ship.append(mae(test, 0.04)); cv_fit.append(mae(test, d_star))
    print(f"  hold alpha {hold:+.0f}: fitted delta {d_star:.3f}  |  "
          f"held-out CL MAE shipped {mae(test, 0.04):.3f} -> fitted {mae(test, d_star):.3f}")
print(f"\n  LOAO mean CL MAE: shipped {np.mean(cv_ship):.3f} -> fitted {np.mean(cv_fit):.3f} "
      f"({(1 - np.mean(cv_fit)/np.mean(cv_ship)):+.0%}); fold deltas {fold_deltas}")

d_all = DELTAS[int(np.argmin([mae(fer, d) for d in DELTAS]))]
print(f"  delta fitted on all four alphas: {d_all:.3f}")

# break-region view (M >= 0.85, the region the audit flagged)
brk = [p for p in fer if p[2] >= 0.85]
print(f"  Ferri break-region (M>=0.85) MAE: shipped {mae(brk, 0.04):.3f} -> {mae(brk, d_all):.3f}")

# ---------- cross-source check: TN 1546 untouched by the fit ----------
print()
print("=" * 74)
print("CROSS-SOURCE CHECK: Ferri-fitted delta applied unchanged to TN 1546 subset")
print("=" * 74)
above = [p for p in tn if p[2] > p[5] + 0.02]
print(f"  TN1546 points at all: {len(tn)}; points in the affected region (M > mach_dd+0.02): {len(above)}")
print(f"  TN1546 overall CL MAE: shipped {mae(tn, 0.04):.3f} -> with delta {d_all:.3f}: {mae(tn, d_all):.3f}")
if above:
    print(f"  TN1546 affected-region CL MAE: shipped {mae(above, 0.04):.3f} -> {mae(above, d_all):.3f}")

# ---------- no-harm ----------
sub = [p for p in pts if p[2] <= p[5] + 0.02]
dmax = max(abs(cl_with_delta(p, d_all) - p[4]) for p in sub)
print(f"\n  no-harm: max |CL change| over the {len(sub)} points below mach_dd+0.02: {dmax:.2e}")
