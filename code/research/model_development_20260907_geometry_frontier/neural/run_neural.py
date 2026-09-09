"""48 fixed neural fits; preserve failures and freeze before exposed scoring."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib,json,pickle,sys,time,traceback
import numpy as np
import pandas as pd
import sklearn
import neural_models as models

HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[1]
CAP=PROJECT/'model_development_20260907_frontier/capacity'
C4=PROJECT/'model_development_20260907_transition'
sys.path.insert(0,str(C4));import shape_inputs as inputs
v2=inputs.transition.v2;OUT=HERE/'results'
LABELS=['neural62__0.5','neural62__1']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def verify_prior_provenance():
    front=PROJECT/'model_development_20260907_frontier'
    witnesses=[front/'assessment_final/report.json',CAP/'results/run_manifest.json',PROJECT/'model_development_20260906_v2/results/run_manifest.json']
    assessment=json.loads(witnesses[0].read_text())['input_sha256']
    capacity=json.loads(witnesses[1].read_text())['hashes']
    original=json.loads(witnesses[2].read_text())['hashes']
    expected={}
    files=list((CAP/'results').glob('predictions_*.csv'))+[CAP/'exposed_results'/f'{name}_predictions.csv' for name in ['SG_exposed','W_new_challenge']]
    assert len(files)==17
    for p in files:expected[str(p)]=assessment[str(p)]
    for section in ['inputs','shape_inputs']:
        for cohort in ['historical','SG_exposed','W_new_challenge']:
            p=C4/section/f'{cohort}.npz';expected[str(p)]=capacity[str(p)]
    old=PROJECT/'model_development_20260906'
    for relative in ['reproduction/dataset_occurrence.npz','methods_audit/entry_group_map.csv','methods_audit/ambiguous_nf2_row_ids.csv']:
        p=old/relative;expected[str(p)]=original[str(p)]
    for p,h in expected.items():assert sha(p)==h,p
    record={'status':'verified_against_recorded_prior_hashes_before_any_data_load','input_expected_sha256':expected,'witness_json_sha256':{str(p):sha(p) for p in witnesses}}
    dump(OUT/'prior_provenance.json',record)
    return {**expected,**record['witness_json_sha256'],str(OUT/'prior_provenance.json'):sha(OUT/'prior_provenance.json')}

def fit_split(task):
    name,d,tr,te=task;started=time.monotonic();artifacts={};predictions={};logs=[]
    if name!='final':assert not set(d['group'][tr])&set(d['group'][te]) and not set(tr)&set(te)
    for seed in models.SEEDS:
        try:model=models.fit(d,tr,seed)
        except Exception as error:
            failure={'split':name,'seed':seed,'traceback':traceback.format_exc(),'diagnostics':getattr(error,'fit_diagnostics',{}),'completed_seed_artifacts':artifacts}
            dump(OUT/f'failure_{name}_seed{seed}.json',failure);raise
        path=OUT/f'fit_{name}_seed{seed}.pkl'
        with path.open('wb') as f:pickle.dump(model,f,protocol=5)
        digest=sha(path);pred=models.predict(model,d,te)
        assert sha(path)==digest
        with path.open('rb') as f:loaded=pickle.load(f)
        np.testing.assert_array_equal(models.predict(loaded,d,te),pred)
        predictions[f'neural62_seed{seed}']=pred;artifacts[str(path)]=digest;logs.append(model['diagnostics'])
    full=np.mean(np.stack(list(predictions.values())),axis=0);base=d['BASE_CD'][te]
    predictions['neural62__1']=full;predictions['neural62__0.5']=base+.5*(full-base)
    if name=='final':
        np.savez_compressed(OUT/'final_fullfit_engineering_references.npz',indices=te,**predictions)
    else:
        frame=pd.read_csv(CAP/'results'/f'predictions_{name}.csv',low_memory=False)
        np.testing.assert_array_equal(frame.nf2_row_id,d['nf2_row_id'][te])
        np.testing.assert_allclose(frame.measured_CD,d['MEAS_CD'][te],rtol=0,atol=1e-14)
        for label,pred in predictions.items():frame[label]=pred
        frame.to_csv(OUT/f'predictions_{name}.csv',index=False)
    result={'split':name,'train_rows':len(tr),'test_rows':len(te),'training_nf2_row_ids':d['nf2_row_id'][tr].tolist(),'training_groups':sorted(set(d['group'][tr])),
            'diagnostics':logs,'artifact_sha256':artifacts,'seconds':time.monotonic()-started}
    dump(OUT/f'log_{name}.json',result);return result

def exposed(freeze):
    directory=HERE/'exposed_results';directory.mkdir(exist_ok=False);fitted=[]
    for seed in models.SEEDS:
        path=OUT/f'fit_final_seed{seed}.pkl';assert sha(path)==freeze['artifact_sha256'][str(path)]
        with path.open('rb') as f:fitted.append(pickle.load(f))
    for name in ['SG_exposed','W_new_challenge']:
        d=inputs.load_exposed(name);frame=pd.read_csv(CAP/'exposed_results'/f'{name}_predictions.csv',low_memory=False)
        idx=np.arange(len(frame));np.testing.assert_array_equal(frame.Re,d['Re']);np.testing.assert_array_equal(frame.alpha,d['alpha'])
        gate=frame.inference_gate.to_numpy();assert gate.dtype==bool and gate.sum()=={'SG_exposed':234,'W_new_challenge':238}[name]
        base=d['BASE_CD'];seedpred=[]
        for seed,model in zip(models.SEEDS,fitted):
            pred=models.predict(model,d,idx);seedpred.append(pred);frame[f'neural62_seed{seed}']=np.where(gate,pred,base)
        full=np.mean(np.stack(seedpred),axis=0)
        for strength in [.5,1.]:frame[f'neural62__{strength:g}']=np.where(gate,base+strength*(full-base),base)
        for label in LABELS+[f'neural62_seed{s}' for s in models.SEEDS]:np.testing.assert_array_equal(frame[label].to_numpy()[~gate],base[~gate])
        frame.to_csv(directory/f'{name}_predictions.csv',index=False)

def assessment():
    sys.path.insert(0,str(PROJECT/'model_development_20260907_frontier'));import frontier_assessment as shared
    frame,_,_,hashes=shared.load_frame(['capacity'])
    for split in frame.split.unique():
        external=split in ['SG_exposed','W_new_challenge'];path=HERE/('exposed_results' if external else 'results')/(f'{split}_predictions.csv' if external else f'predictions_{split}.csv')
        hashes[str(path)]=sha(path);new=pd.read_csv(path,low_memory=False);mask=frame.split==split;old=frame.loc[mask]
        if not external:new=new.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        shared.check_common(old,new)
        for label in LABELS+[f'neural62_seed{s}' for s in models.SEEDS]:frame.loc[mask,label]=new[label].to_numpy()
    panels=shared.old.panels(frame);panels.update({k:v for k,v in shared.reconcile.external_panels(frame).items() if k.startswith('eligible_only/')});assert len(panels)==31
    table=pd.concat([shared.old.metrics(frame,frame[c].to_numpy(),panels,c) for c in LABELS],ignore_index=True)
    table.to_csv(OUT/'panel_metrics.csv',index=False)
    # Seed diagnostics are not competing procedures or selectable candidates.
    pd.concat([shared.old.metrics(frame,frame[f'neural62_seed{s}'].to_numpy(),panels,f'neural62_seed{s}') for s in models.SEEDS],ignore_index=True).to_csv(OUT/'seed_diagnostic_metrics.csv',index=False)
    bootstrap=shared.conditional_bootstrap(frame,LABELS);bootstrap.to_csv(OUT/'conditional_paired_bootstrap.csv',index=False)
    ref=shared.old.metrics(frame,frame[shared.REFERENCE].to_numpy(),panels,shared.REFERENCE)
    decision=shared.stopping_gate(frame,LABELS,pd.concat([table,ref],ignore_index=True),bootstrap);decision.to_csv(OUT/'legacy_global_diagnostic_decisions.csv',index=False)
    for p,h in hashes.items():assert sha(p)==h
    return {'panels':31,'variants':LABELS,'input_sha256':hashes,'legacy_global_diagnostic_only':True,'legacy_rule_passes_not_current_advance':decision.loc[decision.operational_frontier_advance,'candidate'].tolist(),'current_geometry_frontier_decision':'Owned by central assessment against latest unpenalized_transfer and identity-group guards, with half-strength robustness control'}

def main():
    OUT.mkdir(exist_ok=False)
    verified_prior=verify_prior_provenance()
    sourcepaths=[Path(__file__),Path(models.__file__),HERE/'PROTOCOL.md',Path(inputs.__file__),C4/'transition_inputs.py',Path(v2.__file__),Path(v2.old.__file__),CAP/'results/run_manifest.json']
    sourcepaths += [C4/section/f'{cohort}.npz' for section in ['inputs','shape_inputs'] for cohort in ['historical','SG_exposed','W_new_challenge']]
    sourcepaths += list((CAP/'results').glob('predictions_*.csv'))+[CAP/'exposed_results'/f'{name}_predictions.csv' for name in ['SG_exposed','W_new_challenge']]
    hashes={str(p):sha(p) for p in sourcepaths};hashes.update(verified_prior)
    manifest={'status':'frozen_before_48_neural_fits','source_input_sha256':hashes,'seeds':list(models.SEEDS),'variants':LABELS,'workers':2,'sklearn':sklearn.__version__,'numpy':np.__version__,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    dump(OUT/'started_manifest.json',manifest)
    d=inputs.load_historical();assert d['X62'].shape==(8371,62) and len(set(d['group']))==93
    np.testing.assert_allclose(models.balanced_weights(d['group'],d['source']),v2.old.balanced_weights(d['group'],d['source']),rtol=0,atol=1e-13)
    idx=np.arange(8371);tasks=[]
    for seed in [20260906,20260908]:
        for fold,test in enumerate(v2.old.group_folds(d['group'],5,seed)):tasks.append((f'group_{seed}_fold_{fold}',d,idx[~test],idx[test]))
    for source in sorted(set(d['source']))+['all_uiuc_volumes']:
        test=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        train=~test&~np.isin(d['group'],d['group'][test]);tasks.append((f'strict_source_{source}',d,idx[train],idx[test]))
    tasks.append(('final',d,idx,idx));assert len(tasks)==16
    logs=[];failures=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        pending={pool.submit(fit_split,task):task[0] for task in tasks}
        for future in as_completed(pending):
            try:
                result=future.result();logs.append(result)
                print(json.dumps({'split_complete':result['split'],'seconds':result['seconds'],'diagnostics':result['diagnostics']}),flush=True)
            except Exception:failures.append({'split':pending[future],'traceback':traceback.format_exc()})
    if failures:dump(OUT/'incomplete.json',{'failures':failures,'completed_splits':[r['split'] for r in logs]});raise RuntimeError('Preserved fit failure; incomplete run')
    artifacts={p:h for r in logs for p,h in r['artifact_sha256'].items()};assert len(artifacts)==48
    for p,h in {**hashes,**artifacts}.items():assert sha(p)==h
    freeze={**manifest,'status':'all48fits_frozen_before_external_scoring','model_count':48,'artifact_sha256':artifacts,'external_scored_at_freeze':False,'logs':logs}
    dump(OUT/'freeze.json',freeze)
    exposed(freeze);summary=assessment()
    for p,h in {**hashes,**artifacts}.items():assert sha(p)==h
    dump(OUT/'report.json',{'status':'completed_fixed_three_seed_neural_exploration_not_confirmatory','model_count':48,'source_input_sha256':hashes,'artifact_sha256':artifacts,'assessment':summary,'all_fit_diagnostics':[row for r in logs for row in r['diagnostics']]})
    print('COMPLETE neural residual branch',flush=True)

if __name__=='__main__':main()
