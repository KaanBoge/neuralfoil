"""Authenticate completed replay receipts; never execute a model or checker."""
import json
from pathlib import Path
from audit_all_context_producer import ROOT,P,obj,read,pins
OUT=Path(__file__).with_name('ALL_CONTEXT_REPLAY_QA.json')
def main():
    assert not OUT.exists()
    reg=obj(P/'REGISTRY_v3.json','0bf8020c51d8791993d828d3c6dc57c1bb657fcdc143b89f9e556a54abfbdf8a')
    for n,h in reg['sources'].items():read(P/n,h)
    for n,h in reg['external_sources'].items():read(ROOT/n,h)
    p=obj(P/'certificates_produce/COMPLETE.json','0e1a2fd5813ac498cd160a6022fc5e6c9512bfecfde6b4caa94ef7f669a560fd')
    r=obj(P/'certificates_replay/COMPLETE.json','cc3e258a040529fa93c62291a8d142c873934bf7e23d11278d9d5895e1bae0de')
    ap=obj(P/'ROOT_REPLAY_APPROVAL_V3.json',r['approval_sha256'])
    assert r['approval_sha256']=='77e31013131eee17e204ae81d4f0f3db7050a38da383a91d9c98901000b20784'
    assert ap['predecessor_sha256']==r['summary']['predecessor_sha256']=='0e1a2fd5813ac498cd160a6022fc5e6c9512bfecfde6b4caa94ef7f669a560fd'
    assert ap['phase']==r['phase']=='certificates_replay' and ap['registry_sha256']==r['registry_sha256']
    pins(P/'certificates_produce',p);pins(P/'certificates_replay',r)
    table=obj(P/'CONTEXTS.json');assert ap['contexts']==[x['context'] for x in table]
    assert set(r['summary']['contexts'])==set(ap['contexts'])
    count=members=0;times=[];memory=[];last=None
    for row in table:
        ctx=row['context'];pe=p['summary']['contexts'][ctx];e=r['summary']['contexts'][ctx]
        if ctx=='final':
            assert e['status']=='INHERITED_AUTHENTICATED'
            cr=obj(P.parent/'actual_replay_attempt_1/COMPLETE.json',e['replay_complete_sha256']);pins(P.parent/'actual_replay_attempt_1',cr)
            pr=obj(P.parent/'actual_producer_attempt_1/COMPLETE.json',e['producer_complete_sha256']);pins(P.parent/'actual_producer_attempt_1',pr)
            assert e['certificate_sha256']==pe['certificate_sha256'] and e['summary']==pe['summary']
            continue
        folder=P/'certificates_replay'/ctx
        cr=obj(folder/'COMPLETE.json',e['complete_sha256']);pins(folder,cr)
        prior=obj(P/'certificates_produce'/ctx/'COMPLETE.json',pe['complete_sha256']);pins(P/'certificates_produce'/ctx,prior)
        assert e['producer_complete_sha256']==pe['complete_sha256']
        assert e['status']=='PASS_CONTEXT_REPLAY' and cr['status']=='COMPLETE'
        assert cr['registry_sha256']==r['registry_sha256'] and cr['approval_sha256']==r['approval_sha256']
        assert cr['summary']=={k:v for k,v in e.items() if k!='complete_sha256'}
        for k in ['model_sha256','certificate_sha256','counts','summary']:assert e[k]==pe[k]
        assert e['model_sha256']==row['sha256']
        checked=obj(folder/'REPLAY.json',cr['outputs']['REPLAY.json'])
        assert checked['status']=='PASS_INDEPENDENT_ADJACENT_PAIR_REPLAY' and checked['all_cartesian_equals_independent'] is True
        assert checked['model_sha256']==row['sha256'] and checked['summary']==e['summary'] and checked['counts']==e['counts']
        count+=checked['counts']['attempted_pairs'];memory.append(e['memory']['estimated_owned_peak_bytes']);assert e['memory']['limit_bytes']==268435456
        events=obj(folder/'ACCESS.json',cr['outputs']['ACCESS.json']);m=[x for x in events if x.get('kind')=='npz_materialize']
        assert len(m)==7 and all(x['archive_sha256']==row['sha256'] for x in m);members+=len(m)
        assert {x['member'] for x in m}=={'initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets'}
        for event in events:
            if 'path' in event:assert not any(s in event['path'] for s in ['/calibration/','/scoring/','/native/'])
        if last:assert cr['start_utc']>=last
        last=cr['finish_utc'];times.append(cr['seconds'])
        process=obj(P/'certificates_replay'/f'process_{ctx}.json');assert process['returncode']==0 and process['interruption'] is None
    assert count==1313350 and members==105
    logical=sum(x.stat().st_size for name in ['certificates_produce','certificates_replay'] for x in (P/name).rglob('*') if x.is_file())
    assert logical==550345169 and max(memory)==235562531
    result={'status':'PASS_AUTHENTICATED_REPLAY_RECEIPT_AUDIT','fresh_replays':15,'inherited_final':1,'new_pair_records':count,'reported_tree_member_materializations':members,'seconds':r['seconds'],'child_seconds_range':[min(times),max(times)],'max_estimated_owned_bytes':max(memory),'cumulative_logical_bytes':logical,'reviewer_model_loads':0,'reviewer_checker_executions':0}
    with OUT.open('x') as f:json.dump(result,f,indent=2)
    print(result)
if __name__=='__main__':main()
