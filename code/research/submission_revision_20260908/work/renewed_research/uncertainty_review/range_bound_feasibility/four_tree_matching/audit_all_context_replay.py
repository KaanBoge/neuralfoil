"""Saved replay chain only. Execute only after root supplies COMPLETE SHA."""
import argparse,hashlib,json
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];P=ROOT/'model_proposal/four_tree_matching_plan/all_context_proposal/implementation';A=P/'certificates_replay'
REG='7bb56df82346651e91e2832e63879759e39ba5fdbb8a68b2ec2ea3ef265430b4';APP='6917a39c8773c89cb85bea62f79ce2ba7e92ac5b6bed15002d525aa8052f4393';PRODUCER='299f350c07e689a73cc5d8726f19d3598c340976cd005121610c39078761720a'
ledger=[]
def auth(p,h,parse=False):
    if p.suffix=='.npz' or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('no model access/symlinks')
    digest=hashlib.sha256();size=0
    with p.open('rb') as f:
        while b:=f.read(65536):digest.update(b);size+=len(b)
    assert digest.hexdigest()==h,(str(p),digest.hexdigest(),h)
    ledger.append({'path':str(p.relative_to(ROOT)),'sha256':h,'bytes':size})
    return json.loads(p.read_bytes()) if parse else None
def outputs(path,r):
    assert not (path/'FAILURE.json').exists()
    for n,h in r['outputs'].items():assert Path(n).name==n;auth(path/n,h)
