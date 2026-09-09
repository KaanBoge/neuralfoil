"""Historical-only global union; training and assessment strictly separated."""
from pathlib import Path
import importlib.util
import hashlib,json,sys,time,warnings
import numpy as np
import pandas as pd
from scipy.optimize import OptimizeWarning
import scipy,sklearn

HERE=Path(__file__).resolve().parent;FRONTIER=HERE.parent;PROJECT=FRONTIER.parent
PRIOR=PROJECT/'model_development_20260907_positive';OUT=HERE/'results'

def private(name):
    spec=importlib.util.spec_from_file_location(name,PRIOR/'historical_stack.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

loader=private('union_training_loader');solver=private('union_private_solver')
NEW={'capacity':['hist62_moderate','hist62_regularized','extra62_mixed','extra24_mixed'],'kernel':['kernel24_l1','kernel62_l1']}
COMPONENTS=loader.COMPONENTS+[name+'__1' for names in NEW.values() for name in names]
assert len(COMPONENTS)==len(set(COMPONENTS))==27
solver.COMPONENTS=COMPONENTS
original_linprog=solver.linprog
def one_thread_linprog(*args,**kwargs):
    kwargs['options']={**kwargs.get('options',{}),'threads':1}
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',category=OptimizeWarning,message='Unrecognized options detected')
        return original_linprog(*args,**kwargs)
solver.linprog=one_thread_linprog

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def ready(name):
    return all((FRONTIER/branch/'results'/('freeze.json' if name=='final' else 'log_'+name+'.json')).is_file() for branch in NEW)

def training(name):
    frame,enclosing,hashes=loader.load_training(name)
    originals=[loader.C3/'results'/f'{name}_inner_group.npz']+sorted((loader.C3/'results').glob(f'{name}_inner_transfer_*.npz'))
    for branch,names in NEW.items():
        newdir=FRONTIER/branch/'results'
        assert {p.name for p in originals}=={p.name for p in newdir.glob(f'{name}_inner_*.npz')}
        marker=newdir/('freeze.json' if name=='final' else 'log_'+name+'.json');assert marker.is_file();hashes[str(marker)]=sha(marker)
        for oldpath in originals:
            path=newdir/oldpath.name;hashes[str(path)]=sha(path)
            with np.load(oldpath) as old,np.load(path) as a:
                for key in ['indices','train_indices','test_indices']:
                    if key in old:np.testing.assert_array_equal(a[key],old[key])
                for key in ['identity','xlarge_fixed','cycle2_fixed__1','gate_shrink__1']:np.testing.assert_array_equal(a[key],old[key])
                context='group' if oldpath.stem.endswith('_inner_group') else oldpath.stem.split('_inner_',1)[1]
                mask=frame.context==context;idx=a['indices'] if context=='group' else a['test_indices']
                np.testing.assert_array_equal(frame.loc[mask,'historical_index'],idx)
                for family in names:frame.loc[mask,family+'__1']=a[family+'__1']
    assert np.isfinite(frame[COMPONENTS].to_numpy()).all() and (frame[COMPONENTS].to_numpy()>0).all()
    return frame,enclosing,hashes

def fit_one(name):
    f,idx,hashes=training(name);solution=solver.solve(f,solver.training_panels(f),['xlarge_CD','mean8_CD'])
    artifact={'split':name,'components':COMPONENTS,'unique_training_rows':len(idx),'prediction_context_rows':len(f),
              'training_nf2_row_ids':f.loc[f.context=='group','nf2_row_id'].tolist(),'training_groups':sorted(f.group.unique()),
              'input_sha256':hashes,'solutions':{'primary_union_both':solution},'status':'historical_only_inner_context_fit'}
    for p,h in hashes.items():assert sha(p)==h,p
    dump(OUT/f'weights_{name}.json',artifact)
    print(json.dumps({'fit_complete':name,'inner_worst_ratio':solution['actual_worst_training_ratio'],'seconds':solution['seconds']}),flush=True)

def evaluate():
    sys.path.insert(0,str(FRONTIER));import frontier_assessment as assess
    frame,oldcols,labels,hashes=assess.load_frame(['capacity','kernel'])
    for branch,names in NEW.items():
        for name in names:frame[name+'__1']=frame[branch+'__'+name+'__1']
    label='primary_union_both';frame[label]=np.nan
    for split in frame.split.unique():
        external=split in ['SG_exposed','W_new_challenge'];artifact=json.loads((OUT/f"weights_{'final' if external else split}.json").read_text())
        mask=frame.split==split;f=frame.loc[mask];w=np.array([artifact['solutions'][label]['weights'][c] for c in COMPONENTS])
        if not external:
            assert set(f.nf2_row_id).isdisjoint(artifact['training_nf2_row_ids']);assert set(f.group).isdisjoint(artifact['training_groups'])
        pred=f[COMPONENTS].to_numpy()@w
        if external:
            gate=f.inference_gate.map(lambda v:str(v).lower()=='true' or v==1).to_numpy(bool);assert gate.sum()=={'SG_exposed':234,'W_new_challenge':238}[split]
            pred[~gate]=f.mean8_CD.to_numpy()[~gate]
        assert np.isfinite(pred).all() and (pred>0).all();frame.loc[mask,label]=pred
    panels=assess.old.panels(frame);panels.update({k:v for k,v in assess.reconcile.external_panels(frame).items() if k.startswith('eligible_only/')})
    metrics=assess.old.metrics(frame,frame[label].to_numpy(),panels,label);assert len(metrics)==31
    metrics.to_csv(OUT/'panel_metrics.csv',index=False);frame.to_csv(OUT/'all_row_predictions.csv',index=False)
    groups=[]
    for split in frame.split.unique():
        f=frame[frame.split==split];field='airfoil' if split in ['SG_exposed','W_new_challenge'] else 'group'
        for group in sorted(f[field].dropna().unique()):
            ix=np.flatnonzero((frame.split==split)&(frame[field]==group));groups.append(assess.old.metrics(frame,frame[label].to_numpy(),{split+':'+str(group):ix},label))
    pd.concat(groups,ignore_index=True).to_csv(OUT/'identity_group_metrics.csv',index=False)
    metrics.loc[(metrics.xlarge_CD_improvement_percent<0)|(metrics.mean8_CD_improvement_percent<0)].to_csv(OUT/'worsening_panels.csv',index=False)
    for p,h in hashes.items():assert sha(p)==h,p
    dump(OUT/'report.json',{'status':'adaptive_historical_only_union_not_calibration','components':COMPONENTS,'input_sha256':hashes,'evaluation_helper_sha256':sha(FRONTIER/'frontier_assessment.py'),'panel_count':31,'rows':len(frame)})

def main():
    OUT.mkdir(exist_ok=False)
    names=[p.stem.removeprefix('predictions_') for p in sorted((loader.C3/'results').glob('predictions_*.csv'))]+['final'];assert len(names)==16
    paths=[Path(__file__),HERE/'PROTOCOL.md',FRONTIER/'UNION_PROTOCOL.md',PRIOR/'historical_stack.py',Path(loader.v2.__file__),Path(loader.v2.old.__file__)]
    paths += [FRONTIER/b/file for b,file in [('capacity','capacity_models.py'),('capacity','run_capacity.py'),('kernel','kernel_models.py'),('kernel','run_kernel.py')]]
    hashes={str(p):sha(p) for p in paths}
    dump(OUT/'manifest.json',{'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hashes':hashes,'components':COMPONENTS,'names':names,'workers':1,'highs_threads':1,'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__})
    pending=names.copy()
    while pending:
        progressed=False
        for name in pending.copy():
            if ready(name):fit_one(name);pending.remove(name);progressed=True
        if pending and not progressed:time.sleep(10)
    for p,h in hashes.items():assert sha(p)==h,p
    dump(OUT/'freeze.json',{'status':'all16historical_only_weight_fits_complete_before_evaluation','weights_sha256':{str(p):sha(p) for p in OUT.glob('weights_*.json')}})
    while not all((FRONTIER/b/'results/results.json').is_file() for b in NEW):time.sleep(5)
    evaluate()
    for p,h in hashes.items():assert sha(p)==h,p
    print('COMPLETE historical-only 27-component union',flush=True)

if __name__=='__main__':main()
