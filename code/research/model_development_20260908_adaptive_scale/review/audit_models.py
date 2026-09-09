"""Independent memberships, calibration, native predictions and coverage replay.
No producer/assessor/selective imports. One independent diagnostic scale refit.
Writes only review evidence.
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
    assert sha(ROOT/'results/freeze.json')=='9b2cdfb23b57d92c9f4f142170c5583296e5ec6be54e7c14a20af618cdf6b9a3'
    assert frozen['new_fit_count']==64 and frozen['inner_core_count']==48 and frozen['scale_count']==16 and frozen['calibrator_count']==16
    assert len(frozen['artifact_sha256'])==144
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
    records=[];prediction_values=0;refits=0
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


        aroot=PROJECT/'model_development_20260907_cap_ablation/results'
        inherited=read(aroot/f'membership_{name}.json')
        for key,value in inherited.items():
            if key in rec:assert rec[key]==value,(name,key)
            else:assert key in ['calibration_rank','calibration_q','unbounded','calibration_group_scores','calibration_input_excluded_label_mutation_identical'],key
        assert rec['post_calibration_refit'] is False
        corepath=aroot/f'core_{name}_proper_upper_free.pkl'
        assert sha(corepath)==rec['a_proper_core_sha256'] and str(corepath) in verified
        core=pickle.loads(corepath.read_bytes())['model']
        z=np.load(ROOT/f'results/scale_training_{name}.npz')
        for key in ['X62','BASE_CD','MEAS_CD','group','source']:same(z[key],d[key][proper])
        same(z['indices'],proper);same(z['nf2_row_id'],d['nf2_row_id'][proper])
        innernames=np.array(sorted(set(d['group'][proper])))
        np.random.default_rng(2026090731).shuffle(innernames)
        oof=np.full(len(proper),np.nan);seen=np.zeros(len(proper),int)
        for fold in range(3):
            mask=np.isin(d['group'][proper],innernames[fold::3])
            tr,te=proper[~mask],proper[mask];m=rec['inner_folds'][fold]
            for role,idx in [('train',tr),('test',te)]:
                same(m[role+'_indices'],idx);same(m[role+'_nf2_row_ids'],d['nf2_row_id'][idx])
                same(m[role+'_groups'],sorted(set(d['group'][idx])))
            assert not set(d['group'][tr])&set(d['group'][np.r_[te,cal,test]])
            inner=pickle.loads((ROOT/f'results/inner_core_{name}_fold_{fold}.pkl').read_bytes())
            assert inner['family']=='upper_free' and inner['model'].n_iter_==400
            oof[mask]=upper(inner['model'],d['X62'][te],d['BASE_CD'][te])
            same(z['inner_fold'][mask],np.full(mask.sum(),fold))
            seen[mask]+=1
        same(seen,np.ones(len(proper),int));same(oof,z['INNER_OOF_CORE_CD'])
        b,y=d['BASE_CD'][proper],d['MEAS_CD'][proper]
        target=np.log(np.maximum(abs(y-oof)/b,1e-6))
        sources=d['source'][proper];groups=d['group'][proper]
        counts={(s,g):int(((sources==s)&(groups==g)).sum()) for s,g in set(zip(sources,groups))}
        members={s:len(set(groups[sources==s])) for s in set(sources)}
        w=np.array([1/(counts[s,g]*members[s]) for s,g in zip(sources,groups)])
        w/=w.mean();w=(1+w)/2;w/=w.mean()
        same(target,z['scale_target']);same(w,z['scale_weight'])
        sm=pickle.loads((ROOT/f'results/scale_{name}.pkl').read_bytes())
        assert sm['scale_semantics']=='dimensionless_exp_log_residual_magnitude' and sm['target_floor']==1e-6
        estimator=sm['model'];assert estimator.n_iter_==200
        same(np.exp(estimator.predict(d['X62'][proper])),z['dimensionless_scale'])
        if not refits:
            independent=HistGradientBoostingRegressor(loss='absolute_error',max_iter=200,max_leaf_nodes=7,min_samples_leaf=120,learning_rate=.05,l2_regularization=5,random_state=829,early_stopping=False,categorical_features=None).fit(d['X62'][proper],target,sample_weight=w)
            probe=np.r_[proper,cal,test]
            same(independent.predict(d['X62'][probe]),estimator.predict(d['X62'][probe]))
            refits+=1
        c=upper(core,d['X62'][cal],d['BASE_CD'][cal]);sc=np.exp(estimator.predict(d['X62'][cal]))
        cz=np.load(ROOT/f'results/calibration_{name}.npz')
        for key in ['X62','BASE_CD','MEAS_CD','group','nf2_row_id']:same(cz[key],d[key][cal])
        same(c,np.load(aroot/f'calibration_{name}.npz')['CORE_CD_upper_free'])
        for key,value in [('indices',cal),('CORE_CD',c),('dimensionless_scale',sc),('scale_CD',d['BASE_CD'][cal]*sc)]:same(cz[key],value)
        names=np.unique(d['group'][cal]);scores=np.array([max((abs(d['MEAS_CD'][cal]-c)/(d['BASE_CD'][cal]*sc))[d['group'][cal]==g]) for g in names])
        k=(9*(len(names)+1)+9)//10;q=np.inf if k>len(names) else np.sort(scores)[k-1]
        calibrator=read(ROOT/f'results/calibrator_{name}.json')
        assert calibrator['scale_CD']=='mean8_CD * dimensionless_scale'
        assert calibrator['rank']==k and calibrator['q']==(q if np.isfinite(q) else None)
        same(calibrator['group_ids'],names);same(calibrator['group_scores'],scores)
        def replay(path,expected,idx,csvpath):
            nonlocal prediction_values
            zz=np.load(path)
            same(zz['indices'],idx)
            for key in ['X62','BASE_CD','XLARGE_CD']:same(zz[key],expected[key][idx])
            x,b,xl,g=[zz[key] for key in ['X62','BASE_CD','XLARGE_CD','gate']]
            assert g.dtype==bool
            same(g,(expected['Re'][idx]>0)&(expected['Re'][idx]<=600000)&(abs(expected['alpha'][idx])<=12)&(x[:,2]>=.05)&(x[:,2]<=.20))
            c=upper(core,x,b);s=np.exp(estimator.predict(x));u=b*s
            assert np.isfinite(s).all() and (s>0).all() and np.isfinite(u).all() and (u>0).all()
            for key,value in [('CORE_CD',c),('dimensionless_scale',s),('scale_CD',u)]:same(zz[key],value)
            lo=np.where(g,c-q*u,-np.inf);hi=np.where(g,c+q*u,np.inf)
            same(lo,zz['interval_lower']);same(hi,zz['interval_upper']);same(g,zz['interval_applicable'])
            csv=pd.read_csv(csvpath) if csvpath.exists() else None
            assert csv is not None or name=='final'
            for label,base in [('adaptive_project_mean8',b),('adaptive_project_xlarge',xl)]:
                pred=np.clip(base,lo,hi);same(pred,zz[label]);same(pred[~g],base[~g]);same(pred!=base,zz[label+'__intervened'])
                if csv is not None:close(pred,csv[label])
                prediction_values+=len(b)
            for label,p in [('proper_upper_free_full',c),('proper_upper_free_half',b+.5*(c-b))]:
                same(zz[label],np.where(g,p,b))
                if csv is not None:close(zz[label],csv[label])
                prediction_values+=len(b)
        idx=test if name!='final' else ids
        replay(ROOT/f'results/inference_{name}.npz',d,idx,ROOT/f'results/predictions_{name}.csv')
        if name=='final':
            for ext,count in [('SG_exposed',242),('W_new_challenge',255)]:
                ex=shape_inputs.load_exposed(ext);assert len(ex['BASE_CD'])==count
                replay(ROOT/f'exposed_results/{ext}_inference.npz',ex,np.arange(count),ROOT/f'exposed_results/{ext}_predictions.csv')
        records.append(dict(context=name,proper_rows=len(proper),calibration_rows=len(cal),q=float(q)))
    verify(verified.copy())
    result=dict(status='PASS',contexts=16,inner_cores=48,scale_models=16,calibrators=16,scale_refits=refits,refit_raw_prediction_max_difference=0.,prediction_values=prediction_values,hashes_verified=len(verified),contexts_detail=records,audit_code_sha256=sha(Path(__file__)),freeze_sha256=sha(ROOT/'results/freeze.json'))
    (HERE/'models_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='contexts_detail'})
def upper(model,x,b):return b*(1+np.maximum(model.predict(x),-.5))
if __name__=='__main__':main()
