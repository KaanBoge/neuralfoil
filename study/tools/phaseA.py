"""Phase A battery, blocks (b) onset and (c) magnitude, on the sweeps extracted so far.

Per frozen Methods Step 5 / amendment A2:
  M_dd primary rule: cubic fit in M over [onset-0.05, last point <= 0.90], M_dd where dCD/dM = 0.10.
  Backup (fewer than 4 points beyond onset): plateau + 20 counts crossing.
  The rule used is recorded per sweep.
Baselines: flat A1 mean over the sweep's subcritical window. Valid here because BOTH facilities
hold Reynolds constant along a sweep (Harris: constant per series; Guidonia: constant by design).
The Reynolds-varying baseline problem (A13) applies to TN 3607 only and is handled separately.

Facility conventions applied (from the convention tables):
  Harris 8-ft TPT: fixed series xtr = 0.05 both surfaces; free series n_crit = 4.9.
  Guidonia: free transition, n_crit 6 nominal (sensitivity 4-9 noted; drag near-insensitive).
"""
import csv, numpy as np, aerosandbox as asb
from transonic_patch import mach_crit_of, MACH_DD_OFFSET, cd_total


def naca4(m, p, t, n=80):
    x = 0.5 * (1 + np.cos(np.pi * np.arange(n + 1) / n))
    yt = t/0.2*(0.2969*np.sqrt(x)-0.1260*x-0.3516*x**2+0.2843*x**3-0.1036*x**4)
    if p > 0:
        yc = np.where(x < p, m/p**2*(2*p*x-x**2), m/(1-p)**2*((1-2*p)+2*p*x-x**2))
        dy = np.where(x < p, 2*m/p**2*(p-x), 2*m/(1-p)**2*(p-x))
    else:
        yc = np.zeros_like(x); dy = np.zeros_like(x)
    th = np.arctan(dy)
    up = np.column_stack([x-yt*np.sin(th), yc+yt*np.cos(th)])
    lo = np.column_stack([x+yt*np.sin(th), yc-yt*np.cos(th)])[::-1]
    return np.vstack([up, lo[1:]])


