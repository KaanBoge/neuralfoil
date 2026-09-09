"""Path-independent private reproduction of A96+B64 fits; no network use."""
from pathlib import Path
import hashlib
import json
import math
import time
import traceback
import numpy as np
import pandas as pd
import cap_models as cap
import selective
import adaptive_scale as scale

ROOT = Path(__file__).resolve().parent
FAMILIES = ('capped','upper_free','positive_log')
A_LABELS = ([f'{f}_{s}' for f in FAMILIES for s in ['full','half']] +
            [f'proper_{f}_{s}' for f in FAMILIES for s in ['full','half']] +
            [f'project_{b}_{f}' for f in FAMILIES for b in ['mean8','xlarge']])
LABELS = A_LABELS + ['adaptive_project_mean8','adaptive_project_xlarge','unpenalized_transfer','half_strength']


def read(name):
    return json.loads((ROOT/name).read_text())


def load(name):
    with np.load(ROOT/name,allow_pickle=False) as z:
        assert all(z[k].dtype.kind != 'O' for k in z.files)
        return {k:z[k].copy() for k in z.files}


def exact(actual, expected):
    np.testing.assert_array_equal(actual,expected)


def fit(family,d,idx):
    part={k:d[k][idx].copy() for k in ['X62','BASE_CD','MEAS_CD','group','source']}
    return cap.fit(family,part,np.arange(len(idx)))


def group_folds(groups,k,seed):
    names=np.array(sorted(set(groups)))
    np.random.default_rng(seed).shuffle(names)
    return [np.isin(groups,names[i::k]) for i in range(k)]


def validate_membership(context,m,d):
    ids=np.arange(len(d['BASE_CD']))
    if context=='final':train,test=ids,np.array([],int)
    elif context.startswith('group_'):
        _,seed,_,fold=context.split('_')
        mask=group_folds(d['group'],5,int(seed))[int(fold)]
        train,test=ids[~mask],ids[mask]
    else:
        source=context[len('strict_source_'):]
        mask=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        train=ids[~mask & ~np.isin(d['group'],d['group'][mask])];test=ids[mask]
    exact(train,m['enclosing_indices']);exact(test,m['test_indices'])
    names=np.array(sorted(set(d['group'][train])),dtype=str)
    seed=int(hashlib.sha256(('selective_v1:2026090727:'+context).encode()).hexdigest()[:8],16)
    np.random.default_rng(seed).shuffle(names)
    mask=np.isin(d['group'][train],names[:math.ceil(len(names)/4)])
    exact(train[~mask],m['proper_indices']);exact(train[mask],m['calibration_indices'])


def outputs(models,cals,scale_model,scale_cal,d,idx,gate):
    b,xl=d['BASE_CD'][idx],d['XLARGE_CD'][idx]
    a,raw={},{}
    for f in FAMILIES:
        for branch,prefix in [('full',''),('proper','proper_')]:
            c=cap.predict(models[branch,f],d,idx);raw[f'{branch}_core_{f}']=c
            a[f'{prefix}{f}_full']=np.where(gate,c,b)
            a[f'{prefix}{f}_half']=np.where(gate,cap.half(c,b),b)
        c=raw[f'proper_core_{f}']
        for baseline,aa in [('mean8',b),('xlarge',xl)]:
            z=selective.project(cals[f],c,b,aa,gate)
            a[f'project_{baseline}_{f}']=z['prediction']
            a[f'project_{baseline}_{f}__intervened']=z['intervened']
        a[f'interval_lower_{f}'],a[f'interval_upper_{f}']=z['lower'],z['upper']
        a[f'interval_applicable_{f}']=z['applicable'];a['interval_applicable']=z['applicable']
        a[f'calibration_q_{f}']=np.full(len(idx),np.inf if cals[f]['q'] is None else cals[f]['q'])
    c=raw['proper_core_upper_free'];s=scale.predict(scale_model,d['X62'][idx]);v={}
    for baseline,aa in [('mean8',b),('xlarge',xl)]:
        z=scale.project(scale_cal,c,b,s,aa,gate)
        v[f'adaptive_project_{baseline}']=z['prediction'];v[f'adaptive_project_{baseline}__intervened']=z['intervened']
    v.update(proper_upper_free_full=np.where(gate,c,b),proper_upper_free_half=np.where(gate,cap.half(c,b),b),
        interval_lower=z['lower'],interval_upper=z['upper'],interval_applicable=z['applicable'],
        dimensionless_scale=s,scale_CD=z['scale_CD'],CORE_CD=c)
    return {**a,**raw},v


