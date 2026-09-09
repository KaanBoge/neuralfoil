"""Frozen risk-policy assessment only; no fitting, selection, or import-time I/O.

Run only after all prediction files and the 48-policy freeze are complete.
Conditional bootstrap uncertainty is not adaptive-search-adjusted validation.
"""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FRONT=HERE.parent/'model_development_20260907_frontier'
sys.path.insert(0,str(FRONT))
import frontier_assessment as shared

POLICIES=['risk_transfer','unpenalized_transfer','risk_group']
CONTROLS=['half_strength','full_strength','previous_global']
LABELS=POLICIES+CONTROLS
REFERENCE='half_strength'
N_BOOTSTRAP=20000
SEED=2026090721
ROW_TOL=1e-12
PP_TOL=1e-6
OUT=HERE/'assessment'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gate(f):
    return f.inference_gate.map(lambda v:v is True or str(v).lower()=='true' or v==1).to_numpy(bool)

def load_frame():
    freeze=HERE/'results/freeze.json'
    assert freeze.is_file(),'All 48 policies must be frozen before assessment'
    frozen=json.loads(freeze.read_text())
    assert frozen['policy_count']==48 and len(frozen['artifact_sha256'])==48
    assert len(set(frozen['artifact_sha256']))==48
    for path,expected in {**frozen['source_input_sha256'],**frozen['artifact_sha256']}.items():
        assert sha(path)==expected,path
    d,_,_,hashes=shared.load_frame(['capacity'])
    hashes.update(frozen['source_input_sha256']);hashes.update(frozen['artifact_sha256'])
    hashes[str(freeze)]=sha(freeze)
    hashes[str(Path(__file__))]=sha(Path(__file__))
    hashes[str(HERE/'PROTOCOL.md')]=sha(HERE/'PROTOCOL.md')
    for p in (HERE/'results').glob('*.json'):hashes[str(p)]=sha(p)
    d['half_strength']=d['capacity__hist62_regularized__0.5']
    d['full_strength']=d['capacity__hist62_regularized__1']
    d['previous_global']=d[shared.REFERENCE]
    historical=sorted(s for s in d.split.unique() if s not in ['SG_exposed','W_new_challenge'])
    assert len(historical)==15 and len(d)==29856
    for split in historical+['SG_exposed','W_new_challenge']:
        external=split in ['SG_exposed','W_new_challenge']
        path=HERE/('exposed_results' if external else 'results')/(f'{split}_predictions.csv' if external else f'predictions_{split}.csv')
        hashes[str(path)]=sha(path);new=pd.read_csv(path,low_memory=False)
        mask=d.split==split;original=d.loc[mask]
        if not external:
            assert not new.nf2_row_id.duplicated().any() and set(new.nf2_row_id)==set(original.nf2_row_id)
            new=new.set_index('nf2_row_id').loc[original.nf2_row_id].reset_index()
        shared.check_common(original,new)
        for suffix,control in [('0.5','half_strength'),('1','full_strength')]:
            np.testing.assert_allclose(new['hist62_regularized__'+suffix],original[control],rtol=0,atol=1e-13)
        for label in POLICIES:
            strength=new[label+'__strength'].to_numpy();pred=new[label].to_numpy()
            assert strength.shape==(len(new),) and np.isfinite(strength).all() and ((strength>=-1e-12)&(strength<=1+1e-12)).all()
            assert np.isfinite(pred).all() and (pred>0).all()
            base=original.mean8_CD.to_numpy();core=original.full_strength.to_numpy()
            expected=base+strength*(core-base)
            if external:
                g=gate(original);assert int(g.sum())=={'SG_exposed':234,'W_new_challenge':238}[split]
                np.testing.assert_array_equal(g,gate(new))
                expected=np.where(g,expected,base)
                np.testing.assert_allclose(pred[~g],base[~g],rtol=0,atol=1e-13)
            np.testing.assert_allclose(pred,expected,rtol=0,atol=1e-12)
            d.loc[mask,label]=pred;d.loc[mask,label+'__strength']=strength
    assert np.isfinite(d[LABELS].to_numpy()).all()
    return d,hashes

