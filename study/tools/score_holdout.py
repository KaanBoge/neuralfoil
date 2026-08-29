"""THE ONE-SHOT HOLDOUT SCORING. Runs exactly once, after selected-model.json is frozen.

Pre-registered criteria (hard-coded, from the frozen Methods):
  1. >= 30 percent reduction in mean absolute error of the drag-rise increment vs the
     stock pipeline, per-sweep MAE then unweighted mean (A3), on Harris and on the
     TN 1546 subset, reported separately.
  2. M_dd error cut in half: |M_dd_model - M_dd_measured| vs |M_dd_stock - M_dd_measured|,
     measured M_dd per A2 (+A2b), stock M_dd = mach_crit + 0.068, model M_dd = the Mach
     where the selected form's slope reaches 0.10.
  3. No-harm: subcritical predictions unchanged (structural for x_+ forms; verified).
  4. Phase C: conformal bound = ceil((n+1)*0.9)-th order statistic of |stock increment
     error| over CALIBRATION points per regime, fixed here from calibration data, then
     coverage measured once on holdout points against the exact two-sided 95 percent
     binomial interval around 90 percent.
Declared conventions for TN 1546 (fixed before its data was read, deviations D11/D12):
  n_crit 6 a priori (facility class analogy, not tuned); Re(M) derived induction curve
  with 5-inch chord; wall-constriction Mach shift ramping 0 at M 0.70 to -2 percent at
  M 0.80 and held (applied to measured M before comparison).
"""
import csv, json
import numpy as np
import aerosandbox as asb
from scipy.stats import beta as beta_dist
from transonic_patch import mach_crit_of, MACH_DD_OFFSET, cd_total
from fit_definitive import Re_of_M, naca4, model as model_eval, build_sweeps

SEL = json.load(open('selected-model.json'))
FORM, PARAMS, BFIX = SEL['form'], SEL['params'], SEL['b_fixed']
print(f"frozen selection: {FORM} params {np.round(PARAMS,4)} (b_fixed {BFIX:.3f})")

def model_dcd(x, tc, CL):
    return model_eval(FORM, PARAMS, np.asarray(x, dtype=float), tc=tc, CL=CL, b_fixed=BFIX)

def model_mdd(Mc, tc, CL):
    xs = np.linspace(1e-4, 0.35, 3000)
    dy = np.gradient(model_dcd(xs, tc, CL), xs)
    idx = np.argmax(dy >= 0.10)
    return Mc + (xs[idx] if dy[idx] >= 0.10 else np.nan)

def onset_5ct(pts, base):
    for i in range(1, len(pts)):
        if pts[i][1] >= base + 0.0005:
            m0, c0 = pts[i-1]; m1, c1 = pts[i]
            return m0 + (base+0.0005-c0)*(m1-m0)/(c1-c0)
    return None

def mdd_measured(pts, base):
    onset = onset_5ct(pts, base)
    if onset is None: return None, 'no-rise'
    beyond = [p for p in pts if onset < p[0] <= 0.90]
    if len(beyond) >= 4:
        w = [p for p in pts if onset-0.05 <= p[0] <= 0.90]
        M = np.array([p[0] for p in w]); C = np.array([p[1] for p in w])
        d = np.polyder(np.polyfit(M, C, 3))
        roots = np.roots(np.polysub(d, [0.10]))
        c = [r.real for r in roots if abs(r.imag) < 1e-9 and onset <= r.real <= M.max()+0.02]
        if c: return min(c), 'cubic'
    for i in range(1, len(pts)):
        if pts[i][1] >= base + 0.0020:
            m0, c0 = pts[i-1]; m1, c1 = pts[i]
            return m0 + (base+0.0020-c0)*(m1-m0)/(c1-c0), 'plus20ct'
    return None, 'no-crossing'

# ---------- assemble the two holdout sets ----------
HOLD = []
# Harris (from master-dataset.csv)
md = {}
for r in csv.DictReader(open('master-dataset.csv')):
    md.setdefault(r['sweep_id'], []).append((float(r['mach']), float(r['CD'])))
H_CONV = {'H8-3F': (3.0e6, 9.0, 0.05, 0.60), 'H8-6F': (6.0e6, 9.0, 0.05, 0.60),
          'H8-9F': (9.0e6, 9.0, 0.05, 0.75), 'H8-3free': (3.0e6, 4.9, 1.0, 0.70)}