AF = {
    '0012': asb.Airfoil(name="0012", coordinates=naca4(0, 0, 0.12)).to_kulfan_airfoil(),
    '2309': asb.Airfoil(name="2309", coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil(),
}

SWEEPS = {  # sweep_id: (airfoil, alpha, Re, ncrit, xtr, baseline_window_maxM)
    'H8-3F':    ('0012', -0.14, 3.0e6, 9.0, 0.05, 0.60),
    'H8-6F':    ('0012', -0.14, 6.0e6, 9.0, 0.05, 0.60),
    'H8-9F':    ('0012', -0.14, 9.0e6, 9.0, 0.05, 0.75),
    'H8-3free': ('0012', -0.14, 3.0e6, 4.9, 1.0, 0.70),
    'F33-a0':   ('2309', 0.0, 3.8e5, 6.0, 1.0, 0.60),
    'F33-a1':   ('2309', 1.0, 3.8e5, 6.0, 1.0, 0.60),
    'F33-a2':   ('2309', 2.0, 3.8e5, 6.0, 1.0, 0.60),
}


def load_master():
    rows = [l for l in open('master-dataset.csv')]
    data = {}
    for r in csv.DictReader(rows):
        data.setdefault(r['sweep_id'], []).append((float(r['mach']), float(r['CD'])))
    return {k: sorted(v) for k, v in data.items()}


def onset_5ct(pts, base):
    for i in range(1, len(pts)):
        if pts[i][1] >= base + 0.0005:
            m0, c0 = pts[i-1]; m1, c1 = pts[i]
            return m0 + (base + 0.0005 - c0) * (m1 - m0) / (c1 - c0)
    return None


def mdd_measured(pts, base):
    """A2: cubic fit + dCD/dM = 0.10 crossing; +20ct backup. Returns (M_dd, rule)."""
    onset = onset_5ct(pts, base)
    if onset is None:
        return None, 'no-rise'
    beyond = [p for p in pts if p[0] > onset and p[0] <= 0.90]
    if len(beyond) >= 4:
        w = [p for p in pts if p[0] >= onset - 0.05 and p[0] <= 0.90]
        M = np.array([p[0] for p in w]); C = np.array([p[1] for p in w])
        co = np.polyfit(M, C, 3)
        d = np.polyder(co)
        roots = np.roots(np.polysub(d, [0.10]))
        cands = [r.real for r in roots if abs(r.imag) < 1e-9 and M.min() <= r.real <= M.max() + 0.02]
        cands = [c for c in cands if c >= onset]  # A2b sanity: M_dd cannot precede onset
        if cands:
            return min(cands), 'cubic'
        # cubic produced no valid root at or beyond onset: declared fallback
    for i in range(1, len(pts)):
        if pts[i][1] >= base + 0.0020:
            m0, c0 = pts[i-1]; m1, c1 = pts[i]
            return m0 + (base + 0.0020 - c0) * (m1 - m0) / (c1 - c0), 'plus20ct'
    return None, 'no-crossing'


def main():
    data = load_master()
    print(f"{'sweep':10s} {'base':>8s} {'onset5':>7s} {'Mdd_meas':>8s} {'rule':>9s} "
          f"{'Mc_pred':>8s} {'Mdd_pred':>8s} {'dMdd':>7s}  magnitude ratio at (M-Mc)=0.05/0.10/0.15")
    out_rows = []
    for sid, (afn, alpha, Re, nc, xtr, wmax) in SWEEPS.items():
        pts = data[sid]
        base = float(np.mean([c for m, c in pts if m <= wmax]))
        mdd_m, rule = mdd_measured(pts, base)
        af = AF[afn]
        o0 = af.get_aero_from_neuralfoil(alpha=alpha, Re=Re, mach=0.0, model_size="xlarge",
                                         n_crit=nc, xtr_upper=xtr, xtr_lower=xtr)
        cp0 = float(np.asarray(o0['Cpmin_0']).item())
        cd0 = float(np.asarray(o0['CD']).item())
        mc = float(mach_crit_of(cp0))
        mdd_p = mc + MACH_DD_OFFSET
        toc = af.max_thickness()
        # magnitude ratio: predicted wave increment / measured increment at matched (M - Mc)
        ratios = []
        for dm in (0.05, 0.10, 0.15):
            M = mc + dm
            meas = np.interp(M, [p[0] for p in pts], [p[1] for p in pts]) - base
            pred = float(cd_total(M, cp0, cd0, toc)) - cd0
            ratios.append(pred / meas if meas > 1e-5 and M <= max(p[0] for p in pts) else np.nan)
        dmdd = (mdd_p - mdd_m) if mdd_m else np.nan
        print(f"{sid:10s} {base:8.5f} "
              f"{(onset_5ct(pts, base) or np.nan):7.3f} {(mdd_m or np.nan):8.3f} {rule:>9s} "
              f"{mc:8.4f} {mdd_p:8.4f} {dmdd:+7.3f}  "
              + " / ".join(f"{r:5.2f}" if np.isfinite(r) else "  n/a" for r in ratios))
        out_rows.append((sid, base, onset_5ct(pts, base), mdd_m, rule, mc, mdd_p, dmdd, *ratios))
    with open('phaseA-battery.csv', 'w') as f:
        f.write("sweep_id,baseline,onset_5ct,Mdd_measured,mdd_rule,Mcrit_pred,Mdd_pred,"
                "Mdd_pred_minus_meas,ratio_dm05,ratio_dm10,ratio_dm15\n")
        for r in out_rows:
            f.write(",".join("" if v is None or (isinstance(v, float) and not np.isfinite(v))
                             else (f"{v:.5g}" if isinstance(v, float) else str(v)) for v in r) + "\n")
    print("\nwrote phaseA-battery.csv")
    print("\nReading guide: dMdd = predicted minus measured drag-divergence Mach.")
    print("Magnitude ratio > 1 means the stock pipeline overpredicts the wave-drag increment")
    print("at that distance past the critical Mach number; < 1 means underprediction.")


if __name__ == '__main__':
    main()