def compare(reference,values):
    for key,expected in reference.items():
        if key in values:exact(values[key],expected)
        else:raise AssertionError('Missing replay field '+key)


def panels(frame):
    out={}
    for seed in [20260906,20260908]:
        mask=frame.split.str.startswith(f'group_{seed}_').to_numpy()
        out[f'history_{seed}_pooled']=np.flatnonzero(mask)
        assert mask.sum()==8371 and frame.loc[mask,'nf2_row_id'].nunique()==8371
        for source in sorted(frame.loc[mask,'source'].unique()):
            out[f'history_{seed}_{source}']=np.flatnonzero(mask & frame.source.eq(source).to_numpy())
    for name in sorted(s for s in frame.split.unique() if s.startswith('strict_source_')):
        out[name]=np.flatnonzero(frame.split.eq(name).to_numpy())
    for name in ['SG_exposed','W_new_challenge']:
        mask=frame.split.eq(name).to_numpy()
        out[name+'_pooled']=np.flatnonzero(mask)
        for config in sorted(frame.loc[mask,'configuration'].unique()):
            out[name+'_'+config]=np.flatnonzero(mask & frame.configuration.eq(config).to_numpy())
        active=mask & frame.interval_applicable.to_numpy(bool)
        out[f'eligible_only/{name}/pooled']=np.flatnonzero(active)
        for config in sorted(frame.loc[mask,'configuration'].unique()):
            out[f'eligible_only/{name}/{config}']=np.flatnonzero(active & frame.configuration.eq(config).to_numpy())
    assert len(out)==31
    return out


