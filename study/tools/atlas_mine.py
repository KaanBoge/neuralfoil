"""Mine the internal-consistency atlas.

The eight model sizes are surrogates of the same teacher at different capacities.
Where they disagree, at least seven are wrong: CD_range8 (max minus min across
sizes) is a fabrication-free LOWER BOUND on worst-case surrogate error at that
condition. Questions answered here:

1. WHERE does NeuralFoil fail internally? (spread vs Re, alpha, thickness, camber)
2. Does the confidence score KNOW? (confidence vs spread: the audit of contribution 2,
   computable at a scale no experiment allows)
3. How large is the failure region relative to the design space?
"""
import os, csv, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'atlas-out')
UIUC = os.path.join(HERE, '..', 'uiuc-airfoils.json')

with open(UIUC) as f:
    meta = {a['f']: (a.get('t', np.nan), a.get('c', np.nan)) for a in json.load(f)}

rows = []
for fn in os.listdir(OUT):
    if not fn.endswith('.csv'):
        continue
    name = fn[:-4]
    t, c = meta.get(name, (np.nan, np.nan))
    with open(os.path.join(OUT, fn)) as f:
        for r in csv.DictReader(f):
            rows.append((name, t, c, float(r['Re']), float(r['alpha']),
                         float(r['CD_xl']), float(r['conf_xl']),
                         float(r['CD_std8']), float(r['CD_range8']),
                         float(r['CL_std8'])))

N = len(rows)
name_a = np.array([r[0] for r in rows])
t_a = np.array([r[1] for r in rows]); c_a = np.array([r[2] for r in rows])
re_a = np.array([r[3] for r in rows]); al_a = np.array([r[4] for r in rows])
cd_a = np.array([r[5] for r in rows]); cf_a = np.array([r[6] for r in rows])
cdr_a = np.array([r[8] for r in rows]); cls_a = np.array([r[9] for r in rows])
cdr_cts = cdr_a * 1e4  # counts

print(f"atlas rows: {N:,}  ({len(set(name_a))} airfoils)")
print()
print("=" * 78)
print("1. WHERE THE EIGHT SURROGATES DISAGREE (CD spread across sizes, drag counts)")
print("=" * 78)
print(f"{'Re':>8s} {'median':>8s} {'p90':>8s} {'p99':>9s} {'share>20cts':>12s} {'share>100cts':>13s}")
for Re in sorted(set(re_a)):
    m = re_a == Re
    print(f"{Re:8.0e} {np.median(cdr_cts[m]):8.1f} {np.percentile(cdr_cts[m],90):8.1f} "
          f"{np.percentile(cdr_cts[m],99):9.1f} {np.mean(cdr_cts[m]>20)*100:11.1f}% "
          f"{np.mean(cdr_cts[m]>100)*100:12.1f}%")
print()
print(f"{'alpha':>6s} {'median':>8s} {'p90':>8s} {'share>20cts':>12s}   (pooled over Re 2e5-5e6, the training-typical band)")
mtr = (re_a >= 2e5) & (re_a <= 5e6)
for al in sorted(set(al_a)):
    m = mtr & (al_a == al)
    print(f"{al:6.0f} {np.median(cdr_cts[m]):8.1f} {np.percentile(cdr_cts[m],90):8.1f} {np.mean(cdr_cts[m]>20)*100:11.1f}%")
print()
print("thickness bands (Re training band, alpha -4..8):")
mal = mtr & (al_a >= -4) & (al_a <= 8) & np.isfinite(t_a)
for lo, hi in [(0, 6), (6, 9), (9, 12), (12, 15), (15, 20), (20, 60)]:
    m = mal & (t_a >= lo) & (t_a < hi)
    if m.sum() == 0: continue
    print(f"  t/c {lo:2d}-{hi:2d}%: median {np.median(cdr_cts[m]):6.1f} p90 {np.percentile(cdr_cts[m],90):7.1f} "
          f"share>20cts {np.mean(cdr_cts[m]>20)*100:5.1f}%   n={m.sum():,}")
