"""Independent neural equation/split replay; no fits or producer helper import."""
from pathlib import Path
import hashlib,json,pickle,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROUND=HERE.parent
PROJECT=ROUND.parent
BRANCH=ROUND/'neural'
sys.path.insert(0,str(PROJECT/'model_development_20260907_transition'))
import shape_inputs

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def forward(m,x,b):
    span=m['scale'];z=np.clip((x-m['center'])/np.where(span>0,span,1),-3,3);z[:,span==0]=0
    est=m['model'];raw=(np.tanh(z@est.coefs_[0]+est.intercepts_[0])@est.coefs_[1]+est.intercepts_[1]).ravel()
    return np.clip(b*(1+np.clip(raw,-.5,1)),.5*b,2*b),raw

def main():
    freeze=json.loads((BRANCH/'results/freeze.json').read_text())
    report=json.loads((BRANCH/'results/report.json').read_text())
    hashes={**freeze['source_input_sha256'],**freeze['artifact_sha256']}
    for p,h in hashes.items():assert sha(p)==h,p
    d=shape_inputs.load_historical();ids=np.arange(8371);cases=[]
    for seed in [20260906,20260908]:
        for k,test in enumerate(shape_inputs.transition.v2.old.group_folds(d['group'],5,seed)):
            cases.append((f'group_{seed}_fold_{k}',ids[~test],ids[test]))
    for source in sorted(set(d['source']))+['all_uiuc_volumes']:
        test=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        train=~test&~np.isin(d['group'],d['group'][test]);cases.append(('strict_source_'+source,ids[train],ids[test]))
    cases.append(('final',ids,ids));records=[];maxdelta=0.;final=[]
    for name,tr,te in cases:
        log=json.loads((BRANCH/f'results/log_{name}.json').read_text())
        np.testing.assert_array_equal(log['training_nf2_row_ids'],d['nf2_row_id'][tr])
        if name!='final':assert not set(d['group'][tr])&set(d['group'][te])
        frame=pd.read_csv(BRANCH/f'results/predictions_{name}.csv') if name!='final' else None
        if frame is not None:np.testing.assert_array_equal(frame.nf2_row_id,d['nf2_row_id'][te])
        pred=[]
        for seed in [824,825,826]:
            path=BRANCH/f'results/fit_{name}_seed{seed}.pkl';assert sha(path)==freeze['artifact_sha256'][str(path)]
            with path.open('rb') as handle:m=pickle.load(handle)
            np.testing.assert_array_equal(m['center'],np.median(d['X62'][tr],axis=0))
            q=np.quantile(d['X62'][tr],[.05,.95],axis=0);np.testing.assert_array_equal(m['scale'],q[1]-q[0])
            assert m['seed']==seed
            est=m['model'];assert sum(c.size for c in est.coefs_)+sum(c.size for c in est.intercepts_)==1025
            p,raw=forward(m,d['X62'][te],d['BASE_CD'][te]);pred.append(p)
            if frame is not None:maxdelta=max(maxdelta,float(abs(p-frame[f'neural62_seed{seed}']).max()))
            else:final.append(m)
            # Recompute weighted squared CD-to-clipped-target objective independently.
            _,raw=forward(m,d['X62'][tr],d['BASE_CD'][tr]);pairs=list(zip(d['source'][tr],d['group'][tr]))
            counts={};members={}
            for s,g in pairs:counts[s,g]=counts.get((s,g),0)+1;members.setdefault(s,set()).add(g)
            w=np.array([1/(counts[s,g]*len(members[s])) for s,g in pairs]);w/=w.mean()
            b=d['BASE_CD'][tr];w=(1+w)/2*b*b;w/=w.mean();target=np.clip((d['MEAS_CD'][tr]-b)/b,-.5,1)
            loss=(w@(raw-target)**2+10*sum(np.square(c).sum() for c in est.coefs_))/(2*w.sum())
            assert abs(loss-est.loss_)<1e-12
            records.append({'split':name,'seed':seed,'loss_difference':float(loss-est.loss_),'iterations':int(est.n_iter_),'warnings':m['diagnostics']['warnings']})
        if frame is not None:
            full=np.mean(pred,axis=0)
            for s in [.5,1.]:maxdelta=max(maxdelta,float(abs(d['BASE_CD'][te]+s*(full-d['BASE_CD'][te])-frame[f'neural62__{s:g}']).max()))
    for name,n,eligible in [('SG_exposed',242,234),('W_new_challenge',255,238)]:
        ex=shape_inputs.load_exposed(name);f=pd.read_csv(BRANCH/f'exposed_results/{name}_predictions.csv');gate=f.inference_gate.to_numpy()
        assert len(f)==n and gate.dtype==bool and gate.sum()==eligible
        np.testing.assert_array_equal(f.Re,ex['Re']);np.testing.assert_array_equal(f.alpha,ex['alpha'])
        preds=[]
        for seed,m in zip([824,825,826],final):
            p,_=forward(m,ex['X62'],ex['BASE_CD']);preds.append(p)
            maxdelta=max(maxdelta,float(abs(np.where(gate,p,ex['BASE_CD'])-f[f'neural62_seed{seed}']).max()))
        full=np.mean(preds,axis=0)
        for s in [.5,1.]:
            p=np.where(gate,ex['BASE_CD']+s*(full-ex['BASE_CD']),ex['BASE_CD'])
            np.testing.assert_array_equal(p[~gate],ex['BASE_CD'][~gate])
            maxdelta=max(maxdelta,float(abs(p-f[f'neural62__{s:g}']).max()))
    assert len(records)==48 and maxdelta<1e-12
    result={'status':'PASS','models':48,'hashes_verified':len(hashes),'max_saved_prediction_difference_CD':maxdelta,'warning_fits':sum(bool(r['warnings']) for r in records),'records':records}
    (HERE/'neural_audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k!='records'})

if __name__=='__main__':main()