def evaluate(frame,out):
    records,group_records,coverage=[],[],[]
    for name,ii in panels(frame).items():
        f=frame.iloc[ii];y=f.measured_CD.to_numpy()
        for label in LABELS:
            e=np.abs(f[label].to_numpy()-y)
            for baseline in ['mean8_CD','xlarge_CD']:
                be=np.abs(f[baseline].to_numpy()-y);delta=e-be
                records.append(dict(panel=name,candidate=label,baseline=baseline,rows=len(f),
                    mae_counts=e.mean()*1e4,median_counts=np.median(e)*1e4,p90_counts=np.percentile(e,90)*1e4,
                    baseline_mae_counts=be.mean()*1e4,reduction_percent=100*(1-e.mean()/be.mean()),
                    better_rows=int((delta < -1e-12).sum()),equal_rows=int((np.abs(delta)<=1e-12).sum()),
                    harmed_rows=int((delta>1e-12).sum()),mean_positive_excess_counts=np.maximum(delta,0).mean()*1e4,
                    maximum_excess_counts=max(float(delta.max()),0)*1e4))
                unit=f.group.to_numpy() if name.startswith(('history_','strict_source_')) else f.configuration.to_numpy()
                for g in sorted(set(unit)):
                    mask=unit==g
                    group_records.append(dict(panel=name,candidate=label,baseline=baseline,group=g,rows=int(mask.sum()),
                        mae_counts=e[mask].mean()*1e4,baseline_mae_counts=be[mask].mean()*1e4,
                        reduction_percent=100*(1-e[mask].mean()/be[mask].mean()),any_harmed_row=bool((delta[mask]>1e-12).any())))
        for family in list(FAMILIES)+['adaptive']:
            lower=f[f'lower_{family}'].to_numpy();upper=f[f'upper_{family}'].to_numpy();gate=f.interval_applicable.to_numpy(bool)
            hit=(y>=lower)&(y<=upper);tolhit=(y>=lower-1e-12)&(y<=upper+1e-12)
            unit=f.group.to_numpy() if name.startswith(('history_','strict_source_')) else f.configuration.to_numpy()
            eligible_groups=[g for g in sorted(set(unit)) if (gate & (unit==g)).any()]
            cov=np.mean([hit[gate & (unit==g)].all() for g in eligible_groups]) if eligible_groups else np.nan
            for baseline in ['mean8','xlarge']:
                label=f'project_{baseline}_{family}' if family!='adaptive' else f'adaptive_project_{baseline}'
                pred=f[label].to_numpy();b=f[baseline+'_CD'].to_numpy();intervened=pred!=b
                error_change=np.abs(pred-y)-np.abs(b-y)
                coverage.append(dict(panel=name,family=family,baseline=baseline,eligible_rows=int(gate.sum()),
                    eligible_bundles=len(eligible_groups),row_coverage=hit[gate].mean() if gate.any() else np.nan,
                    row_coverage_tolerance=tolhit[gate].mean() if gate.any() else np.nan,bundle_coverage=cov,
                    mean_width_counts=np.mean((upper-lower)[gate])*1e4 if gate.any() else np.nan,
                    interventions=int(intervened.sum()),exact_fallback_rows=int((~intervened).sum()),
                    harm_rate_among_interventions=np.mean(error_change[intervened]>1e-12) if intervened.any() else np.nan,
                    benefit_rate_among_interventions=np.mean(error_change[intervened]<-1e-12) if intervened.any() else np.nan))
    pd.DataFrame(records).to_csv(out/'panel_metrics.csv',index=False)
    pd.DataFrame(group_records).to_csv(out/'group_metrics.csv',index=False)
    pd.DataFrame(coverage).to_csv(out/'coverage_metrics.csv',index=False)
    return {'panels':31,'procedures':len(LABELS),'panel_metric_rows':len(records),'group_metric_rows':len(group_records),'coverage_rows':len(coverage)}


