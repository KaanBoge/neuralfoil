"""Metadata/source-only finite freeze. Never read model, NPZ or geometry bytes."""
from pathlib import Path
import hashlib,json,copy
H=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
ADDED={
 'model_development_20260907_risk_policy/portable/predictor.py':'d97950364c0fb201a93715e90f1558912b6682df0bbfb4b8074452a331f4fb6a',
 'model_development_20260907_risk_policy/risk_policy.py':'dbe6a91fa744d16652b02f15296349407e1567ed328308a79cdbf5375abd9ab8'}
def build(old):
    d=copy.deepcopy(old);d['v4_sources']=old['sources']
    d['v4_registry_sha256']='b48543cc24201a161c609a08d1a1c7160db86d674becd740263bb1301d491a5e'
    d['sources']={n:h for n,h in old['sources'].items() if n not in ['loader_v2.py','measurement_v3.py','runner_v4.py','freeze_v4.py','README_v4.md']}
    for n in ['oracle_v5.py','loader_v5.py','measurement_v5.py','runner_v5.py','freeze_v5.py','README_v5.md','test_v5.py']:d['sources'][n]=sha((H/n).read_bytes())
    d['scopes']['all']['files'].update(ADDED)
    identity='model_development_20260907_risk_policy/portable/inference_references.npz'
    d['scopes']['all']['arrays'][identity]+=['SG_exposed_CORE_CD','W_new_challenge_CORE_CD']
    d['reference_contract']='current_runtime_canonical_portable_bit_exact_with_separate_archive_inventory_v1'
    d['status']='SOURCE_ONLY_V5_REVIEW_REQUIRED_NO_ACTUAL_APPROVAL'
    for route in old['routes']:
        if old['scopes'][route]!=d['scopes'][route]:raise ValueError('cold scope changed')
    for k in ['routes','schedule','workload_rows','runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','cold_repeats','warmups','warm_repeats','workers']:
        if d[k]!=old[k]:raise ValueError('scientific contract changed')
    return d
def main():
    raw=(H/'REGISTRY_v4.json').read_bytes()
    if sha(raw)!='b48543cc24201a161c609a08d1a1c7160db86d674becd740263bb1301d491a5e':raise ValueError('V4 registry identity')
    old=json.loads(raw)
    for n,h in old['sources'].items():
        if sha((H/n).read_bytes())!=h:raise ValueError('preserved V4 source changed')
    project=next(p for p in H.parents if p.name=='NeuralFoil_Research_Paper')
    for n,h in ADDED.items():
        if sha((project/n).read_bytes())!=h:raise ValueError('canonical source identity')
    d=build(old)
    names=['ATTEMPT.json','preflight_FAILURE.json','FAILURE.json','preflight_PROCESS.json','preflight.stderr','preflight.stdout']
    d['preserved_v4_failure']={n:sha((H/'actual_v4_attempt_1'/n).read_bytes()) for n in names}
    with (H/'REGISTRY_v5.json').open('x') as f:json.dump(d,f,indent=2)
    print(sha((H/'REGISTRY_v5.json').read_bytes()))
if __name__=='__main__':main()
