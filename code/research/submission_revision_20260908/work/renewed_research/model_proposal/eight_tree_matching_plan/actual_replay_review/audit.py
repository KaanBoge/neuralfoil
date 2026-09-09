"""Authenticate saved replay metadata; exact decimal bound conversion only."""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PLAN=HERE.parent
ROOT=PLAN.parents[1]
R=PLAN/'replay_plan'

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()

def fraction(v):
    assert set(v)=={'encoding','numerator','denominator'} and v['encoding']=='signed_hex_fraction_v1'
    n,d=int(v['numerator'],16),int(v['denominator'],16)
    assert d>0 and hex(n)==v['numerator'] and hex(d)==v['denominator']
    q=Fraction(n,d)
    assert q.numerator==n and q.denominator==d
    return q

def decimal(q):
    with localcontext() as c:
        c.prec=60
        return str(Decimal(q.numerator)/Decimal(q.denominator))

def main():
    pins={};parses=[]
    def pin(p,h=None):
        p.relative_to(ROOT)
        assert not any(x.is_symlink() for x in (p,*p.parents))
        actual=digest(p)
        if h is not None:assert actual==h,str(p)
        pins[str(p.relative_to(ROOT))]=actual
        return actual
    def read(p,h=None):
        actual=pin(p,h);raw=p.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==actual
        parses.append(str(p.relative_to(ROOT)))
        return json.loads(raw)
    attempt=R/'actual_replay_attempt_1'
    reg=read(R/'REGISTRY.json','49d0505678ca34ad15b1ae0716bb07e010d8d7751c175994baeb5bf2f1fa25d0')
    approval=read(R/'ROOT_APPROVAL.json','f54e32cf7daeb8e46ca0baca5dc9ac1d5075c140d7c885dd49fd4025d03261d9')
    complete=read(attempt/'COMPLETE.json')
    result=read(attempt/'REPLAY.json','0176cd9b3efba8290fe6c148be725acd9c9c58ed8480e8ffe1d607fb57d15c48')
    review=read(R/'ROOT_SOURCE_REVIEW.json',approval['source_review_sha256'])
    assert complete['status']=='COMPLETE' and result['status']=='PASS_INDEPENDENT_EIGHT_TREE_STREAM_REPLAY'
    assert complete['summary']==result and complete['registry_sha256']==approval['registry_sha256']==pin(R/'REGISTRY.json')
    assert review['status']=='PASS_SOURCE_REVIEW' and review['registry_sha256']==complete['registry_sha256']
    assert complete['approval_sha256']==pin(R/'ROOT_APPROVAL.json')
    assert approval['output']==attempt.name and approval['actual_execution_authorized'] is True
    assert approval['seconds']==900 and approval['workers']==1 and approval['owned_cap']==256*2**20 and approval['output_cap']==64*2**20
    assert complete['source_pins']==reg['sources'] and complete['helper_pins']==reg['helpers']
    for name,h in reg['sources'].items():pin(R/name,h)
    for e in reg['helpers'].values():pin(ROOT/e['path'],e['sha256'])
    for e in reg['inputs'].values():pin(ROOT/e['path'],e['sha256'])
    assert len(reg['inputs'])==13
    for name,h in complete['outputs'].items():pin(attempt/name,h)
    assert set(p.name for p in attempt.iterdir())==set(complete['outputs'])|{'COMPLETE.json'}
    refs={k:read(ROOT/e['path'],e['sha256']) for k,e in reg['inputs'].items() if k not in {'model','certificate','old_certificate'}}
    pc,pr=refs['producer_complete'],refs['producer_registry']
    assert pc['status']=='COMPLETE' and complete['producer_complete_sha256']==reg['inputs']['producer_complete']['sha256']
    assert pc['registry_sha256']==reg['inputs']['producer_registry']['sha256']
    assert pc['approval_sha256']==reg['inputs']['producer_approval']['sha256']
    assert pc['outputs']['certificate.jsonl']==complete['certificate_sha256']==result['stream_sha256']==reg['inputs']['certificate']['sha256']
    assert approval['certificate_sha256']==complete['certificate_sha256'] and approval['producer_complete_sha256']==complete['producer_complete_sha256']
    for key in ('counts','final','original_four'):assert pc['summary'][key]==result[key]
    for name,h in pc['outputs'].items():pin((ROOT/reg['inputs']['producer_complete']['path']).parent/name,h)
    for e in pr['inputs'].values():pin(ROOT/e['path'],e['sha256'])
    for name,h in pr['sources'].items():pin(PLAN/name,h)
    for e in pr['helpers'].values():pin(ROOT/e['path'],e['sha256'])
    for key in ('old_producer_complete','old_replay_complete'):
        c=refs[key]
        assert c['status']=='COMPLETE'
        for name,h in c['outputs'].items():pin((ROOT/reg['inputs'][key]['path']).parent/name,h)
    assert refs['old_producer_complete']['outputs']['certificate.json']==reg['inputs']['old_certificate']['sha256']
    assert refs['old_replay_complete']['outputs']['REPLAY.json']==reg['inputs']['old_replay_result']['sha256']
    assert result['identities']==dict(model_sha256=reg['inputs']['model']['sha256'],old4_certificate_sha256=reg['inputs']['old_certificate']['sha256'],old4_replay_complete_sha256=reg['inputs']['old_replay_complete']['sha256'])
    access=read(attempt/'ACCESS.json',complete['outputs']['ACCESS.json'])
    for event in access:
        if 'path' in event and 'sha256' in event:pin(Path(event['path']),event['sha256'])
    materializations=[e for e in access if 'materializ' in e['operation'].lower()]
    members=[e for e in materializations if 'member' in e]
    assert len(members)==7 and len({e['member'] for e in members})==7
    assert result['records']==452 and result['counts']==dict(stages=400,blocks=50,paths=6000,path_edges=32393,pair_classifications=315000,feasible_pairs=265186)
    assert result['stream_bytes']==(ROOT/reg['inputs']['certificate']['path']).stat().st_size
    assert complete['elapsed_seconds']<=900
    assert complete['wrapper_prearray_owned_admission']<=256*2**20 and result['estimated_owned_bytes']<=256*2**20
    sizes={p.name:p.stat().st_size for p in attempt.iterdir()}
    assert sum(sizes.values())<=64*2**20
    old={k:fraction(v) for k,v in result['original_four'].items()}
    new={k:fraction(v) for k,v in result['final'].items()}
    assert 0<new['B']<old['B']
    change=100*(old['B']-new['B'])/old['B']
    display=dict(old_four={k:decimal(v) for k,v in old.items()},eight_tree={k:decimal(v) for k,v in new.items()},
                 B_relative_reduction_percent=decimal(change),B_absolute_reduction=decimal(old['B']-new['B']),
                 exact_strict_B_reduction=True,interpretation='Deterministic bound only; not a measured MAE reduction.')
    for p,h in pins.items():assert digest(ROOT/p)==h
    qa=dict(status='PASS_SAVED_REPLAY_CHAIN_AUDIT',utc=datetime.now(timezone.utc).isoformat(),source_sha256=digest(Path(__file__)),
            pins=pins,unique_pins=len(pins),parsed_metadata=parses,complete=complete,decimal_bound_display=display,
            output_sizes=sizes,actual_output_bytes=sum(sizes.values()),access_records=len(access),
            access_operation_counts=dict(Counter(e['operation'] for e in access)),reported_materializations=materializations,
            audit_model_materializations=0,audit_math_replays=0,
            qualification='Saved independent checker PASS authenticated; this audit does not rerun it. Owned estimates are not RSS. Original conditional producer-accounting record remains unchanged.')
    with (HERE/'QA.json').open('x') as f:json.dump(qa,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(dict(qa_sha256=digest(HERE/'QA.json'),complete_sha256=pin(attempt/'COMPLETE.json'),unique_pins=len(pins),display=display,outputs=sizes)))

if __name__=='__main__':main()
