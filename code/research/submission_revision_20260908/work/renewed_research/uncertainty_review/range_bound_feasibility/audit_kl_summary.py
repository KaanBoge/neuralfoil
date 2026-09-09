"""Independent remaining summary/intervention arithmetic on frozen CSVs."""
from audit_kl_calibration import P,HERE,checked
import pandas as pd,numpy as np,json,io,zipfile
def main():
    r=json.loads((P/'assess/COMPLETE.json').read_bytes())
    frames={n[:-4]:pd.read_csv(io.BytesIO(checked(P/'assess'/n,h)),low_memory=False) for n,h in r['outputs'].items() if n.endswith('.csv')}
    arc=P.parent/'range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
    with zipfile.ZipFile(arc) as z:panels=json.loads(z.read('scoring/panels.json'))
    f=frames['all_row_predictions'];checks=0
    def eq(a,b):
        nonlocal checks
        checks+=1;np.testing.assert_allclose(a,b,atol=2e-10,rtol=2e-12,equal_nan=True)
    for row in frames['intervention_metrics'].to_dict('records'):
        p=f.iloc[panels[row['panel']]];label=row['candidate'];y=p.measured_CD.to_numpy();pred=p[label].to_numpy();sel=abs(pred-p.qualified_matched_half.to_numpy())>1e-12;e=p[label+'__effective_fraction']
        for k,v in {'rows':len(p),'interventions':sel.sum(),'physical_eligible_rows':p.interval_applicable.sum(),'qualified_eligible_rows':p.qualified_gate.sum(),'intervention_fraction':sel.mean(),'effective_fraction_min':e.min(),'effective_fraction_mean':e.mean(),'effective_fraction_max':e.max()}.items():eq(row[k],v)
        for ref in ['qualified_matched_half','proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
            d=(abs(pred-y)-abs(p[ref].to_numpy()-y))[sel]
            for suffix,v in [('selected_harm_fraction',(d>1e-12).mean() if len(d) else np.nan),('selected_benefit_fraction',(d< -1e-12).mean() if len(d) else np.nan),('selected_positive_excess_CD',np.maximum(d,0).mean() if len(d) else np.nan)]:eq(row[ref+'__'+suffix],v)
    for row in frames['candidate_summary'].to_dict('records'):
        t=frames['panel_metrics'];t=t[t.candidate.eq(row['candidate'])];cols=['mean8_CD_improvement_percent','xlarge_CD_improvement_percent']
        for k,v in [('minimum_all31_improvement_both_percent',t[cols].to_numpy().min()),('minimum_eligible8_improvement_both_percent',t[t.panel.str.startswith('eligible_only/')][cols].to_numpy().min()),('worst_strict_source_improvement_both_percent',t[t.panel.str.startswith('strict_source_')][cols].to_numpy().min())]:eq(row[k],v)
        for seed in [20260906,20260908]:
            p=t[t.panel.eq(f'history_{seed}_pooled')].iloc[0];g=frames['group_metrics'];g=g[g.candidate.eq(row['candidate'])&g.assignment.eq(seed)]
            for k in cols+['mae_CD','median_absolute_error_CD','p90_absolute_error_CD']:eq(row[f'{seed}_{k}'],p[k])
            eq(row[f'{seed}_negative_identity_groups'],(g.xlarge_improvement_percent< -1e-6).sum());eq(row[f'{seed}_worst_group_improvement_percent'],g.xlarge_improvement_percent.min())
            b=frames['bootstrap'];b=b[b.candidate.eq(row['candidate'])&b.assignment.eq(seed)]
            for v in b.itertuples():eq(row[f'{seed}_remaining_MAE_reduction_vs_{v.reference}_percent'],v.remaining_MAE_reduction_percent)
    contrasts=[]
    t=frames['panel_metrics']
    for kind in ['structural','generic']:
        new=t[t.candidate.eq(f'qualified_{kind}_kl_harm_001')].set_index('panel');old=t[t.candidate.eq(f'qualified_{kind}_harm_001')].set_index('panel');delta=old.mae_CD-new.mae_CD
        contrasts.append({'kind':kind,'improved_views':int((delta>0).sum()),'worsened_views':list(delta[delta<0].index)})
    return {'status':'PASS','checks':checks,'summary_rows':17,'intervention_rows':62,'same_bound_contrasts':contrasts}
if __name__=='__main__':
    result=main()
    with (HERE/'KL_SUMMARY_QA.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