print()
print("=" * 78)
print("2. DOES THE CONFIDENCE SCORE KNOW? (spread vs confidence, all conditions)")
print("=" * 78)
print(f"{'confidence bin':>16s} {'n':>9s} {'median spread':>14s} {'p90 spread':>11s} {'share>20cts':>12s}")
edges = [0, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 1.01]
for i in range(len(edges)-1):
    m = (cf_a >= edges[i]) & (cf_a < edges[i+1])
    if m.sum() == 0: continue
    print(f"  [{edges[i]:.2f},{edges[i+1]:.2f}) {m.sum():9,} {np.median(cdr_cts[m]):13.1f} "
          f"{np.percentile(cdr_cts[m],90):11.1f} {np.mean(cdr_cts[m]>20)*100:11.1f}%")
r = np.corrcoef(cf_a, np.log10(np.maximum(cdr_cts, 0.1)))[0, 1]
print(f"\ncorrelation(confidence, log10 CD spread): {r:+.3f}")
print()
print("THE FAILURE CASE THAT MATTERS: high confidence AND high spread")
hh = (cf_a > 0.9) & (cdr_cts > 50)
print(f"conditions with confidence > 0.90 yet spread > 50 counts: {hh.sum():,} of {N:,} ({hh.mean()*100:.2f}%)")
if hh.sum():
    idx = np.argsort(-cdr_cts * hh)[:8]
    print("worst offenders:")
    for i in idx[:8]:
        if not hh[i]: break
        print(f"  {name_a[i]:12s} t/c {t_a[i]:4.1f}% Re {re_a[i]:.0e} alpha {al_a[i]:+3.0f}: "
              f"conf {cf_a[i]:.3f}, spread {cdr_cts[i]:.0f} counts, CD_xl {cd_a[i]:.4f}")
print()
print("=" * 78)
print("3. THE SIZE OF THE UNRELIABLE REGION")
print("=" * 78)
band = mtr & (al_a >= -4) & (al_a <= 10)
print(f"Within the practical envelope (Re 2e5-5e6, alpha -4..10): {band.sum():,} conditions")
print(f"  spread <= 5 counts (agreement zone): {np.mean(cdr_cts[band]<=5)*100:5.1f}%")
print(f"  spread 5-20 counts: {np.mean((cdr_cts[band]>5)&(cdr_cts[band]<=20))*100:5.1f}%")
print(f"  spread > 20 counts (unreliable): {np.mean(cdr_cts[band]>20)*100:5.1f}%")
out = ~band
print(f"Outside it: {out.sum():,} conditions, unreliable share {np.mean(cdr_cts[out]>20)*100:.1f}%")

# persist a compact summary table for the paper
with open('atlas-summary.csv', 'w') as f:
    f.write("slice,value,median_spread_counts,p90_spread_counts,share_gt20cts_pct,n\n")
    for Re in sorted(set(re_a)):
        m = re_a == Re
        f.write(f"Re,{Re:.0e},{np.median(cdr_cts[m]):.2f},{np.percentile(cdr_cts[m],90):.2f},"
                f"{np.mean(cdr_cts[m]>20)*100:.2f},{m.sum()}\n")
    for al in sorted(set(al_a)):
        m = mtr & (al_a == al)
        f.write(f"alpha,{al:.0f},{np.median(cdr_cts[m]):.2f},{np.percentile(cdr_cts[m],90):.2f},"
                f"{np.mean(cdr_cts[m]>20)*100:.2f},{m.sum()}\n")
    for i in range(len(edges)-1):
        m = (cf_a >= edges[i]) & (cf_a < edges[i+1])
        if m.sum() == 0: continue
        f.write(f"conf,[{edges[i]:.2f}-{edges[i+1]:.2f}),{np.median(cdr_cts[m]):.2f},"
                f"{np.percentile(cdr_cts[m],90):.2f},{np.mean(cdr_cts[m]>20)*100:.2f},{m.sum()}\n")
print("\nwrote atlas-summary.csv")
