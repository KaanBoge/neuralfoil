"""Authenticate completed replay metadata only; no model/proof execution."""
import json,hashlib
from pathlib import Path
from audit_cold_receipts import auth,ledger,HERE,ROOT,P,PS,CS
R=HERE/'attempt_1';PIN='af092b5b5a7149c1156375bf784c700035d785324d23494f323aa14f5efcb4aa'
def main():
    out=HERE/'ACTUAL_REPLAY_RECEIPT_QA.json'
    if out.exists():raise FileExistsError('preserve audit')
    r=auth(R/'COMPLETE.json',PIN,True);auth(R/'COMPLETE.json.partial',PIN)
    assert r['status']=='COMPLETE' and r['phase']=='four_tree_matching_replay' and not (R/'FAILURE.json').exists()
    reg=auth(HERE/'CHECKER_SOURCE_REGISTRY_V1.json',CS,True);pr=auth(P/'REGISTRY_SOURCE_V1.json',PS,True)
    assert reg['producer_registry_sha256']==PS and reg['sources']==pr['checker_sources']
    for e in reg['sources'].values():auth(ROOT/e['path'],e['sha256'])
    for n,h in pr['sources'].items():auth(P/n,h)
    for e in pr['predecessors'].values():auth(ROOT/e['path'],e['sha256'])
    ap=auth(HERE/'ROOT_REPLAY_APPROVAL.json','07f490cac240de2c4e4196c07d430e1bb05fab7379ff9a8fd6d990c9d4f0d2a8',True)
    assert ap['real_execution_authorized'] is True
    for k in ['checker_registry_sha256','producer_registry_sha256','model_sha256','phase','producer_complete_sha256','certificate_sha256']:assert ap[k]==r[k]
    for k,v in {'workers':1,'seconds':900,'owned_cap':256*2**20,'output_cap':64*2**20}.items():assert ap[k]==r['limits'][k]==v and type(ap[k]) is int
    pc=auth(P/'attempt_1/COMPLETE.json',ap['producer_complete_sha256'],True);pa=auth(P/'ROOT_PRODUCER_APPROVAL.json',ap['producer_approval_sha256'],True)
    assert pc['outputs']['certificate.json']==ap['certificate_sha256'] and pc['approval_sha256']==ap['producer_approval_sha256']
    auth(P/'attempt_1/certificate.json',ap['certificate_sha256'])
    for n,h in [('ROOT_SOURCE_REVIEW.json',ap['source_review_sha256']),('COLD_GATE_PASS.json',ap['synthetic_gate_sha256'])]:auth(P/n,h)
    for n,h in r['outputs'].items():auth(R/n,h)
    assert set(x.name for x in R.iterdir())==set(r['outputs'])|{'COMPLETE.json','COMPLETE.json.partial'}
    result=auth(R/'REPLAY.json',r['outputs']['REPLAY.json'],True)
    for k in ['stage0','original_adjacent','final','counts']:assert result[k]==r['summary'][k]==pc['summary'][k]
    assert result['counts']=={'blocks':100,'stages':400,'paths':6000,'path_edges':32393,'pair_classifications':135000,'feasible_pairs':112430}
    events=auth(R/'ACCESS.json',r['outputs']['ACCESS.json'],True)
    members=[e for e in events if e['operation']=='independent NPZ materialization'];assert len(members)==7 and len({e['member'] for e in members})==7
    modelpaths=set()
    for e in events:
        if 'path' not in e:continue
        if e['path'].endswith('.npz'):modelpaths.add(e['path']);continue
        auth(Path(e['path']),e['sha256'])
    assert modelpaths=={str(ROOT/'independent_environment/bounds_extraction/arrays/tree_31_capped.npz')}
    s=r['summary'];assert s['fits']==s['features_targets_calibration_loaded']==0 and s['R_used'] is False and s['model_materializations']==1
    assert 0<r['elapsed_seconds']<900 and s['checker_accounting']['estimated_owned_bytes']<=s['wrapper_owned_admission_peak']<256*2**20
    logical=sum(x.stat().st_size for x in R.iterdir());assert logical<64*2**20
    q={'status':'PASS_SAVED_INDEPENDENT_REPLAY_RECEIPTS','complete_sha256':PIN,'replay_sha256':r['outputs']['REPLAY.json'],'certificate_sha256':ap['certificate_sha256'],'counts':s['counts'],'elapsed_seconds':r['elapsed_seconds'],'checker_owned_estimate':s['checker_accounting']['estimated_owned_bytes'],'wrapper_admission_peak':s['wrapper_owned_admission_peak'],'logical_bytes':logical,'phase_access_events':len(events),'reported_unique_model_members':7,'source_metadata_hash_checks':len(ledger),'ledger':ledger,'auditor_model_materializations':0,'auditor_proof_replays':0,'exact_producer_replay_result_equality':True}
    with out.open('x') as f:json.dump(q,f,indent=2,sort_keys=True)
    print(json.dumps({k:v for k,v in q.items() if k!='ledger'}));print('QA_SHA256='+hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
