"""Fixed synthetic cross-implementation feasibility/witness comparison."""
from pathlib import Path
import importlib.util,itertools,math,sys,random,json,hashlib,copy
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PATHS=[ROOT/'feature_relation_certification/exact_oracle.py',ROOT/'tree_range_refinement/feature_relation_oracle_review/oracle.py']
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
a,b=[load(p,n) for p,n in zip(PATHS,['first','second'])]
def main():
    grid=[-sys.float_info.max,-1.0,math.nextafter(-1.,0.),-math.ulp(0.),-0.,0.,math.ulp(0.),math.nextafter(1.,0.),1.,sys.float_info.max]
    count=0;feasible=0
    def check(box,truth=None):
        nonlocal count,feasible
        before=copy.deepcopy(box);x=a.feasible_witness(box);y=b.feasible(box);assert (x is not None)==y['feasible'];assert box==before
        if truth is not None:assert (x is not None)==truth
        count+=1;feasible+=int(x is not None)
        for w in [x,y['witness']]:
            if w is None:continue
            assert len(w)==62 and all(type(v) is float and math.isfinite(v) and l<=v<=u for v,(l,u) in zip(w,box))
            assert w[16]==abs(w[0]) and w[18]==min(w[12],w[13]) and w[19]==max(w[12],w[13])
    intervals=[(x,y) for x in grid for y in grid if x<=y]
    for aa,rr in itertools.product(intervals,repeat=2):
        box=[(0.,0.)]*62;box[0]=aa;box[16]=rr
        truth=any(aa[0]<=x<=aa[1] and rr[0]<=abs(x)<=rr[1] for x in set(grid+[-v for v in grid]))
        check(box,truth)
    small=[-1.,0.,1.];ints=[(x,y) for x in small for y in small if x<=y]
    for t,d,m,p in itertools.product(ints,repeat=4):
        box=[(0.,0.)]*62
        for i,v in zip([12,13,18,19],[t,d,m,p]):box[i]=v
        check(box,any(t[0]<=x<=t[1] and d[0]<=y<=d[1] and m[0]<=min(x,y)<=m[1] and p[0]<=max(x,y)<=p[1] for x,y in itertools.product(small,repeat=2)))
    rng=random.Random(202609081733)
    for _ in range(4096):check([tuple(sorted(rng.choices(grid,k=2))) for _ in range(62)])
    return {'status':'PASS','cases':count,'feasible':feasible,'random_seed':202609081733,'random_boxes':4096,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in PATHS},'scope':'synthetic cases only; numeric witness validity, not identical choice; theorem reviewed separately'}
if __name__=='__main__':
    r=main()
    with (HERE/'EXACT_ORACLE_CROSS_QA.json').open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
