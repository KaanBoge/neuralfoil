"""One-time authenticated assembly; no fitting. Project paths are assembly-only."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
RISK = PROJECT / 'model_development_20260907_risk_policy'
CAP = PROJECT / 'model_development_20260907_frontier/capacity'
BUNDLE = PROJECT / 'reproduction_20260908_private/bundle'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def dump(p, value):
    with Path(p).open('x') as f: json.dump(value, f, indent=2, allow_nan=False)
def load(p):
    with np.load(p, allow_pickle=False) as z: return {k: z[k].copy() for k in z.files}


def main():
    data = HERE / 'data'; data.mkdir(exist_ok=False)
    refs = HERE / 'references'; refs.mkdir(exist_ok=False)
    members = HERE / 'memberships'; members.mkdir(exist_ok=False)
    complete = read(RISK / 'results/complete.json')
    assert sha(RISK / 'results/freeze.json') == complete['freeze_sha256']
    bundle = read(BUNDLE / 'manifest.json')
    witnesses = {}
    def checked(p, expected):
        assert sha(p) == expected, str(p)
        witnesses[str(p.relative_to(PROJECT))] = expected
    for name in ['capacity_models.py', 'run_capacity.py']:
        p = CAP / name; checked(p, complete['source_input_sha256'][str(p)])
    for name in ['risk_policy.py', 'run_experiment.py', 'PROTOCOL.md']:
        p = RISK / name; checked(p, complete['source_input_sha256'][str(p)])
    assert sha(HERE/'source/capacity_models.py') == sha(CAP/'capacity_models.py')
    assert sha(HERE/'source/risk_policy.py') == sha(RISK/'risk_policy.py')
    p = BUNDLE/'data/historical.npz'; checked(p,bundle['files']['data/historical.npz'])
    d = load(p)
    keep = ['X62','BASE_CD','XLARGE_CD','all_model_CD','MEAS_CD','group','source','nf2_row_id','entry','alpha','Re']
    np.savez_compressed(data/'historical.npz', **{k:d[k] for k in keep})
    contexts = bundle['contexts']
    planned = {'enclosing':16,'group_inner':48,'transfer_inner':0,'policies':16}
    for context in contexts:
        p = BUNDLE / ('memberships/'+context+'.json'); checked(p,bundle['files']['memberships/'+context+'.json'])
        m = read(p)
        p = RISK/'results'/('policy_'+context+'_unpenalized_transfer.json')
        checked(p,complete['artifact_sha256'][str(p)]); policy = read(p)
        assert policy['training']['training_indices'] == m['enclosing_indices']
        dump(members/(context+'.json'), {'train':m['enclosing_indices'],'test':m['test_indices'],
             'transfer_log':policy['training']['transfer_log'], 'policy_reference':{k:v for k,v in policy.items() if k!='training'}})
        p = CAP/'results'/(context+'_inner_group.npz')
        checked(p,complete['source_input_sha256'][str(p)]); a=load(p)
        np.savez_compressed(refs/(context+'_inner_group.npz'),indices=a['indices'],core=a['hist62_regularized__1'])
        for t in policy['training']['transfer_log']:
            if t['status'] != 'used': continue
            source=t['source']; p=CAP/'results'/(context+'_inner_transfer_'+source+'.npz')
            checked(p,complete['source_input_sha256'][str(p)]);a=load(p)
            np.savez_compressed(refs/(context+'_inner_transfer_'+source+'.npz'),
                train=a['train_indices'],test=a['test_indices'],core=a['hist62_regularized__1'])
            planned['transfer_inner']+=1
        if context!='final':
            p=CAP/'results'/('predictions_'+context+'.csv')
            checked(p,complete['source_input_sha256'][str(p)])
            a=pd.read_csv(p,usecols=['nf2_row_id','hist62_regularized__1','hist62_regularized__0.5'])
            p=RISK/'results'/('predictions_'+context+'.csv')
            # The completed assessment independently witnesses producer CSVs.
            assess=read(RISK/'assessment/report.json')['input_source_sha256']
            checked(p,assess[str(p)])
            b=pd.read_csv(p,usecols=['nf2_row_id','unpenalized_transfer','unpenalized_transfer__strength'])
            np.testing.assert_array_equal(a.nf2_row_id,b.nf2_row_id)
            np.savez_compressed(refs/(context+'_outer.npz'),nf2_row_id=a.nf2_row_id.to_numpy(),
                core_csv=a['hist62_regularized__1'].to_numpy(),half_csv=a['hist62_regularized__0.5'].to_numpy(),
                prediction_csv=b.unpenalized_transfer.to_numpy(),strength_csv=b['unpenalized_transfer__strength'].to_numpy())
    portable=read(RISK/'portable/manifest.json')
    for name,p in [('historical',RISK/'results/historical_inference.npz'),
                   ('SG_exposed',RISK/'exposed_results/SG_exposed_inference.npz'),
                   ('W_new_challenge',RISK/'exposed_results/W_new_challenge_inference.npz')]:
        checked(p,portable['source_label_free_reference_hashes'][str(p)]);a=load(p)
        np.savez_compressed(refs/(name+'_final.npz'),CORE_CD=a['CORE_CD'],prediction=a['unpenalized_transfer'])
        if name!='historical':
            np.savez_compressed(data/(name+'.npz'),**{k:a[k] for k in ['X62','BASE_CD','all_model_CD','gate']})
    assert planned == {'enclosing':16,'group_inner':48,'transfer_inner':56,'policies':16}
    dump(HERE/'input_manifest.json', {'contexts':contexts,'planned':planned,'upstream_sha256':witnesses,
        'files':{str(p.relative_to(HERE)):sha(p) for directory in [data,refs,members] for p in sorted(directory.glob('*'))},
        'external_labels_in_payload':False,'scope':'historical labels only; fixed reference reconstruction'})
    print('Assembly complete',planned)


if __name__=='__main__': main()
