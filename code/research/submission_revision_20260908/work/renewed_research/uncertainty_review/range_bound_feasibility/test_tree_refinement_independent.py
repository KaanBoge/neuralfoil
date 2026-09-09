"""Only synthetic trees. Independent cell oracle and interruption observations."""
from pathlib import Path
from fractions import Fraction as F
import hashlib, importlib.util, itertools, json, math, random, sys, time, traceback
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
p=module('independent_tree_prototype',ROOT/'tree_range_refinement/prototype.py')
qpath=ROOT/'model_proposal/range_bound_feasibility/qualified_numerics.py'
assert hashlib.sha256(qpath.read_bytes()).hexdigest()=='76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a'
q=module('authenticated_synthetic_math',qpath)
def inside(x,b):return all(a<=v<=z for v,(a,z) in zip(x,b))
def native(trees,x):
    value=0.
    for t in trees:
        while isinstance(t,p.Split):t=t.left if x[t.feature]<=t.threshold else t.right
        value=float(value+t.value)
    return value
def main():
    start=time.monotonic();rng=random.Random(20260908);tiny=math.ulp(0.)
    thresholds=[-p.MAX,-1.,-tiny,-0.,0.,tiny,1.,p.MAX]
    splitchecks=0
    for t in thresholds:
        a,b=p.split_box(p.full_box(1),0,t)
        vals={-p.MAX,p.MAX,-tiny,-0.,0.,tiny,t}
        vals.update(x for x in [math.nextafter(t,-math.inf),math.nextafter(t,math.inf)] if math.isfinite(x))
        for x in vals:
            hits=[inside([x],z) for z in [a,b] if z is not None]
            assert sum(hits)==1
            assert (a is not None and inside([x],a))==(x<=t);splitchecks+=1
    def tree(depth):
        if not depth:return p.Leaf(float(rng.choice([-2.**53,-1.,-tiny,0.,tiny,1.,2.**53])))
        return p.Split(rng.randrange(2),rng.choice(thresholds),tree(depth-1),tree(depth-1))
    points=sorted(set(thresholds+[math.nextafter(t,math.inf) for t in thresholds if t<p.MAX]+[math.nextafter(t,-math.inf) for t in thresholds if t> -p.MAX]))
    containment=0;frontier_checks=0
    for case in range(12):
        trees=[tree(3) for _ in range(3)]
        for budget in [0,1,4,16]:
            r=p.refine(trees,2,0.,q.sequential_range,max_splits=budget)
            for old,new in zip(r['history'],r['history'][1:]):assert old[0]<=new[0]<=new[1]<=old[1]
            for x in itertools.product(points,repeat=2):
                boxes=[b for b in r['frontier'] if inside(x,b['box'])];assert len(boxes)==1
                y=F(native(trees,x));b=boxes[0];assert b['lower']<=y<=b['upper'];containment+=1
            # Independent reachable-leaf enumeration across threshold-induced cells.
            for box in r['frontier']:
                for t in trees:
                    actual=set()
                    for x in itertools.product(points,repeat=2):
                        if not inside(x,box['box']):continue
                        n=t
                        while isinstance(n,p.Split):n=n.left if x[n.feature]<=n.threshold else n.right
                        actual.add(n.value)
                    assert actual==set(p.reachable(t,box['box'])[0]);frontier_checks+=1
    t=p.Split(0,0.,p.Leaf(-1.),p.Leaf(1.))
    try:p.refine([t],1,0.,q.sequential_range,max_visits=1)
    except p.VisitBudget:root_failure=True
    else:raise AssertionError('root budget observation changed')
    lines=(ROOT/'tree_range_refinement/prototype.py').read_text().splitlines()
    target=next(i+1 for i,line in enumerate(lines) if 'for c in children:frontier[c' in line)
    observation={}
    def trace(frame,event,arg):
        if event=='line' and frame.f_code.co_filename==p.__file__ and frame.f_lineno==target:
            observation['frontier_size_between_delete_and_add']=len(frame.f_locals['frontier'])
            observation['trace_size']=len(frame.f_locals['trace'])
            raise KeyboardInterrupt('synthetic async interruption at non-atomic frontier gap')
        return trace
    try:
        sys.settrace(trace)
        p.refine([t],1,0.,q.sequential_range)
    except KeyboardInterrupt:pass
    finally:sys.settrace(None)
    assert observation=={'frontier_size_between_delete_and_add':0,'trace_size':0}
    return {'status':'SYNTHETIC_NUMERIC_PASS_WITH_REQUIRED_PRODUCTION_RECOVERY_FIXES','source_sha256':hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'split_coverage_checks':splitchecks,'point_containment_checks':containment,'exact_reachable_leaf_set_checks':frontier_checks,'synthetic_ensembles':12,'root_budget_raises_without_result':root_failure,'asynchronous_gap_observation':observation,'seconds':time.monotonic()-start,'scope':'Finite threshold-cell exhaustive synthetic oracle; no actual tree exports or outcome data. Prototype is not a persistent checkpoint implementation.'}
if __name__=='__main__':
    out=HERE/'TREE_REFINEMENT_SYNTHETIC_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'TREE_REFINEMENT_SYNTHETIC_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
