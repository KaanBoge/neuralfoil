"""Metadata/source-only freeze. Refuses NPZ reads and preserves prior registry."""
from pathlib import Path
import json,hashlib
import context_support as s
HERE=s.HERE;ROOT=s.ROOT;SOLE=ROOT/'model_proposal/four_tree_matching_plan';OLD=ROOT/'model_proposal/paired_tree_plan/all_context_plan';CHECK=ROOT/'uncertainty_review/range_bound_feasibility/four_tree_matching'
SOURCES=['context_support.py','entry.py','processes.py','prepare_freeze.py','test_contexts.py','HANDOFF.md']
metadata={};ledger=[]
def pin(path,expected=None,key=None):
    path=s.safe(path)
    if path.suffix=='.npz':raise ValueError('no model byte reads during freeze')
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(65536):h.update(b)
    digest=h.hexdigest()
    if expected and digest!=expected:raise ValueError('known predecessor mismatch '+str(path))
    metadata[key or str(path.relative_to(ROOT))]={'path':str(path.relative_to(ROOT)),'sha256':digest};return digest
def obj(path,expected=None,key=None):
    pin(path,expected,key)
    if path.stat().st_size>2**20:raise ValueError('metadata JSON cap')
    return s.parse(path.read_bytes())
def output_chain(path,h):
    r=obj(path,h)
    if r.get('status')!='COMPLETE' or (path.parent/'FAILURE.json').exists():raise ValueError('successful predecessor required')
    for n,p in r['outputs'].items():
        if Path(n).name!=n:raise ValueError('flat predecessor output')
        pin(path.parent/n,p)
    return r