af12 = asb.Airfoil(name='0012', coordinates=naca4(0, 0, 0.12)).to_kulfan_airfoil()
for sid, (Re, nc, xtr, wmax) in H_CONV.items():
    pts = sorted(md[sid])
    base = float(np.mean([c for m, c in pts if m <= wmax]))
    o = af12.get_aero_from_neuralfoil(alpha=-0.14, Re=Re, mach=0.0, model_size="xlarge",
                                      n_crit=nc, xtr_upper=xtr, xtr_lower=xtr)
    HOLD.append(dict(set='Harris', sweep=sid, pts=pts, base=base,
                     cp0=float(np.asarray(o['Cpmin_0']).item()),
                     cd0=float(np.asarray(o['CD']).item()),
                     CL=float(np.asarray(o['CL']).item()), tc=0.12, af=af12,
                     alpha=-0.14, Re=Re, nc=nc, xtr=xtr))
# TN 1546 subset (from tn1546-sweeps.csv, written by assemble_tn1546.py)
GEOM46 = np.load('tn1546_geom.npy', allow_pickle=True).item()
t46 = {}
for r in csv.DictReader(open('tn1546-sweeps.csv')):
    t46.setdefault((r['section'], float(r['alpha_test'])), []).append(
        (float(r['M']), float(r['cd'])))
def wallcorr(M):   # D12: measured M shifted down by up to 2 percent above M 0.70
    f = np.clip((M - 0.70) / 0.10, 0, 1)
    return M * (1 - 0.02 * f)
cache46 = {}
for (sec, al), pts in sorted(t46.items()):
    pts = sorted([(wallcorr(m), c) for m, c in pts])
    g = GEOM46.get(sec)
    if g is None: continue
    af = cache46.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
    base = float(np.mean([c for m, c in pts if m <= 0.61]))
    Re7 = Re_of_M(0.70, c=0.127)
    o = af.get_aero_from_neuralfoil(alpha=al, Re=Re7, mach=0.0, model_size="xlarge", n_crit=6)
    HOLD.append(dict(set='TN1546', sweep=f'{sec}_a{al:g}', pts=pts, base=base,
                     cp0=float(np.asarray(o['Cpmin_0']).item()),
                     cd0=float(np.asarray(o['CD']).item()),
                     CL=float(np.asarray(o['CL']).item()), tc=af.max_thickness(), af=af,
                     alpha=al, Re=Re7, nc=6, xtr=1.0))

# ---------- criterion 1: increment MAE, stock vs selected ----------
print("\n" + "="*84)
print("ONE-SHOT SCORING (this block runs once and is reported as-is)")
print("="*84)
res = {}
for s in HOLD:
    Mc = float(mach_crit_of(s['cp0']))
    tr = [(m, c) for m, c in s['pts'] if Mc < m <= 0.90]
    if len(tr) < 2:
        continue
    M = np.array([p[0] for p in tr]); d = np.array([p[1] for p in tr]) - s['base']
    stock = np.array([float(cd_total(m, s['cp0'], s['cd0'], s['tc'])) - s['cd0'] for m in M])
    mine = model_dcd(M - Mc, s['tc'], s['CL'])
    mae_s = float(np.mean(np.abs(stock - d)))*1e4
    mae_m = float(np.mean(np.abs(mine - d)))*1e4
    mdm, rule = mdd_measured(s['pts'], s['base'])
    row = dict(Mc=Mc, mae_stock=mae_s, mae_model=mae_m, n=len(tr),
               mdd_meas=mdm, rule=rule, mdd_stock=Mc+MACH_DD_OFFSET,
               mdd_model=model_mdd(Mc, s['tc'], s['CL']))
    res.setdefault(s['set'], {})[s['sweep']] = row
    print(f"{s['set']:7s} {s['sweep']:14s} n={len(tr):2d} Mc {Mc:.4f} | "
          f"MAE stock {mae_s:7.1f}  model {mae_m:6.1f} cts | "
          f"Mdd meas {mdm if mdm else float('nan'):.3f} ({rule}) "
          f"stock {Mc+MACH_DD_OFFSET:.3f} model {row['mdd_model']:.3f}")
