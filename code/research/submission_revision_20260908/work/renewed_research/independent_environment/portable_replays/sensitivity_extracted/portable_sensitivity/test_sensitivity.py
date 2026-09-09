"""Seeded synthetic checks, including independent rational knot-enumeration oracles."""
from fractions import Fraction as F
import itertools
import unittest

import numpy as np
from sensitivity import RowBox, SharedShifts, ShiftCurve, first_zero


def f(b, c, t, r):
    return (1-r)*abs(b-t)-abs(c-t)


def exact_row(b, c, y, epsilon, r):
    lo, hi = max(F(0), y-epsilon), y+epsilon
    values = [f(b, c, t, r) for t in {lo, hi, b, c} if lo <= t <= hi]
    return min(values), max(values)


def exact_shared(b, c, y, w, epsilon, r):
    knots = {-epsilon, epsilon}
    for bi, ci, yi in zip(b, c, y):
        knots.update(t for t in [-yi, bi-yi, ci-yi] if -epsilon <= t <= epsilon)
    values = [sum(wi*f(bi, ci, max(F(0), yi+d), r) for bi,ci,yi,wi in zip(b,c,y,w)) for d in knots]
    return min(values), max(values)


class TestSensitivity(unittest.TestCase):
    def near(self, actual, expected):
        np.testing.assert_allclose(actual, [float(x) for x in expected], rtol=0, atol=1e-13)

    def test_row_fraction_oracle(self):
        rng = np.random.default_rng(8751)
        for _ in range(300):
            b,c,y,eps = [F(int(x),16) for x in rng.integers(0,33,4)]
            for r in [F(0), F(9,100), F(1)]:
                box = RowBox([float(b)],[float(c)],[float(y)],[1.],float(r))
                self.near(box.bounds(float(eps)), exact_row(b,c,y,eps,r))

    def test_event_sweep_fraction_oracle(self):
        rng = np.random.default_rng(9913)
        for _ in range(150):
            b,c,y = [[F(int(x),16) for x in a] for a in rng.integers(0,33,(3,4))]
            w = [F(1,10), F(2,10), F(3,10), F(4,10)]
            for r in [F(0), F(9,100), F(1)]:
                curve = ShiftCurve(*[np.array(a,dtype=float) for a in [b,c,y,w]],float(r))
                for eps in [F(0), F(1,4), F(1), F(4)]:
                    self.near(curve.bounds(float(eps)), exact_shared(b,c,y,w,eps,r))
                self.assertAlmostEqual(float(curve.slopes[-1]),-float(r),places=13)

    def test_block_mass_and_nesting(self):
        b,c,y,w = [np.array(a) for a in [[.2,.7,.1,.5],[.4,.3,.2,.6],[.3,.4,.7,.1],[.1,.2,.3,.4]]]
        for r in [0,.09,1]:
            box = RowBox(b,c,y,w,r)
            shared = SharedShifts(b,c,y,w,r,np.array(['a','a','b','b']))
            last = None
            for eps in [0,.01,.2,1,4]:
                bounds = shared.bounds(eps)
                direct = np.sum([ShiftCurve(b[ix],c[ix],y[ix],w[ix],r).bounds(eps)
                                 for ix in [np.array([0,1]),np.array([2,3])]],axis=0)
                self.near(bounds,direct)
                bb = box.bounds(eps)
                self.assertGreaterEqual(bounds[0]+1e-13,bb[0])
                self.assertLessEqual(bounds[1]-1e-13,bb[1])
                if last is not None:
                    self.assertLessEqual(bounds[0],last[0]+1e-13)
                    self.assertGreaterEqual(bounds[1],last[1]-1e-13)
                last = bounds

    def test_lipschitz_and_attainable_product(self):
        b,c,y,w = [np.array(a) for a in [[.1,.4],[.2,.5],[.3,.7],[.25,.75]]]
        for r in [0,.09,1]:
            box=RowBox(b,c,y,w,r)
            for eps in [0,.03,.2,2]:
                lo,hi=box.bounds(eps)
                self.assertGreaterEqual(lo+1e-13,box.observed-(2-r)*eps)
                self.assertLessEqual(hi-1e-13,box.observed+(2-r)*eps)
                choices=[set([max(0,yi-eps),yi+eps]+[v for v in [bi,ci] if max(0,yi-eps)<=v<=yi+eps])
                         for bi,ci,yi in zip(b,c,y)]
                values=[sum(wi*f(bi,ci,ti,r) for bi,ci,ti,wi in zip(b,c,t,w)) for t in itertools.product(*choices)]
                self.near((lo,hi),(min(values),max(values)))

    def test_exact_self_controls(self):
        for r in [0,.09]:
            b=np.array([0.,.004,.2,.3]);y=np.array([0.,.007,.8,.9]);w=np.ones(4)/4
            for model in [RowBox(b,b,y,w,r),SharedShifts(b,b,y,w,r,np.array(['a','b','a','b']))]:
                for eps in [0,.0001,.2,4]:
                    lo,hi=model.bounds(eps)
                    if r==0:self.assertEqual((lo,hi),(0.,0.))
                    else:self.assertLessEqual(hi,1e-13)

    def test_first_zero_radius(self):
        # For b=3,c=1,y=0 and r=0, margin first reaches zero at target=2.
        for model in [RowBox([3],[1],[0],[1],0),SharedShifts([3],[1],[0],[1],0,['a'])]:
            result=first_zero(model,0,limit=4)
            self.assertEqual(result['radius_status'],'finite_bracket')
            self.assertLess(result['radius_lower_CD'],2)
            self.assertGreaterEqual(result['radius_upper_CD'],2)
            self.assertLessEqual(result['radius_upper_CD']-result['radius_lower_CD'],1e-12)
            censored=first_zero(model,0,limit=1)
            self.assertEqual(censored['radius_status'],'right_censored')
        self.assertEqual(first_zero(RowBox([1],[1],[0],[1],0),0)['radius_status'],'observed_zero')
        self.assertEqual(first_zero(RowBox([1],[3],[0],[1],0),0)['radius_status'],'observed_negative')

    def test_baseline_denominator(self):
        box=RowBox([1,3],[2,2],[0,4],[.2,.8],0)
        self.assertAlmostEqual(box.minimum_baseline_mae(.5),.5)
        self.assertEqual(box.minimum_baseline_mae(1),0)

    def test_weight_definition(self):
        groups=np.array(['a','a','a','b'])
        _,inv,n=np.unique(groups,return_inverse=True,return_counts=True)
        w=1/(len(n)*n[inv])
        self.near([w[groups==g].sum() for g in ['a','b']],[.5,.5])

    def test_reject_invalid(self):
        for values in [([-1],[1],[1],[1]),([1],[1],[float('nan')],[1]),([],[],[],[])]:
            with self.assertRaises(ValueError):RowBox(*values,0)
        with self.assertRaises(ValueError):RowBox([1],[1],[1],[1],9)
        with self.assertRaises(ValueError):RowBox([1],[1],[1],[1],0).bounds(-1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
