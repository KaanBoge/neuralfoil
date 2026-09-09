"""Supplementary exact flag/count and full decision-field check; no bootstrap rerun."""
from audit_downstream_calibration import HERE,ROOT,P,obj,read
import pandas as pd
import numpy as np
import json,hashlib,collections
r=obj(P/'assess/COMPLETE.json','341b16e2b738a8f01592d2671e57615e602b0fd896f2108241b0c2f53d0a46bc')
def table(n):
    read(P/'assess'/f'{n}.csv',r['outputs'][f'{n}.csv']);return pd.read_csv(P/'assess'/f'{n}.csv')
p=table('panel_metrics');g=table('group_metrics');b=table('bootstrap');d=table('decisions');fields=['mean8_CD_improvement_percent','xlarge_CD_improvement_percent'];checks=0
def eq(a,e):
    global checks
    if isinstance(e,(int,bool,np.integer,np.bool_)):assert a==e
    else:np.testing.assert_allclose(a,e,atol=2e-10,rtol=2e-12)
    checks+=1
for _,row in d.iterrows():
    cand=row.candidate;t=p[p.candidate.eq(cand)];ex=t[t.panel.str.startswith('eligible_only/')][fields];ref=p[p.candidate.eq('unpenalized_transfer')&p.panel.str.startswith('eligible_only/')][fields]
    vals={'eligible_external_negative_panel_baseline_pairs':int((ex< -1e-6).sum().sum()),'performance_reference_negative_pairs':int((ref< -1e-6).sum().sum()),'minimum_eligible_external_improvement_percent':ex.min().min(),'performance_reference_minimum_eligible_improvement_percent':ref.min().min(),'minimum_all31_improvement_both_percent':t[fields].min().min()}
    for prefix,reference in [('performance','unpenalized_transfer'),('robustness','half_strength')]:
        for seed in [20260906,20260908]:
            x=g[g.assignment.eq(seed)&g.candidate.eq(cand)];y=g[g.assignment.eq(seed)&g.candidate.eq(reference)]
            n=int((x.xlarge_improvement_percent< -1e-6).sum());nr=int((y.xlarge_improvement_percent< -1e-6).sum());worst=max(0,-x.xlarge_improvement_percent.min());wr=max(0,-y.xlarge_improvement_percent.min())
            for k,v in {'negative_groups':n,'reference_negative_groups':nr,'worst_group_deterioration_percent':worst,'reference_worst_group_deterioration_percent':wr,'identity_guard_pass':n<=nr and worst<=wr+1e-6,'worst_positive_group_MAE_difference_CD':max(0,x.MAE_difference_vs_xlarge_CD.max()),'reference_worst_positive_group_MAE_difference_CD':max(0,y.MAE_difference_vs_xlarge_CD.max())}.items():vals[f'{prefix}_{seed}_{k}']=v
    for k,v in vals.items():eq(row[k],v)
access=obj(P/'assess/ACCESS.json');ne=[e for e in access if e.get('operation')=='NPZ materialization'];assert len(ne)==90 and len(set(e['member'] for e in ne))==90
oldcsv=[e for e in access if e.get('operation')=='pandas.read_csv' and e.get('origin')=='KL addon'];assert len(oldcsv)==17 and all(e['member'].startswith('prediction_csv/') for e in oldcsv)
expected=[e for e in access if e.get('operation')=='expected CSV comparison parse'];assert len(expected)==5
summary={'status':'PASS_FULL_DECISION_FIELDS_AND_INVENTORY','complete_sha256':hashlib.sha256(read(P/'assess/COMPLETE.json')).hexdigest(),'additional_numeric_checks':checks,'old_prediction_CSV_reads':17,'current_score_CSV_reads':17,'expected_CSV_comparison_reads':5,'typed_NPZ_members':90,'worst_group_and_negative_count_records':d.to_dict('records')}
with (HERE/'DOWNSTREAM_ASSESSMENT_DECISION_QA.json').open('x') as f:json.dump(summary,f,indent=2)
print({k:v for k,v in summary.items() if k!='worst_group_and_negative_count_records'})
