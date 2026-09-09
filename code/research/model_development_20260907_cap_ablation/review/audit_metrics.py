"""Independent current-frontier assessment replay; no producer imports or fitting.

Reads geometry outcomes only after both completion markers and assessment/report.
All writes confined to review/. Uses original source joins and fresh panel masks.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PROJECT=ROOT.parent
A=ROOT/'assessment'
FAMILIES=['capped','upper_free','positive_log']
POINTS=[f'{p}{f}_{s}' for p in ['','proper_'] for f in FAMILIES for s in ['full','half']]
PROJECTIONS=[f'project_{b}_{f}' for f in FAMILIES for b in ['mean8','xlarge']]
CANDIDATES=['upper_free_full','upper_free_half','positive_log_full','positive_log_half']+[f'project_{b}_{f}' for f in ['upper_free','positive_log'] for b in ['mean8','xlarge']]
REFS=['unpenalized_transfer','half_strength']
LABELS=POINTS+PROJECTIONS+REFS
BASES=['xlarge_CD','mean8_CD']
SEEDS=[20260906,20260908]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def masks(d):
    out={}
    for seed in SEEDS:
        mask=d.split.str.startswith(f'group_{seed}_')
        assert mask.sum()==8371 and d.loc[mask,'nf2_row_id'].nunique()==8371
        out[f'history_{seed}_pooled']=mask
        for s in sorted(d.loc[mask,'source'].unique()):out[f'history_{seed}_{s}']=mask&(d.source==s)
    for name in sorted(s for s in d.split.unique() if s.startswith('strict_source_')):out[name]=d.split==name
    for name,field,n,eligible in [('SG_exposed','airfoil',242,234),('W_new_challenge','configuration',255,238)]:
        mask=d.split==name;g=d.inference_gate.eq(True)
        assert mask.sum()==n and (mask&g).sum()==eligible
        out[name+'_pooled']=mask;out[f'eligible_only/{name}/pooled']=mask&g
        for value in sorted(d.loc[mask,field].unique()):
            out[name+'_'+value]=mask&(d[field]==value)
            out[f'eligible_only/{name}/{value}']=mask&g&(d[field]==value)
    assert len(out)==31
    return out


def compare(actual,expected,name):
    """Exact counts/Booleans, appropriately tight tolerances for float summaries."""
    for key,value in expected.items():
        if isinstance(value,(bool,np.bool_)):
            assert bool(actual[key])==bool(value),(name,key,actual[key],value)
        elif isinstance(value,(int,np.integer)):
            assert int(actual[key])==int(value),(name,key,actual[key],value)
        else:
            tol=1e-8 if any(s in key for s in ['percent','95pct']) else 1e-10
            np.testing.assert_allclose(float(actual[key]),float(value),atol=tol,rtol=0,err_msg=f'{name}/{key}')


def source_join(d):
    old=pd.read_csv(PROJECT/'model_development_20260907_geometry_frontier/assessment/all_row_predictions.csv',low_memory=False)
    for split in d.split.unique():
        ext=split in ['SG_exposed','W_new_challenge'];f=d[d.split==split]
        path=ROOT/('exposed_results' if ext else 'results')/(f'{split}_predictions.csv' if ext else f'predictions_{split}.csv')
        fresh=pd.read_csv(path,low_memory=False);prev=old[old.split==split]
        if not ext:
            fresh=fresh.set_index('nf2_row_id').loc[f.nf2_row_id].reset_index()
            prev=prev.set_index('nf2_row_id').loc[f.nf2_row_id].reset_index()
        for key in POINTS+PROJECTIONS+['measured_CD']+BASES:
            np.testing.assert_allclose(f[key],fresh[key],rtol=0,atol=1e-13)
        for key in REFS+['measured_CD','Re','alpha']+BASES:
            np.testing.assert_allclose(f[key],prev[key],rtol=0,atol=1e-13)


def main():
    assert (ROOT/'results/complete.json').exists() and (A/'report.json').exists()
    report=json.loads((A/'report.json').read_text())
    frozen=json.loads((ROOT/'results/freeze.json').read_text())
    assert frozen['core_count']==96 and frozen['external_outcomes_opened'] is False
    hashes={**report['input_source_sha256'],**report['output_sha256'],**frozen['artifact_sha256']}
    for p,h in hashes.items():assert sha(p)==h,p
    d=pd.read_csv(A/'all_row_predictions.csv',low_memory=False)
    assert len(d)==29856 and np.isfinite(d[LABELS+BASES+['measured_CD']]).all().all()
    source_join(d);panels=masks(d)
    pt=pd.read_csv(A/'panel_metrics.csv').set_index(['candidate','panel'])
    ht=pd.read_csv(A/'harm_metrics.csv').set_index(['candidate','reference','panel'])
    gt=pd.read_csv(A/'group_metrics.csv').set_index(['candidate','assignment','group'])
    bt=pd.read_csv(A/'bootstrap.csv').set_index(['candidate','assignment','reference'])
    dt=pd.read_csv(A/'decisions.csv').set_index('candidate')
    computed_panels={};computed_groups={};gains={};checks={'panels':0,'harms':0,'groups':0,'bootstraps':0}
    for label in LABELS:
        for panel,mask in panels.items():
            f=d[mask];y=f.measured_CD.to_numpy();e=abs(f[label].to_numpy()-y)
            expected={'rows':len(f),'mae_CD':e.mean(),'mae_drag_counts':e.mean()*1e4,'median_absolute_error_CD':np.median(e),'p90_absolute_error_CD':np.quantile(e,.9)}
            reductions=[]
            for base in BASES:
                be=abs(f[base].to_numpy()-y);imp=100*(1-e.sum()/be.sum());reductions.append(imp)
                expected.update({base+'_mae':be.mean(),base+'_improvement_percent':imp,base+'_worse_rows':int((e>be+1e-12).sum()),base+'_worse_fraction':float((e>be+1e-12).mean())})
            compare(pt.loc[label,panel],expected,(label,panel));computed_panels[label,panel]=reductions;checks['panels']+=1
            for ref in REFS+BASES:
                delta=e-abs(f[ref].to_numpy()-y);positive=np.maximum(delta,0);worse=delta>1e-12;better=delta< -1e-12;equal=~(worse|better)
                vals={'rows':len(f),'mean_positive_excess_absolute_error_CD':positive.mean(),'mean_positive_excess_absolute_error_drag_counts':positive.mean()*1e4,'mean_signed_excess_absolute_error_CD':delta.mean(),'p90_positive_excess_absolute_error_CD':np.quantile(positive,.9)}
                for key,v in [('worse',worse),('better',better),('equal',equal)]:vals[key+'_rows']=int(v.sum());vals[key+'_fraction']=v.mean()
                compare(ht.loc[label,ref,panel],vals,(label,ref,panel));checks['harms']+=1
    for seed in SEEDS:
        f=d[d.split.str.startswith(f'group_{seed}_')];names,inv=np.unique(f.group,return_inverse=True);assert len(names)==93
        y=f.measured_CD.to_numpy();n=np.bincount(inv);xl=np.bincount(inv,weights=abs(f.xlarge_CD.to_numpy()-y))/n
        sums={label:np.bincount(inv,weights=abs(f[label].to_numpy()-y)) for label in LABELS}
        draws=np.random.default_rng(2026090729).multinomial(93,np.full(93,1/93),size=20000)
        resampled={label:draws@values for label,values in sums.items()}
        for label in LABELS:
            error=sums[label]/n;reduction=100*(1-error/xl);raw=error-xl
            computed_groups[label,seed]=(reduction,raw)
            for i,name in enumerate(names):
                compare(gt.loc[label,seed,name],{'rows':int(n[i]),'mae_CD':error[i],'xlarge_mae_CD':xl[i],'MAE_difference_vs_xlarge_CD':raw[i],'xlarge_improvement_percent':reduction[i],'worse_than_xlarge':bool(reduction[i]< -1e-6)},(label,seed,name));checks['groups']+=1
            for ref in REFS:
                benefit=100*(1-resampled[label]/resampled[ref]);lo,hi=np.quantile(benefit,[.025,.975]);gain=100*(1-sums[label].sum()/sums[ref].sum());gains[label,seed,ref]=gain
                compare(bt.loc[label,seed,ref],{'rows':8371,'groups':93,'remaining_MAE_reduction_percent':gain,'conditional_95pct_lower':lo,'conditional_95pct_upper':hi,'bootstrap_fraction_benefit_positive':float((benefit>0).mean()),'draws':20000,'seed':2026090729},(label,seed,ref));checks['bootstraps']+=1
    verdicts=[]
    for label in CANDIDATES:
        allvalues=np.asarray([computed_panels[label,p] for p in panels]);strict=np.asarray([computed_panels[label,p] for p in panels if p.startswith('strict_source_')]);ext=np.asarray([computed_panels[label,p] for p in panels if p.startswith('eligible_only/')]);rext=np.asarray([computed_panels[REFS[0],p] for p in panels if p.startswith('eligible_only/')])
        strictok=bool((strict>=-1e-6).all());allok=bool((allvalues>=-1e-6).all());extok=bool((ext < -1e-6).sum()<=(rext < -1e-6).sum() and ext.min()>=rext.min()-1e-6)
        vals={'strict_source_guard_pass':strictok,'eligible_external_negative_panel_baseline_pairs':int((ext< -1e-6).sum()),'performance_reference_negative_pairs':int((rext< -1e-6).sum()),'minimum_eligible_external_improvement_percent':ext.min(),'performance_reference_minimum_eligible_improvement_percent':rext.min(),'performance_external_guard_pass':extok,'minimum_all31_improvement_both_percent':allvalues.min(),'all31_nonnegative_both_baselines':allok}
        for ref,prefix in zip(REFS,['performance','robustness']):
            gainok=all(gains[label,s,ref]>=1-1e-6 for s in SEEDS);groupok=True
            for seed in SEEDS:
                c,raw=computed_groups[label,seed];r,rr=computed_groups[ref,seed];cn=int((c< -1e-6).sum());rn=int((r< -1e-6).sum());cw=max(0.,-c.min());rw=max(0.,-r.min());ok=bool(cn<=rn and cw<=rw+1e-6);groupok &= ok
                for k,v in {'negative_groups':cn,'reference_negative_groups':rn,'worst_group_deterioration_percent':cw,'reference_worst_group_deterioration_percent':rw,'identity_guard_pass':ok,'worst_positive_group_MAE_difference_CD':max(0.,raw.max()),'reference_worst_positive_group_MAE_difference_CD':max(0.,rr.max())}.items():vals[f'{prefix}_{seed}_{k}']=v
            vals[prefix+'_historical_gain_both_at_least_1pct']=gainok;vals[prefix+'_identity_guard_both_assignments']=groupok
            vals[prefix+'_advance']=bool(gainok and groupok and (strictok and extok if prefix=='performance' else allok))
        compare(dt.loc[label],vals,label);verdicts.append({'candidate':label,'performance_advance':vals['performance_advance'],'robustness_advance':vals['robustness_advance']})
    result={'status':'PASS','hashes_verified':len(hashes),'checks':checks,'decisions':verdicts,'assessment_report_sha256':sha(A/'report.json'),'audit_code_sha256':sha(Path(__file__)),'scope':'Independent arithmetic/source joins; no fitting or new outcomes; intervals conditional and adaptive.'}
    (HERE/'assessment_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(result)


if __name__=='__main__':main()


