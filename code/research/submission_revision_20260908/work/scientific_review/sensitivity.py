"""Fixed retrospective weighting and case-deletion arithmetic; no fitting."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
FAMILIES=['capped','upper_free','positive_log']
LABELS=[f'{prefix}{family}_{strength}' for prefix in ['','proper_'] for family in FAMILIES for strength in ['full','half']]+[f'project_{base}_{family}' for family in FAMILIES for base in ['mean8','xlarge']]+['adaptive_project_mean8','adaptive_project_xlarge','unpenalized_transfer','half_strength','mean8_CD','xlarge_CD']
BASES=['mean8_CD','xlarge_CD']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=HERE/'sensitivity_results';assert not out.exists()
    manifests={}
    for name in ['model_development_20260907_cap_ablation','model_development_20260908_adaptive_scale']:
        p=PROJECT/name/'assessment/report.json';r=json.loads(p.read_text());manifests[str(p)]=sha(p)
        for path,h in r['output_sha256'].items():assert sha(path)==h;manifests[path]=h
    assert manifests[str(PROJECT/'model_development_20260908_adaptive_scale/assessment/report.json')]=='7e6a3d074c0aaa6c433cf2f598a1e1866fa8e3c202a99959cbb4b4161fcb0dee'
    manifests[str(HERE/'SENSITIVITY_PLAN.md')]=sha(HERE/'SENSITIVITY_PLAN.md');manifests[str(Path(__file__))]=sha(Path(__file__))
    d=pd.read_csv(PROJECT/'model_development_20260908_adaptive_scale/assessment/all_row_predictions.csv',low_memory=False)
    full=[];deleted=[];identity=[];previous=None
    for seed in [20260906,20260908]:
        f=d[d.split.str.startswith(f'group_{seed}_')].sort_values('nf2_row_id').reset_index(drop=True)
        assert len(f)==8371 and f.nf2_row_id.nunique()==8371 and f.group.nunique()==93
        if previous is not None:
            for key in ['nf2_row_id','group','measured_CD']+BASES:np.testing.assert_array_equal(f[key],previous[key])
        previous=f
        names,inv=np.unique(f.group,return_inverse=True);n=np.bincount(inv)
        errors=abs(f[LABELS].to_numpy()-f.measured_CD.to_numpy()[:,None]);assert np.isfinite(errors).all()
        sums=np.stack([np.bincount(inv,weights=errors[:,i]) for i in range(24)],axis=1);means=sums/n[:,None]
        np.testing.assert_allclose(sums.sum(axis=0),errors.sum(axis=0),atol=1e-12,rtol=0)
        for j,label in enumerate(LABELS):
            for i,g in enumerate(names):identity.append(dict(assignment=seed,candidate=label,group=g,rows=int(n[i]),absolute_error_sum_CD=sums[i,j],mae_CD=means[i,j]))
        for weighting in ['row_weighted','equal_identity']:
            aggregate=errors.mean(axis=0) if weighting=='row_weighted' else means.mean(axis=0)
            for j,label in enumerate(LABELS):
                for base in BASES:
                    bidx=LABELS.index(base);baseline=aggregate[bidx];reduction=None if baseline==0 else 100*(1-aggregate[j]/baseline)
                    row=dict(assignment=seed,candidate=label,baseline=base,weighting=weighting,rows=8371,identities=93,mae_CD=aggregate[j],baseline_mae_CD=baseline,reduction_percent=reduction,zero_baseline=bool(baseline==0),identity_mae_median_CD=np.median(means[:,j]),identity_mae_p25_CD=np.quantile(means[:,j],.25),identity_mae_p75_CD=np.quantile(means[:,j],.75),identity_mae_max_CD=means[:,j].max(),identity_rows_min=int(n.min()),identity_rows_max=int(n.max()))
                    if label==base:assert reduction==0
                    full.append(row)
            for i,g in enumerate(names):
                remain=inv!=i
                aggregate_minus=(sums.sum(axis=0)-sums[i])/(8371-n[i]) if weighting=='row_weighted' else (means.sum(axis=0)-means[i])/92
                direct=errors[remain].mean(axis=0) if weighting=='row_weighted' else means[np.arange(93)!=i].mean(axis=0)
                np.testing.assert_allclose(aggregate_minus,direct,rtol=0,atol=1e-12)
                for j,label in enumerate(LABELS):
                    for base in BASES:
                        bidx=LABELS.index(base);b=aggregate_minus[bidx]
                        red=None if b==0 else 100*(1-aggregate_minus[j]/b)
                        orig=None if aggregate[bidx]==0 else 100*(1-aggregate[j]/aggregate[bidx])
                        directred=None if direct[bidx]==0 else 100*(1-direct[j]/direct[bidx])
                        if red is not None:np.testing.assert_allclose(red,directred,rtol=0,atol=1e-8)
                        deleted.append(dict(assignment=seed,candidate=label,baseline=base,weighting=weighting,omitted_identity=g,omitted_rows=int(n[i]),retained_rows=int(remain.sum()),retained_identities=92,mae_CD=aggregate_minus[j],baseline_mae_CD=b,reduction_percent=red,full_reduction_percent=orig,shift_percentage_points=None if red is None or orig is None else red-orig))
    full=pd.DataFrame(full);deleted=pd.DataFrame(deleted);identity=pd.DataFrame(identity)
    assert (len(full),len(deleted),len(identity))==(192,17856,4464)
    crosschecks=0
    for stage in ['model_development_20260907_cap_ablation','model_development_20260908_adaptive_scale']:
        old=pd.read_csv(PROJECT/stage/'assessment/panel_metrics.csv')
        for _,r in old[old.panel.isin(['history_20260906_pooled','history_20260908_pooled'])].iterrows():
            seed=int(r.panel.split('_')[1])
            for b in BASES:
                row=full[(full.assignment==seed)&(full.candidate==r.candidate)&(full.baseline==b)&(full.weighting=='row_weighted')].iloc[0]
                np.testing.assert_allclose(row.mae_CD,r.mae_CD,rtol=0,atol=1e-12)
                np.testing.assert_allclose(row.reduction_percent,r[b+'_improvement_percent'],rtol=0,atol=1e-8);crosschecks+=1
    summary=[]
    for keys,f in deleted.groupby(['assignment','candidate','baseline','weighting'],sort=False):
        valid=f.reduction_percent.notna()&f.full_reduction_percent.notna();z=f[valid]
        maxshift=abs(z.shift_percentage_points).max() if len(z) else None
        sign=lambda a:np.where(a>1e-6,1,np.where(a< -1e-6,-1,0))
        summary.append(dict(zip(['assignment','candidate','baseline','weighting'],keys))|dict(minimum_deletion_reduction_percent=z.reduction_percent.min(),maximum_deletion_reduction_percent=z.reduction_percent.max(),maximum_absolute_shift_percentage_points=maxshift,most_influential_identities=';'.join(z.loc[abs(abs(z.shift_percentage_points)-maxshift)<=1e-10,'omitted_identity']) if len(z) else '',sign_change_count=int((sign(z.reduction_percent)!=sign(z.full_reduction_percent)).sum()),undefined_deletions=int((~valid).sum())))
    for path,h in manifests.items():assert sha(path)==h
    out.mkdir()
    for name,frame in [('full_metrics',full),('delete_one_identity',deleted),('identity_errors',identity),('influence_summary',pd.DataFrame(summary))]:frame.to_csv(out/(name+'.csv'),index=False)
    result=dict(status='PASS',retrospective=True,refits=0,full_rows=len(full),deletion_rows=len(deleted),identity_rows=len(identity),archived_comparisons=crosschecks,input_sha256=manifests,output_sha256={str(p):sha(p) for p in out.iterdir()})
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if 'sha256' not in k})
if __name__=='__main__':main()
