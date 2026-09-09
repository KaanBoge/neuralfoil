"""Metadata-only successor freeze, no scientific materialization."""
from pathlib import Path
import hashlib,json
H=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    raw=(H/'REGISTRY_v3.json').read_bytes()
    if sha(raw)!='b02c64e7d9a930a3c556a729fc2cdeaadc12f21ebd7842a9b17b2db74bda6014':raise ValueError('V3 registry identity')
    old=json.loads(raw)
    for n,h in old['sources'].items():
        if sha((H/n).read_bytes())!=h:raise ValueError('preserved V3 source changed')
    d=dict(old);d['v3_registry_sha256']=sha(raw);d['v3_sources']=old['sources']
    d['sources']={n:h for n,h in old['sources'].items() if n not in ['runner_v3.py','freeze_v3.py','README_v3.md']}
    for n in ['runner_v4.py','freeze_v4.py','README_v4.md','test_v4.py']:d['sources'][n]=sha((H/n).read_bytes())
    d['status']='SOURCE_ONLY_V4_REVIEW_REQUIRED_NO_ACTUAL_APPROVAL'
    for k in ['scopes','routes','schedule','workload_rows','runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','cold_repeats','warmups','warm_repeats','workers']:
        if d[k]!=old[k]:raise ValueError('scientific/workload contract changed')
    with (H/'REGISTRY_v4.json').open('x') as f:json.dump(d,f,indent=2)
    print(sha((H/'REGISTRY_v4.json').read_bytes()))
if __name__=='__main__':main()
