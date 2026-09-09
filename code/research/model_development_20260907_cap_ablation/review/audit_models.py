"""Independent memberships, calibration, native predictions and coverage replay.
No producer/assessor/selective imports and no fitting.
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
    records=[];prediction_values=0;tree_pairs=[]
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

        prior=PROJECT/'model_development_20260907_selective/results'
        assert rec==read(prior/f'membership_{name}.json')
        calibration=np.load(ROOT/f'results/calibration_{name}.npz')
        same(calibration['indices'],cal)
        for key in ['X62','BASE_CD','MEAS_CD','group']:same(calibration[key],d[key][cal])
        models={}
        qs={}
        for family in ['capped','upper_free','positive_log']:
            for branch in ['full','proper']:
                cp=ROOT/f'results/core_{name}_{branch}_{family}.pkl'
                assert str(cp) in frozen['artifact_sha256']
                with cp.open('rb') as stream: obj=pickle.load(stream)
                assert obj['family']==family and obj['feature_key']=='X62'
                models[branch,family]=obj['model']
            est=models['proper',family]
            c=prediction(est,family,d['X62'][cal],d['BASE_CD'][cal])
            same(c,calibration['CORE_CD_'+family])
            groups=np.unique(d['group'][cal])
            scores=np.array([max(abs(d['MEAS_CD'][cal][d['group'][cal]==g]-c[d['group'][cal]==g])/d['BASE_CD'][cal][d['group'][cal]==g]) for g in groups])
            k=(9*(len(groups)+1)+9)//10
            q=np.inf if k>len(groups) else np.sort(scores)[k-1]
            obj=read(ROOT/f'results/calibrator_{name}_{family}.json')
            same(obj['group_ids'],groups);same(obj['group_scores'],scores)
            assert obj['rank']==k and obj['q']==(float(q) if np.isfinite(q) else None)
            qs[family]=q
            if family=='capped':
                assert obj==read(prior/f'calibrator_{name}.json')
                same(c,np.load(prior/f'calibration_{name}.npz')['CORE_CD'])
        for branch in ['full','proper']:
            a,z=models[branch,'capped'],models[branch,'upper_free']
            same(a._baseline_prediction,z._baseline_prediction)
            assert len(a._predictors)==len(z._predictors)==400
            for at,zt in zip(a._predictors,z._predictors):
                assert len(at)==len(zt)
                for x,y in zip(at,zt):
                    for field in ['nodes','binned_left_cat_bitsets','raw_left_cat_bitsets']:same(getattr(x,field),getattr(y,field))
            # Conservative sum of per-tree leaf extrema, not a reachable-input proof.
            upper=float(a._baseline_prediction.ravel()[0]+sum(t[0].nodes['value'][t[0].nodes['is_leaf'].astype(bool)].max() for t in a._predictors))
            tree_pairs.append(dict(context=name,branch=branch,identical=True,loose_raw_upper=upper))
        def replay(path,expected,idx,csvpath):
            nonlocal prediction_values
            z=np.load(path)
            same(z['indices'],idx)
            for key in ['X62','BASE_CD','XLARGE_CD']:same(z[key],expected[key][idx])
            x,b,xl,g=[z[k] for k in ['X62','BASE_CD','XLARGE_CD','gate']]
            assert g.dtype==bool
            expectedgate=(expected['Re'][idx]>0)&(expected['Re'][idx]<=600000)&(abs(expected['alpha'][idx])<=12)&(x[:,2]>=.05)&(x[:,2]<=.20)
            same(g,expectedgate)
            csv=pd.read_csv(csvpath) if csvpath.exists() else None
            assert csv is not None or (name=='final' and len(b)==8371)
            for family in ['capped','upper_free','positive_log']:
                for branch,prefix in [('full',''),('proper','proper_')]:
                    p=prediction(models[branch,family],family,x,b)
                    same(p,z[f'{branch}_core_{family}'])
                    for strength,value in [('full',p),('half',b+.5*(p-b))]:
                        label=prefix+family+'_'+strength
                        out=np.where(g,value,b)
                        same(out,z[label]);same(out[~g],b[~g]);prediction_values+=len(b)
                        if csv is not None:close(out,csv[label])
                raw=z['proper_core_'+family];q=qs[family]
                lo=np.where(g,raw-q*b,-np.inf);hi=np.where(g,raw+q*b,np.inf)
                same(lo,z['interval_lower_'+family]);same(hi,z['interval_upper_'+family])
                same(z['interval_applicable_'+family],g)
                for label,base in [('mean8',b),('xlarge',xl)]:
                    key='project_'+label+'_'+family;out=np.clip(base,lo,hi)
                    same(out,z[key]);same(out[~g],base[~g]);same(out!=base,z[key+'__intervened'])
                    if csv is not None:close(out,csv[key])
                    prediction_values+=len(b)
            # Native and archived CSV capped controls.
            old=np.load(prior/f'inference_{name}.npz') if name!='final' or len(b)==8371 else np.load(PROJECT/'model_development_20260907_selective/exposed_results'/path.name)
            same(z['proper_core_capped'],old['CORE_CD'])
            if name=='final' and len(b)==8371:
                witness=PROJECT/'model_development_20260907_risk_policy/results/historical_inference.npz'
                assert str(witness) in verified
                same(z['full_core_capped'],np.load(witness)['CORE_CD'])
            else:
                witness=PROJECT/'model_development_20260907_frontier/capacity'/('results' if len(b) not in [242,255] else 'exposed_results')/csvpath.name
                assert str(witness) in verified
                archived=pd.read_csv(witness)
                if 'nf2_row_id' in archived:
                    same(archived.nf2_row_id,expected['nf2_row_id'][idx])
                close(z['capped_full'],archived['hist62_regularized__1'])
                close(z['capped_half'],archived['hist62_regularized__0.5'])
        idx=test if name!='final' else ids
        replay(ROOT/f'results/inference_{name}.npz',d,idx,ROOT/f'results/predictions_{name}.csv')
        if name=='final':
            for ext,count in [('SG_exposed',242),('W_new_challenge',255)]:
                ex=shape_inputs.load_exposed(ext);assert len(ex['BASE_CD'])==count
                replay(ROOT/f'exposed_results/{ext}_inference.npz',ex,np.arange(count),ROOT/f'exposed_results/{ext}_predictions.csv')
        records.append(dict(context=name,proper_rows=len(proper),calibration_rows=len(cal),q=qs))
    verify(verified.copy())
    result=dict(status='PASS',contexts=16,cores=96,calibrators=48,prediction_values=prediction_values,identical_tree_pairs=tree_pairs,hashes_verified=len(verified),contexts_detail=records)
    (HERE/'models_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print({k:v for k,v in result.items() if k not in ['identical_tree_pairs','contexts_detail']})
def prediction(model,family,x,b):
    r=model.predict(x)
    if family=='capped': return np.clip(b*(1+np.clip(r,-.5,1)),.5*b,2*b)
    if family=='upper_free':return b*(1+np.maximum(r,-.5))
    return b*np.exp(r)
if __name__=='__main__':main()
