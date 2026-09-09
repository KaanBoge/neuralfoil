"""Pinned metadata and synthetic state/accounting checks; no real tree loading."""
from pathlib import Path
import hashlib,json,sys,tempfile
HERE=Path(__file__).resolve().parent
P=HERE.parents[1]/'tree_range_refinement';sys.path.insert(0,str(P))
import test_pilot_v2 as t
import pilot_engine as old
PIN='5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    assert sha(P/'PILOT_REGISTRY_V2.json')==PIN
    r=json.loads((P/'PILOT_REGISTRY_V2.json').read_bytes())
    for item in r['sources'].values():assert sha(P/item['path'])==item['sha256']
    prior=json.loads((P/'PILOT_REGISTRY.json').read_bytes())
    assert all(r['sources'][k]==v for k,v in prior['sources'].items())
    model=t.E.SequentialHist(t.arrays([t.stump(),t.stump(10.,0.)]),required_stages=2)
    completed=[];replays=[]
    with tempfile.TemporaryDirectory() as td:
        def publish(s):
            path=Path(td)/f"checkpoint_{s['splits']}.json";t.exclusive_json(path,s);completed.append(path)
            replays.append(t.checker.replay(json.loads(path.read_bytes()),model.stages,0.,t.Q.sequential_range))
        limit=t.engine.Limits(model.stages);final,reason=t.engine.refine(model.stages,0.,t.Q.sequential_range,limit,publish,splits=2)
        assert reason=='routing_resolved' and final['splits']==limit.completed_splits==1 and limit.initialized
        assert len(completed)==2 and all(x['status']=='PASS_FULL_DOMAIN_REPLAY' for x in replays)
        before=sha(completed[0]);counter=[0]
        def abort(chunk):
            counter[0]+=1
            if counter[0]==20:raise KeyboardInterrupt('synthetic serialization interruption')
        path=Path(td)/'interrupted.json'
        try:t.exclusive_json(path,final,serialization_interrupt=abort)
        except KeyboardInterrupt:pass
        else:raise AssertionError('interruption did not occur')
        assert not path.exists() and Path(str(path)+'.partial').exists() and sha(completed[0])==before
        t.checker.replay(json.loads(completed[0].read_bytes()),model.stages,0.,t.Q.sequential_range)
    differences=[]
    for n in [1,2,400]:
        stages=[t.stump() for _ in range(n)]
        for stage in stages:stage.setflags(write=False)
        for container in [stages,tuple(stages)]:
            for persistent,transient in [((),()),({'f':[1.,2.,3.]},[{'x':4.}]),(final,(final,stages))]:
                a=old.Limits(container);b=t.engine.Limits(container);a.persistent=persistent;b.persistent=persistent;a.check(transient);b.check(transient)
                assert b.peak_estimate>=a.peak_estimate
                differences.append(b.peak_estimate-a.peak_estimate)
    return {'status':'PASS_BOUNDED_SOURCE_CLEARANCE','registry_sha256':PIN,'source_pins_verified':len(r['sources']),'v1_preserved':True,'synthetic_completed_checkpoints_replayed':2,'interrupted_stream_prior_preserved':True,'cached_accounting_cases':len(differences),'minimum_extra_estimate_bytes':min(differences),'maximum_extra_estimate_bytes':max(differences),'audit_source_sha256':sha(__file__),'real_model_arrays_opened':False,'scope':'Only exact final/proper/capped pilot with120s search plus≤60s checker, pending root approval. Not actual enclosure results.'}
if __name__=='__main__':
    out=HERE/'PILOT_V2_SOURCE_QA.json';assert not out.exists();result=main()
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
