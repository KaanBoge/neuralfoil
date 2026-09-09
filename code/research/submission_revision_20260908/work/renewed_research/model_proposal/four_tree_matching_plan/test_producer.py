"""Small pure fixtures only. Does not execute full135000 classification gate."""
import unittest,math,sys,json
from fractions import Fraction as F
import numpy as np
import producer as p
import fixtures as f

def q(v):return F(int(v['numerator'],16),int(v['denominator'],16))
def result(a):return p.construct(a,p.Budget(),model_sha='0'*64)
def bounds(c,k='final'):return q(c[k]['lower']),q(c[k]['upper'])
class Tests(unittest.TestCase):
    def test_fixed_zero_and_inventory(self):
        c=result(f.pack([]));self.assertEqual(bounds(c),(0,0));self.assertEqual(c['counts']['pair_classifications'],600);self.assertEqual(len(c['blocks']),100);self.assertEqual(c['counts']['paths'],400)
        for b in c['blocks']:
            self.assertEqual([x['stages'] for x in b['pairs']],[[b['stages'][i],b['stages'][j]] for i,j in p.PAIRS]);self.assertTrue(all(x['status_hex']=='02' for x in b['pairs']))
    def test_actual_cross_tree_improvement(self):
        a=f.cross_cancellation();c=result(a);lo,hi=bounds(c);ol,oh=bounds(c,'original_adjacent');self.assertGreater(lo,ol);self.assertLess(hi,oh)
        for x in [-1.,0.,math.nextafter(0.,1.),1.]:self.assertLessEqual(lo,F(f.evaluate(a,[x]*62)));self.assertGreaterEqual(hi,F(f.evaluate(a,[x]*62)))
        self.assertEqual(list(map(q,c['blocks'][0]['real_sum'])),[0,0])
    def test_pairwise_relaxation_not_global_attainment(self):
        a=f.onehot();c=result(a);self.assertEqual(list(map(q,c['blocks'][0]['real_sum'])),[0,2])
        self.assertEqual({f.evaluate(a,[x]*62) for x in [-2.,-.5,.5,2.]},{1.})
    def test_native_order_not_reassociated(self):
        a=f.rounding_counterexample();c=result(a);self.assertEqual(f.evaluate(a,[0.]*62),0.);self.assertEqual(list(map(q,c['blocks'][0]['real_sum'])),[1,1]);lo,hi=bounds(c);self.assertLessEqual(lo,0);self.assertGreaterEqual(hi,0)
    def test_signed_zero_and_subnormal(self):
        eta=math.nextafter(0.,1.);a=f.pack([f.stump(-eta,eta,threshold=-0.),f.stump(eta,-eta,threshold=0.)]);c=result(a);lo,hi=bounds(c)
        for x in [-eta,-0.,0.,eta]:self.assertLessEqual(lo,F(f.evaluate(a,[x]*62)));self.assertGreaterEqual(hi,F(f.evaluate(a,[x]*62)))
        self.assertEqual(q(c['blocks'][0]['error_steps'][0]['delta']),p.U*F(eta)+p.HALF_ETA)
    def test_max_threshold_empty_right(self):
        c=result(f.pack([f.stump(0.,1.,threshold=sys.float_info.max)]));self.assertTrue(c['paths'][0]['leaves'][1]['empty']);self.assertEqual(c['blocks'][0]['pairs'][0]['status_hex'],'0200')
    def test_repeated_feature_impossible_path_preserved(self):
        t=f.chain([0.,1.,2.],thresholds=[1.,0.]);c=result(f.pack([t]));self.assertEqual(len(c['paths'][0]['leaves']),3);self.assertEqual(sum(x['empty'] for x in c['paths'][0]['leaves']),1)
    def test_large_incoming_cancellation(self):
        a=f.pack([f.constant(-2.**53),f.constant(1.)],initial=2.**53);c=result(a);self.assertEqual(f.evaluate(a,[0.]*62),1.);self.assertLessEqual(bounds(c)[0],1);self.assertGreaterEqual(bounds(c)[1],1)
    def test_overflow_refusal(self):
        with self.assertRaisesRegex(ValueError,'overflow'):result(f.pack([f.constant(sys.float_info.max)],initial=sys.float_info.max))
    def test_topology_and_dtype_failures(self):
        for mutation in ['cycle','unreachable','floatindex','categorical','nonfinite','missingmember','offset']:
            a=f.pack([f.stump(0.,1.)])
            if mutation=='cycle':a['nodes'][0]['left']=0
            if mutation=='unreachable':a['nodes'][0]['right']=1
            if mutation=='floatindex':a['nodes_offsets']=a['nodes_offsets'].astype(float)
            if mutation=='categorical':a['nodes'][0]['is_categorical']=1
            if mutation=='nonfinite':a['nodes'][1]['value']=np.nan
            if mutation=='missingmember':del a['initial']
            if mutation=='offset':a['nodes_offsets'][2]=a['nodes_offsets'][1]
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):result(a)
    def test_expired_budget(self):
        with self.assertRaises(TimeoutError):p.construct(f.pack([]),p.Budget(seconds=-1),model_sha='0'*64)
    def test_memory_precharge(self):
        with self.assertRaises(MemoryError):p.construct(f.pack([]),p.Budget(),model_sha='0'*64,input_bytes=128*2**20)
    def test_integer_limb_cap(self):
        with self.assertRaises(ValueError):p.encode(F(2**4096))
    def test_small_cartesian_native_containment(self):
        a=f.pack([f.stump(-.25,.5,feature=i) for i in range(4)]);c=result(a);lo,hi=bounds(c)
        import itertools
        for bits in itertools.product([-1.,1.],repeat=4):
            point=list(bits)+[0.]*58;v=F(f.evaluate(a,point));self.assertLessEqual(lo,v);self.assertGreaterEqual(hi,v)
        self.assertEqual(sum(x['feasible'] for x in c['blocks'][0]['pairs']),24)
    def test_serialization_roundtrip(self):
        c=result(f.cross_cancellation());self.assertEqual(json.loads(json.dumps(c,allow_nan=False)),c)
if __name__=='__main__':unittest.main()
