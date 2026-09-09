"""Source/metadata-only registry successor; no scientific input reads."""
from pathlib import Path
import hashlib,json,copy
H=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    raw=(H/'REGISTRY_v5.json').read_bytes()
    if sha(raw)!='b70d1db4369a1ad8404f0a1c2ff1deef661af22c4644b3243b9c81f0cd654906':raise ValueError('V5 registry identity')
    old=json.loads(raw)
    for n,h in old['sources'].items():
        if sha((H/n).read_bytes())!=h:raise ValueError('preserved V5 source changed')
    d=copy.deepcopy(old);d['v5_registry_sha256']=sha(raw);d['v5_sources']=old['sources']
    d['sources']={n:h for n,h in old['sources'].items() if n not in ['runner_v5.py','watchdog_v3.py','freeze_v5.py','README_v5.md']}
    for n in ['runner_v6.py','watchdog_v6.py','freeze_v6.py','README_v6.md','test_v6.py']:d['sources'][n]=sha((H/n).read_bytes())
    d['status']='SOURCE_ONLY_V6_REVIEW_REQUIRED_NO_ACTUAL_APPROVAL'
    d['terminal_observation_contract']={'max_grace_seconds':.05,'query_timeout_seconds':2,'requires_prior_valid_sample':True,'requires_exit_zero':True,'requires_authenticated_positive_finite_self_peak_under_cap':True,'not_continuous_RSS_certificate':True}
    for k in ['scopes','routes','schedule','workload_rows','runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','cold_repeats','warmups','warm_repeats','workers','reference_contract']:
        if d[k]!=old[k]:raise ValueError('unchanged contract '+k)
    names=['FAILURE.json','preflight_COMPLETE.json','cold_original_unpenalized_transfer_quantized_teacher_COMPLETE.json','cold_original_unpenalized_transfer_quantized_teacher_PROCESS.json','ARCHIVE_COMPARISONS.json']
    d['preserved_v5_failure']={n:sha((H/'actual_v5_attempt_1'/n).read_bytes()) for n in names}
    with (H/'REGISTRY_v6.json').open('x') as f:json.dump(d,f,indent=2)
    print(sha((H/'REGISTRY_v6.json').read_bytes()))
if __name__=='__main__':main()
