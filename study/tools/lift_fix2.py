"""Candidate 2 for the lift-break defect: ALPHA-DETACHED onset.
Measured breaks cluster near one Mach per airfoil regardless of alpha; the shipped
onset follows per-alpha mach_dd. Candidate: onset = mach_dd(reference alpha) + delta,
so it still moves with geometry and Reynolds but not with alpha.
Same protocol: LOAO on Ferri, cross-source on TN 1546, exploratory label.
"""
import csv
import numpy as np
import aerosandbox as asb
import aerosandbox.numpy as anp
from fit_definitive import Re_of_M, naca4

def rows(path):
    return list(csv.DictReader([l for l in open(path) if not l.startswith('#')]))

def buffet(m, onset):
    return anp.blend(50 * (m - onset), anp.blend((m - 1) / 0.1, 1, 0.5), 1)

pts = []  # (src, alpha, M, cl_meas, CL_shipped, mdd_own, mdd_ref)
af29 = asb.Airfoil(name='2309', coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()
o0 = af29.get_aero_from_neuralfoil(alpha=0.0, Re=3.8e5, mach=0.5, model_size="xlarge", n_crit=6)
mddref_fer = float(np.asarray(o0['mach_dd']).item())
for r in rows('ferri-cl.csv'):
    al, m, cl = float(r['alpha']), float(r['M']), float(r['CL'])
    o = af29.get_aero_from_neuralfoil(alpha=al, Re=3.8e5, mach=m, model_size="xlarge", n_crit=6)
    pts.append(('ferri', al, m, cl, float(np.asarray(o['CL']).item()),
                float(np.asarray(o['mach_dd']).item()), mddref_fer))

GEOM46 = np.load('tn1546_geom.npy', allow_pickle=True).item()
cache, refcache = {}, {}
for r in rows('tn1546-cl.csv'):
    sec, al, m, cl = r['section'], float(r['alpha_test']), float(r['M']), float(r['cl'])
    g = GEOM46.get(sec)
    if g is None:
        continue
    af = cache.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
    if sec not in refcache:
        orf = af.get_aero_from_neuralfoil(alpha=-0.23, Re=Re_of_M(0.7, c=0.127), mach=0.5,
                                          model_size="xlarge", n_crit=6)
        refcache[sec] = float(np.asarray(orf['mach_dd']).item())
    o = af.get_aero_from_neuralfoil(alpha=al, Re=Re_of_M(m, c=0.127), mach=m,
                                    model_size="xlarge", n_crit=6)
    pts.append(('tn1546', al, m, cl, float(np.asarray(o['CL']).item()),
                float(np.asarray(o['mach_dd']).item()), refcache[sec]))

def cl_mod(p, delta):
    src, al, m, cl, clship, mdd, mddref = p
    return clship / buffet(m, mdd + 0.04) * buffet(m, mddref + delta)

def mae(sel, delta=None):
    if delta is None:  # shipped
        return np.mean([abs(p[4] - p[3]) for p in sel])
    return np.mean([abs(cl_mod(p, delta) - p[3]) for p in sel])

DELTAS = np.round(np.arange(0.00, 0.201, 0.005), 3)
fer = [p for p in pts if p[0] == 'ferri']
tn = [p for p in pts if p[0] == 'tn1546']

print("LEAVE-ONE-ALPHA-OUT, onset = mach_dd(ref alpha) + delta  (alpha-detached)")
alphas = sorted(set(p[1] for p in fer))
cv_s, cv_f, fds = [], [], []
for hold in alphas:
    train = [p for p in fer if p[1] != hold]
    test = [p for p in fer if p[1] == hold]
    d = DELTAS[int(np.argmin([mae(train, x) for x in DELTAS]))]
    fds.append(float(d))
    cv_s.append(mae(test)); cv_f.append(mae(test, d))
    print(f"  hold alpha {hold:+.0f}: delta {d:.3f} | held-out MAE shipped {mae(test):.3f} -> {mae(test, d):.3f}")
print(f"  LOAO mean: shipped {np.mean(cv_s):.3f} -> {np.mean(cv_f):.3f} "
      f"({(1 - np.mean(cv_f)/np.mean(cv_s)):+.0%}); deltas {fds}")
d_all = DELTAS[int(np.argmin([mae(fer, x) for x in DELTAS]))]
brk = [p for p in fer if p[2] >= 0.85]
print(f"  delta on all alphas {d_all:.3f}; Ferri break-region MAE {mae(brk):.3f} -> {mae(brk, d_all):.3f}")
print(f"  cross-source TN1546: overall {mae(tn):.3f} -> {mae(tn, d_all):.3f}")
above = [p for p in tn if p[2] > min(p[5], p[6] + d_all) - 0.02]
print(f"  TN1546 points near/above either onset: {len(above)}: {mae(above):.3f} -> {mae(above, d_all):.3f}")
sub = [p for p in pts if p[2] <= min(p[5] + 0.04, p[6] + d_all) - 0.02]
ch = max(abs(cl_mod(p, d_all) - p[4]) for p in sub)
print(f"  no-harm: max CL change over {len(sub)} points below both onsets: {ch:.2e}")