def bootstrap(d):
    rows=[]
    for seed in [20260906,20260908]:
        f=d[d.split.str.startswith(f'group_{seed}_')]
        assert len(f)==8371 and f.nf2_row_id.nunique()==8371
        groups,inv=np.unique(f.group,return_inverse=True);assert len(groups)==93
        y=f.measured_CD.to_numpy();reference=np.bincount(inv,weights=abs(f[REFERENCE].to_numpy()-y))
        counts=np.random.default_rng(SEED).multinomial(len(groups),np.full(len(groups),1/len(groups)),size=N_BOOTSTRAP)
        re=counts@reference;assert (re>0).all()
        for label in LABELS:
            error=np.bincount(inv,weights=abs(f[label].to_numpy()-y));benefit=100*(1-counts@error/re)
            lo,hi=np.quantile(benefit,[.025,.975])
            rows.append({'candidate':label,'assignment':seed,'reference':REFERENCE,'rows':len(f),'groups':len(groups),
                         'remaining_MAE_reduction_percent':float(100*(1-error.sum()/reference.sum())),
                         'conditional_95pct_lower':float(lo),'conditional_95pct_upper':float(hi),
                         'bootstrap_fraction_benefit_positive':float((benefit>0).mean()),'draws':N_BOOTSTRAP,'seed':SEED,
                         'interpretation':'Conditional paired identity-group bootstrap of fixed predictions; no search adjustment, no confirmatory p-value; assignments overlap'})
    return pd.DataFrame(rows)

def harms(d,panels):
    rows=[];y=d.measured_CD.to_numpy()
    for label in LABELS:
        e=abs(d[label].to_numpy()-y)
        for comparator in ['half_strength','xlarge_CD','mean8_CD']:
            be=abs(d[comparator].to_numpy()-y);excess=e-be
            for panel,idx in panels.items():
                delta=excess[idx];worse=delta>ROW_TOL;better=delta<-ROW_TOL;equal=~(worse|better)
                rows.append({'candidate':label,'comparator':comparator,'panel':panel,'rows':len(idx),
                             'mean_positive_excess_absolute_error_CD':float(np.maximum(delta,0).mean()),
                             'mean_positive_excess_absolute_error_counts':float(1e4*np.maximum(delta,0).mean()),
                             'mean_signed_excess_absolute_error_CD':float(delta.mean()),
                             'median_positive_excess_absolute_error_CD':float(np.median(np.maximum(delta,0))),
                             'p90_positive_excess_absolute_error_CD':float(np.quantile(np.maximum(delta,0),.9)),
                             'worse_rows':int(worse.sum()),'better_rows':int(better.sum()),'equal_rows':int(equal.sum()),
                             'worse_fraction':float(worse.mean()),'better_fraction':float(better.mean()),'equal_fraction':float(equal.mean()),'equality_tolerance_CD':ROW_TOL})
    return pd.DataFrame(rows)

def strengths(d,panels):
    rows=[]
    for label in POLICIES+['half_strength','full_strength']:
        values=d[label+'__strength'].to_numpy() if label in POLICIES else np.full(len(d),.5 if label=='half_strength' else 1.)
        # Runner policy strengths are already applied strengths (zero outgate).
        # Convert nominal constant controls to that SAME applied convention.
        effective=values.copy();external=d.split.isin(['SG_exposed','W_new_challenge']).to_numpy();effective[external&~gate(d)]=0.
        for panel,idx in panels.items():
            row={'candidate':label,'panel':panel,'rows':len(idx)}
            for prefix,x in [('applied_after_gate',effective[idx])]:
                row.update({prefix+'_mean':float(x.mean()),prefix+'_std_population':float(x.std()),prefix+'_min':float(x.min()),prefix+'_max':float(x.max()),
                            prefix+'_p05':float(np.quantile(x,.05)),prefix+'_p25':float(np.quantile(x,.25)),prefix+'_median':float(np.median(x)),prefix+'_p75':float(np.quantile(x,.75)),prefix+'_p95':float(np.quantile(x,.95)),
                            prefix+'_below_half_fraction':float((x<.5-1e-12).mean()),prefix+'_above_half_fraction':float((x>.5+1e-12).mean())})
            rows.append(row)
    return pd.DataFrame(rows)

