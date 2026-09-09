"""Paired frozen-prediction increments and numerical-tolerance harm counts."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
RESULTS=ROOT/'results'
manifest=json.loads((RESULTS/'run_manifest.json').read_text())
labels=manifest['labels']+['guarded_pooled','minimax','transfer_minimax','cycle1_nested','cycle2_nested']
frames=pd.concat([pd.read_csv(p) for p in sorted(RESULTS.glob('predictions_*.csv'))],ignore_index=True)
increments=[];harms=[]
for ev in ['group_20260906','group_20260908']+[f'strict_source_{s}' for s in ['stec8','vol1','vol2','vol3','all_uiuc_volumes']]:
    f=frames[frames.split.str.startswith(ev)]
    assert not f.nf2_row_id.duplicated().any()
    for candidate in labels:
        for base in ['xlarge_CD','mean8_CD','cycle2_nested']:
            e=(f[candidate]-f.measured_CD).abs()*1e4;b=(f[base]-f.measured_CD).abs()*1e4
            g=pd.DataFrame({'g':f.group,'e':e,'b':b}).groupby('g')[['e','b']].mean()
            tol=1e-8
            harms.append({'evaluation':ev,'candidate':candidate,'baseline':base,'rows':len(f),'groups':len(g),
                'strict_worse_rows':int((e>b).sum()),'tolerance_worse_rows':int((e>b+tol).sum()),
                'tolerance_equal_rows':int((np.abs(e-b)<=tol).sum()),
                'strict_worse_groups':int((g.e>g.b).sum()),'tolerance_worse_groups':int((g.e>g.b+tol).sum()),
                'tolerance_equal_groups':int((np.abs(g.e-g.b)<=tol).sum()),'tolerance_drag_counts':tol})
    if not ev.startswith('group_'):continue
    for candidate in ['guarded_pooled','minimax']:
        e=(f[candidate]-f.measured_CD).abs()*1e4;b=(f.cycle2_nested-f.measured_CD).abs()*1e4
        g=pd.DataFrame({'g':f.group,'e':e,'b':b,'n':1}).groupby('g')[['e','b','n']].sum()
        rng=np.random.default_rng(20260909);draw=rng.integers(len(g),size=(20000,len(g)))
        es=g.e.to_numpy()[draw].sum(axis=1);bs=g.b.to_numpy()[draw].sum(axis=1);ns=g.n.to_numpy()[draw].sum(axis=1)
        gain=100*(1-es/bs);delta=(es-bs)/ns
        increments.append({'evaluation':ev,'candidate':candidate,'baseline':'cycle2_nested','rows':len(f),'groups':len(g),
            'candidate_MAE_counts':float(e.mean()),'Cycle2_MAE_counts':float(b.mean()),
            'delta_MAE_counts_positive_is_worse':float(e.mean()-b.mean()),
            'relative_reduction_percent_positive_is_better':float(100*(1-e.sum()/b.sum())),
            'paired_cluster_95_delta_MAE_counts':np.quantile(delta,[.025,.975]).tolist(),
            'paired_cluster_95_relative_reduction_percent':np.quantile(gain,[.025,.975]).tolist(),
            'one_sided95_lower_relative_reduction_percent':float(np.quantile(gain,.05)),
            'bootstrap_fraction_improving_descriptive_not_pvalue':float((gain>0).mean()),
            'replicates':20000,'warning':'Conditional paired group resampling of frozen predictions, no refitting or adaptive-history adjustment; neither pvalue nor global optimality evidence.'})
pd.DataFrame(harms).to_csv(OUT/'tolerance_harm_counts.csv',index=False)
result={'comparisons':increments,'all_candidate_harm_records':len(harms),'harm_tolerance_counts':1e-8,
    'harm_records_with_strict_vs_tolerance_difference':sum(h['strict_worse_rows']!=h['tolerance_worse_rows'] or h['strict_worse_groups']!=h['tolerance_worse_groups'] for h in harms)}
(OUT/'paired_increment_qa.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
