"""Does combining the 8 NeuralFoil model sizes beat the single xlarge network on
measured wind-tunnel data? Decides the core of the 'new NeuralFoil'.
Scored on the subsonic/subcritical experimental points where facility conventions
are settled (Harris fig8 fixed-transition absolutes; TN 1546 subcritical absolutes;
TN 1546 + Ferri subcritical lift). Also calibrates the spread-to-bound factor k with
cross-source validation. All reported as it lands.
"""
import csv, json
import numpy as np
import aerosandbox as asb
from fit_definitive import Re_of_M, naca4

SIZES = ["xxsmall","xsmall","small","medium","large","xlarge","xxlarge","xxxlarge"]

def rows(path):
    return list(csv.DictReader([l for l in open(path) if not l.startswith('#')]))

def run_all(af, alpha, Re, mach, **kw):
    out = {}
    for s in SIZES:
        o = af.get_aero_from_neuralfoil(alpha=alpha, Re=Re, mach=mach, model_size=s, **kw)
        out[s] = {k: float(np.asarray(o[k]).item()) for k in
                  ('CL','CD','CM','analysis_confidence','mach_crit')}
    return out

conds = []  # (tag, cd_meas or None, cl_meas or None, per-size dict)

# Harris fig8: 0012, alpha -0.14. NOTE: the measured rows kept by the M filter span
# Re 3.0e6 to 9.0e6 with BOTH fixed and free transition; predictions below are run
# uniformly at Re 3e6, fixed x/c=0.05, n_crit 9, so the absolute level of this group
# is dominated by condition mismatch and only the between-candidate ranking is meaningful.
af12 = asb.Airfoil("naca0012").to_kulfan_airfoil()
for r in rows('harris-fig8.csv'):
    m = float(r['mach'])
    if m > 0.70: continue
    o = run_all(af12, -0.14, 3.0e6, m, n_crit=9, xtr_upper=0.05, xtr_lower=0.05)
    conds.append((f"harris_M{m}", float(r['CD']), None, o))

# TN1546 subcritical cd: free transition nc6, Re(M) c=0.127
GEOM46 = np.load('tn1546_geom.npy', allow_pickle=True).item()
cache = {}
for r in rows('tn1546-sweeps.csv'):
    m = float(r['M']); sec = r['section']
    g = GEOM46.get(sec)
    if g is None or m > 0.60: continue
    af = cache.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
    o = run_all(af, float(r['alpha_test']), Re_of_M(m, c=0.127), m, n_crit=6)
    if o['xlarge']['mach_crit'] - 0.02 < m: continue   # keep strictly subcritical
    conds.append((f"tn1546_{sec}_M{m}", float(r['cd']), None, o))

# Lift: TN1546 cl + Ferri subcritical
for r in rows('tn1546-cl.csv'):
    m = float(r['M']); sec = r['section']
    g = GEOM46.get(sec)
    if g is None or m > 0.60: continue
    af = cache.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
    o = run_all(af, float(r['alpha_test']), Re_of_M(m, c=0.127), m, n_crit=6)
    conds.append((f"tn1546cl_{sec}_M{m}", None, float(r['cl']), o))
af29 = asb.Airfoil(name='2309', coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()
for r in rows('ferri-cl.csv'):
    m = float(r['M'])
    if m > 0.60: continue
    o = run_all(af29, float(r['alpha']), 3.8e5, m, n_crit=6)
    conds.append((f"ferricl_a{r['alpha']}_M{m}", None, float(r['CL']), o))

def combine(o, how, key):
    v = np.array([o[s][key] for s in SIZES])
    if how == 'xlarge':   return o['xlarge'][key]
    if how == 'median8':  return float(np.median(v))
    if how == 'mean8':    return float(np.mean(v))
    if how == 'trim2':    return float(np.mean(np.sort(v)[1:-1]))
    if how == 'confw':
        w = np.array([max(o[s]['analysis_confidence'], 1e-3) for s in SIZES])
        return float(np.sum(v * w) / np.sum(w))
    if how == 'big4med':  return float(np.median(v[4:]))

CANDS = ['xlarge','median8','mean8','trim2','confw','big4med']
print("=" * 76)
print("CORE CANDIDATES vs MEASURED (subcritical only; errors: CD in counts, CL abs)")
print("=" * 76)
groups = {'harris': ('cd', [c for c in conds if c[0].startswith('harris')]),
          'tn1546cd': ('cd', [c for c in conds if c[0].startswith('tn1546_')]),
          'tn1546cl': ('cl', [c for c in conds if c[0].startswith('tn1546cl')]),
          'ferricl': ('cl', [c for c in conds if c[0].startswith('ferricl')])}
res = {}
for how in CANDS:
    line = {}
    for gname, (kind, g) in groups.items():
        if kind == 'cd':
            e = [abs(combine(o, how, 'CD') - cd) * 1e4 for _, cd, _, o in g]
        else:
            e = [abs(combine(o, how, 'CL') - cl) for _, _, cl, o in g]
        line[gname] = np.mean(e) if e else float('nan')
    res[how] = line
hdr = f"{'candidate':>10s}" + "".join(f"{g:>12s}(n={len(groups[g][1]):d})" for g in groups)
print(hdr)
for how in CANDS:
    print(f"{how:>10s}" + "".join(f"{res[how][g]:>17.2f}" for g in groups))

# spread -> bound calibration with cross-source validation (CD only)
print()
print("=" * 76)
print("SPREAD-TO-BOUND FACTOR k (|error| <= k * spread90) with cross-source coverage")
print("=" * 76)
def spread(o, key):
    v = np.array([o[s][key] for s in SIZES])
    return float(np.percentile(v, 90) - np.percentile(v, 10))
pairs = {}
for gname in ('harris', 'tn1546cd'):
    kind, g = groups[gname]
    pairs[gname] = [(abs(combine(o, 'xlarge', 'CD') - cd), max(spread(o, 'CD'), 1e-6))
                    for _, cd, _, o in g]
for fit_on, test_on in (('harris','tn1546cd'), ('tn1546cd','harris')):
    ks = sorted(e / s for e, s in pairs[fit_on])
    k = ks[min(int(np.ceil(0.9 * (len(ks) + 1))) - 1, len(ks) - 1)]  # 90th conformal
    cov = np.mean([e <= k * s for e, s in pairs[test_on]])
    med_bound = np.median([k * s for e, s in pairs[test_on]]) * 1e4
    print(f"  k fit on {fit_on} = {k:.2f}; coverage on {test_on}: {cov:.0%} "
          f"(target 90%), median bound there {med_bound:.1f} counts")
json.dump({h: res[h] for h in CANDS}, open('ensemble-eval.json', 'w'), indent=1)
print("\nwrote ensemble-eval.json")
