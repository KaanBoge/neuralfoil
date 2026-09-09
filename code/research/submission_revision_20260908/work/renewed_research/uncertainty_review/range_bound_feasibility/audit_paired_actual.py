"""Audit the one approved proof execution; never loads the model or reruns it."""
import collections,hashlib,json
from fractions import Fraction as F
from pathlib import Path
from decimal import Decimal,localcontext

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'model_proposal/paired_tree_plan'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_bytes())
def rat(q):
    assert set(q)=={'encoding','numerator','denominator'} and q['encoding']=='signed_hex_fraction_v1'
    n,d=int(q['numerator'],16),int(q['denominator'],16);z=F(n,d)
    assert hex(n)==q['numerator'] and hex(d)==q['denominator'] and d>0 and (z.numerator,z.denominator)==(n,d)
    return z
def decimal(q):
    with localcontext() as ctx:ctx.prec=50;return str(Decimal(q.numerator)/Decimal(q.denominator))
def main():
    output=Path(__file__).with_name('PAIRED_ACTUAL_QA.json')
    if output.exists():raise FileExistsError(output)
    reg=load(P/'REGISTRY_v3.json');rp=sha(P/'REGISTRY_v3.json')
    assert rp=='7c53d7c0385d9df5222e901ec9a7b971b72c96ea72301a3d5e398089600061a2'
    for group in ('sources','preserved_failed_gate','wrapper_synthetic_evidence'):
        for name,pin in reg[group].items():assert sha(P/name)==pin
    for name,pin in reg['dependencies'].items():assert sha(ROOT/name)==pin
    folders={'producer':P/'actual_producer_attempt_1','replay':P/'actual_replay_attempt_1'}
    receipts={};ledgers={}
    for phase,p in folders.items():
        r=load(p/'COMPLETE.json');a=load(P/f'ROOT_ACTUAL_{phase.upper()}_APPROVAL.json')
        assert r['registry_sha256']==a['registry_sha256']==rp
        assert r['approval_sha256']==sha(P/f'ROOT_ACTUAL_{phase.upper()}_APPROVAL.json')
        assert r['phase']==a['phase']=='paired_tree_'+phase
        assert r['model_sha256']==a['model_sha256']==reg['input']['sha256']
        assert r['status']=='COMPLETE'
        for name,pin in r['outputs'].items():assert sha(p/name)==pin
        ledger=load(p/'ACCESS.json');members=[]
        for e in ledger:
            if 'path' in e:assert sha(Path(e['path']))==e['sha256']
            if e['kind']=='npz_materialize':
                assert e['archive_sha256']==reg['input']['sha256'];members.append(e['member'])
        assert members==reg['input']['members'] and len(members)==7
        assert not (p/'FAILURE.json').exists()
        receipts[phase]=r;ledgers[phase]=dict(collections.Counter(e['kind'] for e in ledger))
    prod=folders['producer'];replay=folders['replay']
    assert sha(prod/'COMPLETE.json')=='dce7280d67453cf120001a412d05ba6cbde4c33c05c4a0b65284ae359ddc433c'
    assert sha(prod/'certificate.json')==sha(prod/'certificate.json.partial')=='72c4caa8013f61b2943bafb7096d0b69d0ae9f10169e5a055e921ad39e584106'
    approval=load(P/'ROOT_ACTUAL_REPLAY_APPROVAL.json')
    assert approval['producer_complete_sha256']==sha(prod/'COMPLETE.json')
    assert approval['certificate_sha256']==sha(prod/'certificate.json')
    cert=load(prod/'certificate.json');result=load(replay/'REPLAY.json')
    assert result['status']=='PASS_INDEPENDENT_ADJACENT_PAIR_REPLAY'
    assert result['model_sha256']==cert['model_sha256']==reg['input']['sha256']
    assert result['counts']==cert['counts'] and result['summary']==cert['summary'] and result['stage0']==cert['stage0']
    assert result['all_cartesian_equals_independent'] is True
    paths=collections.defaultdict(list)
    for row in cert['paths']:paths[row['stage']].append(row['leaf'])
    assert set(paths)==set(range(400)) and len(cert['paths'])==6000
    assert sum(len(p['edges']) for p in cert['paths'])==32393
    counts={};attempts=0
    for domain in ('D','R'):
        blocks=cert['domains'][domain]['blocks'];assert len(blocks)==200
        cc=collections.Counter()
        for j,b in enumerate(blocks):
            assert b['block']==j and b['stages']==[2*j,2*j+1]
            assert [r['leaves'] for r in b['pairs']]==[[a,z] for a in paths[2*j] for z in paths[2*j+1]]
            cc.update(r['status'] for r in b['pairs'])
            if j:assert b['incoming']==blocks[j-1]['outgoing']
            if (j+1)%20==0:
                q=load(prod/f'checkpoint_{domain}_{j+1:03d}.json')
                assert q['completed_blocks']==j+1 and [q['lower'],q['upper']]==b['outgoing']
        assert sum(cc.values())==45000 and cert['summary'][domain]['feasible_pairs']==cc['feasible']
        counts[domain]=dict(cc);attempts+=sum(cc.values())
    assert attempts==90000 and counts['D']=={'feasible':37141,'intersection_empty':7859}
    assert counts['R']=={'feasible':37038,'intersection_empty':7859,'R_infeasible':103}
    allbounds={'Stage0':cert['stage0'],**cert['summary']}
    b={name:{k:rat(value[k]) for k in ('lower','upper','B')} for name,value in allbounds.items()}
    for x in b.values():
        clip=lambda v:max(F(-1,2),min(F(1),v));u=F(1,2**53);e=4*u+2*u*u
        assert x['B']==max(abs(clip(clip(x['lower'])-e)),abs(clip(clip(x['upper'])+e)))/2+3*u/2
    assert b['Stage0']['lower']<b['D']['lower']<b['R']['lower']
    assert b['Stage0']['upper']>b['D']['upper']==b['R']['upper']
    assert b['Stage0']['B']>b['D']['B']==b['R']['B']
    assert sha(P/'wrapper_synthetic_attempt_1/FAILURE.json')=='27f03e28a9932ad21aaad574438f363d44a0b9bc8557e1503c404c1d9af54f54'
    report={'status':'PASS_AUTHENTICATED_SINGLE_PROOF_RECEIPT_AUDIT','counts':cert['counts'],'classifications':counts,
      'bounds_decimal':{n:{k:decimal(v) for k,v in q.items()} for n,q in b.items()},
      'D_vs_Stage0_B_reduction_exact':str(b['Stage0']['B']-b['D']['B']),
      'R_vs_D_B_reduction_exact':str(b['D']['B']-b['R']['B']),
      'receipts':{name:{'sha256':sha(folders[name]/'COMPLETE.json'),'seconds':r['elapsed_seconds'],'summary':r['summary']} for name,r in receipts.items()},
      'ledgers':ledgers,'model_materializations_in_this_audit':0,'proof_rerun':False,'certificate_sha256':sha(prod/'certificate.json')}
    with output.open('x') as f:json.dump(report,f,indent=2)
    print(report['status'],counts,report['bounds_decimal'])
if __name__=='__main__':main()