def group_metrics(d):
    rows=[]
    for seed in [20260906,20260908]:
        f=d[d.split.str.startswith(f'group_{seed}_')]
        for name,part in f.groupby('group',sort=True):
            y=part.measured_CD.to_numpy();xb=abs(part.xlarge_CD.to_numpy()-y).mean();assert xb>0
            for label in LABELS:
                err=abs(part[label].to_numpy()-y).mean();improvement=100*(1-err/xb)
                rows.append({'candidate':label,'assignment':seed,'group':name,'rows':len(part),'mae_CD':float(err),'xlarge_mae_CD':float(xb),
                             'MAE_difference_vs_xlarge_CD':float(err-xb),'xlarge_improvement_percent':float(improvement),
                             'worse_than_xlarge':bool(improvement<-PP_TOL),'comparison_tolerance_percentage_points':PP_TOL})
    return pd.DataFrame(rows)

def decisions(table,boot,groups,established):
    fields=['xlarge_CD_improvement_percent','mean8_CD_improvement_percent'];rows=[]
    for label in POLICIES:
        t=table[table.candidate==label];b=boot[boot.candidate==label]
        assert len(t)==31 and len(b)==2
        gain=bool((b.remaining_MAE_reduction_percent>=1-PP_TOL).all())
        positive=bool((t[fields].to_numpy()>=-PP_TOL).all())
        row={'candidate':label,'primary_procedure':label=='risk_transfer','both_history_remaining_MAE_gain_vs_half_at_least_1pct':gain,
             'all31_panels_nonnegative_both_baselines':positive,'minimum_all31_improvement_both_percent':float(t[fields].to_numpy().min())}
        row['all31_panels_strictly_positive_both_baselines']=bool((t[fields].to_numpy()>0).all())
        group_guard=True;raw_guard=True
        for seed in [20260906,20260908]:
            c=groups[(groups.candidate==label)&(groups.assignment==seed)].xlarge_improvement_percent.to_numpy()
            h=groups[(groups.candidate=='half_strength')&(groups.assignment==seed)].xlarge_improvement_percent.to_numpy()
            assert len(c)==len(h)==93
            count=int((c<-PP_TOL).sum());refcount=int((h<-PP_TOL).sum());magnitude=max(0.,float(-c.min()));refmag=max(0.,float(-h.min()))
            passes=count<=refcount and magnitude<=refmag+PP_TOL;group_guard &= passes
            cr=groups[(groups.candidate==label)&(groups.assignment==seed)].MAE_difference_vs_xlarge_CD.to_numpy()
            hr=groups[(groups.candidate=='half_strength')&(groups.assignment==seed)].MAE_difference_vs_xlarge_CD.to_numpy()
            raw_count=int((cr>ROW_TOL).sum());raw_refcount=int((hr>ROW_TOL).sum())
            raw_worst=max(0.,float(cr.max()));raw_refworst=max(0.,float(hr.max()))
            raw_pass=raw_count<=raw_refcount and raw_worst<=raw_refworst+ROW_TOL;raw_guard &= raw_pass
            row.update({f'{seed}_negative_identity_groups':count,f'{seed}_half_negative_identity_groups':refcount,
                        f'{seed}_worst_negative_group_magnitude_percent':magnitude,f'{seed}_half_worst_negative_group_magnitude_percent':refmag,f'{seed}_identity_guard_pass':passes})
            row.update({f'{seed}_raw_CD_worse_identity_groups':raw_count,f'{seed}_raw_CD_half_worse_identity_groups':raw_refcount,
                        f'{seed}_raw_CD_worst_positive_MAE_difference':raw_worst,f'{seed}_raw_CD_half_worst_positive_MAE_difference':raw_refworst,f'{seed}_raw_CD_identity_guard_pass':raw_pass})
        row['identity_group_guard_both_assignments']=group_guard;row['tradeoff_advance']=gain and positive and group_guard
        row['raw_CD_identity_group_guard_both_assignments']=raw_guard
        row['alternate_raw_CD_tradeoff_advance']=gain and positive and raw_guard
        row['primary_decision_changes_under_raw_CD_guard']=row['tradeoff_advance']!=row['alternate_raw_CD_tradeoff_advance']
        prior=established[established.candidate==label].iloc[0]
        row.update({'established_'+k:v for k,v in prior.to_dict().items() if k!='candidate'})
        rows.append(row)
    return pd.DataFrame(rows)

