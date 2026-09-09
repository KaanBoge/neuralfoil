"""Independent memberships, calibration, native predictions and coverage replay.
No producer/assessor/selective imports. One diagnostic refit, not a new candidate.
Writes only review evidence, preserving a failure traceback if needed.
"""
from pathlib import Path
import hashlib,json,pickle,sys,traceback
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PROJECT=ROOT.parent
verified={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def same(a,b):np.testing.assert_array_equal(a,b)
def close(a,b):np.testing.assert_allclose(a,b,rtol=0,atol=1e-13)
def boolean(s):
    assert s.notna().all() and set(s.astype(str).str.lower())<={'true','false'}
    return s.astype(str).str.lower().eq('true').to_numpy()
def verify(mapping):
    for p,h in mapping.items():assert sha(p)==h,p;verified[p]=h
def native(model,x,b):
    return np.clip(b*(1+np.clip(model.predict(x),-.5,1)),.5*b,2*b)
def cmp(row,values):
    for k,v in values.items():
        if v is None:assert pd.isna(row[k]),(k,row[k])
        elif isinstance(v,(bool,np.bool_)):assert bool(row[k])==bool(v),(k,row[k],v)
        elif isinstance(v,(int,np.integer)):assert int(row[k])==int(v),(k,row[k],v)
        else:np.testing.assert_allclose(float(row[k]),v,rtol=0,atol=1e-10,err_msg=k)

def main():
    complete=read(ROOT/'results/complete.json');frozen=read(ROOT/'results/freeze.json')
    assert complete['freeze_sha256']==sha(ROOT/'results/freeze.json')
    assert frozen['external_outcomes_opened'] is False
    for obj in [complete,frozen]:
        for key in ['source_input_sha256','artifact_sha256','output_sha256','external_input_sha256']:
            if key in obj:verify(obj[key])
    # Authenticated shared data loader only; no training or assessment producer imported.
    sys.path.insert(0,str(PROJECT/'model_development_20260907_transition'))
    import shape_inputs
    d=shape_inputs.load_historical();n=len(d['BASE_CD']);assert n==8371
    gate=(d['Re']>0)&(d['Re']<=600000)&(abs(d['alpha'])<=12)&(d['X62'][:,2]>=.05)&(d['X62'][:,2]<=.20)
    assert gate.all(),'Historical calibration includes an ineligible row'
    ids=np.arange(n);tasks={}
    for seed in [20260906,20260908]:
        names=np.array(sorted(set(d['group'])));np.random.default_rng(seed).shuffle(names)
        for k in range(5):
            m=np.isin(d['group'],names[k::5]);tasks[f'group_{seed}_fold_{k}']=(ids[~m],ids[m])
    for source in sorted(set(d['source']))+['all_uiuc_volumes']:
        m=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        tr=~m&~np.isin(d['group'],d['group'][m]);tasks['strict_source_'+source]=(ids[tr],ids[m])
    tasks['final']=(ids,np.array([],int));assert set(tasks)==set(frozen['contexts'])
    records=[];prediction_values=0;refit_difference=None
    for name,(train,test) in tasks.items():
        rec=read(ROOT/f'results/membership_{name}.json')
        names=np.array(sorted(set(d['group'][train])))
        seed=int(hashlib.sha256(('selective_v1:2026090727:'+name).encode()).hexdigest()[:8],16)
        np.random.default_rng(seed).shuffle(names);ng=(len(names)+3)//4
        m=np.isin(d['group'][train],names[:ng]);proper,cal=train[~m],train[m]
        for key,idx in [('proper',proper),('calibration',cal),('test',test),('enclosing',train)]:
            same(rec[key+'_indices'],idx);same(rec[key+'_nf2_row_ids'],d['nf2_row_id'][idx])
        for a,b in [(proper,cal),(proper,test),(cal,test)]:assert not set(d['group'][a])&set(d['group'][b])
        assert rec['post_calibration_refit'] is False
        cp=ROOT/f'results/core_{name}.pkl';assert str(cp) in frozen['artifact_sha256']
        with cp.open('rb') as stream:model=pickle.load(stream)
        estimator=model['model'];assert model['family']=='hist62_regularized' and model['feature_key']=='X62'
        calibration=np.load(ROOT/f'results/calibration_{name}.npz')
        same(calibration['indices'],cal)
        for key in ['X62','BASE_CD','MEAS_CD','group']:same(calibration[key],d[key][cal])
        c=native(estimator,d['X62'][cal],d['BASE_CD'][cal]);same(c,calibration['CORE_CD'])
        groups=np.unique(d['group'][cal]);scores=np.array([max(abs(d['MEAS_CD'][cal][d['group'][cal]==g]-c[d['group'][cal]==g])/d['BASE_CD'][cal][d['group'][cal]==g]) for g in groups])
        k=(9*(len(groups)+1)+9)//10;q=np.inf if k>len(groups) else np.sort(scores)[k-1]
        calibrator=read(ROOT/f'results/calibrator_{name}.json')
        same(calibrator['group_ids'],groups);same(calibrator['group_scores'],scores)
        assert calibrator['rank']==k and calibrator['q']==(float(q) if np.isfinite(q) else None)
        # Diagnostic reproduction of first context only, independently constructed weights/settings.
        if refit_difference is None:
            sources=d['source'][proper];g=d['group'][proper]
            counts={(s,h):int(((sources==s)&(g==h)).sum()) for s,h in set(zip(sources,g))}
            members={s:len(set(g[sources==s])) for s in set(sources)}
            w=np.array([1/(counts[s,h]*members[s]) for s,h in zip(sources,g)]);w/=w.mean()
            b=d['BASE_CD'][proper];w=(1+w)/2*b;w/=w.mean()
            target=np.clip((d['MEAS_CD'][proper]-b)/b,-.5,1)
            fitted=HistGradientBoostingRegressor(loss='absolute_error',max_iter=400,max_leaf_nodes=15,min_samples_leaf=120,learning_rate=.035,l2_regularization=5,early_stopping=False,categorical_features=None,random_state=824).fit(d['X62'][proper],target,sample_weight=w)
            probe=np.r_[proper,cal,test];a=native(fitted,d['X62'][probe],d['BASE_CD'][probe]);z=native(estimator,d['X62'][probe],d['BASE_CD'][probe])
            refit_difference=float(abs(a-z).max());same(a,z)
        def replay(path,expected_d=None,expected_idx=None):
            nonlocal prediction_values
            z=np.load(path);x,b,xl,raw,g=[z[key] for key in ['X62','BASE_CD','XLARGE_CD','CORE_CD','gate']]
            if expected_d is not None:
                same(z['indices'],expected_idx)
                for key in ['X62','BASE_CD','XLARGE_CD']:same(z[key],expected_d[key][expected_idx])
            same(native(estimator,x,b),raw)
            lo=np.full(len(b),-np.inf);hi=-lo
            if np.isfinite(q):lo[g]=raw[g]-q*b[g];hi[g]=raw[g]+q*b[g]
            same(lo,z['interval_lower']);same(hi,z['interval_upper']);same(g,z['interval_applicable'])
            for label,a in [('project_mean8',b),('project_xlarge',xl)]:
                pred=np.clip(a,lo,hi);same(pred,z[label]);same(pred[~g],a[~g]);same(z[label+'__intervened'],pred!=a)
                prediction_values+=len(a)
            same(z['proper_core'],np.where(g,raw,b));same(z['proper_half'],np.where(g,b+.5*(raw-b),b))
        idx=test if name!='final' else ids
        replay(ROOT/f'results/inference_{name}.npz',d,idx)
        if name=='final':
            for ext,count in [('SG_exposed',242),('W_new_challenge',255)]:
                ex=shape_inputs.load_exposed(ext);assert len(ex['BASE_CD'])==count
                replay(ROOT/f'exposed_results/{ext}_inference.npz',ex,np.arange(count))
        records.append(dict(context=name,proper_rows=len(proper),calibration_rows=len(cal),calibration_groups=len(groups),rank=k,q=None if not np.isfinite(q) else float(q)))
    # Authenticate and reconstruct coverage from saved assessment values, separately from its functions.
    report=read(ROOT/'assessment/report.json');verify(report['input_source_sha256']);verify(report['output_sha256'])
    import audit_metrics as independent
    f=pd.read_csv(ROOT/'assessment/all_row_predictions.csv',low_memory=False)
    f['interval_applicable']=boolean(f.interval_applicable)
    for label in ['project_mean8','project_xlarge']:f[label+'__intervened']=boolean(f[label+'__intervened'])
    cv=pd.read_csv(ROOT/'assessment/coverage_metrics.csv').set_index('panel')
    bv=pd.read_csv(ROOT/'assessment/bundle_coverage.csv').set_index(['panel','bundle'])
    bundle_count=0;coverage_records=[]
    for panel,mask in independent.masks(f).items():
        part=f[mask].copy();g=part.interval_applicable.to_numpy();y=part.measured_CD.to_numpy();lo=part.interval_lower.to_numpy();hi=part.interval_upper.to_numpy();covered=(y>=lo)&(y<=hi);tolerant=(y>=lo-1e-12)&(y<=hi+1e-12)
        part['bundle']=np.where(part.split.isin(['SG_exposed','W_new_challenge']),part.split+':'+part.configuration.astype(str),part.group)
        part['covered']=covered;success=[]
        for bundle,h in part.groupby('bundle'):
            sub=h[h.interval_applicable];ok=None if not len(sub) else bool(sub.covered.all())
            if ok is not None:success.append(ok)
            vals=dict(rows=len(h),eligible_rows=len(sub),fully_covered_eligible_bundle=ok,eligible_row_coverage=None if not len(sub) else sub.covered.mean())
            for label,base in [('project_mean8','mean8_CD'),('project_xlarge','xlarge_CD')]:
                delta=abs(h[label]-h.measured_CD)-abs(h[base]-h.measured_CD)
                vals.update({label+'__any_harmed_row':bool((delta>1e-12).any()),label+'__worse_group_mae':bool(delta.mean()>1e-12),label+'__intervened_rows':int(h[label+'__intervened'].sum())})
            cmp(bv.loc[panel,bundle],vals);bundle_count+=1
        widths=(hi-lo)[g]
        vals=dict(rows=len(part),eligible_rows=int(g.sum()),outside_gate_rows_unassessed=int((~g).sum()),assessed_bundles=len(success),fully_covered_bundles=sum(success),eligible_row_coverage=covered[g].mean(),eligible_bundle_coverage=np.mean(success),covered_rows_at_1e12_tolerance=int(tolerant[g].sum()),covered_rows_exact_endpoints=int(covered[g].sum()),median_interval_width_CD=np.median(widths),mean_interval_width_CD=np.mean(widths),p90_interval_width_CD=np.quantile(widths,.9),unbounded_eligible_intervals=int(np.isinf(widths).sum()))
        for label,base in [('project_mean8','mean8_CD'),('project_xlarge','xlarge_CD')]:
            act=part[label+'__intervened'].to_numpy();delta=abs(part[label].to_numpy()-y)-abs(part[base].to_numpy()-y)
            assert not (act&~g).any();viol=covered&g&(delta>1e-12);assert not viol.any()
            vals.update({label+'__intervened_rows':int(act.sum()),label+'__intervention_fraction_all':act.mean(),label+'__intervention_fraction_eligible':act[g].mean(),label+'__worse_rows_vs_supplied_baseline':int((delta>1e-12).sum()),label+'__harm_fraction_among_interventions':(delta[act]>1e-12).mean() if act.any() else None,label+'__benefit_fraction_among_interventions':(delta[act]<-1e-12).mean() if act.any() else None,label+'__mean_signed_excess_error_among_interventions_CD':delta[act].mean() if act.any() else None,label+'__covered_target_projection_violations':int(viol.sum())})
        cmp(cv.loc[panel],vals)
        coverage_records.append({'panel':panel,**{k:(v.item() if isinstance(v,np.generic) else v) for k,v in vals.items()}})
    verify(verified.copy())
    result=dict(status='PASS',contexts=16,diagnostic_refits=1,refit_max_difference_CD=refit_difference,projection_reference_values=prediction_values,coverage_panels=31,bundle_records=bundle_count,hashes_verified=len(verified),contexts_detail=records,coverage=coverage_records,assessment_report_sha256=sha(ROOT/'assessment/report.json'),code_sha256=sha(Path(__file__)))
    (HERE/'selective_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ['contexts_detail','coverage']})

if __name__=='__main__':
    try:main()
    except BaseException:
        p=HERE/'audit_failure.json'
        with p.open('x') as s:json.dump({'traceback':traceback.format_exc()},s,indent=2)
        raise
