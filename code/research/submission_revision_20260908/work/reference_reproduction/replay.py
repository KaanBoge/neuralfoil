"""Path-relative frozen reference replay. No data reads or fitting on import."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import platform
import sys
import time
import traceback
import numpy as np
import pandas as pd
import scipy
import sklearn

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
import capacity_models as cap
import risk_policy as policy


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def dump(p,value):
    with Path(p).open('x') as f: json.dump(value,f,indent=2,allow_nan=False)
def load(p):
    with np.load(p,allow_pickle=False) as z:
        a={k:z[k].copy() for k in z.files}
    if any(v.dtype.kind=='O' for v in a.values()): raise ValueError('Object dtype')
    return a
def exact(a,b): np.testing.assert_array_equal(a,b)
def group_folds(groups,k,seed):
    names=np.array(sorted(set(groups)))
    np.random.default_rng(seed).shuffle(names)
    return [np.isin(groups,names[i::k]) for i in range(k)]
def csv_roundtrip(a):
    return pd.read_csv(io.StringIO(pd.DataFrame({'value':a}).to_csv(index=False))).value.to_numpy()


def roles(d,name):
    ids=np.arange(len(d['BASE_CD']))
    if name=='final': return ids,np.array([],int)
    if name.startswith('group_'):
        _,seed,_,fold=name.split('_');test=group_folds(d['group'],5,int(seed))[int(fold)]
    else:
        source=name.removeprefix('strict_source_')
        test=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
    return ids[~test & ~np.isin(d['group'],d['group'][test])],ids[test]


def transfers(d,tr):
    for source in sorted(set(d['source'][tr])):
        te=d['source'][tr]==source
        train=~te & ~np.isin(d['group'][tr],d['group'][tr[te]])
        support=len(set(d['group'][tr[train]]))>=6 and train.sum()>=300
        yield source,tr[train],tr[te],support


def policy_inputs(d,gi,gc,ti,tc):
    blocks=[(gi,gc)]+([(ti,tc)] if len(ti) else [])
    weights=[]
    for idx,_ in blocks:
        w=(1.+cap.balanced_weights(d['group'][idx],d['source'][idx]))/2.
        weights.append(w/w.sum()/len(blocks))
    ids=np.concatenate([x[0] for x in blocks]);core=np.concatenate([x[1] for x in blocks])
    return {'base':d['BASE_CD'][ids], 'core':core,'y':d['MEAS_CD'][ids],
            'all_model_CD':d['all_model_CD'][ids],'weights':np.concatenate(weights),
            'feature_reference':(d['BASE_CD'][gi],gc,d['all_model_CD'][gi])}


def preflight():
    if sys.flags.optimize: raise ValueError('Do not use Python -O')
    expected={'python':'3.12.14','numpy':'2.3.5','scipy':'1.16.1','sklearn':'1.7.1','pandas':'2.2.3'}
    actual={'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,
            'sklearn':sklearn.__version__,'pandas':pd.__version__}
    if actual!=expected: raise ValueError(('Runtime mismatch',actual,expected))
    frozen=read(HERE/'source_manifest.json');inputs=read(HERE/'input_manifest.json')
    for name,h in {**frozen['files'],**inputs['files']}.items():
        if sha(HERE/name)!=h: raise ValueError('Hash mismatch: '+name)
    d=load(HERE/'data/historical.npz')
    if d['X62'].shape!=(8371,62) or len(set(d['group']))!=93: raise ValueError('Cohort changed')
    counts={'enclosing':0,'group_inner':0,'transfer_inner':0,'policies':0};records=[]
    for name in inputs['contexts']:
        m=read(HERE/'memberships'/(name+'.json'));tr,te=roles(d,name)
        exact(tr,m['train']);exact(te,m['test'])
        if set(d['group'][tr]) & set(d['group'][te]): raise ValueError('Outer identity overlap')
        g=load(HERE/'references'/(name+'_inner_group.npz'));exact(g['indices'],tr)
        for mask in group_folds(d['group'][tr],3,20260907):
            if set(d['group'][tr[mask]]) & set(d['group'][tr[~mask]]): raise ValueError('Inner overlap')
            counts['group_inner']+=1
        available=[]
        for source,a,b,ok in transfers(d,tr):
            if not ok: continue
            z=load(HERE/'references'/(name+'_inner_transfer_'+source+'.npz'))
            exact(a,z['train']);exact(b,z['test'])
            if set(d['group'][a])&set(d['group'][b]) or source in set(d['source'][a]): raise ValueError('Transfer overlap')
            counts['transfer_inner']+=1;available.append(source)
        if available!=[v['source'] for v in m['transfer_log'] if v['status']=='used']: raise ValueError('Support changed')
        # No excluded outcome enters the policy input construction; test before fitting.
        args=policy_inputs(d,tr,g['core'],np.array([],int),np.array([],float))
        changed={**d,'MEAS_CD':d['MEAS_CD'].copy()};changed['MEAS_CD'][np.setdiff1d(np.arange(8371),tr)]=np.nan
        altered=policy_inputs(changed,tr,g['core'],np.array([],int),np.array([],float))
        exact(args['y'],altered['y'])
        counts['enclosing']+=1;counts['policies']+=1
        records.append({'context':name,'train_rows':len(tr),'test_rows':len(te),'transfer_sources':available,
                        'excluded_label_mutation_inputs_identical':True})
    if counts!=inputs['planned']: raise ValueError(('Planned fit counts',counts))
    return d,inputs,{'status':'PASS','versions':actual,'planned':counts,'roles':records,
                   'source_manifest_sha256':sha(HERE/'source_manifest.json'),'input_manifest_sha256':sha(HERE/'input_manifest.json')}


def execute(out):
    if out.exists(): raise FileExistsError('Preserve existing attempt: '+str(out))
    d,inputs,check=preflight()
    out.mkdir(parents=True,exist_ok=False)
    counts={'enclosing':0,'group_inner':0,'transfer_inner':0,'policies':0};logs=[]
    final_core=final_policy=None
    try:
        dump(out/'preflight.json',check)
        def fit(tr):
            # Only matching training labels exist in the supplied model dictionary.
            part={k:d[k][tr].copy() for k in ['X62','BASE_CD','MEAS_CD','group','source']}
            return cap.fit('hist62_regularized',part,np.arange(len(tr)))
        for name in inputs['contexts']:
            start=time.monotonic();tr,te=roles(d,name);m=read(HERE/'memberships'/(name+'.json'))
            gc=np.full(len(tr),np.nan)
            for fold,mask in enumerate(group_folds(d['group'][tr],3,20260907)):
                model=fit(tr[~mask]);counts['group_inner']+=1
                gc[mask]=cap.predict(model,d,tr[mask])
            exact(gc,load(HERE/'references'/(name+'_inner_group.npz'))['core'])
            np.savez_compressed(out/(name+'_group.npz'),indices=tr,core=gc)
            ti=[];tc=[]
            for source,a,b,ok in transfers(d,tr):
                if not ok: continue
                model=fit(a);counts['transfer_inner']+=1;cp=cap.predict(model,d,b)
                exact(cp,load(HERE/'references'/(name+'_inner_transfer_'+source+'.npz'))['core'])
                ti.append(b);tc.append(cp)
                np.savez_compressed(out/(name+'_transfer_'+source+'.npz'),train=a,test=b,core=cp)
            ti=np.concatenate(ti) if ti else np.array([],int);tc=np.concatenate(tc) if tc else np.array([],float)
            args=policy_inputs(d,tr,gc,ti,tc)
            fitted=policy.fit(**args,penalty=0.);counts['policies']+=1
            if fitted!=m['policy_reference']:
                dump(out/(name+'_policy_mismatch.json'),{'actual':fitted,'expected':m['policy_reference']})
                raise ValueError('Exact policy dictionary mismatch: '+name)
            dump(out/('policy_'+name+'.json'),fitted)
            core=fit(tr);counts['enclosing']+=1
            if name=='final': final_core,final_policy=core,fitted
            else:
                native=cap.predict(core,d,te);serialized=csv_roundtrip(native)
                ref=load(HERE/'references'/(name+'_outer.npz'));exact(d['nf2_row_id'][te],ref['nf2_row_id'])
                exact(serialized,ref['core_csv'])
                pred,strength=policy.predict(fitted,d['BASE_CD'][te],serialized,d['all_model_CD'][te],np.ones(len(te),bool))
                exact(csv_roundtrip(pred),ref['prediction_csv']);exact(csv_roundtrip(strength),ref['strength_csv'])
                half=d['BASE_CD'][te]+.5*(native-d['BASE_CD'][te]);exact(csv_roundtrip(half),ref['half_csv'])
                np.savez_compressed(out/(name+'_outer.npz'),indices=te,native_core=native,serialized_core=serialized,
                    prediction=pred,strength=strength,half=half)
                drift=float(np.max(np.abs(native-serialized)))
            logs.append({'context':name,'seconds':time.monotonic()-start,'counts':dict(counts),
                         'max_core_csv_drift':None if name=='final' else drift})
            print(json.dumps(logs[-1]),flush=True)
        if counts!=inputs['planned']: raise ValueError('Actual count mismatch')
        paths=[out/('policy_'+name+'.json') for name in inputs['contexts']]
        dump(out/'freeze.json',{'policy_count':16,'counts':counts,'external_inference_started':False,
            'policy_sha256':{p.name:sha(p) for p in paths},'preflight_sha256':sha(out/'preflight.json')})
        # All 16 policies are now frozen; external arrays contain no labels.
        for name in ['historical','SG_exposed','W_new_challenge']:
            x=d if name=='historical' else load(HERE/'data'/(name+'.npz'))
            idx=np.arange(len(x['BASE_CD']));gate=np.ones(len(idx),bool) if name=='historical' else x['gate']
            c=cap.predict(final_core,x,idx);ref=load(HERE/'references'/(name+'_final.npz'));exact(c,ref['CORE_CD'])
            pred,strength=policy.predict(final_policy,x['BASE_CD'],c,x['all_model_CD'],gate)
            exact(pred,ref['prediction']);exact(pred[~gate],x['BASE_CD'][~gate])
            half=np.where(gate,x['BASE_CD']+.5*(c-x['BASE_CD']),x['BASE_CD'])
            np.savez_compressed(out/(name+'_final.npz'),core=c,prediction=pred,strength=strength,half=half,gate=gate)
        preflight()
        dump(out/'complete.json',{'status':'PASS','counts':counts,'Hist_fits':120,'LP_solves':32,
            'policy_fits':16,'native_parity':'exact','policy_numeric_parity':'exact','historical_CSV_parity':'exact',
            'logs':logs,'freeze_sha256':sha(out/'freeze.json'),
            'output_sha256':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()},
            'same_installed_environment':True,'new_accuracy_experiment':False})
    except BaseException:
        dump(out/'failure.json',{'status':'FAIL','counts':counts,'logs':logs,'traceback':traceback.format_exc()})
        raise


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','run']);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.mode=='preflight': print(json.dumps(preflight()[2],indent=2))
    else:
        if a.output is None: p.error('--output required')
        execute(a.output.resolve())


if __name__=='__main__': main()
