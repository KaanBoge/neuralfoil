"""No fitting: authenticate saved NPZ, freeze 16 scalar calibrations, then score."""
from pathlib import Path
import hashlib
import io
import json
import time
import numpy as np
import pandas as pd
import incremental_harm as policy

HERE=Path(__file__).resolve().parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
A=PROJECT/'model_development_20260907_cap_ablation'
FREEZE_SHA='7d07b1beacb39de88f4c1c8b96b48ac6988c619f9e344843df3b565531c835f3'
SEAL_SHA='d7d9c278bd1f34628a3302bf9620efb282a098ea49249f3cb3af712d7c5c275e'
PROPOSAL_SHA='3f7c4b1f73b283e434c4d670fdd16c67c8d3eaff221dd634a47ba66dd39414f7'
OUT=HERE/'results'
EXPOSED=HERE/'exposed_results'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def dump(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def checked(p,h):
    data=Path(p).read_bytes()
    if hashlib.sha256(data).hexdigest()!=h:raise ValueError(f'Authentication failed: {p}')
    return data
def load_npz(p,h):
    with np.load(io.BytesIO(checked(p,h)),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def save_npz(p,**values):
    with Path(p).open('xb') as f:np.savez_compressed(f,**values)


def main():
    start=time.monotonic()
    assert not OUT.exists() and not EXPOSED.exists(),'Never overwrite results'
    checked(HERE/'PROPOSAL.md',PROPOSAL_SHA)
    frozen=json.loads(checked(A/'results/freeze.json',FREEZE_SHA))
    seal=json.loads(checked(A/'DELIVERY_QA.json',SEAL_SHA))
    h=seal['source_and_result_sha256'][str(A/'results/complete.json')]
    complete=json.loads(checked(A/'results/complete.json',h))
    assert complete['freeze_sha256']==FREEZE_SHA
    assert frozen['core_count']==96 and frozen['calibrator_count']==48
    assert len(frozen['contexts'])==16 and frozen['external_outcomes_opened'] is False
    hashes={str(A/'results/freeze.json'):FREEZE_SHA,str(A/'DELIVERY_QA.json'):SEAL_SHA,
            str(A/'results/complete.json'):h}
    for name in ['PROPOSAL.md','APPROVAL.md','incremental_harm.py','test_incremental_harm.py','run_experiment.py','assess_experiment.py']:
        hashes[str(HERE/name)]=sha(HERE/name)
    def archived(p):
        h=frozen['artifact_sha256'][str(p)];hashes[str(p)]=h
        return load_npz(p,h)
    final=archived(A/'results/inference_final.npz')
    assert len(final['indices'])==8371 and len(np.unique(final['indices']))==8371
    assert final['gate'].dtype==bool and final['gate'].all()
    gates={int(i):bool(g) for i,g in zip(final['indices'],final['gate'])}
    OUT.mkdir()
    dump(OUT/'run_manifest.json',{'started_utc':now(),'no_new_core_fits':True,
         'proposal_sha256':PROPOSAL_SHA,'approval_sha256':sha(HERE/'APPROVAL.md'),
         'source_sha256':hashes,'external_outcomes_opened':False})
    models={};artifacts={};calibration_rows=[]
    for context in frozen['contexts']:
        mp=A/'results'/f'membership_{context}.json'
        mh=frozen['artifact_sha256'][str(mp)];hashes[str(mp)]=mh
        member=json.loads(checked(mp,mh))
        proper=set(member['proper_groups']);cal=set(member['calibration_groups']);test=set(member['test_groups'])
        assert not proper&cal and not proper&test and not cal&test
        assert member['post_calibration_refit'] is False
        z=archived(A/'results'/f'calibration_{context}.npz')
        np.testing.assert_array_equal(z['indices'],member['calibration_indices'])
        np.testing.assert_array_equal(z['nf2_row_id'],member['calibration_nf2_row_ids'])
        assert set(z['group'].astype(str))==cal
        gate=np.array([gates[int(i)] for i in z['indices']],bool)
        model=policy.calibrate(z['BASE_CD'],z['CORE_CD_capped'],z['MEAS_CD'],z['group'],gate)
        assert model['groups']==len(cal) and model['groups']>=9
        model.update(context=context,calibration_npz_sha256=hashes[str(A/'results'/f'calibration_{context}.npz')],
                     membership_sha256=mh,conditional_not_certified=True)
        models[context]=model
        path=OUT/f'calibrator_{context}.json';dump(path,model);artifacts[str(path)]=sha(path)
        path=OUT/f'membership_{context}.json';dump(path,member);artifacts[str(path)]=sha(path)
        calibration_rows.extend({'context':context,'group':g,'rows':n,'endpoint_loss':l} for g,n,l in zip(
            model['group_names'],model['group_rows'],model['group_endpoint_losses']))
    assert len(models)==16 and len(artifacts)==32
    for p,h in hashes.items():checked(p,h)
    dump(OUT/'freeze.json',{'frozen_utc':now(),'calibrator_count':16,'new_core_fits':0,
        'contexts':frozen['contexts'],'artifact_sha256':artifacts,'source_input_sha256':hashes,
        'external_outcomes_opened':False,'proposal_sha256':PROPOSAL_SHA,
        'epsilon':policy.EPSILON,'delta':policy.DELTA,'B':policy.BOUND})
    print('All 16 scalar calibrators frozen before external outcome access.',flush=True)
    # Only after this persistent freeze may external prediction/outcome CSVs load.
    outputs={};external_hashes={};native_checks=[]
    EXPOSED.mkdir()
    for split in frozen['contexts']+['SG_exposed','W_new_challenge']:
        external=split in ['SG_exposed','W_new_challenge']
        model=models['final' if external else split]
        if external:
            p=A/'exposed_results'/f'{split}_inference.npz'
            h=complete['output_sha256'][str(p)];external_hashes[str(p)]=h;z=load_npz(p,h)
        else:z=archived(A/'results'/f'inference_{split}.npz')
        values=policy.predict(model,z['BASE_CD'],z['proper_core_capped'],z['gate'])
        np.testing.assert_array_equal(values['prediction'][~z['gate']],z['BASE_CD'][~z['gate']])
        np.testing.assert_allclose(values['anchor'],z['proper_capped_half'],rtol=0,atol=1e-15)
        np.testing.assert_array_equal(values['endpoint'],z['proper_capped_full'])
        dest=EXPOSED if external else OUT
        path=dest/f'inference_{split}.npz'
        save_npz(path,indices=z['indices'],BASE_CD=z['BASE_CD'],CORE_CD=z['proper_core_capped'],
            gate=z['gate'],**values)
        outputs[str(path)]=sha(path)
        native_checks.append({'split':split,'rows':len(z['BASE_CD']),'eligible_rows':int(z['gate'].sum()),
            'fallback_exact':True,'matched_half_max_abs_CD':float(abs(values['anchor']-z['proper_capped_half']).max(initial=0))})
        if split=='final':continue  # All-history references are NOT held-out scores.
        p=A/('exposed_results' if external else 'results')/(f'{split}_predictions.csv' if external else f'predictions_{split}.csv')
        h=complete['output_sha256'][str(p)]
        (external_hashes if external else hashes)[str(p)]=h
        frame=pd.read_csv(io.BytesIO(checked(p,h)),low_memory=False)
        assert len(frame)==len(z['BASE_CD'])
        if not external:
            member=json.loads((OUT/f'membership_{split}.json').read_text())
            np.testing.assert_array_equal(z['indices'],member['test_indices'])
            np.testing.assert_array_equal(frame.nf2_row_id,member['test_nf2_row_ids'])
        np.testing.assert_allclose(frame.mean8_CD,z['BASE_CD'],atol=1e-13,rtol=0)
        np.testing.assert_allclose(frame.proper_capped_full,values['endpoint'],atol=1e-13,rtol=0)
        frame[policy.LABEL]=values['prediction']
        frame[policy.LABEL+'__strength']=values['applied_strength']
        frame[policy.LABEL+'__intervened']=values['intervened_vs_anchor']
        frame['calibration_t']=model['t']
        path=dest/(f'{split}_predictions.csv' if external else f'predictions_{split}.csv')
        frame.to_csv(path,index=False,mode='x');outputs[str(path)]=sha(path)
    path=OUT/'calibration_groups.csv';pd.DataFrame(calibration_rows).to_csv(path,index=False,mode='x');outputs[str(path)]=sha(path)
    for p,h in {**hashes,**artifacts,**external_hashes}.items():checked(p,h)
    dump(OUT/'complete.json',{'completed_utc':now(),'calibrator_count':16,'new_core_fits':0,
         'freeze_sha256':sha(OUT/'freeze.json'),'source_input_sha256':hashes,'artifact_sha256':artifacts,
         'external_input_sha256':external_hashes,'output_sha256':outputs,'native_checks':native_checks,
         'elapsed_seconds':time.monotonic()-start,'status':'exploratory_reused_outcomes_not_certified'})
    print('Completed all native references and 17 held-out/exposed CSVs.',flush=True)


if __name__=='__main__':main()
