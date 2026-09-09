"""Audit-only strict versus numerical-tolerance harm counters, all exposed rows."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
results=json.loads((ROOT/'exposed_results/results.json').read_text())
frames={name:pd.read_csv(ROOT/'exposed_results'/(name+'_predictions.csv'),float_precision='round_trip') for name in ['SG_exposed','W_new_challenge']}
rows=[]
for s in results['summaries']:
    f=frames[s['set']]
    if s['cohort']=='eligible':f=f[f.eligible]
    if s['subset']!='pooled':f=f[(f.airfoil==s['subset'])|(f.configuration==s['subset'])]
    e=(f[s['candidate']]-f.measured_CD).abs()*1e4;b=(f[s['baseline']]-f.measured_CD).abs()*1e4
    g=pd.DataFrame({'group':f.airfoil,'e':e,'b':b}).groupby('group')[['e','b']].mean()
    rows.append({**{k:s[k] for k in ['set','cohort','subset','candidate','baseline','rows','groups']},
        'strict_worse_rows':int((e>b).sum()),'tolerance_worse_rows':int((e>b+1e-8).sum()),
        'tolerance_equal_rows':int((np.abs(e-b)<=1e-8).sum()),
        'strict_worse_groups':int((g.e>g.b).sum()),'tolerance_worse_groups':int((g.e>g.b+1e-8).sum()),
        'tolerance_equal_groups':int((np.abs(g.e-g.b)<=1e-8).sum()),'tolerance_counts':1e-8})
pd.DataFrame(rows).to_csv(OUT/'exposed_tolerance_harm_counts.csv',index=False)
changed=[r for r in rows if r['strict_worse_rows']!=r['tolerance_worse_rows'] or r['strict_worse_groups']!=r['tolerance_worse_groups']]
summary={'records':len(rows),'records_with_changed_tie_classification':len(changed),
    'tolerance_counts':1e-8,'scope':'audit-only numerical equality convention; original results preserved',
    'pooled_eligible_selected_vs_xlarge':[r for r in rows if r['cohort']=='eligible' and r['subset']=='pooled' and r['baseline']=='xlarge_CD' and r['candidate'] in ['guarded_pooled','minimax','transfer_minimax']]}
(OUT/'exposed_harm_tolerance.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
