"""NeuralFoil internal-consistency atlas.

Runs every UIUC airfoil through all eight NeuralFoil model sizes across an
alpha x Reynolds grid, recording per-condition CL/CD for each size plus the
xlarge confidence score. The eight sizes are surrogates of the same teacher
trained at different capacities: where they disagree, at least seven are wrong,
so ensemble spread is a fabrication-free LOWER BOUND on model error at that
condition. Crossing spread against the confidence score audits whether the
confidence knows where the model is failing (study contribution 2), across
1,655 airfoils, with no experimental data and therefore no digitization risk.

Deliberately restartable: work is chunked per airfoil, results appended as
one CSV row set per airfoil to atlas-out/<name>.csv; completed airfoils are
skipped on restart. Run under nohup so it survives session end.
"""
import json, os, sys, time
import numpy as np
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
UIUC = os.path.join(HERE, '..', 'uiuc-airfoils.json')
OUT = os.path.join(HERE, 'atlas-out')
os.makedirs(OUT, exist_ok=True)

SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
ALPHAS = np.arange(-10.0, 16.1, 1.0)
RES = [5e4, 2e5, 5e5, 1e6, 5e6, 2e7, 1e8]

def load_airfoils():
    with open(UIUC) as f:
        db = json.load(f)
    out = []
    for a in db:
        pts = np.array(a['p'], dtype=float)
        if len(pts) < 20:
            continue
        out.append((a['f'], pts))
    return out

def run_one(item):
    name, pts = item
    dest = os.path.join(OUT, name + '.csv')
    if os.path.exists(dest):
        return (name, 'skip')
    try:
        import neuralfoil as nf
        rows = []
        for Re in RES:
            per_size = {}
            for s in SIZES:
                r = nf.get_aero_from_coordinates(pts, alpha=ALPHAS, Re=Re,
                                                 model_size=s, n_crit=9,
                                                 xtr_upper=1, xtr_lower=1)
                per_size[s] = (np.atleast_1d(r['CL']), np.atleast_1d(r['CD']),
                               np.atleast_1d(r['analysis_confidence']))
            for i, al in enumerate(ALPHAS):
                cls = np.array([per_size[s][0][i] for s in SIZES])
                cds = np.array([per_size[s][1][i] for s in SIZES])
                conf = per_size['xlarge'][2][i]
                rows.append((Re, al,
                             per_size['xlarge'][0][i], per_size['xlarge'][1][i], conf,
                             cls.mean(), cls.std(), cds.mean(), cds.std(),
                             cds.max() - cds.min()))
        with open(dest, 'w') as f:
            f.write("Re,alpha,CL_xl,CD_xl,conf_xl,CL_mean8,CL_std8,CD_mean8,CD_std8,CD_range8\n")
            for r in rows:
                f.write(",".join(f"{v:.6g}" for v in r) + "\n")
        return (name, 'ok')
    except Exception as e:
        with open(os.path.join(OUT, name + '.err'), 'w') as f:
            f.write(repr(e))
        return (name, 'err')

if __name__ == '__main__':
    foils = load_airfoils()
    print(f"airfoils: {len(foils)}  grid per foil: {len(RES)} Re x {len(ALPHAS)} alpha x {len(SIZES)} sizes "
          f"= {len(RES)*len(ALPHAS)*len(SIZES)} evals -> total ~{len(foils)*len(RES)*len(ALPHAS)*len(SIZES):,}",
          flush=True)
    t0 = time.time()
    done = ok = err = skip = 0
    with Pool(processes=16) as pool:
        for name, st in pool.imap_unordered(run_one, foils, chunksize=4):
            done += 1
            if st == 'ok': ok += 1
            elif st == 'err': err += 1
            else: skip += 1
            if done % 50 == 0:
                el = time.time() - t0
                print(f"{done}/{len(foils)} ok={ok} err={err} skip={skip} "
                      f"elapsed={el/60:.1f}min eta={(el/max(1,done))*(len(foils)-done)/60:.1f}min", flush=True)
    print(f"DONE {done} airfoils, ok={ok} err={err} skip={skip}, {(time.time()-t0)/60:.1f} min", flush=True)
