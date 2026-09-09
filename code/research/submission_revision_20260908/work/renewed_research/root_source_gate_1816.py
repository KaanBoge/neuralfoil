"""Finite source/metadata authentication before separately approved execution."""
from pathlib import Path
import datetime
import hashlib
import json

ROOT = Path(__file__).resolve().parent
sha = lambda raw: hashlib.sha256(raw).hexdigest()
ledger = []

def check(path, expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError('nonregular source '+str(path))
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError('source identity '+str(path))
    ledger.append({'path':str(path.relative_to(ROOT)), 'sha256':expected, 'bytes':len(raw)})
    return raw

def members(directory, table):
    for name, pin in table.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('noncanonical source')
        check(directory/name, pin)

def main():
    paired = ROOT/'model_proposal/paired_tree_plan/all_context_plan'
    bench = ROOT/'independent_environment/inference_benchmark_plan'
    p = json.loads(check(paired/'REGISTRY_v3.json', '0bf8020c51d8791993d828d3c6dc57c1bb657fcdc143b89f9e556a54abfbdf8a'))
    b = json.loads(check(bench/'REGISTRY_v4.json', 'b48543cc24201a161c609a08d1a1c7160db86d674becd740263bb1301d491a5e'))
    members(paired,p['sources']); members(ROOT,p['external_sources']); members(paired,p['synthetic_evidence'])
    p2 = json.loads(check(paired/'REGISTRY_v2.json',p['v2_registry_sha256']))
    for name, pin in p2['sources'].items():
        check((paired/'v2_snapshot'/name) if name.endswith(('.py','.md')) else paired/name, pin)
    members(bench,b['sources'])
    b3 = json.loads(check(bench/'REGISTRY_v3.json',b['v3_registry_sha256']))
    members(bench,b3['sources'])
    for key in ['scopes','routes','schedule','workload_rows','runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','cold_repeats','warmups','warm_repeats','workers']:
        if b[key] != b3[key]:
            raise ValueError('benchmark workload changed: '+key)
    if len(p['contexts']) != 16 or p['new_scalar_count'] != 32 or p['actual_phase_authorized']:
        raise ValueError('paired source contract')
    for item in ledger:
        check_again = ROOT/item['path']
        if sha(check_again.read_bytes()) != item['sha256']:
            raise ValueError('end source mutation')
    result={'status':'PASS_SOURCE_METADATA_ONLY','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'actual_arrays_materialized':0,'actual_requests':0,'ledger':ledger,
            'scope':'Source review and synthetic results are not actual execution approval.'}
    out=ROOT/'ROOT_SOURCE_GATE_1816.json'
    with out.open('x') as f:
        json.dump(result,f,indent=2)
    print(json.dumps({'status':result['status'],'source_metadata_checks':len(ledger),'sha256':sha(out.read_bytes())}))

if __name__=='__main__':
    main()
