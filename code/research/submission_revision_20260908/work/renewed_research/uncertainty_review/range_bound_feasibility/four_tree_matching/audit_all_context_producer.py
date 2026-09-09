"""Saved producer inventory/provenance audit. Requires root completion pin.

No scientific module import, NPZ open, fit, or independent checker execution.
Do not execute until root explicitly supplies the completed aggregate SHA.
"""
import argparse,csv,hashlib,io,json
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
P=ROOT/'model_proposal/four_tree_matching_plan/all_context_proposal/implementation';A=P/'certificates_produce'
REG='7bb56df82346651e91e2832e63879759e39ba5fdbb8a68b2ec2ea3ef265430b4';APP='9a14f4bf022613717288f9ed20b7c8ad308ab3de5071470c8867e9694bd8f1f1'
CONTEXTS=[f'group_{s}_fold_{i}' for s in (20260906,20260908) for i in range(5)]+['strict_source_'+s for s in ('stec8','vol1','vol2','vol3','all_uiuc_volumes')]+['final']
ledger=[]
def auth(path,pin,parse=False):
    if path.suffix=='.npz' or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('no model access or symlinks')
    h=hashlib.sha256();n=0
    with path.open('rb') as f:
        while b:=f.read(65536):h.update(b);n+=len(b)
    assert h.hexdigest()==pin,(str(path),h.hexdigest(),pin)
    ledger.append({'path':str(path.relative_to(ROOT)),'sha256':pin,'bytes':n})
    return json.loads(path.read_bytes()) if parse else None
def dec(v):
    f=F(int(v['numerator'],16),int(v['denominator'],16));assert v=={'encoding':'signed_hex_fraction_v1','numerator':hex(f.numerator),'denominator':hex(f.denominator)};return f
def outputs(path,r):
    assert not (path/'FAILURE.json').exists()
    for n,h in r['outputs'].items():assert Path(n).name==n;auth(path/n,h)
