"""Receipt and saved inventory arithmetic only; never opens model NPZ."""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import hashlib,json
from audit_cold_receipts import auth,ledger,ROOT,HERE,P,PS,CS
A=P/'attempt_1'
def dec(v):
    q=F(int(v['numerator'],16),int(v['denominator'],16));assert v=={'encoding':'signed_hex_fraction_v1','numerator':hex(q.numerator),'denominator':hex(q.denominator)};return q
def main():
    out=HERE/'ACTUAL_PRODUCER_RECEIPT_QA.json'
    if out.exists():raise FileExistsError('preserve audit')
    completepin=hashlib.sha256((A/'COMPLETE.json').read_bytes()).hexdigest();r=auth(A/'COMPLETE.json',completepin,True)
    assert r['status']=='COMPLETE' and r['phase']=='four_tree_matching_produce' and not (A/'FAILURE.json').exists()
    p=auth(P/'REGISTRY_SOURCE_V1.json',PS,True);cr=auth(HERE/'CHECKER_SOURCE_REGISTRY_V1.json',CS,True)
    assert cr['producer_registry_sha256']==PS and cr['sources']==p['checker_sources']
    for n,h in p['sources'].items():auth(P/n,h)
    refs={}
    for k,e in p['predecessors'].items():refs[k]=auth(ROOT/e['path'],e['sha256'],True)
    for e in p['checker_sources'].values():auth(ROOT/e['path'],e['sha256'])
    app=auth(P/'ROOT_PRODUCER_APPROVAL.json',r['approval_sha256'],True)
    assert app['registry_sha256']==r['registry_sha256']==PS and app['checker_registry_sha256']==CS and app['model_sha256']==r['model_sha256']==p['model_sha256']
    assert app['real_execution_authorized'] is True and app['phase']==r['phase'] and app['domain']==r['domain']=='FINITE_X62_V1'
    for k,v in {'workers':1,'seconds':900,'owned_cap':128*2**20,'output_cap':64*2**20}.items():assert app[k]==r['limits'][k]==v and type(app[k]) is int
    review=auth(P/'ROOT_SOURCE_REVIEW.json',app['source_review_sha256'],True);gate=auth(P/'COLD_GATE_PASS.json',app['synthetic_gate_sha256'],True)
    assert review['status']=='PASS_SOURCE_REVIEW' and gate['status']=='PASS_FIXED_135000_GATE'
    for x in [review,gate]:assert x['registry_sha256']==PS and x['checker_registry_sha256']==CS
    assert app['synthetic_gate_sha256']=='b5fc0fa6463f2704519df2a4be658cf21d4afbbcb7a52bf5d4e6c5035b86f6a0'
    for n,h in r['outputs'].items():auth(A/n,h)
    auth(A/'COMPLETE.json.partial',completepin)
    assert {x.name for x in A.iterdir()}==set(r['outputs'])|{'COMPLETE.json','COMPLETE.json.partial'}
    c=auth(A/'certificate.json',r['outputs']['certificate.json'],True)
    assert c['model_sha256']==r['model_sha256'] and c['domain']=='FINITE_X62_V1'
    assert c['counts']==r['summary']['counts'] and len(c['paths'])==400 and len(c['blocks'])==100
    paths=c['paths'];assert [x['stage'] for x in paths]==list(range(400))
    assert sum(len(x['leaves']) for x in paths)==6000 and sum(len(y['edges']) for x in paths for y in x['leaves'])==32393
    for x in paths:assert [y['leaf'] for y in x['leaves']]==sorted({y['leaf'] for y in x['leaves']})
    counts=Counter();pairs=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3));matchings=((0,5),(1,4),(2,3))
    for bi,b in enumerate(c['blocks']):
        assert b['block']==bi and b['stages']==list(range(4*bi,4*bi+4)) and len(b['pairs'])==6
        sums=[]
        for row,(i,j) in zip(b['pairs'],pairs):
            assert row['stages']==[4*bi+i,4*bi+j]
            left,right=paths[4*bi+i]['leaves'],paths[4*bi+j]['leaves'];assert row['shape']==[len(left),len(right)]
            code=bytes.fromhex(row['status_hex']);assert len(code)==len(left)*len(right) and set(code)<={0,1,2};counts.update(code);values=[]
            for k,status in enumerate(code):
                l,rr=left[k//len(right)],right[k%len(right)]
                assert (status==0)==(l['empty'] or rr['empty'])
                if status==2:values.append(F(float.fromhex(l['value']))+F(float.fromhex(rr['value'])))
            assert len(values)==row['feasible'] and values
            interval=[min(values),max(values)];assert interval==list(map(dec,row['real_sum']));sums.append(interval)
        m=[]
        for row,(i,j) in zip(b['matchings'],matchings):
            assert row['pair_indices']==[i,j];v=[sums[i][0]+sums[j][0],sums[i][1]+sums[j][1]];assert v==list(map(dec,row['real_sum']));m.append(v)
        assert list(map(dec,b['real_sum']))==[max(x[0] for x in m),min(x[1] for x in m)]
    assert sum(counts.values())==135000 and counts[2]==112430
    converted={}
    for k in ['stage0','original_adjacent','final']:
        assert c[k]==r['summary'][k];converted[k]={n:float(dec(v)) for n,v in c[k].items()}
    for a,b in [('stage0','original_adjacent'),('original_adjacent','final')]:
        assert dec(c[a]['lower'])<=dec(c[b]['lower'])<=dec(c[b]['upper'])<=dec(c[a]['upper']) and dec(c[b]['B'])<=dec(c[a]['B'])
    for k in ['lower','upper','B']:assert dec(c['original_adjacent'][k])==dec(refs['adjacent_replay']['summary']['D'][k])
    s0=next(x for x in refs['stage0']['records'] if x['context']=='final')
    for k in ['lower','upper']:assert dec(c['stage0'][k])==F(int(s0['range'][k]['numerator']),int(s0['range'][k]['denominator']))
    v=s0['B_structural'];assert dec(c['stage0']['B'])==F(int(v['numerator']),int(v['denominator']))
    a=c['accounting'];formula=16*2**20+4*a['source_bytes']+2*a['input_bytes']+6*a['array_bytes']+1024*6000+512*84000+262144*100+4*135000+4*2**20
    assert formula==a['estimated_owned_bytes']
    pre=16*2**20+4*a['source_bytes']+2*a['input_bytes']+6*4*2**20+1024*6000+512*84000+262144*100+4*135000+4*2**20
    assert r['summary']['owned_estimate_peak']==max(pre,formula)<128*2**20 and r['elapsed_seconds']<900
    events=auth(A/'ACCESS.json',r['outputs']['ACCESS.json'],True);members=[e for e in events if e['operation']=='NPZ materialization'];assert len(members)==7 and len({e['member'] for e in members})==7
    scientific_paths={e['path'] for e in events if 'path' in e and e['path'].endswith('.npz')};assert scientific_paths=={str(ROOT/'independent_environment/bounds_extraction/arrays/tree_31_capped.npz')}
    assert all(e['model_sha256']==r['model_sha256'] for e in members)
    logical=sum(x.stat().st_size for x in A.iterdir());assert logical<64*2**20
    reduction=float((dec(c['original_adjacent']['B'])-dec(c['final']['B']))/dec(c['original_adjacent']['B'])*100)
    result={'status':'PASS_RECEIPT_AND_SAVED_INVENTORY_ONLY','complete_sha256':completepin,'certificate_sha256':r['outputs']['certificate.json'],'converted_bounds':converted,'B_relative_reduction_vs_adjacent_percent':reduction,'classification_counts':dict(counts),'receipt_counts':c['counts'],'owned_accounting':a,'owned_admission_peak':pre,'elapsed_seconds':r['elapsed_seconds'],'logical_bytes':logical,'producer_reported_model_members':len(members),'auditor_model_materializations':0,'proof_replays':0,'ledger':ledger,'limitation':'Pair statuses were counted and their saved-leaf sums reconciled, not verified against original model paths. Independent model-bound checker approval remains necessary.'}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k not in ['ledger','owned_accounting']},indent=2))
    print('QA_SHA256='+hashlib.sha256(out.read_bytes()).hexdigest())
if __name__=='__main__':main()
