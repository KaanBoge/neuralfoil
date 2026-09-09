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
CANDIDATES=['geometry4','geometry8','geometry_condition4','geometry8_free','neural62__0.5','neural62__1']
REFS=['unpenalized_transfer','half_strength']
LABELS=CANDIDATES+REFS+['previous_global','moderate_full_strength']
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
    for branch,labels in [('geometry',CANDIDATES[:4]),('neural',CANDIDATES[4:])]:
        for split in d.split.unique():
            ex=split in ['SG_exposed','W_new_challenge']
            path=ROOT/branch/('exposed_results' if ex else 'results')/(f'{split}_predictions.csv' if ex else f'predictions_{split}.csv')
            old=pd.read_csv(path,low_memory=False);f=d[d.split==split]
            if not ex:
                assert not old.nf2_row_id.duplicated().any()
                assert set(old.nf2_row_id)==set(f.nf2_row_id)
                old=old.set_index('nf2_row_id').loc[f.nf2_row_id].reset_index()
            assert len(old)==len(f)
            for key in ['Re','alpha','measured_CD']+BASES+labels:
                np.testing.assert_allclose(old[key],f[key],atol=1e-13,rtol=0)
            if ex:np.testing.assert_array_equal(old.inference_gate,f.inference_gate)
    # Independently verify both newest controls and contextual full core against
    # their original prior prediction tables, not just the combined assessment.
    for split in d.split.unique():
        ex=split in ['SG_exposed','W_new_challenge'];f=d[d.split==split]
        risk=PROJECT/'model_development_20260907_risk_policy'/('exposed_results' if ex else 'results')/(f'{split}_predictions.csv' if ex else f'predictions_{split}.csv')
        cap=PROJECT/'model_development_20260907_frontier/capacity'/('exposed_results' if ex else 'results')/(f'{split}_predictions.csv' if ex else f'predictions_{split}.csv')
        for path,cols in [(risk,{'unpenalized_transfer':'unpenalized_transfer','half_strength':'hist62_regularized__0.5'}),(cap,{'moderate_full_strength':'hist62_moderate__1'})]:
            old=pd.read_csv(path,low_memory=False)
            if not ex:old=old.set_index('nf2_row_id').loc[f.nf2_row_id].reset_index()
            for dest,src in cols.items():np.testing.assert_allclose(old[src],f[dest],rtol=0,atol=1e-13)
    prior=pd.read_csv(PROJECT/'model_development_20260907_positive/historical_results/all_row_predictions.csv',low_memory=False)
    for split in d.split.unique():
        f=d[d.split==split];old=prior[prior.split==split]
        if split.startswith(('group_','strict_source_')):old=old.set_index('nf2_row_id').loc[f.nf2_row_id].reset_index()
        for key in ['Re','alpha','measured_CD']+BASES:np.testing.assert_allclose(old[key],f[key],atol=1e-13,rtol=0)
        np.testing.assert_allclose(old.primary_both,f.previous_global,atol=1e-13,rtol=0)


def main():
    assert (ROOT/'geometry/results/complete.json').exists() and (ROOT/'neural/results/report.json').exists()
    assert (A/'report.json').exists(),'Wait for completed central assessment'
    report=json.loads((A/'report.json').read_text())
    geo=json.loads((ROOT/'geometry/results/freeze.json').read_text())
    neural=json.loads((ROOT/'neural/results/freeze.json').read_text())
    assert geo['all_64_frozen_before_exposed'] and len(geo['model_sha256'])==64
    assert neural['external_scored_at_freeze'] is False and len(neural['artifact_sha256'])==48
    hashes={**report['input_source_sha256'],**report['output_sha256'],**geo['model_sha256'],**neural['artifact_sha256']}
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
        draws=np.random.default_rng(2026090723).multinomial(93,np.full(93,1/93),size=20000)
        resampled={label:draws@values for label,values in sums.items()}
        for label in LABELS:
            error=sums[label]/n;reduction=100*(1-error/xl);raw=error-xl
            computed_groups[label,seed]=(reduction,raw)
            for i,name in enumerate(names):
                compare(gt.loc[label,seed,name],{'rows':int(n[i]),'mae_CD':error[i],'xlarge_mae_CD':xl[i],'MAE_difference_vs_xlarge_CD':raw[i],'xlarge_improvement_percent':reduction[i],'worse_than_xlarge':bool(reduction[i]< -1e-6)},(label,seed,name));checks['groups']+=1
            for ref in REFS:
                benefit=100*(1-resampled[label]/resampled[ref]);lo,hi=np.quantile(benefit,[.025,.975]);gain=100*(1-sums[label].sum()/sums[ref].sum());gains[label,seed,ref]=gain
                compare(bt.loc[label,seed,ref],{'rows':8371,'groups':93,'remaining_MAE_reduction_percent':gain,'conditional_95pct_lower':lo,'conditional_95pct_upper':hi,'bootstrap_fraction_benefit_positive':float((benefit>0).mean()),'draws':20000,'seed':2026090723},(label,seed,ref));checks['bootstraps']+=1
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
