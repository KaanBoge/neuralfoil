"""Read-only trained-model, preprocessing, objective and prediction replay."""
from pathlib import Path
import json,pickle,sys,hashlib
import numpy as np
import pandas as pd
import neural_models as models
HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[1]
sys.path.insert(0,str(PROJECT/'model_development_20260907_transition'));import shape_inputs as inputs
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=HERE/'results';freeze=json.loads((out/'freeze.json').read_text());report=json.loads((out/'report.json').read_text())
    assert freeze['model_count']==48 and not freeze['external_scored_at_freeze']
    for p,h in {**freeze['artifact_sha256'],**freeze['source_input_sha256']}.items():assert sha(p)==h
    d=inputs.load_historical();lookup={int(v):i for i,v in enumerate(d['nf2_row_id'])};maxloss=maxpred=maxnumpy=0.;checks=0
    for log in freeze['logs']:
        name=log['split'];tr=np.array([lookup[int(v)] for v in log['training_nf2_row_ids']]);isfinal=name=='final'
        if isfinal:te=np.arange(8371);frame=None
        else:
            frame=pd.read_csv(out/f'predictions_{name}.csv');te=np.array([lookup[int(v)] for v in frame.nf2_row_id]);assert not set(d['group'][tr])&set(d['group'][te])
        seedpred=[]
        for seed in models.SEEDS:
            path=out/f'fit_{name}_seed{seed}.pkl';assert sha(path)==freeze['artifact_sha256'][str(path)]
            with path.open('rb') as f:m=pickle.load(f)
            q=np.quantile(d['X62'][tr],[.05,.95],axis=0)
            np.testing.assert_array_equal(m['center'],np.median(d['X62'][tr],axis=0));np.testing.assert_array_equal(m['scale'],q[1]-q[0])
            x=models.transform(d['X62'][tr],m['center'],m['scale']);est=m['model'];raw=est.predict(x)
            base=d['BASE_CD'][tr];target=np.clip((d['MEAS_CD'][tr]-base)/base,-.5,1.)
            w=(1+models.balanced_weights(d['group'][tr],d['source'][tr]))/2*base**2;w/=w.mean()
            objective=.5*np.average((raw-target)**2,weights=w)+10*sum(np.sum(c*c) for c in est.coefs_)/(2*w.sum())
            maxloss=max(maxloss,abs(objective-est.loss_));assert abs(objective-est.loss_)<1e-9
            xx=models.transform(d['X62'][te],m['center'],m['scale']);nr=(np.tanh(xx@est.coefs_[0]+est.intercepts_[0])@est.coefs_[1]+est.intercepts_[1]).ravel()
            npcd=np.clip(d['BASE_CD'][te]*(1+np.clip(nr,-.5,1.)),.5*d['BASE_CD'][te],2*d['BASE_CD'][te])
            pred=models.predict(m,d,te);maxnumpy=max(maxnumpy,float(abs(pred-npcd).max()));seedpred.append(pred)
            altered=dict(d,MEAS_CD=np.full(8371,np.nan),source=np.full(8371,'changed'),group=np.full(8371,'changed'))
            np.testing.assert_array_equal(models.predict(m,altered,te),pred)
            assert models.predict(m,d,np.array([],dtype=int)).shape==(0,)
            if frame is not None:maxpred=max(maxpred,float(abs(pred-frame[f'neural62_seed{seed}']).max()))
            checks+=1
        if frame is not None:
            full=np.mean(seedpred,axis=0)
            for strength in [.5,1.]:maxpred=max(maxpred,float(abs(d['BASE_CD'][te]+strength*(full-d['BASE_CD'][te])-frame[f'neural62__{strength:g}']).max()))
    np.testing.assert_array_equal(models.transform(np.array([[1.,-1e9],[2.,1e9]]),np.array([0.,5.]),np.array([1.,0.])),np.array([[1.,0.],[2.,0.]]))
    for name in ['SG_exposed','W_new_challenge']:
        ext=inputs.load_exposed(name);frame=pd.read_csv(HERE/'exposed_results'/f'{name}_predictions.csv');g=frame.inference_gate.to_numpy(bool);seeds=[];ix=np.arange(len(g))
        for seed in models.SEEDS:
            path=out/f'fit_final_seed{seed}.pkl';assert sha(path)==freeze['artifact_sha256'][str(path)]
            with path.open('rb') as f:m=pickle.load(f)
            pred=models.predict(m,ext,ix);seeds.append(pred)
            maxpred=max(maxpred,float(abs(np.where(g,pred,ext['BASE_CD'])-frame[f'neural62_seed{seed}']).max()))
        full=np.mean(seeds,axis=0)
        for strength in [.5,1.]:maxpred=max(maxpred,float(abs(np.where(g,ext['BASE_CD']+strength*(full-ext['BASE_CD']),ext['BASE_CD'])-frame[f'neural62__{strength:g}']).max()))
    assert maxpred<1e-12 and maxnumpy<1e-12
    result={'status':'PASS objective/scaling/native/NumPy-equation replay no refits','models_checked':checks,'max_abs_objective_difference':maxloss,'max_abs_saved_prediction_CD':maxpred,'max_abs_numpy_tanh_equation_CD':maxnumpy,'warning_fits':sum(bool(x['warnings']) for x in report['all_fit_diagnostics']),'source_sha256':sha(Path(__file__))}
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
