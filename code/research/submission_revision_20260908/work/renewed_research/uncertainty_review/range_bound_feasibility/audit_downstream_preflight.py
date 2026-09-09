"""Read-only preflight ledger/bound authentication, no array materialization."""
import json,hashlib,collections
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'model_proposal/paired_tree_plan/all_context_downstream_plan'
OUT=Path(__file__).with_name('DOWNSTREAM_PREFLIGHT_QA.json')
def read(p,h=None):
    b=p.read_bytes()
    if h:assert hashlib.sha256(b).hexdigest()==h,str(p)
    return b
def obj(p,h=None):return json.loads(read(p,h))
def q(v):return Fraction(int(v['numerator'],16),int(v['denominator'],16))
def main():
    assert not OUT.exists()
    pin='9abd91d55147c12c7ba2e4c6446e398409ebc4b91accd9cee6bf7a81994e7912'
    r=obj(P/'preflight/COMPLETE.json',pin)
    assert read(P/'preflight/COMPLETE.pending.json')==read(P/'preflight/COMPLETE.json')
    assert not (P/'preflight/FAILURE.json').exists()
    reg=obj(P/'REGISTRY.json',r['registry_sha256'])
    assert r['registry_sha256']=='f55a993c6b9029db25bb53e0329d84f8f6f4b4efdb14107ceabd7af5b82b2b17'
    ap=obj(P/'ROOT_PREFLIGHT_APPROVAL.json',r['approval_sha256'])
    assert r['approval_sha256']=='b6073acc3f74114cef2fb9e9626a1805a1c4cd6e39b850b7642a46566dd35932'
    assert ap['phase']==r['phase']=='preflight' and ap['registry_sha256']==r['registry_sha256']
    assert ap['predecessor_sha256']==r['summary']['predecessor_sha256']==reg['inherited']['replay_sha256']
    for n,h in r['outputs'].items():read(P/'preflight'/n,h)
    for n,h in reg['sources'].items():read(P/n,h)
    for n,h in reg['external_sources'].items():read(ROOT/n,h)
    a=obj(P/'preflight/ACCESS.json');seen={}
    for x in a:
        if 'path' in x and 'sha256' in x:
            p=x['path'];assert p not in seen or seen[p]==x['sha256'];seen[p]=x['sha256']
    for p,h in seen.items():read(Path(p),h)
    z=[x for x in a if x.get('operation')=='NPZ materialization'];assert len(z)==202
    inventory=collections.defaultdict(list)
    for x in z:inventory[x['file']].append(x['member'])
    expected={f'calibration/{ctx}.npz':{'indices','BASE_CD','core','anchor','gate','group','nf2_row_id'} for ctx in reg['contexts']}
    expected.update({f'native/{ctx}.npz':{'indices','BASE_CD','core','anchor','gate'} for ctx in reg['contexts']+['SG_exposed','W_new_challenge']})
    assert set(inventory)==set(expected)
    for f,keys in inventory.items():assert len(keys)==len(set(keys)) and set(keys)==expected[f]
    assert not any(x.get('member')=='MEAS_CD' or x.get('operation')=='pandas.read_csv' for x in a)
    assert not any(x.get('operation')=='JSON parse' and any(t in str(x.get('member','')) for t in ['scalars/','scoring/']) for x in a)
    ref=obj(P/'preflight/REFERENCE_PASS.json')
    assert ref['target_members_materialized'] is False and ref['contexts']==reg['contexts']
    assert set(ref['native_contexts'])==set(reg['contexts']+['SG_exposed','W_new_challenge'])
    prior=obj(P.parent/'all_context_plan/certificates_replay/COMPLETE.json',reg['inherited']['replay_sha256'])
    old=obj(ROOT/'model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json')
    old={v['context']:v for v in old['records']}
    assert set(ref['bounds'])==set(reg['contexts'])
    for ctx,v in ref['bounds'].items():
        s=prior['summary']['contexts'][ctx]['summary']
        assert q(v['D'])==q(s['D']['B']) and q(v['R_diagnostic'])==q(s['R']['B'])
        b=old[ctx]['B_structural'];assert q(v['Stage0'])==Fraction(int(b['numerator']),int(b['denominator']))
        assert 0<=q(v['R_diagnostic'])<=q(v['D'])<q(v['Stage0'])
    used=sum(x.stat().st_size for n in reg['output_roots'] for x in (ROOT/n).rglob('*') if x.is_file())
    assert used<reg['logical_cap']-reg['failure_reserve']
    result={'status':'PASS_PREFLIGHT_RECEIPT_LEDGER_BOUND_AUDIT','complete_sha256':pin,'seconds':r['seconds'],'events':len(a),'unique_path_pins_verified':len(seen),'array_containers':34,'array_members':202,'contexts':16,'target_member_materializations':0,'reviewer_array_materializations':0,'cumulative_bytes_at_audit':used,'recorded_pre_complete_bytes':r['cumulative_bytes_before_complete']}
    with OUT.open('x') as f:json.dump(result,f,indent=2)
    print(result)
if __name__=='__main__':main()
