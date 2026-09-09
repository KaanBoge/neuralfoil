"""Export only after producer completion; open no measured-outcome files."""
from pathlib import Path
import copy
import hashlib
import json
import numpy as np
from predictor import LABELS, validate

HERE=Path(__file__).resolve().parent
RISK=HERE.parent
PROJECT=RISK.parent


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path,value): Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def main():
    complete_path=RISK/'results/complete.json'
    if not complete_path.is_file(): raise RuntimeError('Wait for results/complete.json; export is prohibited before completion')
    complete=read(complete_path); freeze_path=RISK/'results/freeze.json'; freeze=read(freeze_path)
    assert sha(freeze_path)==complete['freeze_sha256']
    assert freeze['policy_count']==48 and len(freeze['artifact_sha256'])==48
    assert freeze['artifact_sha256']==complete['artifact_sha256']
    for path,expected in freeze['artifact_sha256'].items(): assert sha(path)==expected,path
    for name in ['risk_policy.py','run_experiment.py']:
        path=RISK/name
        assert sha(path)==freeze['source_input_sha256'][str(path)],name
    origin=PROJECT/'model_development_20260907_frontier/capacity/portable'
    original=origin/'hist62_regularized_half.json'
    original_manifest=read(origin/'manifest.json')
    # Original exporter manifests may store the model under a dedicated field.
    expected=original_manifest.get('artifact_sha256',original_manifest.get('portable_json_sha256'))
    if expected is None: expected=original_manifest['hashes'].get(str(original))
    if expected is None: raise ValueError('Original portable model hash not found')
    assert sha(original)==expected
    core=copy.deepcopy(read(original)); assert core['strength']==.5; core['strength']=1.
    policies={}
    for label in LABELS:
        model=read(RISK/f'results/policy_final_{label}.json')
        policies[label]={key:model[key] for key in ['schema','endpoints','corners','penalty']}
    artifact={'schema':'experimental-risk-policy-package-v1','status':'experimental_not_deployed_no_default_promotion',
              'core':core,'policies':policies}
    validate(artifact)
    refs={}; source_refs={}
    for name,path in [('historical',RISK/'results/historical_inference.npz'),
                      ('SG_exposed',RISK/'exposed_results/SG_exposed_inference.npz'),
                      ('W_new_challenge',RISK/'exposed_results/W_new_challenge_inference.npz')]:
        source_refs[str(path)]=sha(path)
        with np.load(path,allow_pickle=False) as data:
            assert set(data.files)=={'BASE_CD','CORE_CD','all_model_CD','X62','gate',*LABELS}
            for key in data.files: refs[name+'_'+key]=data[key].copy()
    write(HERE/'experimental_policies.json',artifact)
    np.savez_compressed(HERE/'inference_references.npz',**refs)
    module_paths=[RISK/'risk_policy.py',RISK/'run_experiment.py',
                  PROJECT/'model_development_20260907_search/portable/portable_models.py']
    manifest={'status':'numerical_reproducibility_only_not_accuracy_validation_not_deployed',
              'original_half_core_sha256':sha(original),'original_half_core_path':str(original),
              'freeze_sha256':sha(freeze_path),'complete_sha256':sha(complete_path),
              'all_48_policy_hashes':freeze['artifact_sha256'],
              'producer_module_hashes':{str(p):sha(p) for p in module_paths},
              'source_label_free_reference_hashes':source_refs,
              'package_hashes':{p.name:sha(p) for p in [HERE/'experimental_policies.json',HERE/'inference_references.npz',
                   HERE/'predictor.py',HERE/'export_verify.py',HERE/'verify_portable.py',HERE/'README.md']}}
    write(HERE/'manifest.json',manifest)
    from verify_portable import main as verify
    verify()


if __name__=='__main__': main()
