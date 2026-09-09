"""Exact-rational synthetic checks only. No project data, fitting or dependencies."""
from fractions import Fraction as F
import itertools
import random
import unittest


def margin(t, b, c, r=F(0)):
    return (1-r)*abs(b-t)-abs(c-t)


def row_bounds(y, b, c, eps, r=F(0)):
    if min(y, eps)<0 or not 0<=r<=1:
        raise ValueError('Nonnegative label/radius and r in [0,1] required')
    lo, hi=max(F(0),y-eps),y+eps
    points=sorted({lo,hi}|{z for z in (b,c) if lo<=z<=hi})
    values=[margin(t,b,c,r) for t in points]
    return min(values),max(values)


def box_bounds(rows, weights, eps, r=F(0)):
    if len(rows)!=len(weights) or not rows or min(weights)<0 or sum(weights)!=1:
        raise ValueError('Fixed nonnegative normalized weights required')
    bounds=[row_bounds(*row,eps,r) for row in rows]
    return tuple(sum(w*z[j] for w,z in zip(weights,bounds)) for j in (0,1))


def common_shift_bounds(rows, weights, eps, r=F(0)):
    # Invoke validation without altering the fixed weights.
    box_bounds(rows,weights,eps,r)
    knots={-eps,eps}
    for y,b,c in rows:
        knots.update(z for z in (-y,b-y,c-y) if -eps<=z<=eps)
    values=[sum(w*margin(max(F(0),y+d),b,c,r)
                for w,(y,b,c) in zip(weights,rows)) for d in knots]
    return min(values),max(values)


def sweep_bounds(rows, weights, eps, r=F(0)):
    box_bounds(rows,weights,eps,r)
    if any(min(row)<0 for row in rows):
        raise ValueError('Event formula assumes nonnegative values')
    events={}
    constant=sum(w*((1-r)*b-c) for w,(y,b,c) in zip(weights,rows))
    for w,(y,b,c) in zip(weights,rows):
        for x,jump in [(-y,r*w),(b-y,2*(1-r)*w),(c-y,-2*w)]:
            events[x]=events.get(x,F(0))+jump
    ordered=sorted(events.items())
    def evaluate(d):
        val=constant;slope=F(0);last=ordered[0][0]
        for x,jump in ordered:
            if x>d: break
            val+=slope*(x-last);last=x;slope+=jump
        return val+slope*(d-last)
    points={-eps,eps}|{x for x in events if -eps<=x<=eps}
    values=[evaluate(d) for d in points]
    if sum(events.values())!=-r:
        raise AssertionError('Terminal slope invariant')
    return min(values),max(values)


class Checks(unittest.TestCase):
    def test_event_sweep_matches_direct_knots(self):
        rng=random.Random(20260908)
        for _ in range(250):
            rows=[tuple(F(rng.randrange(15),10) for _ in range(3)) for _ in range(4)]
            weights=[F(1,10),F(2,10),F(3,10),F(4,10)]
            for eps,r in itertools.product([F(0),F(1,10),F(3)],[F(0),F(9,100),F(1)]):
                self.assertEqual(sweep_bounds(rows,weights,eps,r),common_shift_bounds(rows,weights,eps,r))

    def test_coincident_sweep_self_control(self):
        rows=[(F(0),F(0),F(0)),(F(1),F(2),F(2))]
        for eps in [F(0),F(1,100000),F(1),F(1000000)]:
            self.assertEqual(sweep_bounds(rows,[F(1,2)]*2,eps),(0,0))

    def test_exact_breakpoints_and_lipschitz(self):
        rng=random.Random(824)
        for _ in range(500):
            y,b,c,eps=[F(rng.randrange(31),10) for _ in range(4)]
            r=rng.choice([F(0),F(9,100),F(1)])
            low,high=row_bounds(y,b,c,eps,r)
            obs=margin(y,b,c,r)
            self.assertGreaterEqual(low,obs-(2-r)*eps)
            self.assertLessEqual(high,obs+(2-r)*eps)
            l,u=max(F(0),y-eps),y+eps
            for j in range(31):
                f=margin(l+(u-l)*F(j,30),b,c,r)
                self.assertLessEqual(low,f); self.assertGreaterEqual(high,f)
            self.assertLessEqual(row_bounds(y,b,c,eps+F(1,10),r)[0],low)

    def test_interior_knot_needed(self):
        y,b,c,eps,r=F(1),F(0),F(1),F(1),F(9,100)
        low,high=row_bounds(y,b,c,eps,r)
        self.assertEqual(low,F(-1));self.assertEqual(high,F(91,100))
        self.assertGreater(high,max(margin(F(0),b,c,r),margin(F(2),b,c,r)))

    def test_product_attainability(self):
        rows=[(F(1),F(0),F(1)),(F(1),F(2),F(1))]
        weights=[F(1,2)]*2;eps=F(1);r=F(9,100)
        scores=[sum(w*margin(t,b,c,r) for w,t,(_,b,c) in zip(weights,ts,rows))
                for ts in itertools.product([F(0),F(1),F(2)],repeat=2)]
        self.assertEqual(box_bounds(rows,weights,eps,r),(min(scores),max(scores)))

    def test_common_shift_is_less_adversarial(self):
        rows=[(F(1),F(0),F(1)),(F(1),F(2),F(1))];w=[F(1,2)]*2
        self.assertEqual(box_bounds(rows,w,F(1)),(F(-1),F(1)))
        self.assertEqual(common_shift_bounds(rows,w,F(1)),(F(0),F(1)))

    def test_common_shift_dense_checks(self):
        rng=random.Random(925)
        for _ in range(100):
            rows=[tuple(F(rng.randrange(21),10) for _ in range(3)) for _ in range(3)]
            w=[F(1,3)]*3;eps=F(7,10);r=F(9,100)
            lo,hi=common_shift_bounds(rows,w,eps,r)
            box=box_bounds(rows,w,eps,r)
            self.assertGreaterEqual(lo,box[0]);self.assertLessEqual(hi,box[1])
            for j in range(51):
                d=-eps+2*eps*F(j,50)
                value=sum(a*margin(max(F(0),y+d),b,c,r) for a,(y,b,c) in zip(w,rows))
                self.assertLessEqual(lo,value);self.assertGreaterEqual(hi,value)

    def test_equal_identity_not_row_mean(self):
        rows=[(F(1),F(0),F(1))]*2+[(F(0),F(0),F(1))]
        self.assertEqual(box_bounds(rows,[F(1,4),F(1,4),F(1,2)],F(0))[0],0)
        self.assertEqual(box_bounds(rows,[F(1,3)]*3,F(0))[0],F(1,3))

    def test_exact_radius_endpoint(self):
        # One row y=c=1,b=0: minimum advantage 1−2eps until eps=1.
        self.assertEqual(row_bounds(F(1),F(0),F(1),F(1,2))[0],0)
        # A 9% margin first vanishes at eps=(1-r)/(2-r)=91/191.
        self.assertEqual(row_bounds(F(1),F(0),F(1),F(91,191),F(9,100))[0],0)

    def test_own_baseline_and_invalid_contract(self):
        self.assertEqual(row_bounds(F(1),F(2),F(2),F(5)),(0,0))
        self.assertEqual(margin(F(2),F(2),F(2),F(9,100)),0)  # ratio is still 0/0
        with self.assertRaises(ValueError): row_bounds(F(-1),F(1),F(1),F(1))
        with self.assertRaises(ValueError): box_bounds([(F(1),)*3],[F(2)],F(1))


if __name__=='__main__':
    unittest.main(verbosity=2)
