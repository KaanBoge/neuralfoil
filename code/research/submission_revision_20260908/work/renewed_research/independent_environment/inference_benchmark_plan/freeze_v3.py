"""Bounded source-only V3 freeze; retains V2 registry and all source bytes."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    raw=(H/'REGISTRY_v2.json').read_bytes()
    if sha(raw)!='edd4cf632d01fd1560fa5ae9b1dd6a10f63257c248f7e85f26b47e11950c9c4c':raise ValueError('V2 registry changed')
    old=json.loads(raw)
    for n,h in old['sources'].items():
        if sha((H/n).read_bytes())!=h:raise ValueError('V2 source changed '+n)
    d=dict(old);d['v2_registry_sha256']=sha(raw);d['v2_sources']=old['sources']
    d['sources']={n:h for n,h in old['sources'].items() if n in ['PLAN.md','serving.py','timing.py','provenance_v2.py','loader_v2.py']}
    for n in ['README_v3.md','measurement_v3.py','watchdog_v3.py','runner_v3.py','freeze_v3.py','test_v3.py']:d['sources'][n]=sha((H/n).read_bytes())
    d['status']='SOURCE_ONLY_V3_REVIEW_REQUIRED_NO_ACTUAL_APPROVAL'
    with (H/'REGISTRY_v3.json').open('x') as f:json.dump(d,f,indent=2)
    print(sha((H/'REGISTRY_v3.json').read_bytes()))
if __name__=='__main__':main()
