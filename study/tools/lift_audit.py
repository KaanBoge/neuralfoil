"""THE UNAUDITED LAYER: lift versus Mach through the full shipped compressibility
pipeline (CL/beta softmax correction + buffet factor + supersonic CLa ratio),
scored against 120 digitized measured lift points that the study collected but
never used for this purpose: Ferri 2309 CL(M) at four angles, and the TN 1546
subset cl(M) at two angles per airfoil.

Everything here is audit, not fitting: no parameter is tuned.
"""
import csv
import numpy as np
import aerosandbox as asb
from fit_definitive import Re_of_M, naca4

def rows(path):
    return list(csv.DictReader([l for l in open(path) if not l.startswith('#')]))

print("=" * 78)
print("LIFT-COMPRESSIBILITY AUDIT (shipped pipeline CL vs measured, all data on hand)")
print("=" * 78)

# ---- Ferri 2309: alpha -1, 0, 1, 2 at M 0.30..0.94, Re 3.8e5, nc 6 ----
af29 = asb.Airfoil(name='2309', coordinates=naca4(0.02, 0.3, 0.09)).to_kulfan_airfoil()
FER = {}
for r in rows('ferri-cl.csv'):
    FER.setdefault(float(r['alpha']), []).append((float(r['M']), float(r['CL']), float(r['u_CL'])))
print("\nFerri 2309 (Guidonia, Re 3.8e5, free transition, n_crit 6):")
print(f"{'alpha':>6s} {'band':>12s} {'meas dCL/CL(M.4->M.78)':>23s} {'pred':>6s} | subcritical MAE | break-region MAE (M>=0.85)")
allsub, allbrk = [], []
for al in sorted(FER):
    pts = sorted(FER[al])
    sub = [(m, c, u) for m, c, u in pts if m <= 0.80]
    brk = [(m, c, u) for m, c, u in pts if m >= 0.85]
    pm = np.array([p[0] for p in pts])
    o = af29.get_aero_from_neuralfoil(alpha=al, Re=3.8e5, mach=pm, model_size="xlarge", n_crit=6)
    clp = np.atleast_1d(o['CL'])
    pred = dict(zip(pm, clp))
    esub = [abs(pred[m] - c) for m, c, u in sub]
    ebrk = [abs(pred[m] - c) for m, c, u in brk]
    allsub += esub; allbrk += ebrk
    m4 = [c for m, c, u in pts if abs(m - 0.40) < 0.01][0]
    m78 = [c for m, c, u in pts if abs(m - 0.78) < 0.01][0]
    g_meas = (m78 - m4) / max(abs(m4), 0.05)
    p4, p78 = pred[[m for m in pm if abs(m-0.40)<0.01][0]], pred[[m for m in pm if abs(m-0.78)<0.01][0]]
    g_pred = (p78 - p4) / max(abs(p4), 0.05)
    print(f"{al:+6.0f} {'M .30-.94':>12s} {g_meas:+22.2%} {g_pred:+6.0%} | "
          f"{np.mean(esub):14.3f} | {np.mean(ebrk) if ebrk else float('nan'):.3f}")
print(f"\nFerri overall: subcritical CL MAE {np.mean(allsub):.3f} "
      f"(digitization u_CL ~0.010-0.015), lift-break region MAE {np.mean(allbrk):.3f}")

# ---- TN 1546 subset: cl(M) at alpha -0.23 and 1.77, Re(M) curve, nc 6 ----
GEOM46 = np.load('tn1546_geom.npy', allow_pickle=True).item()
T46 = {}
for r in rows('tn1546-cl.csv'):
    T46.setdefault((r['section'], float(r['alpha_test'])), []).append(
        (float(r['M']), float(r['cl']), float(r['u_cl'])))
print("\nTN 1546 subset (Langley 24-in HST, Re(M) 0.85-2e6, free transition, n_crit 6):")
print(f"{'sweep':>16s} {'n':>3s} {'CL MAE':>8s} {'mean signed (pred-meas)':>24s}")
errs_all, signed_all = [], []
cache = {}
for (sec, al), pts in sorted(T46.items()):
    g = GEOM46.get(sec)
    if g is None: continue
    af = cache.setdefault(sec, asb.Airfoil(name=sec, coordinates=g).to_kulfan_airfoil())
    es, ss = [], []
    for m, c, u in sorted(pts):
        o = af.get_aero_from_neuralfoil(alpha=al, Re=Re_of_M(m, c=0.127), mach=m,
                                        model_size="xlarge", n_crit=6)
        p = float(np.asarray(o['CL']).item())
        es.append(abs(p - c)); ss.append(p - c)
    errs_all += es; signed_all += ss
    print(f"{sec+'_a'+format(al,'g'):>16s} {len(pts):3d} {np.mean(es):8.3f} {np.mean(ss):+24.3f}")
print(f"\nTN1546 overall: CL MAE {np.mean(errs_all):.3f}, mean signed {np.mean(signed_all):+.3f} "
      f"(digitization u_cl 0.01-0.02; wall corrections NOT applied to cl)")
print()
print("Reading guide: subcritical lift error at or below digitization noise = the")
print("Prandtl-Glauert-type correction is adequate there. Break-region error shows how")
print("the RANS-tuned buffet factor performs against 1940s measured lift breaks.")
