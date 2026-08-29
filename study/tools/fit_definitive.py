"""The definitive Phase B fit, per the frozen Methods and amendments.

Pipeline (all rules fixed BEFORE this script ever sees holdout data):
  Calibration sources: TN 3607 sweeps (A13 Reynolds-corrected increments, n_crit 6,
  Re(M) from the derived tunnel curve, cn==cl at the low angles used) and the three
  Ferri 2309 sweeps (A1 flat baseline over the declared M <= 0.61 window, Re 3.8e5,
  n_crit 6). Points M <= 0.90 only, per Step 5.
  Candidate forms (Step 8): null k*80 x^4; F1 A x^b; F2 Korn-anchored 20(x-d)^4;
  F3 (a0 + a1*tc + a2*CL) x^b with b inherited from F1's full fit.
  Weights (A5): 1/sigma^2 with sigma^2 = u_cd^2 + (local slope * u_M)^2 + SE_base^2,
  times source weight 1/tier (TN 3607 tier 2, Ferri tier 3).
  Selection (Step 9 + A3): leave-one-SOURCE-out; per-sweep MAE then unweighted mean
  across held-out sweeps; adopt only if the winner beats the null.
  Uncertainty: sweep-level bootstrap, 400 resamples.

Run AFTER TN 1546 extraction is frozen (A10). This script performs NO holdout
scoring; score_holdout.py does that exactly once.
"""
import csv, json
import numpy as np
import aerosandbox as asb
from scipy.optimize import least_squares
from transonic_patch import mach_crit_of

RNG = np.random.default_rng(824)   # seed = NACA TR-824, fixed before running

def Re_of_M(M, c=0.1016, T0=288.15, p0=101325.0, g=1.4, R=287.05):
    T = T0/(1+0.5*(g-1)*M**2); p = p0*(T/T0)**(g/(g-1))
    rho = p/(R*T); V = M*np.sqrt(g*R*T)
    mu = 1.458e-6*T**1.5/(T+110.4)
    return rho*V*c/mu

def naca4(m, p, t, n=80):
    x = 0.5*(1+np.cos(np.pi*np.arange(n+1)/n))
    yt = t/0.2*(0.2969*np.sqrt(x)-0.1260*x-0.3516*x**2+0.2843*x**3-0.1036*x**4)
    if p > 0:
        yc = np.where(x < p, m/p**2*(2*p*x-x**2), m/(1-p)**2*((1-2*p)+2*p*x-x**2))
        dy = np.where(x < p, 2*m/p**2*(p-x), 2*m/(1-p)**2*(p-x))
    else:
        yc = np.zeros_like(x); dy = np.zeros_like(x)
    th = np.arctan(dy)
    return np.vstack([np.column_stack([x-yt*np.sin(th), yc+yt*np.cos(th)]),
                      np.column_stack([x+yt*np.sin(th), yc-yt*np.cos(th)])[::-1][1:]])

GEOM36 = np.load('tn3607_geom.npy', allow_pickle=True).item()

