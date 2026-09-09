"""Authenticate and replay completed numerical outputs without estimator or LP fitting."""
from pathlib import Path
import json
import numpy as np
import replay as r


def main():
    root=Path(__file__).resolve().parent
    if (root/'release_manifest.json').exists():
        for name,h in r.read(root/'release_manifest.json')['files'].items():
            if r.sha(root/name)!=h: raise ValueError('Release hash mismatch: '+name)
    d,m,pre=r.preflight();out=root/'results';complete=r.read(out/'complete.json')
    if complete['status']!='PASS' or complete['counts']!=m['planned']: raise ValueError('Incomplete result')
    for name,h in complete['output_sha256'].items():
        if r.sha(out/name)!=h: raise ValueError('Output changed: '+name)
    frozen=r.read(out/'freeze.json')
    if frozen['policy_count']!=16 or frozen['external_inference_started'] is not False: raise ValueError('Freeze boundary')
    for name,h in frozen['policy_sha256'].items():
        if r.sha(out/name)!=h: raise ValueError('Policy changed')
    comparisons=0
    for name in m['contexts']:
        expected=r.read(root/'memberships'/(name+'.json'))['policy_reference'];model=r.read(out/('policy_'+name+'.json'))
        if model!=expected: raise ValueError('Policy numeric mismatch: '+name)
        a=r.load(out/(name+'_group.npz'));b=r.load(root/'references'/(name+'_inner_group.npz'))
        r.exact(a['indices'],b['indices']);r.exact(a['core'],b['core']);comparisons+=1
        tr,te=r.roles(d,name)
        for source,_,_,ok in r.transfers(d,tr):
            if not ok: continue
            a=r.load(out/(name+'_transfer_'+source+'.npz'));b=r.load(root/'references'/(name+'_inner_transfer_'+source+'.npz'))
            for key in ['train','test','core']:r.exact(a[key],b[key])
            comparisons+=1
        if name!='final':
            a=r.load(out/(name+'_outer.npz'));b=r.load(root/'references'/(name+'_outer.npz'))
            r.exact(r.csv_roundtrip(a['native_core']),a['serialized_core']);r.exact(a['serialized_core'],b['core_csv'])
            pred,s=r.policy.predict(model,d['BASE_CD'][te],a['serialized_core'],d['all_model_CD'][te],np.ones(len(te),bool))
            r.exact(pred,a['prediction']);r.exact(s,a['strength'])
            r.exact(r.csv_roundtrip(pred),b['prediction_csv']);r.exact(r.csv_roundtrip(s),b['strength_csv'])
            r.exact(r.csv_roundtrip(a['half']),b['half_csv'])
    for name in ['historical','SG_exposed','W_new_challenge']:
        data=d if name=='historical' else r.load(root/'data'/(name+'.npz'))
        a=r.load(out/(name+'_final.npz'));b=r.load(root/'references'/(name+'_final.npz'))
        r.exact(a['core'],b['CORE_CD']);r.exact(a['prediction'],b['prediction'])
        pred,s=r.policy.predict(r.read(out/'policy_final.json'),data['BASE_CD'],a['core'],data['all_model_CD'],a['gate'])
        r.exact(pred,a['prediction']);r.exact(s,a['strength']);r.exact(pred[~a['gate']],data['BASE_CD'][~a['gate']])
    ev=r.read(root/'evaluation/manifest.json')
    if r.sha(root/'evaluation/reference_predictions.npz')!=ev['reference_sha256']: raise ValueError('Evaluation reference changed')
    refs=r.load(root/'evaluation/reference_predictions.npz');n=0
    for name,pos in ev['positions'].items():
        suffix='_final.npz' if name in ['SG_exposed','W_new_challenge'] else '_outer.npz'
        a=r.load(out/(name+suffix));n+=len(pos)
        for label,key in [('unpenalized_transfer','prediction'),('half_strength','half')]:r.exact(r.csv_roundtrip(a[key]),refs[label][pos])
    if n!=29856 or comparisons!=72: raise ValueError('Comparison coverage changed')
    print(json.dumps({'status':'PASS','mode':'completed_output_replay_no_fitting','inner_archives_exact':comparisons,
         'policy_numeric_dictionaries_exact':16,'evaluation_rows_per_reference':n,'references':2,
         'final_native_rows':8868,'prior_reconstructed_Hist_fits':120,'prior_policy_fits':16,
         'complete_sha256':r.sha(out/'complete.json'),'same_installed_environment':True},indent=2))


if __name__=='__main__':main()
