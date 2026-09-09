"""One approved checker-only replay; no engine, search, labels or calibration."""
import json, sys, time, signal, hashlib
from pathlib import Path
from fractions import Fraction as F
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]/'tree_range_refinement'
sys.path.insert(0,str(ROOT))
import pilot_adapter as a
import pilot_checker as c
PIN='5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a'
def main():
    out=HERE/'PILOT_RESULT_QA.json'
    if out.exists(): raise FileExistsError(out)
    signal.signal(signal.SIGALRM,lambda *args: (_ for _ in ()).throw(TimeoutError('60 second audit ceiling')))
    signal.alarm(60); start=time.monotonic()
    witness=json.loads((ROOT/'PILOT_V2_ATTEMPT_1_WITNESS.json').read_bytes())
    for name,h in witness['files_sha256'].items(): assert a.sha(ROOT/name)==h,name
    assert a.sha(ROOT/'ROOT_PILOT_V2_APPROVAL.json')==witness['approval_sha256']
    r,root=a.authenticate(ROOT/'PILOT_REGISTRY_V2.json',PIN)
    d=ROOT/'pilot_v2_attempt_1'
    assert {str(p.relative_to(ROOT)) for p in d.iterdir()}==set(witness['files_sha256'])
    f=json.loads((d/'FINAL.json').read_bytes()); v=json.loads((d/'verified.json').read_bytes())
    assert a.sha(d/'FINAL.json')=='0d8eb0142bc711f666fc53d1b4092877ebcd69245b85e797e392059a5ff7fc53'
    assert a.sha(d/'verified.json')=='f1fd965320fcae9bc426ace0e9c1bd07d561330fa12551465c74bd0fbf514dd6'
    for k,value in v.items(): assert f[k]==value,k
    model=a.load_model(r,root); q=a.source_module(r,root,'qualified_numerics')
    checkpoint=json.loads((d/'candidate_001.json').read_bytes())
    replay=c.replay(checkpoint,model.stages,model.initial,q.sequential_range,deadline=start+60)
    for k,value in replay.items(): assert v[k]==value,k
    B=q.structural_bound(replay['lower'],replay['upper']); assert B==F(v['B_structural'])
    inherited=a.inherited(r,root)
    assert inherited==json.loads((d/'checkpoint_000_inherited.json').read_bytes())
    for k in ['lower','upper']:
        z=inherited['range'][k]; assert F(z['numerator'])/F(z['denominator'])==F(replay[k])
    cert=json.loads((root/r['sources']['stage0_certificate']['path']).read_bytes())
    z=next(x for x in cert['records'] if x['context']=='final')['B_structural']
    assert B==F(z['numerator'])/F(z['denominator'])
    assert f['search']=={'returncode':None,'timeout':True}
    assert not (d/'worker_status.json').exists()
    assert all(p.stat().st_size==0 for p in d.glob('*.txt'))
    assert (d/'checkpoint_000_inherited.json').stat().st_mtime_ns < (d/'candidate_000.json').stat().st_mtime_ns < (d/'candidate_001.json').stat().st_mtime_ns < (d/'verified.json').stat().st_mtime_ns
    a.authenticate(ROOT/'PILOT_REGISTRY_V2.json',PIN)
    for name,h in witness['files_sha256'].items(): assert a.sha(ROOT/name)==h
    result={'status':'PASS','seconds':time.monotonic()-start,'replay':replay,'B_structural':str(B),'exact_tightening':'0','source_pins':len(r['sources']),'attempt_files':len(witness['files_sha256']),'worker_total_statistics':'unavailable; no worker_status','scope':'one checker-only replay; no search, labels, calibration or fits','witness_sha256':a.sha(ROOT/'PILOT_V2_ATTEMPT_1_WITNESS.json')}
    with out.open('x') as stream:json.dump(result,stream,indent=2)
    signal.alarm(0);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