def main():
    assert not OUT.exists(),'Preserve prior assessment; no overwrite'
    d,hashes=load_frame()
    panels=shared.old.panels(d);panels.update({k:v for k,v in shared.reconcile.external_panels(d).items() if k.startswith('eligible_only/')});assert len(panels)==31
    table=pd.concat([shared.old.metrics(d,d[label].to_numpy(),panels,label) for label in LABELS],ignore_index=True)
    boot=bootstrap(d);group=group_metrics(d)
    # Reuse the previous frontier rule unchanged, including its reference,
    # bootstrap convention, comparison semantics and operational tolerances.
    oldboot=shared.conditional_bootstrap(d,POLICIES)
    oldtable=pd.concat([table,shared.old.metrics(d,d[shared.REFERENCE].to_numpy(),panels,shared.REFERENCE)],ignore_index=True)
    established=shared.stopping_gate(d,POLICIES,oldtable,oldboot)
    decision=decisions(table,boot,group,established)
    summary=[];fields=['xlarge_CD_improvement_percent','mean8_CD_improvement_percent']
    for label in LABELS:
        t=table[table.candidate==label].set_index('panel');b=boot[boot.candidate==label].set_index('assignment')
        row={'candidate':label,'role':'fixed_procedure' if label in POLICIES else 'fixed_control',
             'minimum_all23_improvement_both_percent':float(t.loc[~t.index.str.startswith('eligible_only/'),fields].to_numpy().min()),
             'minimum_eligible8_improvement_both_percent':float(t.loc[t.index.str.startswith('eligible_only/'),fields].to_numpy().min()),
             'worst_strict_source_improvement_both_percent':float(t.loc[t.index.str.startswith('strict_source_'),fields].to_numpy().min())}
        for seed in [20260906,20260908]:
            row[f'{seed}_remaining_MAE_reduction_vs_half_percent']=float(b.loc[seed,'remaining_MAE_reduction_percent'])
            for field in fields:row[f'{seed}_{field}']=float(t.loc[f'history_{seed}_pooled',field])
            g=group[(group.candidate==label)&(group.assignment==seed)].xlarge_improvement_percent
            row[f'{seed}_negative_identity_groups_vs_xlarge']=int((g<-PP_TOL).sum());row[f'{seed}_worst_identity_improvement_vs_xlarge_percent']=float(g.min())
        summary.append(row)
    for p in [Path(__file__),HERE/'PROTOCOL.md',HERE/'INTERPRETATION.md',HERE/'results/complete.json',HERE/'run_experiment.py',HERE/'risk_policy.py',Path(shared.__file__),Path(shared.old.__file__)]:hashes[str(p)]=sha(p)
    for p,h in hashes.items():assert sha(p)==h
    OUT.mkdir()
    outputs={'panel_metrics':table,'candidate_summary':pd.DataFrame(summary),'decisions':decision,'bootstrap':boot,'harm_metrics':harms(d,panels),'strength_metrics':strengths(d,panels),'group_metrics':group,
             'established_frontier_bootstrap':oldboot,'established_frontier_decisions':established}
    for name,frame in outputs.items():frame.to_csv(OUT/(name+'.csv'),index=False)
    report={'status':'completed_fixed_risk_policy_assessment_adaptive_not_confirmatory','policies':POLICIES,'controls':CONTROLS,'rows_with_repeated_contexts':len(d),'panels':31,'input_source_sha256':hashes,
            'bootstrap_draws':N_BOOTSTRAP,'bootstrap_seed':SEED,'row_equality_tolerance_CD':ROW_TOL,'tradeoff_comparison_tolerance_percentage_points':PP_TOL,
            'tradeoff_advances':decision.loc[decision.tradeoff_advance,'candidate'].tolist(),'established_frontier_advances':established.loc[established.operational_frontier_advance,'candidate'].tolist(),
            'no_qualifying_tradeoff_improvement':not bool(decision.tradeoff_advance.any()),'warning':'All candidates fixed, not selected here. Existing exposed outcomes/adaptive research; conditional CIs unadjusted for three tested procedures. Negative observations retained. No guarantee of per-row or held-out risk control.',
            'metric_semantics':'Panel improvements are ratios of absolute-error sums. Group guard uses group MAE improvement percentages versus xlarge; raw CD group differences also saved. Positive-excess magnitudes use exact max(delta,0); 1e-12CD only defines row equality.',
            'output_sha256':{str(OUT/(name+'.csv')):sha(OUT/(name+'.csv')) for name in outputs}}
    (OUT/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(decision.to_string(index=False),flush=True)

if __name__=='__main__':main()
