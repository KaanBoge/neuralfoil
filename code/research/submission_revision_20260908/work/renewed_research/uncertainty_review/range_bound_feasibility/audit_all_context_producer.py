"""Receipt/certificate inventory audit only: no model loading or proof replay."""
import hashlib,json,itertools,collections
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'model_proposal/paired_tree_plan/all_context_plan'
OUT=Path(__file__).with_name('ALL_CONTEXT_PRODUCER_QA.json')
def read(p,h=None):
    b=p.read_bytes()
    if h is not None:assert hashlib.sha256(b).hexdigest()==h,str(p)
    return b
def obj(p,h=None):return json.loads(read(p,h))
def pins(p,r):
    for n,h in r['outputs'].items():read(p/n,h)
def frac(v):return F(int(v['numerator'],16),int(v['denominator'],16))
def oldfrac(v):return F(int(v['numerator']),int(v['denominator']))
def main():
    assert not OUT.exists()
    reg=obj(P/'REGISTRY_v3.json','0bf8020c51d8791993d828d3c6dc57c1bb657fcdc143b89f9e556a54abfbdf8a')
    for n,h in reg['sources'].items():read(P/n,h)
    for n,h in reg['external_sources'].items():read(ROOT/n,h)
    r=obj(P/'certificates_produce/COMPLETE.json','0e1a2fd5813ac498cd160a6022fc5e6c9512bfecfde6b4caa94ef7f669a560fd')
    approval=obj(P/'ROOT_PRODUCER_APPROVAL_V3.json',r['approval_sha256'])
    assert approval['phase']==r['phase']=='certificates_produce' and approval['registry_sha256']==r['registry_sha256']
    pins(P/'certificates_produce',r)
    table=obj(P/'CONTEXTS.json',reg['sources']['CONTEXTS.json']);contexts=[x['context'] for x in table]
    assert approval['contexts']==contexts and set(r['summary']['contexts'])==set(contexts)
    states=obj(P/'certificates_produce/CONTEXT_STATUS.json')
    assert states=={c:('INHERITED_AUTHENTICATED' if c=='final' else 'COMPLETE') for c in contexts}
    old=obj(ROOT/'model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json',reg['external_sources']['model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json'])
    old={x['context']:x for x in old['records']}
    rows=[];members=0;times=[];peaks=[];lastfinish=None
    for row in table:
        ctx=row['context'];e=r['summary']['contexts'][ctx]
        if ctx=='final':
            folder=P.parent/'actual_producer_attempt_1';cr=obj(folder/'COMPLETE.json',e['producer_complete_sha256'])
        else:
            folder=P/'certificates_produce'/ctx;cr=obj(folder/'COMPLETE.json',e['complete_sha256'])
            assert cr['summary']=={k:v for k,v in e.items() if k!='complete_sha256'}
            assert cr['registry_sha256']==r['registry_sha256'] and cr['approval_sha256']==r['approval_sha256']
            assert cr['context']==ctx and cr['status']=='COMPLETE'
            if lastfinish:assert cr['start_utc']>=lastfinish
            lastfinish=cr['finish_utc'];times.append(cr['seconds']);peaks.append(e['estimated_owned_peak_bytes'])
            events=obj(folder/'ACCESS.json',cr['outputs']['ACCESS.json'])
            material=[x for x in events if x.get('kind')=='npz_materialize']
            assert len(material)==7 and all(x['archive_sha256']==row['sha256'] for x in material)
            assert {x['member'] for x in material}=={'initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets'}
            members+=len(material)
            for event in events:
                if 'path' in event:assert not any(s in event['path'] for s in ['/calibration/','/scoring/','/native/'])
            proc=obj(P/'certificates_produce'/f'process_{ctx}.json')
            assert proc['returncode']==0 and proc['interruption'] is None
            assert len([n for n in cr['outputs'] if n.startswith('checkpoint_')])==20
        pins(folder,cr)
        cert=obj(folder/'certificate.json',e['certificate_sha256'])
        assert cert['model_sha256']==row['sha256'] and cert['summary']==e['summary']
        assert cert['counts']['stages']==400 and cert['counts']['blocks_per_domain']==200
        assert len(cert['paths'])==cert['counts']['paths']
        leaves=collections.defaultdict(set)
        for path in cert['paths']:
            assert path['leaf'] not in leaves[path['stage']];leaves[path['stage']].add(path['leaf'])
        assert set(leaves)==set(range(400))
        for k in ['lower','upper']:assert frac(cert['stage0'][k])==oldfrac(old[ctx]['range'][k])
        assert frac(cert['stage0']['B'])==oldfrac(old[ctx]['B_structural'])
        for domain in ['D','R']:
            d=cert['domains'][domain];assert d['id']==('FINITE_X62_V1' if domain=='D' else 'FINITE_X62_ABS_MINMAX_NUMERIC_V1')
            assert len(d['blocks'])==200
            attempted=feasible=0;previous=None
            for j,block in enumerate(d['blocks']):
                assert block['block']==j and block['stages']==[2*j,2*j+1]
                pairs=block['pairs'];expected=set(itertools.product(leaves[2*j],leaves[2*j+1]))
                assert len(pairs)==len(expected) and {tuple(x['leaves']) for x in pairs}==expected
                assert all(x['status'] in ['feasible','path_empty','intersection_empty','R_infeasible'] for x in pairs)
                if domain=='D':assert all(x['status']!='R_infeasible' for x in pairs)
                if previous is not None:assert block['incoming']==previous
                previous=block['outgoing'];attempted+=len(pairs);feasible+=sum(x['status']=='feasible' for x in pairs)
            s=cert['summary'][domain];assert attempted==s['attempted_pairs'] and feasible==s['feasible_pairs']
            assert [frac(x) for x in previous]==[frac(s['lower']),frac(s['upper'])]
        s=cert['summary'];assert frac(s['D']['lower'])<=frac(s['R']['lower'])<=frac(s['R']['upper'])<=frac(s['D']['upper'])
        assert frac(cert['stage0']['lower'])<=frac(s['D']['lower']) and frac(s['D']['upper'])<=frac(cert['stage0']['upper'])
        b0=frac(cert['stage0']['B']);bd=frac(s['D']['B']);br=frac(s['R']['B']);assert 0<=br<=bd<b0
        rows.append({'context':ctx,'paths':len(cert['paths']),'records':cert['counts']['attempted_pairs'],'B0':str(b0),'BD':str(bd),'BR':str(br),'R_additional_B':br<bd})
    logical=sum(x.stat().st_size for x in (P/'certificates_produce').rglob('*') if x.is_file())
    assert members==105 and logical==548863520 and logical<9*2**28
    result={'status':'PASS_RECEIPT_AND_CERTIFICATE_INVENTORY_NOT_PROOF_REPLAY','contexts':16,'fresh_contexts':15,'inherited_contexts':1,'model_members_reported':members,'seconds':r['seconds'],'child_seconds_range':[min(times),max(times)],'max_estimated_owned_bytes':max(peaks),'logical_bytes':logical,'D_strictly_tighter_B':16,'R_additional_B':sum(x['R_additional_B'] for x in rows),'rows':rows,'reviewer_model_materializations':0,'reviewer_proof_replays':0}
    with OUT.open('x') as f:json.dump(result,f,indent=2)
    print({k:v for k,v in result.items() if k!='rows'})
if __name__=='__main__':main()
