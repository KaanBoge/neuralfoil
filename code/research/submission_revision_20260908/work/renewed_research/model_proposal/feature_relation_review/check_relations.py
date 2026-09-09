"""Independent synthetic containment only; no feature/model/outcome inputs."""
import hashlib,itertools,json,math,random,sys,time,types
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parents[1]/'feature_relation_certification/relations.py'
PIN='1f175bdfe40e0e13451963bb4752e2d5903592f0f92c07246038c96e1b8c0127'
def main():
    start=time.monotonic();raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==PIN
    m=types.ModuleType('reviewed_relations');exec(compile(raw,str(SOURCE),'exec'),m.__dict__)
    M=sys.float_info.max;s=math.ulp(0.0)
    grid=[-M,-1.,-s,-0.,0.,s,1.,M];rng=random.Random(2026090841)
    checks=0
    for a,b,c in itertools.product(grid,repeat=3):
        x=[0.]*62;x[0]=a;x[16]=abs(a);x[12]=b;x[13]=c;x[18]=b if b<c else c;x[19]=b if b>c else c
        assert m.relation_guard(x)
        for trial in range(8):
            box=[]
            for v in x:
                lows=[t for t in grid if t<=v];highs=[t for t in grid if t>=v]
                box.append((v,v) if trial==0 else (rng.choice(lows),rng.choice(highs)))
            original=tuple(box)
            for passes in [0,1,2,16]:
                contracted=m.contract(box,passes)
                assert contracted is not None
                assert all(lo<=v<=hi for (lo,hi),v in zip(contracted,x))
                assert all(olo<=lo<=hi<=ohi for (olo,ohi),(lo,hi) in zip(box,contracted))
                assert tuple(box)==original
                checks+=1
    # Strict minimum/maximum equality and disconnected signs independently pinned.
    b=[(-M,M)]*62;b[0]=(-1.,1.);b[16]=(1.,1.)
    out=m.contract(b);assert out[0]==(-1.,1.)
    for a,c in [(1.,2.),(-1.,-2.)]:
        b=[(-M,M)]*62;b[12]=(a,a);b[13]=(c,c);b[18]=(min(a,c),)*2;b[19]=(max(a,c),)*2
        assert m.contract(b) is not None
    result={'status':'SYNTHETIC_CONTAINMENT_PASS','source_sha256':PIN,'feasible_base_points':512,
        'planted_boxes':4096,'containment_and_subset_checks':checks,'seed':2026090841,
        'includes':['max finite','minimum subnormal','signed zeros','strict-implication equality','sign-straddling'],
        'seconds':time.monotonic()-start,'python':sys.version,'actual_features_models_targets_loaded':False}
    with (HERE/'RESULT.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
if __name__=='__main__':main()
