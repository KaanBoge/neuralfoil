"""EXPLORATORY (post-hoc, calibration data only, holdout untouched and unusable since
the one-shot is spent): does transonic-similarity thickness scaling collapse the
drag rise where the registered candidate family could not?

Form S1: dCD = A * (t/c)^(5/3) * [ (M - Mc) / (t/c)^(2/3) ]^b   (von Karman scaling)
Compared against F1 (no thickness scaling) under the SAME leave-one-source-out
protocol on the SAME 17 calibration sweeps. Also S2 adds the camber axis via CL.
"""
import numpy as np
from scipy.optimize import least_squares
from fit_definitive import build_sweeps

sweeps = build_sweeps()
print(f"sweeps: {len(sweeps)} (calibration only; holdout not loaded)")

def model(form, p, x, tc, CL):
    x = np.maximum(1e-12, x)
    if form == 'F1':
        return p[0]*x**p[1]
    if form == 'S1':
        return p[0] * tc**(5/3) * (x / tc**(2/3))**p[1]
    if form == 'S2':
        return (p[0] + p[2]*CL**2) * tc**(5/3) * (x / tc**(2/3))**p[1]
    raise ValueError

def fit(form, train):
    def resid(p):
        r = []
        for s in train:
            M = np.array([q[0] for q in s['pts']]); d = np.array([q[1] for q in s['pts']])
            sig = np.array([q[2] for q in s['pts']])
            m = model(form, p, M - s['Mc'], s['tc'], s['CL'])
            r.append((m - d)/sig/np.sqrt(s['tier']))
        return np.concatenate(r)
    x0 = {'F1': [1.2, 2.5], 'S1': [5.0, 2.5], 'S2': [5.0, 2.5, 0.0]}[form]
    lo = {'F1': [1e-4, 0.5], 'S1': [1e-4, 0.5], 'S2': [1e-4, 0.5, -100]}[form]
    hi = {'F1': [500, 6], 'S1': [500, 6], 'S2': [500, 6, 100]}[form]
    return least_squares(resid, x0, loss='soft_l1', bounds=(lo, hi)).x

def mae(form, p, s):
    M = np.array([q[0] for q in s['pts']]); d = np.array([q[1] for q in s['pts']])
    return float(np.mean(np.abs(model(form, p, M - s['Mc'], s['tc'], s['CL']) - d)))*1e4

srcs = sorted(set(s['source'] for s in sweeps))
print(f"{'form':4s} {'LOSO mean':>10s} {'in-fit mean':>12s}  full-fit params")
for form in ['F1', 'S1', 'S2']:
    held = []
    for hold in srcs:
        p = fit(form, [s for s in sweeps if s['source'] != hold])
        held += [mae(form, p, s) for s in sweeps if s['source'] == hold]
    pf = fit(form, sweeps)
    infit = np.mean([mae(form, pf, s) for s in sweeps])
    print(f"{form:4s} {np.mean(held):10.1f} {infit:12.1f}  {np.round(pf, 3)}")
print()
print("Per-sweep in-fit MAE for the best similarity form (S2), to see WHERE residual lives:")
pf = fit('S2', sweeps)
for s in sorted(sweeps, key=lambda s: -mae('S2', pf, s))[:6]:
    print(f"  {s['sweep']:14s} tc {s['tc']:.2f} CL {s['CL']:+.2f}: {mae('S2', pf, s):6.1f} cts")
print()
print("VERDICT NOTE: these numbers are exploratory model development, not validation.")
print("Confirmatory testing requires data the one-shot never touched: the 16 unextracted")
print("TN 1546 airfoils, Gothert TM 1240, or the boundary probes.")
