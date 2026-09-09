"""One bounded checker replay of exact published V3 checkpoint; no search."""
from pathlib import Path
from fractions import Fraction as F
import sys,json,signal,time,traceback
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]/'tree_range_refinement/performance_diagnosis'
sys.path.insert(0,str(ROOT.parent))
import pilot_adapter as a
import pilot_checker as c
PIN='a989ed3215fd933650c49d15644219e678e59e001affa141091fdabb02eba2a5'
def main():
    start=time.monotonic();signal.signal(signal.SIGALRM,lambda *x:(_ for _ in ()).throw(TimeoutError('60 second ceiling')));signal.alarm(60)
    w=json.loads((ROOT/'PILOT_V3_ATTEMPT_1_WITNESS.json').read_bytes())
    for n,h in w['files_sha256'].items():assert a.sha(ROOT/n)==h,n
    r,root=a.authenticate(ROOT/'PILOT_REGISTRY_V3.json',PIN);d=ROOT/'pilot_v3_attempt_1';f=json.loads((d/'FINAL.json').read_bytes());v=json.loads((d/'verified.json').read_bytes())
    for k,x in v.items():assert f[k]==x
    p=d/'candidate_004.json';assert a.sha(p)=='cc82b47f2f688e95fcf6109c1968fca4b01a99727597107740fcac7cba7ed0c5'
    model=a.load_model(r,root);q=a.source_module(r,root,'qualified_numerics');result=c.replay(json.loads(p.read_bytes()),model.stages,model.initial,q.sequential_range,deadline=start+60)
    for k,x in result.items():assert v[k]==x
    assert result['splits']==4 and result['boxes']==5 and result['replay_node_visits']==56750
    B=q.structural_bound(result['lower'],result['upper']);assert B==F(v['B_structural'])
    inherited=a.inherited(r,root);assert inherited==json.loads((d/'checkpoint_000_inherited.json').read_bytes())
    for key in ['lower','upper']:
        z=inherited['range'][key];assert F(z['numerator'])/F(z['denominator'])==F(result[key])
    cert=json.loads((root/r['sources']['stage0_certificate']['path']).read_bytes());z=next(x for x in cert['records'] if x['context']=='final')['B_structural'];assert B==F(z['numerator'])/F(z['denominator'])
    for n in ['candidate_000.json','candidate_001.json']:assert a.sha(d/n)==a.sha(ROOT.parent/'pilot_v2_attempt_1'/n)
    assert not (d/'worker_status.json').exists();assert f['search']['timeout'] is True
    for n,h in w['files_sha256'].items():assert a.sha(ROOT/n)==h
    a.authenticate(ROOT/'PILOT_REGISTRY_V3.json',PIN);signal.alarm(0)
    return {'status':'PASS','seconds':time.monotonic()-start,'checker':result,'B_structural':str(B),'tightening_exact':'0','source_pins':len(r['sources']),'candidate000_001_exactly_equal_V2':True,'worker_total_statistics':'unavailable','witness_sha256':a.sha(ROOT/'PILOT_V3_ATTEMPT_1_WITNESS.json'),'scope':'one checker-only replay, no search/outcomes/calibration'}
if __name__=='__main__':
    out=HERE/'PILOT_V3_RESULT_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'PILOT_V3_AUDIT_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