def main(pin):
    dest=HERE/'all_context_replay_audit';dest.mkdir(exist_ok=False)
    try:
        r=auth(A/'COMPLETE.json',pin,True);auth(A/'COMPLETE.json.partial',pin)
        assert r['status']=='COMPLETE' and r['phase']=='certificates_replay' and r['registry_sha256']==REG and r['approval_sha256']==APP and r['producer_complete_sha256']==PRODUCER
        reg=auth(P/'REGISTRY_v3.json',REG,True);ap=auth(P/'ROOT_CERTIFICATES_REPLAY_APPROVAL.json',APP,True)
        assert ap['registry_sha256']==REG and ap['producer_complete_sha256']==PRODUCER and ap['actual_execution_authorized'] is True and ap['phase']=='certificates_replay'
        for k,v in {'workers':1,'seconds':900,'child_seconds':900,'producer_owned_cap':128*2**20,'checker_owned_cap':256*2**20,'child_output_cap':64*2**20,'combined_output_cap':9*2**28}.items():assert type(ap[k]) is int and ap[k]==v
        for n,h in reg['sources'].items():auth(P/n,h)
        for e in [*reg['external_sources'].values(),*reg['metadata'].values()]:auth(ROOT/e['path'],e['sha256'])
        pc=auth(P/'certificates_produce/COMPLETE.json',PRODUCER,True);outputs(P/'certificates_produce',pc)
        pa=auth(P/'ROOT_CERTIFICATES_PRODUCE_APPROVAL.json',pc['approval_sha256'],True);assert pa['registry_sha256']==REG and pa['actual_execution_authorized'] is True
        pqa=auth(HERE/'all_context_producer_audit/QA.json','8b20ec23f8668f93cce90bd3888a1c4229eece79d96361ba238e30ee36ff6c8e',True);assert pqa['complete_sha256']==PRODUCER
        contexts=[v['context'] for v in reg['contexts']];assert len(contexts)==16 and len(set(contexts))==16 and set(r['contexts'])==set(pc['contexts'])==set(contexts)==set(ap['contexts'])
        outputs(A,r);statuses=auth(A/'CONTEXT_STATUS.json',r['outputs']['CONTEXT_STATUS.json'],True);assert statuses=={c:('COMPLETE' if c!='final' else 'INHERITED_AUTHENTICATED') for c in contexts}
        token=auth(A/'TOKEN.json',r['outputs']['TOKEN.json'],True);assert token['phase']=='certificates_replay' and token['approval_sha256']==APP and token['registry_sha256']==REG
        summaries=[];totals=Counter();members=0
        for row in reg['contexts'][:-1]:
            c=row['context'];e=r['contexts'][c];cr=auth(A/c/'COMPLETE.json',e['complete_sha256'],True);auth(A/c/'COMPLETE.json.partial',e['complete_sha256']);outputs(A/c,cr)
            pe=pc['contexts'][c];old=auth(P/'certificates_produce'/c/'COMPLETE.json',pe['complete_sha256'],True);outputs(P/'certificates_produce'/c,old)
            assert cr['status']=='COMPLETE' and cr['phase']=='certificates_replay' and cr['context']==c and cr['registry_sha256']==REG and cr['approval_sha256']==APP and cr['model_sha256']==row['model_sha256'] and cr['parent_pid']==token['parent_pid'] and cr['summary']==e['summary']
            assert cr['summary']['producer_complete_sha256']==pe['complete_sha256'] and cr['summary']['certificate_sha256']==old['outputs']['certificate.json']
            v=auth(A/c/'REPLAY.json',cr['outputs']['REPLAY.json'],True)
            for k in ('counts','stage0','original_adjacent','final'):assert v[k]==cr['summary'][k]==old['summary'][k]
            assert v['model_sha256']==row['model_sha256']
            count=v['counts'];assert count['stages']==400 and count['blocks']==100 and count['pair_classifications']<=135000;totals.update(count)
            assert v['checker_accounting']['estimated_owned_bytes']<=cr['summary']['owned_peak']<256*2**20 and cr['elapsed_seconds']<900
            ev=auth(A/c/'ACCESS.json',cr['outputs']['ACCESS.json'],True);m=[x for x in ev if x['operation']=='independent NPZ materialization'];assert len(m)==7 and len({x['member'] for x in m})==7 and all(x['model_sha256']==row['model_sha256'] for x in m);members+=len(m)
            npz={x['path'] for x in ev if 'path' in x and x['path'].endswith('.npz')};assert npz=={str(ROOT/'independent_environment/bounds_extraction'/row['member'])}
            logical=sum(x.stat().st_size for x in (A/c).iterdir());assert logical<64*2**20
            summaries.append({'context':c,'counts':count,'owned_peak':cr['summary']['owned_peak'],'seconds':cr['elapsed_seconds'],'logical_bytes':logical,'exact_original_and_producer_equality':True})
        assert r['contexts']['final']==pc['contexts']['final'] and not (A/'final').exists()
        final=r['contexts']['final'];fr=reg['final']['replay'];f=auth(ROOT/fr['path'],fr['sha256'],True);outputs((ROOT/fr['path']).parent,f);assert final['replay_complete_sha256']==fr['sha256'] and final['summary']=={k:f['summary'][k] for k in ('counts','stage0','original_adjacent','final')}
        assert r['fresh_contexts']==15 and r['inherited_contexts']==1 and r['fits']==r['features_targets_loaded']==0 and r['R_used'] is False and r['elapsed_seconds']<900
        logical=sum(x.stat().st_size for phase in ('certificates_produce','certificates_replay') for x in (P/phase).rglob('*') if x.is_file());assert logical<9*2**28
        q={'status':'PASS_SAVED_ALL_CONTEXT_INDEPENDENT_REPLAY','complete_sha256':pin,'producer_complete_sha256':PRODUCER,'contexts':summaries,'new_counts':dict(totals),'inherited_final':final,'aggregate_seconds':r['elapsed_seconds'],'combined_logical_bytes':logical,'reported_unique_member_events':members,'ledger':ledger,'auditor_model_access':0,'auditor_proof_replays':0}
        with (dest/'QA.json').open('x') as h:json.dump(q,h,sort_keys=True,indent=2)
        print(json.dumps({'status':q['status'],'qa_sha256':hashlib.sha256((dest/'QA.json').read_bytes()).hexdigest(),'contexts':len(summaries),'new_counts':dict(totals),'combined_logical_bytes':logical,'hash_checks':len(ledger)}))
    except BaseException as e:
        with (dest/'FAILURE.json').open('x') as h:json.dump({'error':repr(e),'ledger':ledger},h,indent=2)
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--complete-sha256',required=True);main(p.parse_args().complete_sha256)
