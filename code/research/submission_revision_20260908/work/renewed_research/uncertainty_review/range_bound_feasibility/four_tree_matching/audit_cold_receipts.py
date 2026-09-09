"""Saved synthetic certificate/metadata reconciliation, not a proof rerun."""
from pathlib import Path
from datetime import datetime
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];P=ROOT/'model_proposal/four_tree_matching_plan';C=P/'cold_attempt_1'
PS='6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc';CS='2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26';COMPLETE='b5fc0fa6463f2704519df2a4be658cf21d4afbbcb7a52bf5d4e6c5035b86f6a0'
ledger=[]
def auth(path,pin,parse=False):
    assert path.suffix in {'.json','.py','.md','.txt','.partial'}
    assert not any(x.is_symlink() for x in (path,*path.parents))
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(65536):h.update(b)
    assert h.hexdigest()==pin,(str(path),h.hexdigest(),pin)
    ledger.append({'path':str(path.relative_to(ROOT)),'sha256':pin,'bytes':path.stat().st_size})
    return json.loads(path.read_bytes()) if parse else None
def main():
    out=HERE/'COLD_RECEIPT_QA.json'
    if out.exists():raise FileExistsError('preserve audit')
    parent=auth(C/'COMPLETE.json',COMPLETE,True)
    assert parent['status']=='PASS_FIXED_135000_GATE' and parent['actual_model_access'] is False
    reg=auth(P/'REGISTRY_SOURCE_V1.json',PS,True);creg=auth(HERE/'CHECKER_SOURCE_REGISTRY_V1.json',CS,True)
    assert creg['producer_registry_sha256']==PS and creg['sources']==reg['checker_sources']
    for n,h in reg['sources'].items():auth(P/n,h)
    for e in [*reg['predecessors'].values(),*reg['checker_sources'].values()]:auth(ROOT/e['path'],e['sha256'])
    app=auth(P/'ROOT_COLD_GATE_APPROVAL.json',parent['approval_sha256'],True)
    expected={'phase':'four_tree_fixed_cold_gate','registry_sha256':PS,'checker_registry_sha256':CS,'fixture_sha256':hashlib.sha256(b'fixed-four-tree400x15-allpairs-v1').hexdigest(),'producer_seconds':120,'checker_seconds':120,'workers':1,'producer_owned_cap':128*2**20,'checker_owned_cap':256*2**20,'aggregate_output_cap':64*2**20,'synthetic_execution_authorized':True,'actual_model_execution_authorized':False}
    assert app==expected and all(type(app[k]) is type(v) for k,v in expected.items())
    assert not list(C.rglob('*FAILURE*'))
    for n,h in parent['outputs'].items():auth(C/n,h)
    token=auth(C/'TOKEN.json',parent['outputs']['TOKEN.json'],True)
    assert token['registry_sha256']==PS and token['checker_registry_sha256']==CS and token['approval_sha256']==parent['approval_sha256']
    counts={'blocks':100,'stages':400,'paths':6000,'path_edges':47600,'pair_classifications':135000,'feasible_pairs':135000}
    phases={};events={}
    for phase,cap in [('producer',128*2**20),('checker',256*2**20)]:
        r=auth(C/phase/'COMPLETE.json',parent[phase]['complete_sha256'],True);phases[phase]=r
        for k in ['registry_sha256','checker_registry_sha256','approval_sha256','fixture_sha256']:assert r[k]==parent[k]==token[k]
        assert r['parent_pid']==token['parent_pid'] and r['pid']!=r['parent_pid'] and r['phase']==phase and r['status']=='COMPLETE'
        assert r['summary']['counts']==counts and 0<=r['seconds']<=parent[phase]['seconds']<=120
        assert 0<=r['summary']['deep_owned_retained_bytes']<=r['summary']['owned_estimate']<=cap
        for k in ['owned_estimate','deep_owned_retained_bytes']:assert r['summary'][k]==parent[phase][k]
        files={n for n in r['outputs']}|{'COMPLETE.json','COMPLETE.json.partial'}
        assert files=={x.name for x in (C/phase).iterdir() if x.is_file()}
        for n,h in r['outputs'].items():auth(C/phase/n,h)
        auth(C/phase/'COMPLETE.json.partial',parent[phase]['complete_sha256'])
        assert sum(x.stat().st_size for x in (C/phase).iterdir())==parent[phase]['logical_output_bytes']
        events[phase]=auth(C/phase/'ACCESS.json',r['outputs']['ACCESS.json'],True)
        for e in events[phase]:
            if 'path' in e:
                path=Path(e['path']);assert path.suffix!='.npz';auth(path,e['sha256'])
    assert phases['producer']['pid']!=phases['checker']['pid']
    assert datetime.fromisoformat(phases['producer']['finish_utc'])<datetime.fromisoformat(phases['checker']['start_utc'])
    assert phases['checker']['summary']['producer_complete_sha256']==parent['producer']['complete_sha256']
    certpin=phases['producer']['summary']['certificate_sha256'];assert certpin==phases['checker']['summary']['certificate_sha256']
    cert=auth(C/'producer/certificate.json',certpin,True);replay=auth(C/'checker/REPLAY.json',phases['checker']['outputs']['REPLAY.json'],True)
    assert cert['model_sha256']==parent['fixture_sha256'] and cert['counts']==replay['counts']==counts
    assert len(cert['paths'])==400 and sum(len(x['leaves']) for x in cert['paths'])==6000
    assert sum(len(y['edges']) for x in cert['paths'] for y in x['leaves'])==47600
    statuses=[bytes.fromhex(p['status_hex']) for b in cert['blocks'] for p in b['pairs']]
    assert len(cert['blocks'])==100 and len(statuses)==600 and all(len(v)==225 and set(v)=={2} for v in statuses)
    assert sum(map(len,statuses))==135000
    assert all((C/(phase+'.'+suffix)).stat().st_size==0 for phase in phases for suffix in ['stdout.txt','stderr.txt'])
    logical=sum(x.stat().st_size for x in C.rglob('*') if x.is_file());assert logical<64*2**20
    auth(C/'COMPLETE.json.partial',COMPLETE)
    result={'status':'PASS_SAVED_SYNTHETIC_RECEIPT_AUDIT','complete_sha256':COMPLETE,'producer_registry_sha256':PS,'checker_registry_sha256':CS,'certificate_sha256':certpin,'counts':counts,'phases':{k:{'parent_observed_seconds':parent[k]['seconds'],'internal_seconds':v['seconds'],**v['summary']} for k,v in phases.items()},'aggregate_logical_bytes':logical,'no_failure_files':True,'empty_parent_logs':True,'source_metadata_events':{k:len(v) for k,v in events.items()},'ledger':ledger,'checker_reruns':0,'model_array_materializations':0,'scope':'Saved synthetic receipts/counts and authentication, not a second mathematical proof replay or actual-model result.'}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps({'status':result['status'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'logical_bytes':logical,'hash_checks':len(ledger)}))
if __name__=='__main__':main()
