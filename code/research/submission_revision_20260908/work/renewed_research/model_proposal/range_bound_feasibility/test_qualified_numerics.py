"""Synthetic-only Stage0 tests; no project outcome or calibration arrays."""
import unittest
from fractions import Fraction as F
import math
import numpy as np
import qualified_numerics as q
import certify_stage0 as cert


class Numerics(unittest.TestCase):
    def test_directed(self):
        for x in [F(1,3), -F(1,3), F(1,2**1100), -F(1,2**1100), F(0)]:
            self.assertLessEqual(q.rat(q.directed(x, False)), x)
            self.assertGreaterEqual(q.rat(q.directed(x, True)), x)

    def test_sequential_enclosure(self):
        stages = [[.1, -.2], [1e-20, -.3], [1e-4, -.02]]
        r = q.sequential_range(.05, stages)
        import itertools
        for leaves in itertools.product(*stages):
            v = .05
            for leaf in leaves:
                v += leaf
            self.assertTrue(r['lower'] <= q.rat(v) <= r['upper'])

    def test_structural_bound_and_generic(self):
        self.assertLess(q.structural_bound(F(-7,10), F(3,4)), q.GENERIC_BOUND)
        self.assertEqual(q.structural_bound(-2, 2), q.GENERIC_BOUND)

    def test_guard_and_empty(self):
        b = np.array([np.nextafter(0.,1.), 2.**-501, 2.**-500, 1., 2.**500, 2.**501, np.finfo(float).max])
        c,h,g = q.guarded_core(b, np.ones(len(b)), np.ones(len(b), bool))
        np.testing.assert_array_equal(g, [False,False,True,True,True,False,False])
        np.testing.assert_array_equal(c[~g], b[~g])
        np.testing.assert_array_equal(h[~g], b[~g])
        self.assertEqual(len(q.guarded_core([], [], np.array([],bool))[0]), 0)

    def test_physical_gate(self):
        c,h,g = q.guarded_core([1.], [.8], [False])
        self.assertEqual((c[0],h[0],g[0]), (1.,1.,False))

    def test_invalid_inputs(self):
        for b,r,g in [([0.],[0.],[True]), ([1.],[math.nan],[True]),
                      ([1.],[0.],[1]), ([[1.]],[[0.]],[[True]])]:
            with self.assertRaises(ValueError): q.guarded_core(b,r,g)

    def test_synthetic_core_and_endpoint_properties(self):
        rng = np.random.default_rng(830)
        b = np.ldexp(rng.uniform(1.,2.,3000), rng.integers(-500,500,3000))
        b = np.r_[b, 2.**-500, 2.**500]
        r = np.r_[rng.uniform(-.7,.76,3000), -.5, .76]
        c,h,g = q.guarded_core(b,r,np.ones(len(b),bool))
        bound = q.structural_bound(F(-7,10), q.rat(.76))
        for bb,rr,cc,hh in zip(b,r,c,h):
            br, cr, hr = map(q.rat,(bb,cc,hh))
            self.assertLessEqual(abs(cr/br-1-q.clipq(q.rat(rr))), q.CORE_ERROR)
            self.assertLessEqual(abs(hr-(br+(cr-br)/2))/br, F(3,2)*q.U)
            self.assertLessEqual(abs(cr-hr)/br, bound)
            for y in (0., bb, -np.finfo(float).max, np.finfo(float).max):
                self.assertLessEqual(q.exact_endpoint_loss(bb,cc,hh,y), bound)

    def test_exact_group_means(self):
        self.assertEqual(q.exact_group_means([F(1,4),0,F(1,3)],['a','a','b'],F(1,2)), {'a':F(1,8),'b':F(1,3)})
        for losses,ids in [([F(3,4)],['a']),([0],['']),([0],[b'a'])]:
            with self.assertRaises(ValueError): q.exact_group_means(losses,ids,F(1,2))

    def test_log_and_sqrt(self):
        lo,hi = q.log20_enclosure()
        # Independent Decimal comparison is a diagnostic, not the rigorous proof.
        from decimal import Decimal, localcontext
        with localcontext() as ctx:
            ctx.prec = 180
            truth = Decimal(20).ln()
            self.assertLess(Decimal(lo.numerator)/Decimal(lo.denominator), truth)
            self.assertGreater(Decimal(hi.numerator)/Decimal(hi.denominator), truth)
        for x in [F(0),F(1),F(2),F(1,10**200),F(123,77)]:
            s=q.sqrt_upper(x)
            self.assertGreaterEqual(s*s,x)

    def test_synthetic_confidence(self):
        for bound in [F(0), F(1,4), q.GENERIC_BOUND]:
            for values in [[],[F(0)]*20,[bound/3]*20]:
                z=q.synthetic_confidence(values,bound)
                self.assertLessEqual(q.rat(z['t'])*z['upper'], q.TAU)
        with self.assertRaises(ValueError): q.synthetic_confidence([1],F(1,2))

    def test_inward(self):
        rng=np.random.default_rng(831)
        for _ in range(3000):
            b=math.ldexp(float(rng.uniform(1,2)),int(rng.integers(-500,500)))
            c,h,g=q.guarded_core([b],[float(rng.uniform(-1,2))],[True])
            t=float(rng.uniform())
            p=q.inward_predict(h[0],c[0],t)
            if c[0] != h[0]:
                f=(q.rat(p)-q.rat(h[0]))/(q.rat(c[0])-q.rat(h[0]))
                self.assertTrue(0 <= f <= q.rat(t))
        self.assertEqual(q.inward_predict(1.,1.,.5),1.)

    def test_io_whitelist_before_access(self):
        from pathlib import Path
        for name in ['arrays/calibration_00.npz','../tree_01_capped.npz','roles.npz']:
            with self.assertRaises(ValueError): cert.load_tree(Path('/nonexistent'),name,{}, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