def inventory(c):
    paths=c['paths'];assert len(paths)==400 and [x['stage'] for x in paths]==list(range(400));assert len(c['blocks'])==100
    for p in paths:assert [v['leaf'] for v in p['leaves']]==sorted({v['leaf'] for v in p['leaves']})
    counts=Counter();pairs=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3));matchings=((0,5),(1,4),(2,3))
    for i,b in enumerate(c['blocks']):
        assert b['block']==i and b['stages']==list(range(i*4,i*4+4)) and len(b['pairs'])==6 and len(b['matchings'])==3;intervals=[]
        for row,(x,y) in zip(b['pairs'],pairs):
            assert row['stages']==[4*i+x,4*i+y];left,right=paths[4*i+x]['leaves'],paths[4*i+y]['leaves'];assert row['shape']==[len(left),len(right)]
            statuses=bytes.fromhex(row['status_hex']);assert len(statuses)==len(left)*len(right) and set(statuses)<={0,1,2};counts.update(statuses);sums=[]
            for k,status in enumerate(statuses):
                l,r=left[k//len(right)],right[k%len(right)];assert (status==0)==bool(l['empty'] or r['empty'])
                if status==2:sums.append(F(float.fromhex(l['value']))+F(float.fromhex(r['value'])))
            assert sums and row['feasible']==len(sums);v=[min(sums),max(sums)];assert list(map(dec,row['real_sum']))==v;intervals.append(v)
        ms=[]
        for row,(x,y) in zip(b['matchings'],matchings):
            v=[intervals[x][0]+intervals[y][0],intervals[x][1]+intervals[y][1]];assert row['pair_indices']==[x,y] and list(map(dec,row['real_sum']))==v;ms.append(v)
        assert list(map(dec,b['real_sum']))==[max(x[0] for x in ms),min(x[1] for x in ms)]
        adjacent=list(map(dec,b['adjacent_transfer'][-1]));rounding=list(map(dec,b['rounding_branch']));out=list(map(dec,b['outgoing']));assert out==[max(adjacent[0],rounding[0]),min(adjacent[1],rounding[1])] and out[0]<=out[1]
        if i:assert b['incoming']==c['blocks'][i-1]['outgoing'] and b['original_incoming']==c['blocks'][i-1]['original_outgoing']
    expected={'stages':400,'blocks':100,'paths':sum(len(p['leaves']) for p in paths),'path_edges':sum(len(v['edges']) for p in paths for v in p['leaves']),'pair_classifications':sum(counts.values()),'feasible_pairs':counts[2]};assert c['counts']==expected
    assert c['final']['lower']==c['blocks'][-1]['outgoing'][0] and c['final']['upper']==c['blocks'][-1]['outgoing'][1]
    for a,b in [('stage0','original_adjacent'),('original_adjacent','final')]:assert dec(c[a]['lower'])<=dec(c[b]['lower'])<=dec(c[b]['upper'])<=dec(c[a]['upper']) and dec(c[b]['B'])<=dec(c[a]['B'])
    return dict(counts)
def main(pin):
    dest=HERE/'all_context_producer_audit';dest.mkdir(exist_ok=False)
    try:
        r=auth(A/'COMPLETE.json',pin,True);assert r['status']=='COMPLETE' and r['phase']=='certificates_produce' and r['registry_sha256']==REG and r['approval_sha256']==APP
        reg=auth(P/'REGISTRY_v3.json',REG,True);ap=auth(P/'ROOT_CERTIFICATES_PRODUCE_APPROVAL.json',APP,True)
        assert ap['actual_execution_authorized'] is True and ap['registry_sha256']==REG and ap['contexts']==CONTEXTS and ap['seconds']==ap['child_seconds']==900 and ap['workers']==1
        assert ap['producer_owned_cap']==128*2**20 and ap['checker_owned_cap']==256*2**20 and ap['child_output_cap']==64*2**20 and ap['combined_output_cap']==9*2**28
        for n,h in reg['sources'].items():auth(P/n,h)
        for e in [*reg['external_sources'].values(),*reg['metadata'].values()]:auth(ROOT/e['path'],e['sha256'])
        assert [v['context'] for v in reg['contexts']]==CONTEXTS and set(r['contexts'])==set(CONTEXTS)
        outputs(A,r);status=auth(A/'CONTEXT_STATUS.json',r['outputs']['CONTEXT_STATUS.json'],True);assert status=={c:('COMPLETE' if c!='final' else 'INHERITED_AUTHENTICATED') for c in CONTEXTS}
        stage=auth(ROOT/reg['metadata']['stage0']['path'],reg['metadata']['stage0']['sha256'],True);token=auth(A/'TOKEN.json',r['outputs']['TOKEN.json'],True);result=[];total=Counter()
        for row in reg['contexts'][:-1]:
            name=row['context'];e=r['contexts'][name];path=A/name;cr=auth(path/'COMPLETE.json',e['complete_sha256'],True);auth(path/'COMPLETE.json.partial',e['complete_sha256']);outputs(path,cr)
            assert cr['context']==name and cr['model_sha256']==row['model_sha256'] and cr['registry_sha256']==REG and cr['approval_sha256']==APP and cr['status']=='COMPLETE' and cr['phase']=='certificates_produce' and cr['summary']==e['summary'] and cr['parent_pid']==token['parent_pid']
            c=auth(path/'certificate.json',cr['outputs']['certificate.json'],True);assert c['model_sha256']==row['model_sha256'] and c['domain']=='FINITE_X62_V1';count=inventory(c);total.update(count)
            for k in ('counts','stage0','original_adjacent','final'):assert c[k]==cr['summary'][k]
            old=next(v for v in stage['records'] if v['context']==name);assert stage['accessed_tree_sha256'][row['member']]==row['model_sha256']
            for k in ('lower','upper'):assert dec(c['stage0'][k])==F(int(old['range'][k]['numerator']),int(old['range'][k]['denominator']))
            assert dec(c['stage0']['B'])==F(int(old['B_structural']['numerator']),int(old['B_structural']['denominator']))
            for k in ('lower','upper','B'):assert dec(c['original_adjacent'][k])==dec(row['old_D'][k])
            a=c['accounting'];base=16*2**20+4*a['source_bytes']+2*a['input_bytes']+1024*6000+512*84000+262144*100+4*135000+4*2**20
            assert a['estimated_owned_bytes']==base+6*a['array_bytes'] and cr['summary']['owned_peak']==max(base+6*4*2**20,a['estimated_owned_bytes'])<128*2**20 and cr['elapsed_seconds']<900
            ev=auth(path/'ACCESS.json',cr['outputs']['ACCESS.json'],True);members=[v for v in ev if v['operation']=='NPZ materialization'];assert len(members)==7 and len({v['member'] for v in members})==7 and all(v['model_sha256']==row['model_sha256'] for v in members)
            npz={v['path'] for v in ev if 'path' in v and v['path'].endswith('.npz')};assert npz=={str(ROOT/'independent_environment/bounds_extraction'/row['member'])}
            logical=sum(v.stat().st_size for v in path.iterdir());assert logical<64*2**20
            result.append({'context':name,'status':'NEW_SAVED_INVENTORY_PASS','counts':c['counts'],'statuses':count,'bounds':{k:{n:float(dec(v)) for n,v in c[k].items()} for k in ('stage0','original_adjacent','final')},'owned_peak':cr['summary']['owned_peak'],'seconds':cr['elapsed_seconds'],'logical_bytes':logical})
        final=r['contexts']['final'];assert final['status']=='INHERITED_AUTHENTICATED' and final['context']=='final';fr=reg['final']['replay'];rr=auth(ROOT/fr['path'],fr['sha256'],True);outputs((ROOT/fr['path']).parent,rr)
        assert final['replay_complete_sha256']==fr['sha256'] and final['summary']=={k:rr['summary'][k] for k in ('counts','stage0','original_adjacent','final')};assert not (A/'final').exists()
        assert r['fresh_contexts']==15 and r['inherited_contexts']==1 and r['fits']==r['features_targets_loaded']==0 and r['R_used'] is False and r['elapsed_seconds']<900
        logical=sum(x.stat().st_size for x in A.rglob('*') if x.is_file());assert logical<9*2**28
        q={'status':'PASS_SAVED_PRODUCER_INVENTORY_ONLY','complete_sha256':pin,'contexts':result,'inherited_final':final,'new_status_counts':dict(total),'aggregate_seconds':r['elapsed_seconds'],'logical_bytes':logical,'ledger':ledger,'auditor_model_access':0,'proof_replays':0,'limitation':'Saved-path/status arithmetic is internally reconciled; original-model path correctness awaits separately approved independent replay.'}
        with (dest/'QA.json').open('x') as f:json.dump(q,f,indent=2,sort_keys=True)
        print(json.dumps({'status':q['status'],'qa_sha256':hashlib.sha256((dest/'QA.json').read_bytes()).hexdigest(),'new_contexts':len(result),'logical_bytes':logical}))
    except BaseException as e:
        with (dest/'FAILURE.json').open('x') as f:json.dump({'error':repr(e),'input_ledger':ledger},f,indent=2)
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--complete-sha256',required=True);main(p.parse_args().complete_sha256)
