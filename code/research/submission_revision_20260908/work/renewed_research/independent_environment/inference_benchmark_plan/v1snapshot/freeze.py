"""Source-only freeze: hashes bytes/manifests; never opens a numerical array."""
from pathlib import Path
import json,hashlib,zipfile
H=Path(__file__).resolve().parent
ROOT=H.parents[4]
sha=lambda b:hashlib.sha256(b).hexdigest()
REV='submission_revision_20260908/work/'
R=REV+'renewed_research/'
FEATURE=REV+'feature_reproduction/addon/'
ORIGINAL='model_development_20260907_risk_policy/portable/'
PARENT=R+'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
ADDON=R+'model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip'

def main():
    out=H/'REGISTRY.json'
    if out.exists():raise FileExistsError(out)
    paths=[FEATURE+n for n in ['manifest.json','feature_math.py','expected_runtime.json','data/SG_exposed.npz','data/W_new_challenge.npz']]
    paths += [ORIGINAL+n for n in ['manifest.json','experimental_policies.json','inference_references.npz']]
    paths += ['model_development_20260907_geometry_frontier/engineering/fast_inference/prepared.py']
    fm=json.loads((ROOT/FEATURE/'manifest.json').read_text())
    for cohort in ['SG_exposed','W_new_challenge']:
        for d in fm['coordinates'][cohort].values():paths.append(FEATURE+d['path'])
    files={p:sha((ROOT/p).read_bytes()) for p in sorted(set(paths))}
    expected_fm='7279aa56fee85d3ae16223efe0067ab9aba6901e58600f65b7066f5489d55903'
    assert files[FEATURE+'manifest.json']==expected_fm
    for p,h in files.items():
        if p.startswith(FEATURE) and p[len(FEATURE):] in fm['files']:assert fm['files'][p[len(FEATURE):]]==h
    om=json.loads((ROOT/ORIGINAL/'manifest.json').read_text())
    assert files[ORIGINAL+'manifest.json']=='706d9604d95b31f5614fc9c768e67bb3c6a84c2b7d8aa1c9f133e03c03397d82'
    for n in ['experimental_policies.json','inference_references.npz']:assert files[ORIGINAL+n]==om['package_hashes'][n]
    archives={}
    for path,expected,manifest_sha,names in [
      (PARENT,'673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3','3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154',
       ['code/qualified_numerics.py','code/policy.py','code/evaluator.py','trees/final.npz']+[f'native/{c}.npz' for c in ['SG_exposed','W_new_challenge']]+[f'scalars/qualified_{b}_harm_001_final.json' for b in ['generic','structural']]),
      (ADDON,'45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b','dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d',
       [f'predictions/{c}.npz' for c in ['SG_exposed','W_new_challenge']]+[f'scalars/qualified_{b}_kl_harm_001_final.json' for b in ['generic','structural']])]:
        assert sha((ROOT/path).read_bytes())==expected
        with zipfile.ZipFile(ROOT/path) as z:
            raw=z.read('manifest.json');assert sha(raw)==manifest_sha
            manifest=json.loads(raw)
        archives[path]={'sha256':expected,'manifest_sha256':manifest_sha,'members':{n:manifest['files'][n] for n in names}}
    sources={n:sha((H/n).read_bytes()) for n in ['PLAN.md','README.md','serving.py','timing.py','loader.py','runner.py','test_source.py','freeze.py']}
    result={'status':'SOURCE_ONLY_NO_REAL_REQUEST_APPROVAL','project_root_argument_required':True,'files':files,'archives':archives,'sources':sources,
            'workload_rows':{'SG_exposed':242,'W_new_challenge':255},'runtime':'/opt/anaconda3/bin/python','max_seconds':600,'max_request_seconds':60,'max_rss_bytes':2*1024**3,
            'source_stage_numerical_arrays_opened':False,'outcomes_allowed':False}
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(sha(out.read_bytes()))
if __name__=='__main__':main()

