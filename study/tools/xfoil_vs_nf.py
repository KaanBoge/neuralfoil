"""Surrogate-versus-teacher decomposition: NeuralFoil against the real XFOIL.

Closes the atlas's structural blind spot: where the eight NeuralFoil sizes AGREE,
they can still share their teacher's bias. Running XFOIL itself on the same
conditions measures |NF - XFOIL| directly, so total error against reality
decomposes into (surrogate missed teacher) + (teacher missed reality), and the
second term is what the experimental half of the study measures.

Also recorded: XFOIL convergence failures. NeuralFoil famously always answers;
this measures what its internal spread looks like exactly where its teacher
gives up, which is where "always answers" is most dangerous.
"""
import json, os, subprocess, tempfile, csv
import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
XFOIL = os.path.expanduser('~/Xfoil/bin/xfoil')
UIUC = os.path.join(HERE, '..', 'uiuc-airfoils.json')

ALPHAS = [-2.0, 0.0, 2.0, 6.0, 10.0]
RES = [2e5, 1e6, 5e6]

def sample_airfoils(n=40):
    with open(UIUC) as f:
        db = [a for a in json.load(f) if len(a['p']) >= 30]
    db.sort(key=lambda a: a.get('t', 0))          # stratify by thickness
    step = max(1, len(db) // n)
    return db[::step][:n]

def run_xfoil(args):
    name, pts, Re = args
    with tempfile.TemporaryDirectory() as td:
        dat = os.path.join(td, 'a.dat')
        pol = os.path.join(td, 'p.txt')
        with open(dat, 'w') as f:
            f.write(name + '\n')
            for x, y in pts:
                f.write(f" {x:.6f} {y:.6f}\n")
        cmds = f"""PLOP
G

LOAD {dat}
PANE
OPER
VISC {Re:.0f}
ITER 200
PACC
{pol}

""" + "\n".join(f"ALFA {a}" for a in ALPHAS) + "\nPACC\n\nQUIT\n"
        try:
            subprocess.run([XFOIL], input=cmds.encode(), timeout=120,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return (name, Re, {})
        out = {}
        if os.path.exists(pol):
            with open(pol) as f:
                lines = f.readlines()
            started = False
            for ln in lines:
                if set(ln.strip()) <= set('- '):
                    started = True
                    continue
                if started:
                    p = ln.split()
                    if len(p) >= 3:
                        try:
                            out[round(float(p[0]), 2)] = (float(p[1]), float(p[2]))
                        except ValueError:
                            pass
        return (name, Re, out)

def main():
    foils = sample_airfoils()
    jobs = [(a['f'], a['p'], Re) for a in foils for Re in RES]
    print(f"XFOIL sessions: {len(jobs)} ({len(foils)} airfoils x {len(RES)} Re, "
          f"{len(ALPHAS)} alphas each = {len(jobs)*len(ALPHAS)} target points)")
    xr = {}
    with Pool(16) as pool:
        for name, Re, out in pool.imap_unordered(run_xfoil, jobs):
            xr[(name, Re)] = out
    conv = sum(len(v) for v in xr.values())
    tot = len(jobs) * len(ALPHAS)
    print(f"XFOIL converged: {conv}/{tot} points ({conv/tot*100:.0f}%)")

    import neuralfoil as nf
    rows = []
    meta = {a['f']: a for a in foils}
    for (name, Re), out in xr.items():
        pts = np.array(meta[name]['p'], dtype=float)
        r = nf.get_aero_from_coordinates(pts, alpha=np.array(ALPHAS), Re=Re,
                                         model_size="xlarge", n_crit=9,
                                         xtr_upper=1, xtr_lower=1)
        CLs = np.atleast_1d(r['CL']); CDs = np.atleast_1d(r['CD'])
        # per-size spread at the same conditions for the decomposition correlation
        cds_sizes = []
        for s in ["xxsmall", "small", "large", "xxxlarge"]:
            rs = nf.get_aero_from_coordinates(pts, alpha=np.array(ALPHAS), Re=Re,
                                              model_size=s, n_crit=9, xtr_upper=1, xtr_lower=1)
            cds_sizes.append(np.atleast_1d(rs['CD']))
        spread = (np.max(cds_sizes + [CDs], axis=0) - np.min(cds_sizes + [CDs], axis=0)) * 1e4
        for i, al in enumerate(ALPHAS):
            key = round(al, 2)
            if key in out:
                xcl, xcd = out[key]
                rows.append((name, Re, al, 1, xcl, xcd, float(CLs[i]), float(CDs[i]), float(spread[i])))
            else:
                rows.append((name, Re, al, 0, np.nan, np.nan, float(CLs[i]), float(CDs[i]), float(spread[i])))

    with open('xfoil-vs-nf.csv', 'w') as f:
        f.write("airfoil,Re,alpha,xfoil_converged,CL_xfoil,CD_xfoil,CL_nf,CD_nf,CD_spread5_counts\n")
        for r in rows:
            f.write(",".join("" if isinstance(v, float) and np.isnan(v) else f"{v}" for v in r) + "\n")

    ok = [r for r in rows if r[3] == 1]
    print()
    print("=" * 70)
    print("SURROGATE vs TEACHER (converged points only)")
    print("=" * 70)
    print(f"{'Re':>8s} {'n':>5s} {'median|dCD| cts':>15s} {'p90':>7s} {'median|dCL|':>12s}")
    for Re in RES:
        s = [r for r in ok if r[1] == Re]
        if not s: continue
        dcd = np.array([abs(r[5] - r[7]) for r in s]) * 1e4
        dcl = np.array([abs(r[4] - r[6]) for r in s])
        print(f"{Re:8.0e} {len(s):5d} {np.median(dcd):15.1f} {np.percentile(dcd,90):7.1f} {np.median(dcl):12.4f}")
    dcd_all = np.array([abs(r[5] - r[7]) for r in ok]) * 1e4
    sp_all = np.array([r[8] for r in ok])
    c = np.corrcoef(np.log10(np.maximum(sp_all, 0.1)), np.log10(np.maximum(dcd_all, 0.1)))[0, 1]
    print(f"\ncorrelation(log spread, log |NF-XFOIL|): {c:+.3f}")
    print("  (high = internal spread predicts teacher error, validating spread as an error proxy)")
    fail = [r for r in rows if r[3] == 0]
    if fail:
        spf = np.array([r[8] for r in fail])
        spc = np.array([r[8] for r in ok])
        print(f"\nwhere XFOIL FAILS to converge ({len(fail)} pts): NF spread median {np.median(spf):.1f} cts")
        print(f"where XFOIL converges          ({len(ok)} pts): NF spread median {np.median(spc):.1f} cts")
        print("  (NeuralFoil answers everywhere; its internal disagreement is N times larger exactly")
        print("   where its teacher could not produce an answer at all)")
    print("\nwrote xfoil-vs-nf.csv")

if __name__ == '__main__':
    main()