def main():
    started=time.monotonic();out=ROOT/'reproduced'
    assert not out.exists(),'Do not overwrite an earlier reproduction attempt'
    manifest=read('manifest.json')
    for name,h in manifest['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    import sklearn,scipy
    versions={'numpy':np.__version__,'scipy':scipy.__version__,'scikit-learn':sklearn.__version__,'pandas':pd.__version__}
    assert versions==manifest['observed_dependencies'],(versions,manifest['observed_dependencies'])
    out.mkdir()
    d=load('data/historical.npz');meta=load('data/evaluation.npz');frame=pd.DataFrame(meta)
    for label in LABELS[:-2]:frame[label]=np.nan
    counts={'A_core_fits':0,'A_calibrators':0,'B_inner_core_fits':0,'B_scale_fits':0,'B_calibrators':0}
    for context in manifest['contexts']:
        m=read('memberships/'+context+'.json');train=np.array(m['enclosing_indices']);proper=np.array(m['proper_indices']);cal=np.array(m['calibration_indices']);test=np.array(m['test_indices'],int)
        validate_membership(context,m,d)
        assert not set(d['group'][proper]) & set(d['group'][cal])
        assert not set(d['group'][train]) & set(d['group'][test])
        models,cals={},{}
        for family in FAMILIES:
            for branch,idx in [('full',train),('proper',proper)]:
                models[branch,family]=fit(family,d,idx);counts['A_core_fits']+=1
            cp=cap.predict(models['proper',family],d,cal)
            exact(cp,load('references/A_calibration_'+context+'.npz')['CORE_CD_'+family])
            cals[family]=selective.calibrate(cp,d['BASE_CD'][cal],d['MEAS_CD'][cal],d['group'][cal])
            assert cals[family]==m['A_calibrators'][family];counts['A_calibrators']+=1
        inner=np.full(len(proper),np.nan)
        generated=group_folds(d['group'][proper],3,2026090731)
        for fold,r in enumerate(m['inner_folds']):
            tr=np.array(r['train_indices']);te=np.array(r['test_indices'])
            exact(tr,proper[~generated[fold]]);exact(te,proper[generated[fold]])
            assert not set(d['group'][tr]) & set(d['group'][te])
            im=fit('upper_free',d,tr);counts['B_inner_core_fits']+=1
            inner[generated[fold]]=cap.predict(im,d,te)
        ref=load('references/B_training_'+context+'.npz');exact(inner,ref['INNER_OOF_CORE_CD'])
        target,weight=scale.training_arrays(d['MEAS_CD'][proper],inner,d['BASE_CD'][proper],d['group'][proper],d['source'][proper])
        exact(target,ref['scale_target']);exact(weight,ref['scale_weight'])
        sm=scale.fit(d['X62'][proper],d['MEAS_CD'][proper],inner,d['BASE_CD'][proper],d['group'][proper],d['source'][proper]);counts['B_scale_fits']+=1
        exact(scale.predict(sm,d['X62'][proper]),ref['dimensionless_scale'])
        core=cap.predict(models['proper','upper_free'],d,cal);s=scale.predict(sm,d['X62'][cal])
        cr=load('references/B_calibration_'+context+'.npz');exact(core,cr['CORE_CD']);exact(s,cr['dimensionless_scale']);exact(scale.scale_cd(d['BASE_CD'][cal],s),cr['scale_CD'])
        sc=scale.calibrate(core,d['BASE_CD'][cal],s,d['MEAS_CD'][cal],d['group'][cal]);assert sc==m['B_calibrator'];counts['B_calibrators']+=1
        cases=[(context,d,test if context!='final' else np.arange(len(d['BASE_CD'])),None)]
        if context=='final':
            cases += [(name,load('data/'+name+'.npz'),np.arange(n),name) for name,n in [('SG_exposed',242),('W_new_challenge',255)]]
        for name,data,idx,ext in cases:
            gate=data['gate'][idx] if ext else np.ones(len(idx),bool)
            av,bv=outputs(models,cals,sm,sc,data,idx,gate)
            compare(load('references/A_inference_'+name+'.npz'),av)
            compare(load('references/B_inference_'+name+'.npz'),bv)
            np.savez_compressed(out/('predictions_'+name+'.npz'),**av,**{k:v for k,v in bv.items() if k not in av})
            if name!='final':
                positions=np.array(manifest['evaluation_positions'][name])
                exact(frame.loc[positions,'mean8_CD'].to_numpy(),data['BASE_CD'][idx])
                for label in A_LABELS:frame.loc[positions,label]=av[label]
                for label in ['adaptive_project_mean8','adaptive_project_xlarge']:frame.loc[positions,label]=bv[label]
                for f in FAMILIES:
                    frame.loc[positions,'lower_'+f]=av['interval_lower_'+f];frame.loc[positions,'upper_'+f]=av['interval_upper_'+f]
                frame.loc[positions,'lower_adaptive']=bv['interval_lower'];frame.loc[positions,'upper_adaptive']=bv['interval_upper']
        print(json.dumps({'context':context,**counts}),flush=True)
    assert counts=={'A_core_fits':96,'A_calibrators':48,'B_inner_core_fits':48,'B_scale_fits':16,'B_calibrators':16}
    assert np.isfinite(frame[LABELS].to_numpy()).all()
    metrics=evaluate(frame,out);frame.to_csv(out/'all_row_predictions.csv',index=False)
    report={'status':'PASS','native_array_parity':'exact','calibrator_parity':'exact',**counts,**metrics,
            'observed_dependencies':versions,'seconds':time.monotonic()-started,
            'independent_environment':False,'archived_references_retrained':False,
            'warning':'Private same-installed-environment reproduction, not independent validation or redistribution clearance'}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        out=ROOT/'reproduced';out.mkdir(exist_ok=True)
        if not (out/'failure.txt').exists():(out/'failure.txt').write_text(traceback.format_exc())
        raise
