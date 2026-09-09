"""Metadata/source-only preparation. Never loads reference NPZ or model members.

Do not execute until source review is clear; this creates no actual approval.
"""
from pathlib import Path
import copy,hashlib,json,os
H=Path(__file__).resolve().parent
B=H.parents[3]/'independent_environment/inference_benchmark_plan'
P=next(p for p in H.parents if p.name=='NeuralFoil_Research_Paper')
sha=lambda b:hashlib.sha256(b).hexdigest()
PINS={'REGISTRY_v6.json':'59aae736fae33f9ac2faede293152fec70e19496e4a2c7e6b627b998ebc17978',
      'ROOT_ACTUAL_APPROVAL_V6.json':'3f4135cb5dc467e982952cc8b31ea02b3242f2a8334462bf8c8eff396c1f74d6',
      'actual_v6_attempt_1/COMPLETE.json':'5d0eb7516743161f1c228fed34755ffeb45b31a9108d31df1babdd0c75845fa8',
      'actual_v6_attempt_1/preflight_COMPLETE.json':'be5f83007ac7b7e68b21d0b031acce3fc45637362b6ec726a2005531dd516812'}
CONTRACT='one_request_local_Kulfan_and_complete_unquantized_ncrit9_response_v1_against_frozen_V6'
def read(p):
    if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('symlink')
    return p.read_bytes()
def build():
    meta={}
    for name,h in PINS.items():
        b=read(B/name)
        if sha(b)!=h:raise ValueError('legacy identity '+name)
        meta[name]=json.loads(b)
    old=meta['REGISTRY_v6.json'];complete=meta['actual_v6_attempt_1/COMPLETE.json'];pre=meta['actual_v6_attempt_1/preflight_COMPLETE.json'];approval=meta['ROOT_ACTUAL_APPROVAL_V6.json']
    if complete['status']!='COMPLETE_REQUIRES_INDEPENDENT_REVIEW' or pre['status']!='PASS':raise ValueError('legacy status')
    for receipt in [complete,pre]:
        if receipt['registry_sha256']!=PINS['REGISTRY_v6.json'] or receipt['approval_sha256']!=PINS['ROOT_ACTUAL_APPROVAL_V6.json']:raise ValueError('legacy binding')
    if complete['preflight_sha256']!=PINS['actual_v6_attempt_1/preflight_COMPLETE.json'] or approval['registry_sha256']!=PINS['REGISTRY_v6.json']:raise ValueError('legacy predecessor')
    for n,h in old['sources'].items():
        if sha(read(B/n))!=h:raise ValueError('immutable V6 source changed')
    d=copy.deepcopy(old);d['status']='SOURCE_ONLY_REVIEW_REQUIRED_NO_EXECUTION_AUTHORITY';d['optimization_contract']=CONTRACT
    d['source_paths']={n:os.path.relpath(B/n,H) for n in old['sources']}
    for n in ['response_snapshot.py','feature_adapter.py','serving_optimized.py','preflight.py','test_request_local.py','test_preflight.py','README.md','SOURCE_REVIEW.json']:
        key='cache_'+n if n=='README.md' else n
        d['sources'][key]=sha(read(H.parent/n));d['source_paths'][key]='../'+n
    for n in ['runner_cache.py','loader_cache.py','preflight_cache.py','prepare_registry.py','test_execution.py','README.md']:
        key='execution_'+n if n=='README.md' else n
        d['sources'][key]=sha(read(H/n));d['source_paths'][key]=n
    d['v6_receipts']={str((B/n).relative_to(P)):h for n,h in PINS.items()}
    # Preserve all first accepted V6 output pins. Actual phase authenticates their
    # bytes; preparation only reads the already authenticated completion metadata.
    for n,h in complete['outputs'].items():d['v6_receipts'][str((B/'actual_v6_attempt_1'/n).relative_to(P))]=h
    d['v6_reference_files']={}
    for route in d['routes']:
        name='reference_'+route+'.npz';h=pre['outputs'][name]
        if complete['outputs'][name]!=h:raise ValueError('V6 reference chain')
        fields=['raw_CD','quantized_CD'] if route.startswith('native_') else (['CD','strength'] if route==d['routes'][2] else ['CD','effective_fraction','strength','intervened'])
        path=str((B/'actual_v6_attempt_1'/name).relative_to(P))
        d['v6_reference_files'][route]={'path':path,'sha256':h,'members':[c+'/'+f for c in d['workload_rows'] for f in fields]}
    for scope in d['scopes'].values():
        # Every child authenticates chain metadata, but native cold children must
        # not materialize or authenticate unrelated correction reference arrays.
        scope['files'].update({str((B/n).relative_to(P)):h for n,h in PINS.items()})
    d['scopes']['all']['files'].update(d['v6_receipts'])
    for spec in d['v6_reference_files'].values():d['scopes']['all']['arrays'][spec['path']]=spec['members']
    d['legacy_metadata_paths']=[str((B/n).relative_to(P)) for n in PINS]
    d['preflight_phase_seconds']=60
    return d
def main():
    target=H/'REGISTRY.json'
    if target.exists():raise FileExistsError('registry exists')
    value=build()
    with target.open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
if __name__=='__main__':main()
