import itertools
import math
import random
import unittest
from oracle import MAX,feasible,valid_witness,absolute_witness,transition_witness

SUB=math.nextafter(0.0,math.inf)


def full():return [(-MAX,MAX) for _ in range(62)]


def intervals(grid):return [(a,b) for i,a in enumerate(grid) for b in grid[i:]]


def brute_transition(t,b,m,p,grid):
    return any(t[0]<=x<=t[1] and b[0]<=y<=b[1] and m[0]<=min(x,y)<=m[1] and p[0]<=max(x,y)<=p[1]
               for x,y in itertools.product(grid,repeat=2))


class Tests(unittest.TestCase):
    def test_unrestricted_box(self):
        box=full();result=feasible(box)
        self.assertTrue(result['feasible']);self.assertTrue(valid_witness(box,result['witness']))

    def test_absolute_all_extreme_grid_intervals(self):
        grid=[-MAX,-1.,-SUB,0.,SUB,1.,MAX]
        for a,r in itertools.product(intervals(grid),repeat=2):
            expected=any(a[0]<=x<=a[1] and r[0]<=abs(x)<=r[1] for x in grid)
            result=absolute_witness(a,r)
            self.assertEqual(result is not None,expected,(a,r))
            if result is not None:
                x,y=result;self.assertTrue(a[0]<=x<=a[1] and r[0]<=y<=r[1]);self.assertEqual(y,abs(x))

    def test_transition_all_three_point_intervals(self):
        grid=[-1.,0.,1.]
        for t,b,m,p in itertools.product(intervals(grid),repeat=4):
            expected=brute_transition(t,b,m,p,grid)
            result=transition_witness(t,b,m,p)
            self.assertEqual(result is not None,expected,(t,b,m,p))
            if result is not None:
                x,y,lo,hi=result
                self.assertTrue(all(a<=v<=z for v,(a,z) in zip(result,(t,b,m,p))))
                self.assertEqual(lo,min(x,y));self.assertEqual(hi,max(x,y))

    def test_negative_absolute_range(self):
        box=full();box[16]=(-MAX,-SUB)
        self.assertEqual(feasible(box)['reason'],'absolute_block')

    def test_bottom_minimum_orientation(self):
        box=full();box[12]=(2.,3.);box[13]=(-3.,-2.);box[18]=(-3.,-2.);box[19]=(2.,3.)
        result=feasible(box);self.assertTrue(valid_witness(box,result['witness']))

    def test_incompatible_order(self):
        box=full();box[18]=(2.,3.);box[19]=(-3.,-2.)
        self.assertEqual(feasible(box)['reason'],'transition_block')

    def test_signed_zero_numeric_equality(self):
        for a,b in itertools.product((-0.0,0.0),repeat=2):
            box=full()
            for i in (0,12,13,16,18,19):box[i]=(a,b)
            result=feasible(box);self.assertTrue(valid_witness(box,result['witness']))

    def test_singleton_extremes_and_subnormals(self):
        for a,t,b in itertools.product((-MAX,-SUB,-0.,0.,SUB,MAX),repeat=3):
            box=full();values={0:a,16:abs(a),12:t,13:b,18:min(t,b),19:max(t,b)}
            for i,v in values.items():box[i]=(v,v)
            result=feasible(box);self.assertTrue(valid_witness(box,result['witness']))

    def test_adjacent_endpoint_infeasibility(self):
        box=full();box[0]=(1.,1.);nextone=math.nextafter(1.,math.inf);box[16]=(nextone,nextone)
        self.assertFalse(feasible(box)['feasible'])

    def test_fixed_full_box_enumeration_oracle(self):
        grid=[-MAX,-1.,-SUB,0.,SUB,1.,MAX];rng=random.Random(824)
        choices=intervals(grid)
        for _ in range(500):
            box=[rng.choice(choices) for _ in range(62)]
            absolute=any(box[0][0]<=v<=box[0][1] and box[16][0]<=abs(v)<=box[16][1] for v in grid)
            expected=absolute and brute_transition(box[12],box[13],box[18],box[19],grid)
            result=feasible(box);self.assertEqual(result['feasible'],expected)
            if expected:self.assertTrue(valid_witness(box,result['witness']))

    def test_reject_nonfinite(self):
        for value in (float('nan'),float('inf'),float('-inf')):
            box=full();box[2]=(value,value)
            with self.assertRaises(ValueError):feasible(box)

    def test_reject_shape_type_reversal(self):
        for box in ([],full()[:-1],[(0.,)]*62,[(0,1)]*62,[(True,1.)]*62,[(1.,0.)]*62):
            with self.assertRaises(ValueError):feasible(box)


if __name__=='__main__':unittest.main(verbosity=2)
