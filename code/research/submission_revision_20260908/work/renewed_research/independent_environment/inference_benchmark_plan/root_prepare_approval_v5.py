"""Root's explicit, source-reviewed one-attempt V5 benchmark approval.

This prepares approval only; no actual input arrays, inference or timing runs.
"""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
RESEARCH=HERE.parents[1]

def checked(path,h):
    path=Path(path).absolute()
    assert path.is_relative_to(PROJECT) and not any(p.is_symlink() for p in (path,*path.parents))
    raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==h,str(path)
    return raw

def main():
    regsha='b70d1db4369a1ad8404f0a1c2ff1deef661af22c4644b3243b9c81f0cd654906'
    reg=json.loads(checked(HERE/'REGISTRY_v5.json',regsha))
    for key in ('sources','v4_sources'):
        for name,h in reg[key].items():checked(HERE/name,h)
    for name,h in reg['preserved_v4_failure'].items():checked(HERE/'actual_v4_attempt_1'/name,h)
    review=RESEARCH/'model_proposal/editorial/benchmark_v5_review/REVIEW.md'
    text=checked(review,'d0a841a60501fcc00258fd9cb961f416d7b6e33305f5701d4e56f628ead6fc8d').decode()
    assert regsha in text and 'PASS' in text
    old=json.loads(checked(HERE/'ROOT_ACTUAL_APPROVAL_V4.json','1b58ef0b87300f3ed4173ce98afc8b5030c8222a33d14fee675d7e1411f99462'))
    for k in ('runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','routes','schedule','cold_repeats','warmups','warm_repeats','workers'):
        assert old[k]==reg[k],k
    out=HERE/'actual_v5_attempt_1';assert not out.exists()
    old.update(authorized_phase='one_fixed_inference_benchmark_v5',registry_sha256=regsha,
        output=str(out),reference_contract=reg['reference_contract'],host_other_scientific_jobs_stopped=True)
    raw=(json.dumps(old,indent=2)+'\n').encode()
    target=HERE/'ROOT_ACTUAL_APPROVAL_V5.json'
    with target.open('xb') as f:f.write(raw)
    print(json.dumps({'approval':str(target),'sha256':hashlib.sha256(raw).hexdigest(),
        'output':str(out),'reference_contract':reg['reference_contract'],
        'actual_execution_performed':False}))

if __name__=='__main__':main()
