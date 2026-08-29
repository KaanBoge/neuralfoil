"""Convert the TN 1546 holdout extraction journal into tn1546-sweeps.csv.

Declared data-quality rule, fixed BEFORE any scoring: points whose reader-assigned
u_cd exceeds 0.0015 (the 'bounded estimate, not a clean read' class the agents
flagged where traces merge into the drag-rise blob) are excluded from the scored
set and listed here for the record. Everything else is kept verbatim.
"""
import json, csv

U_MAX = 0.0015
rows, dropped, cl_rows = [], [], []
seen = set()
for line in open('tn1546-journal.jsonl'):
    if '"result"' not in line:
        continue
    d = json.loads(line)
    r = d.get('result', {})
    if 'curves' not in r or 'airfoil' not in r:
        continue
    sec = r['airfoil'].replace('NACA', '').strip().split()[0]
    if (sec, r.get('page')) in seen:
        continue
    seen.add((sec, r.get('page')))
    if not r.get('caption_verified', False):
        print(f"CAPTION NOT VERIFIED for {sec} page {r.get('page')}: EXCLUDED WHOLESALE")
        continue
    for c in r['curves']:
        for p in c.get('cd_points', []):
            rec = (sec, r['page'], c['alpha'], p['M'], p['cd'], p.get('u_cd', 0.001),
                   p.get('note', ''))
            if p.get('u_cd', 0.001) > U_MAX:
                dropped.append(rec)
            else:
                rows.append(rec)
        for p in c.get('cl_points', []):
            cl_rows.append((sec, c['alpha'], p['M'], p['cl'], p.get('u_cl', 0.015)))

with open('tn1546-sweeps.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['section', 'page', 'alpha_test', 'M', 'cd', 'u_cd', 'note'])
    for r_ in sorted(rows):
        w.writerow(r_)
with open('tn1546-cl.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['section', 'alpha_test', 'M', 'cl', 'u_cl'])
    for r_ in sorted(cl_rows):
        w.writerow(r_)

print(f"tn1546-sweeps.csv: {len(rows)} cd points kept, "
      f"{len(set((r_[0], r_[2]) for r_ in rows))} sweeps, "
      f"sections: {sorted(set(r_[0] for r_ in rows))}")
print(f"tn1546-cl.csv: {len(cl_rows)} lift points")
if dropped:
    print(f"dropped by the declared u_cd > {U_MAX} rule ({len(dropped)}):")
    for r_ in dropped:
        print(f"  {r_[0]} a{r_[2]} M{r_[3]}: cd {r_[4]} u {r_[5]}  ({r_[6][:60]})")