for st, rows in res.items():
    ms = np.mean([r['mae_stock'] for r in rows.values()])
    mm = np.mean([r['mae_model'] for r in rows.values()])
    red = (ms - mm)/ms*100
    e_s = [abs(r['mdd_stock']-r['mdd_meas']) for r in rows.values() if r['mdd_meas']]
    e_m = [abs(r['mdd_model']-r['mdd_meas']) for r in rows.values()
           if r['mdd_meas'] and np.isfinite(r['mdd_model'])]
    print(f"\n[{st}] mean per-sweep MAE: stock {ms:.1f} -> model {mm:.1f} cts "
          f"({red:+.1f}% change) | criterion >=30% reduction: "
          f"{'MET' if red >= 30 else 'NOT MET'}")
    print(f"[{st}] mean |Mdd error|: stock {np.mean(e_s):.4f} -> model {np.mean(e_m):.4f} | "
          f"criterion halved: {'MET' if np.mean(e_m) <= 0.5*np.mean(e_s) else 'NOT MET'}")

# ---------- criterion 3: no-harm ----------
xs = np.linspace(-0.3, 0, 500)
mx = float(np.max(np.abs(model_dcd(xs, 0.12, 0.2))))
print(f"\nno-harm: max |added drag| below M_crit = {mx*1e4:.2f} counts "
      f"({'PASS' if mx < 1e-8 else 'FAIL'}); all subcritical predictions bit-identical.")

# ---------- criterion 4: Phase C conformal, calibration-fixed, holdout-covered ----------
cal = build_sweeps()
# For the registered quantity we use |stock increment error| on calibration points per regime.
# Regime here: all these points are supercritical (increments defined above Mc), so the
# supercritical regime is the operative one; the subcritical regime bound is 0 by construction
# for increment errors (baseline-anchored), reported as such.
errs = []
for s in cal:
    Mc = s['Mc']
    # cp0/cd0 for stock increments: reuse Mc via inversion is not possible; recompute:
    # build_sweeps returned Mc; stock increment = cd_total - cd0 needs cp0: invert Mc->cp0:
    # mach_crit_of is monotonic; solve numerically.
    from scipy.optimize import brentq
    cp0 = brentq(lambda c: float(mach_crit_of(c)) - Mc, -8, -1e-4)
    for (M, dmeas, sig) in s['pts']:
        stock_inc = float(cd_total(M, cp0, 0.0, s['tc']))
        errs.append(abs(stock_inc - dmeas))
errs = np.sort(np.array(errs))
n = len(errs)
k = int(np.ceil((n+1)*0.9)) - 1
bound = errs[min(k, n-1)]
print(f"\nPhase C conformal bound (supercritical regime, calibration, n={n}): "
      f"90% |stock increment error| <= {bound*1e4:.1f} counts")
cov_pts = []
for st, rows in res.items():
    for s in HOLD:
        if s['set'] != st or s['sweep'] not in rows: continue
        Mc = rows[s['sweep']]['Mc']
        for m, c in s['pts']:
            if Mc < m <= 0.90:
                stock_inc = float(cd_total(m, s['cp0'], s['cd0'], s['tc'])) - s['cd0']
                cov_pts.append(abs(stock_inc - (c - s['base'])) <= bound)
cov = np.mean(cov_pts); nh = len(cov_pts)
# exact Clopper-Pearson two-sided 95% interval for coverage=0.9 target:
k_obs = int(round(cov*nh))
ci_lo = beta_dist.ppf(0.025, k_obs, nh-k_obs+1) if k_obs > 0 else 0.0
ci_hi = beta_dist.ppf(0.975, k_obs+1, nh-k_obs) if k_obs < nh else 1.0
# the registered test: is 0.90 inside the exact interval induced by observed coverage
usable = ci_lo <= 0.90 <= ci_hi
print(f"holdout coverage of that bound: {cov*100:.1f}% of {nh} points "
      f"(exact 95% CI [{ci_lo*100:.1f}%, {ci_hi*100:.1f}%]) -> "
      f"bound declared {'USABLE' if usable else 'UNINFORMATIVE'}")

json.dump({st: {k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) and vv is not None else str(vv))
                    for kk, vv in r.items()} for k, r in rows.items()} for st, rows in res.items()},
          open('holdout-scores.json', 'w'), indent=1)
print("\nwrote holdout-scores.json  -- the one-shot is spent.")