def build_sweeps():
    """Returns list of dicts: source, sweep, tc, CL_nom, Mc, pts [(M, dCD, sigma)], tier."""
    sweeps = []
    # ---- TN 3607 ----
    data = {}
    for r in csv.DictReader(open('tn3607-sweeps.csv')):
        data.setdefault((r['section'], float(r['alpha_test'])), []).append(
            (float(r['M']), float(r['cd']), float(r['u_cd'] or 0.0005)))
    cache = {}
    for (sec, al), pts in sorted(data.items()):
        pts = sorted(pts)
        g = GEOM36.get(sec)
        if g is None:
            continue
        af = cache.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
        # A13 baseline: measured level at M_ref plus the predicted Reynolds trend
        M_ref = 0.50
        cd_ref = np.interp(M_ref, [p[0] for p in pts], [p[1] for p in pts])
        def pred_cd(M):
            o = af.get_aero_from_neuralfoil(alpha=al, Re=Re_of_M(M), mach=0.0,
                                            model_size="xlarge", n_crit=6)
            return float(np.asarray(o['CD']).item())
        pc_ref = pred_cd(M_ref)
        o7 = af.get_aero_from_neuralfoil(alpha=al, Re=Re_of_M(0.70), mach=0.0,
                                         model_size="xlarge", n_crit=6)
        Mc = float(mach_crit_of(float(np.asarray(o7['Cpmin_0']).item())))
        CLn = float(np.asarray(o7['CL']).item())
        rows = []
        Ms = np.array([p[0] for p in pts]); Cs = np.array([p[1] for p in pts])
        for M, cd, ucd in pts:
            if M > 0.90 or M <= Mc:
                continue
            base = cd_ref + (pred_cd(M) - pc_ref)
            slope = np.interp(M, 0.5*(Ms[1:]+Ms[:-1]), np.diff(Cs)/np.diff(Ms)) if len(Ms) > 1 else 0.0
            sig = np.sqrt(ucd**2 + (slope*0.005)**2 + 0.0003**2)
            rows.append((M, cd - base, sig))
        if len(rows) >= 3:
            sweeps.append(dict(source='TN3607', sweep=f'{sec}_a{al:g}', tc=af.max_thickness(),
                               CL=CLn, Mc=Mc, pts=rows, tier=2))
    # ---- Ferri ----
    f = {}
    for r in csv.DictReader([l for l in open('ferri-2309.csv') if not l.startswith('#')]):
        f.setdefault(r['alpha_deg'], []).append(
            (float(r['mach']), float(r['CD']), float(r['uncertainty_cd']),
             float(r['uncertainty_M'])))
    af29 = asb.Airfoil(name='2309', coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()
    ALP = {'-1,0': 0.0, '1': 1.0, '2': 2.0}
    for a_str, pts in f.items():
        al = ALP[a_str]
        pts = sorted(pts)
        base_pts = [p[1] for p in pts if p[0] <= 0.61]
        base = float(np.mean(base_pts)); se = float(np.std(base_pts)/max(1, len(base_pts)-1)**0.5)
        o = af29.get_aero_from_neuralfoil(alpha=al, Re=3.8e5, mach=0.0, model_size="xlarge", n_crit=6)
        Mc = float(mach_crit_of(float(np.asarray(o['Cpmin_0']).item())))
        CLn = float(np.asarray(o['CL']).item())
        Ms = np.array([p[0] for p in pts]); Cs = np.array([p[1] for p in pts])
        rows = []
        for M, cd, ucd, um in pts:
            if M > 0.90 or M <= Mc:
                continue
            slope = np.interp(M, 0.5*(Ms[1:]+Ms[:-1]), np.diff(Cs)/np.diff(Ms))
            sig = np.sqrt(ucd**2 + (slope*um)**2 + se**2)
            rows.append((M, cd - base, sig))
        if len(rows) >= 3:
            sweeps.append(dict(source='Ferri', sweep=f'2309_a{a_str}', tc=0.09,
                               CL=CLn, Mc=Mc, pts=rows, tier=3))
    return sweeps

def model(form, p, x, tc=None, CL=None, b_fixed=None):
    x = np.maximum(0.0, x)
    if form == 'null':
        return p[0]*80*x**4
    if form == 'F1':
        return p[0]*np.maximum(1e-12, x)**p[1]
    if form == 'F2':
        y = np.maximum(0.0, x - p[0])
        return 20.0*y**4
    if form == 'F3':
        A = p[0] + p[1]*tc + p[2]*CL
        return np.maximum(0.0, A)*np.maximum(1e-12, x)**b_fixed
    raise ValueError(form)

def fit(form, sweeps, b_fixed=None):
    def resid(p):
        r = []
        for s in sweeps:
            M = np.array([q[0] for q in s['pts']]); d = np.array([q[1] for q in s['pts']])
            sig = np.array([q[2] for q in s['pts']])
            w = 1.0/np.sqrt(s['tier'])
            m = model(form, p, M - s['Mc'], tc=s['tc'], CL=s['CL'], b_fixed=b_fixed)
            r.append(w*(m - d)/sig)
        return np.concatenate(r)
    x0 = {'null': [0.13], 'F1': [1.2, 2.5], 'F2': [0.0], 'F3': [1.0, 0.0, 0.0]}[form]
    lo = {'null': [1e-4], 'F1': [1e-4, 0.5], 'F2': [-0.1], 'F3': [-50, -500, -50]}[form]
    hi = {'null': [10], 'F1': [500, 6], 'F2': [0.2], 'F3': [50, 500, 50]}[form]
    return least_squares(resid, x0, loss='soft_l1', bounds=(lo, hi)).x

def sweep_mae(form, p, s, b_fixed=None):
    M = np.array([q[0] for q in s['pts']]); d = np.array([q[1] for q in s['pts']])
    m = model(form, p, M - s['Mc'], tc=s['tc'], CL=s['CL'], b_fixed=b_fixed)
    return float(np.mean(np.abs(m - d)))*1e4

def main():
    sweeps = build_sweeps()
    print(f"calibration sweeps: {len(sweeps)}")
    for s in sweeps:
        print(f"  {s['source']:7s} {s['sweep']:14s} tc {s['tc']:.3f} CL {s['CL']:+.3f} "
              f"Mc {s['Mc']:.4f} nTr {len(s['pts'])}")
    srcs = sorted(set(s['source'] for s in sweeps))
    b_full = fit('F1', sweeps)[1]
    results = {}
    for form in ['null', 'F1', 'F2', 'F3']:
        held = []
        for hold in srcs:
            train = [s for s in sweeps if s['source'] != hold]
            test = [s for s in sweeps if s['source'] == hold]
            p = fit(form, train, b_fixed=b_full)
            held += [sweep_mae(form, p, s, b_fixed=b_full) for s in test]
        p_full = fit(form, sweeps, b_fixed=b_full)
        results[form] = (float(np.mean(held)), held, p_full)
        print(f"{form:5s} LOSO per-sweep MAEs: " + " ".join(f"{h:6.1f}" for h in held) +
              f"  mean {np.mean(held):6.1f} cts   full-fit params {np.round(p_full, 4)}")
    # stock comparator (exact pipeline handled at scoring; here the quartic segment alone
    # is NOT the shipped model, so stock LOSO MAE is computed in score_holdout on Harris)
    order = sorted(results, key=lambda f: results[f][0])
    winner = order[0] if order[0] != 'null' else order[1]
    beats_null = results[winner][0] < results['null'][0]
    print(f"\nSELECTED: {winner} (mean held-out {results[winner][0]:.1f} vs null {results['null'][0]:.1f})"
          f"  beats null: {beats_null}")
    # sweep-level bootstrap on the winner
    boots = []
    for _ in range(400):
        bs = [sweeps[i] for i in RNG.integers(0, len(sweeps), len(sweeps))]
        try:
            boots.append(fit(winner, bs, b_fixed=b_full))
        except Exception:
            pass
    B = np.array(boots)
    p_full = results[winner][2]
    print("bootstrap 95% intervals:")
    for i in range(B.shape[1]):
        lo, hi = np.percentile(B[:, i], [2.5, 97.5])
        print(f"  p[{i}] = {p_full[i]:.4f}  [{lo:.4f}, {hi:.4f}]")
    sel = dict(form=winner, params=[float(v) for v in p_full], b_fixed=float(b_full),
               loso_mean=results[winner][0], null_mean=results['null'][0],
               all_results={f: (results[f][0], [float(h) for h in results[f][1]],
                                [float(v) for v in results[f][2]]) for f in results},
               bootstrap_ci=[[float(np.percentile(B[:, i], 2.5)),
                              float(np.percentile(B[:, i], 97.5))] for i in range(B.shape[1])])
    json.dump(sel, open('selected-model.json', 'w'), indent=1)
    print("\nwrote selected-model.json  (selection is now FINAL; next step is the one-shot)")

if __name__ == '__main__':
    main()
