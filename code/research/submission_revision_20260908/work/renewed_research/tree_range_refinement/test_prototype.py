"""Synthetic cases only. Imports authenticated pure Stage0 arithmetic source."""
import hashlib,importlib.util,itertools,math,unittest
from fractions import Fraction as F
from pathlib import Path
from prototype import Leaf,Split,MAX,full_box,split_box,reachable,refine,predict

SOURCE=Path(__file__).resolve().parent.parent/'model_proposal/range_bound_feasibility/qualified_numerics.py'
PIN='76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a'
if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=PIN:raise ValueError('Stage0 source mutation')
spec=importlib.util.spec_from_file_location('unchanged_stage0_math',SOURCE)
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

def stump(t,a,b,feature=0):return Split(feature,t,Leaf(a),Leaf(b))
def inside(x,box):return all(a<=v<=b for v,(a,b) in zip(x,box))

class Refinement(unittest.TestCase):
    def test_opposite_correlated_trees(self):
        trees=[stump(0.,10.,0.),stump(0.,0.,10.)]
        r=refine(trees,1,0.,q.sequential_range)
        self.assertEqual(r['history'][0],(F(0),F(20)))
        self.assertEqual((r['lower'],r['upper']),(F(10),F(10)))
    def test_impossible_within_tree_path(self):
        tree=Split(0,0.,Split(0,1.,Leaf(2.),Leaf(1000.)),Leaf(3.))
        self.assertEqual(reachable(tree,full_box(1))[0],[2.,3.])
    def test_zero_and_neighbors_cover_exactly(self):
        children=split_box(full_box(1),0,-0.)
        for x in [-MAX,-math.ulp(0.),-0.,0.,math.ulp(0.),MAX]:
            hits=[inside([x],b) for b in children if b is not None]
            self.assertEqual(sum(hits),1)
            self.assertEqual(hits[0],x<=0.)
    def test_max_threshold(self):
        a,b=split_box(full_box(1),0,MAX)
        self.assertEqual(a,full_box(1));self.assertIsNone(b)
    def test_min_threshold(self):
        a,b=split_box(full_box(1),0,-MAX)
        self.assertEqual(a,((-MAX,-MAX),));self.assertEqual(b[0][0],math.nextafter(-MAX,math.inf))
    def test_zero_budget_preserves_root(self):
        r=refine([stump(0.,-1.,1.)],1,0.,q.sequential_range,max_splits=0)
        self.assertEqual(len(r['frontier']),1);self.assertEqual(r['stop'],'split_budget')
    def test_atomic_child_failure(self):
        calls=[]
        def fail(initial,stages):
            calls.append(1)
            if len(calls)==3:raise RuntimeError('injected second-child failure')
            return q.sequential_range(initial,stages)
        r=refine([stump(0.,-1.,1.)],1,0.,fail)
        self.assertEqual(len(r['frontier']),1);self.assertFalse(r['trace'])
        self.assertIn('injected',r['failure'])
    def test_visit_budget_preserves_root(self):
        r=refine([stump(0.,-1.,1.)],1,0.,q.sequential_range,max_visits=4)
        self.assertEqual(len(r['frontier']),1);self.assertIn('VisitBudget',r['failure'])
    def test_threshold_cell_oracle_and_monotonicity(self):
        trees=[stump(0.,1.,-.25),stump(1.,-.5,.75),stump(-1.,.125,-.125,1)]
        points=[-MAX,math.nextafter(-1.,-math.inf),-1.,math.nextafter(-1.,math.inf),-0.,0.,math.ulp(0.),1.,math.nextafter(1.,math.inf),MAX]
        for budget in [0,1,2,4,8,16]:
            r=refine(trees,2,0.,q.sequential_range,max_splits=budget)
            for x in itertools.product(points,repeat=2):
                matches=[b for b in r['frontier'] if inside(x,b['box'])]
                self.assertEqual(len(matches),1)
                y=F.from_float(predict(trees,0.,x))
                self.assertLessEqual(matches[0]['lower'],y);self.assertLessEqual(y,matches[0]['upper'])
            for a,b in zip(r['history'],r['history'][1:]):
                self.assertLessEqual(a[0],b[0]);self.assertLessEqual(b[1],a[1])
    def test_rounding_cancellation_is_enclosed(self):
        trees=[Leaf(2.**53),Leaf(1.),Leaf(-2.**53)]
        r=refine(trees,1,0.,q.sequential_range)
        y=F.from_float(predict(trees,0.,[0.]))
        self.assertEqual(y,0);self.assertLessEqual(r['lower'],y);self.assertLessEqual(y,r['upper'])
    def test_subnormal_enclosure(self):
        tiny=math.ulp(0.);trees=[stump(0.,-tiny,tiny),Leaf(tiny)]
        r=refine(trees,1,0.,q.sequential_range)
        for x in [-0.,0.,tiny]:
            y=F.from_float(predict(trees,0.,[x]));self.assertLessEqual(r['lower'],y);self.assertLessEqual(y,r['upper'])
    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):refine([stump(math.nan,0.,1.)],1,0.,q.sequential_range)
    def test_shared_child_rejected(self):
        leaf=Leaf(0.)
        with self.assertRaises(ValueError):refine([Split(0,0.,leaf,leaf)],1,0.,q.sequential_range)
    def test_nonfinite_input_rejected(self):
        with self.assertRaises(ValueError):predict([Leaf(0.)],0.,[math.inf])
    def test_stage0_unchanged(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),PIN)

if __name__=='__main__':unittest.main()
