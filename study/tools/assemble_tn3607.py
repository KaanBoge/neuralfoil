"""Convert the TN 3607 extraction journal into tn3607-sweeps.csv (raw layer)."""
import json, csv

rows = []
fig17 = []
for line in open('tn3607-journal.jsonl'):
    if '"result"' not in line:
        continue
    d = json.loads(line)
    r = d.get('result', {})
    if 'curves' in r and 'airfoil' in r:
        sec = r['airfoil'].split()[1] if r['airfoil'].startswith('NACA') else r['airfoil']
        sec = sec.split()[0]
        for c in r['curves']:
            for p in c['points']:
                rows.append((sec, r['page'], c['alpha'], p['M'], p['cd'],
                             p.get('u_cd', 0.0005), p.get('note', '')))
    elif 'panels' in r:
        for pan in r['panels']:
            for cv in pan['curves']:
                for p in cv['points']:
                    fig17.append((cv['airfoil'], pan['panel'][:40], p['cn'], p['M_dr'],
                                  p.get('u_M', 0.005)))

with open('tn3607-sweeps.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['section', 'page', 'alpha_test', 'M', 'cd', 'u_cd', 'note'])
    for r in sorted(rows):
        w.writerow(r)
print(f"tn3607-sweeps.csv: {len(rows)} points, "
      f"{len(set((r[0], r[2]) for r in rows))} sweeps, sections: {sorted(set(r[0] for r in rows))}")

if fig17:
    with open('tn3607-fig17.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['airfoil', 'panel', 'cn', 'M_dr', 'u_M'])
        for r in fig17:
            w.writerow(r)
    print(f"tn3607-fig17.csv: {len(fig17)} drag-rise summary points")
else:
    print("Fig 17 not yet in journal")
