"""Saved capsule metadata audit. Old certificate hash-only; no model reader."""
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import math
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
PLAN=HERE.parent
ROOT=PLAN.parents[1]
REG='2bc694c0a87cd0ddec3152ec03fe41d8a3e429141c41fcd8f227f1ab0314ba2a'
CAP='0b1fd98b47b715c2007ccc598d740b7a9995b81e27d4e2462cd1238c2694a369'
APP='d74f24fb8d23f613e997aec8903adc88e20997542920664c2bf57f997280bbc5'
MODEL='ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'


def digest(path):
    assert not any(x.is_symlink() for x in (path,*path.parents))
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):h.update(b)
    return h.hexdigest()


def fraction(d):
    assert type(d)==dict and set(d)=={'encoding','numerator','denominator'}
    assert d['encoding']=='signed_hex_fraction_v1'
    n,z=d['numerator'],d['denominator']
    assert type(n)==str and type(z)==str and max(len(n),len(z))<=1027
    a,b=int(n,16),int(z,16)
    assert hex(a)==n and hex(b)==z and b>0
    assert max(abs(a).bit_length(),b.bit_length())<=4096 and math.gcd(a,b)==1
    return Fraction(a,b)


def main():
    pins={};reads=[]
    def pin(p,h=None):
        actual=digest(p)
        if h:assert actual==h,str(p)
        pins[str(p.relative_to(ROOT))]=actual
        return actual
    def load(p,h=None):
        actual=pin(p,h)
        assert p.name!='certificate.json' and p.suffix=='.json'
        assert p.stat().st_size<2**20
        raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==actual
        reads.append(str(p.relative_to(ROOT)))
        return json.loads(raw)
    reg=load(PLAN/'CAPSULE_REGISTRY.json',REG)
    approval=load(PLAN/'ROOT_CAPSULE_APPROVAL.json',APP)
    review=load(PLAN/'ROOT_CAPSULE_SOURCE_REVIEW.json',approval['source_review_sha256'])
    assert review['status']=='PASS_SOURCE_REVIEW' and review['registry_sha256']==REG
    attempt=PLAN/'capsule_attempt_1'
    complete=load(attempt/'COMPLETE.json')
    capsule=load(attempt/'CAPSULE.json',CAP)
    assert complete['status']=='COMPLETE' and complete['phase']=='capsule'
    assert complete['registry_sha256']==REG and complete['approval_sha256']==APP
    assert complete['source_pins']==reg['sources'] and complete['helper_pins']==reg['helpers']
    assert set(reg['sources'])=={'adapter.py','prototype.py','production_support.py','capsule.py','run_phase.py'}
    for name,h in reg['sources'].items():pin(PLAN/name,h)
    for row in reg['helpers'].values():pin(ROOT/row['path'],row['sha256'])
    for name,h in complete['outputs'].items():pin(attempt/name,h)
    assert set(p.name for p in attempt.iterdir())==set(complete['outputs'])|{'COMPLETE.json'}
    refs={}
    for role,row in reg['inputs'].items():
        p=ROOT/row['path']
        if role=='old_certificate':pin(p,row['sha256'])
        else:refs[role]=load(p,row['sha256'])
    pc,rc,rr=(refs[k] for k in ('old_producer_complete','old_replay_complete','old_replay_result'))
    h=lambda role:reg['inputs'][role]['sha256']
    assert pc['status']==rc['status']=='COMPLETE'
    assert pc['model_sha256']==rc['model_sha256']==rr['model_sha256']==MODEL
    assert pc['outputs']['certificate.json']==rc['certificate_sha256']==h('old_certificate')
    assert rc['producer_complete_sha256']==h('old_producer_complete')
    assert rc['outputs']['REPLAY.json']==h('old_replay_result')
    assert pc['registry_sha256']==rc['producer_registry_sha256']==h('old_producer_registry')
    assert rc['checker_registry_sha256']==h('old_checker_registry')
    assert pc['approval_sha256']==h('old_producer_approval') and rc['approval_sha256']==h('old_replay_approval')
    assert rr['status']=='PASS_INDEPENDENT_FOUR_TREE_MATCHING_REPLAY'
    keys={'schema','model_sha256','domain','initial','certificate_sha256','producer_complete_sha256','replay_complete_sha256','replay_result_sha256','extraction_source_sha256','endpoints','final'}
    assert set(capsule)==keys and capsule['schema']=='OLD_FOUR_GLOBAL_CHAIN_V1'
    assert capsule['model_sha256']==MODEL and capsule['domain']=='FINITE_X62_V1'
    for a,b in [('certificate_sha256','old_certificate'),('producer_complete_sha256','old_producer_complete'),('replay_complete_sha256','old_replay_complete'),('replay_result_sha256','old_replay_result')]:assert capsule[a]==h(b)
    assert capsule['extraction_source_sha256']==reg['sources']['capsule.py']
    assert capsule['final']==rr['final']==rc['summary']['final']
    initial=float.fromhex(capsule['initial']);assert math.isfinite(initial)
    assert type(capsule['endpoints'])==list and len(capsule['endpoints'])==100
    for j,row in enumerate(capsule['endpoints']):
        assert set(row)=={'stage','outgoing'} and type(row['stage'])==int and row['stage']==4*(j+1)
        assert type(row['outgoing'])==list and len(row['outgoing'])==2
        lo,hi=map(fraction,row['outgoing']);assert lo<=hi
    assert capsule['endpoints'][-1]['outgoing']==[capsule['final']['lower'],capsule['final']['upper']]
    for x in capsule['final'].values():fraction(x)
    access=load(attempt/'ACCESS.json',complete['outputs']['ACCESS.json'])
    for event in access:
        if 'path' in event and 'sha256' in event:pin(Path(event['path']),event['sha256'])
    parsed=[e for e in access if e['operation']=='bounded_old_certificate_JSON_parse']
    assert len(parsed)==1 and parsed[0]['sha256']==h('old_certificate')
    assert parsed[0]['lexical_allocation']==complete['summary']['lexical_allocation']==57338817
    assert complete['summary']['global_endpoints']==100 and complete['summary']['model_materializations']==0
    assert complete['limits']==dict(output_cap=64*2**20,owned_cap=256*2**20,seconds=900,workers=1)
    assert complete['elapsed_seconds']<900 and sum(p.stat().st_size for p in attempt.iterdir())<64*2**20
    assert approval['registry_sha256']==REG and approval['entrypoint_sha256']==reg['sources']['run_phase.py']
    assert approval['actual_execution_authorized'] is True and approval['output']=='capsule_attempt_1'
    proposal=dict(schema='EIGHT_SOURCE_REGISTRY_V1',phase='producer',sources=reg['sources'],
                  helpers={'old_inventory':dict(path='model_proposal/four_tree_matching_plan/producer.py',sha256='a445462d5faf314ecbd7ea06cb45feb8c26cf99de8d05d246d026b4bbea4b40e')},
                  inputs={})
    for role,p in [('capsule',attempt/'CAPSULE.json'),('capsule_complete',attempt/'COMPLETE.json'),('capsule_approval',PLAN/'ROOT_CAPSULE_APPROVAL.json'),('capsule_registry',PLAN/'CAPSULE_REGISTRY.json')]:
        proposal['inputs'][role]=dict(path=str(p.relative_to(ROOT)),sha256=pin(p))
    proposal['inputs']['model']=dict(path='independent_environment/bounds_extraction/arrays/tree_31_capped.npz',sha256=MODEL)
    qa=dict(status='PASS_SAVED_CAPSULE_SCHEMA_AND_LINEAGE_AUDIT',utc=datetime.now(timezone.utc).isoformat(),
            pins=pins,unique_pins=len(pins),audit_source_sha256=digest(Path(__file__)),
            capsule_sha256=CAP,complete_sha256=pin(attempt/'COMPLETE.json'),registry_sha256=REG,
            endpoints=100,first_stage=4,last_stage=400,final=capsule['final'],
            elapsed_seconds=complete['elapsed_seconds'],lexical_allocation=57338817,
            actual_directory_bytes=sum(p.stat().st_size for p in attempt.iterdir()),
            producer_ledger_records=len(access),audit_JSON_parses=reads,
            audit_old_certificate_parses=0,audit_model_reads=0,
            limitations=['Endpoint extraction correctness inherits the authenticated completed old proof and frozen extractor; old certificate was hash-only here.',
                         'Lexical allocation is an engineering estimate, not RSS. No actual eight-tree result.'])
    for name,value in [('QA.json',qa),('PRODUCER_REGISTRY_PROPOSAL.json',proposal)]:
        with (HERE/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(qa,sort_keys=True))


if __name__=='__main__':main()