def main():
    destination=HERE/'REGISTRY_v3.json'
    if destination.exists():raise FileExistsError('immutable registry')
    pin(HERE/'SOURCE_V1_PRESERVED.tar');pin(HERE/'REGISTRY.json','3afe0a0dc130d8602886fc4b63a6a3223022b101b030538969eeb934ac680208')
    pin(HERE/'SOURCE_V2_PRESERVED.tar');pin(HERE/'REGISTRY_v2.json','ac4d9636d8823732a671e0a636525654602cab4f573f34cee3ca81fff546db44')
    preg=obj(SOLE/'REGISTRY_SOURCE_V1.json','6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc')
    creg=obj(CHECK/'CHECKER_SOURCE_REGISTRY_V1.json','2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26')
    for n,h in preg['sources'].items():pin(SOLE/n,h)
    for e in preg['predecessors'].values():pin(ROOT/e['path'],e['sha256'])
    for role in ('adjacent_complete','adjacent_producer_complete'):
        e=preg['predecessors'][role];output_chain(ROOT/e['path'],e['sha256'])
    ext={'producer':{'path':str((SOLE/'producer.py').relative_to(ROOT)),'sha256':preg['sources']['producer.py']},'producer_entry':{'path':str((SOLE/'run.py').relative_to(ROOT)),'sha256':preg['sources']['run.py']},'io':creg['sources']['io'],'checker':creg['sources']['checker'],'checker_entry':creg['sources']['entry'],'primitive':creg['sources']['primitive']}
    for e in ext.values():pin(ROOT/e['path'],e['sha256'])
    manifest=obj(ROOT/'independent_environment/bounds_extraction/manifest.json','210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea','manifest')
    obj(ROOT/'model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json','8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782','stage0')
    oldp=output_chain(OLD/'certificates_produce/COMPLETE.json','0e1a2fd5813ac498cd160a6022fc5e6c9512bfecfde6b4caa94ef7f669a560fd');oldr=output_chain(OLD/'certificates_replay/COMPLETE.json','cc3e258a040529fa93c62291a8d142c873934bf7e23d11278d9d5895e1bae0de')
    if oldr['summary']['predecessor_sha256']!=metadata[str((OLD/'certificates_produce/COMPLETE.json').relative_to(ROOT))]['sha256']:raise ValueError('old aggregate chain')
    oldreg=obj(OLD/'REGISTRY_v3.json',oldr['registry_sha256'])
    for n,h in oldreg['sources'].items():pin(OLD/n,h)
    for n,h in oldreg['external_sources'].items():pin(ROOT/n,h)
    for phase,r in [('certificates_produce',oldp),('certificates_replay',oldr)]:
        candidates=[x for x in OLD.glob('*APPROVAL*.json') if hashlib.sha256(x.read_bytes()).hexdigest()==r['approval_sha256']]
        if len(candidates)!=1:raise ValueError('unique old aggregate approval')
        ap=obj(candidates[0],r['approval_sha256'])
        if ap['phase']!=phase or ap['registry_sha256']!=r['registry_sha256'] or ap['actual_execution_authorized'] is not True:raise ValueError('old phase approval')
    rows=[]
    for i,c in enumerate(s.CONTEXTS):
        member=f'arrays/tree_{2*i+1:02d}_capped.npz';rr=oldr['summary']['contexts'][c];pp=oldp['summary']['contexts'][c]
        row={'context':c,'member':member,'model_sha256':manifest['files'][member],'old_D':{k:rr['summary']['D'][k] for k in ('lower','upper','B')}}
        if rr['model_sha256']!=row['model_sha256'] or pp['model_sha256']!=row['model_sha256']:raise ValueError('old model context')
        if c!='final':
            rp=output_chain(OLD/'certificates_replay'/c/'COMPLETE.json',rr['complete_sha256']);cp=output_chain(OLD/'certificates_produce'/c/'COMPLETE.json',pp['complete_sha256'])
            if rp['summary']!={k:v for k,v in rr.items() if k!='complete_sha256'} or cp['summary']!={k:v for k,v in pp.items() if k!='complete_sha256'} or rr['producer_complete_sha256']!=pp['complete_sha256'] or rr['certificate_sha256']!=cp['outputs']['certificate.json'] or rp['registry_sha256']!=oldr['registry_sha256'] or cp['registry_sha256']!=oldp['registry_sha256'] or rp['approval_sha256']!=oldr['approval_sha256'] or cp['approval_sha256']!=oldp['approval_sha256']:raise ValueError('old child ancestry')
        rows.append(row)
    s.validate_contexts(rows,manifest)
    final={}
    for role,path,h in [('producer',SOLE/'attempt_1/COMPLETE.json','dcb30c773b23f1a4dff91e5eb49058566793826aa9b699512b76390c5acc3704'),('replay',CHECK/'attempt_1/COMPLETE.json','af092b5b5a7149c1156375bf784c700035d785324d23494f323aa14f5efcb4aa')]:
        r=output_chain(path,h);final[role]={'path':str(path.relative_to(ROOT)),'sha256':h}
        apath=(SOLE/'ROOT_PRODUCER_APPROVAL.json') if role=='producer' else CHECK/'ROOT_REPLAY_APPROVAL.json';ap=obj(apath,r['approval_sha256'])
        obj(SOLE/'ROOT_SOURCE_REVIEW.json',ap['source_review_sha256']);obj(SOLE/'COLD_GATE_PASS.json',ap['synthetic_gate_sha256'])
    pin(SOLE/'all_context_proposal/PROTOCOL_DRAFT.md')
    reg={'schema':'FOUR_TREE_ALL_CONTEXT_SOURCE_V1','actual_execution_authorized':False,'contexts':rows,'sources':{n:pin(HERE/n) for n in SOURCES},'external_sources':ext,'metadata':metadata,'final':final}
    with destination.open('x') as f:json.dump(reg,f,sort_keys=True,indent=2)
    print(json.dumps({'registry_sha256':s.sha(destination.read_bytes()),'metadata_pins':len(metadata),'contexts':len(rows),'model_byte_reads':0}))
if __name__=='__main__':main()
