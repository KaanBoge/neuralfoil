import copy
import unittest
import numpy as np
import incremental_harm as m


class Tests(unittest.TestCase):
    def setUp(self):
        self.b = np.ones(6)
        self.c = np.array([2., .5, 1.2, 1., 1.8, .8])
        self.y = np.array([1., 2., .1, 1., 1.2, 2.])
        self.g = np.ones(6, bool)
        self.ids = np.array(['a','a','b','b','c','c'])
        self.model = m.calibrate(self.b,self.c,self.y,self.ids,self.g)

    def test_exact_formula(self):
        _,loss,_,_ = m.group_losses(self.b,self.c,self.y,self.ids,self.g)
        u = min(.5,loss.mean()+.5*np.sqrt(np.log(20)/6))
        self.assertEqual(self.model['upper_bound'],u)
        self.assertEqual(self.model['t'],.01/u)

    def test_group_not_row_mean(self):
        b=np.ones(4);c=np.array([2.,1.,1.,1.]);ids=np.array(['a','b','b','b'])
        z=m.calibrate(b,c,b,ids,np.ones(4,bool))
        self.assertEqual(z['endpoint_mean'],.25)

    def test_convex_domination(self):
        rng=np.random.default_rng(831);b=np.exp(rng.normal(size=10000))
        c=b*rng.uniform(.5,2,len(b));y=rng.normal(size=len(b))*100
        h=b+.5*(c-b);end=np.maximum(abs(c-y)-abs(h-y),0)/b
        for t in [0,.02,.05,.5,1]:
            z=np.maximum(abs(h+t*(c-h)-y)-abs(h-y),0)/b
            self.assertTrue(np.all(z<=t*end+1e-11))

    def test_gate_fallback(self):
        g=np.array([0,1,0,1,0,1],bool)
        z=m.predict(self.model,self.b,self.c,g)
        np.testing.assert_array_equal(z['prediction'][~g],self.b[~g])
        self.assertTrue((z['applied_strength'][~g]==0).all())

    def test_empty_inference(self):
        z=m.predict(self.model,[],[],np.array([],bool))
        self.assertEqual(z['prediction'].shape,(0,))

    def test_empty_calibration_fallback(self):
        z=m.calibrate([],[],[],np.array([],str),np.array([],bool))
        self.assertEqual(z['t'],.02)
        self.assertEqual(z['status'],'deterministic_bound_only')

    def test_permutation(self):
        j=np.array([4,2,0,5,1,3]); p=m.predict(self.model,self.b,self.c,self.g)['prediction']
        np.testing.assert_array_equal(m.predict(self.model,self.b[j],self.c[j],self.g[j])['prediction'],p[j])

    def test_chunking(self):
        p=m.predict(self.model,self.b,self.c,self.g)['prediction']
        q=np.concatenate([m.predict(self.model,self.b[j:j+2],self.c[j:j+2],self.g[j:j+2])['prediction'] for j in range(0,6,2)])
        np.testing.assert_array_equal(p,q)

    def test_no_input_mutation(self):
        before=[a.copy() for a in [self.b,self.c,self.g]];model=copy.deepcopy(self.model)
        m.predict(self.model,self.b,self.c,self.g)
        self.assertEqual(model,self.model)
        for a,b in zip(before,[self.b,self.c,self.g]):np.testing.assert_array_equal(a,b)

    def test_invalid_gate(self):
        with self.assertRaises(ValueError):m.predict(self.model,self.b,self.c,self.g.astype(int))

    def test_invalid_domain(self):
        for bad in [np.full(6,np.nan),np.zeros(6),np.full(6,2.00000000001),np.full(6,.49999999999)]:
            with self.assertRaises(ValueError):m.predict(self.model,self.b,bad,self.g)

    def test_invalid_shapes(self):
        with self.assertRaises(ValueError):m.predict(self.model,self.b[:,None],self.c,self.g)

    def test_empty_byte_identity(self):
        with self.assertRaises(ValueError):m.calibrate([1],[1],[1],np.array([b'']),np.array([True]))

    def test_target_validation(self):
        with self.assertRaises(ValueError):m.calibrate(self.b,self.c,np.full(6,np.nan),self.ids,self.g)

    def test_invalid_artifact(self):
        for field,value in [('t',.9),('B',.51),('epsilon',.02),('upper_bound',float('nan'))]:
            z=copy.deepcopy(self.model);z[field]=value
            with self.assertRaises(ValueError):m.predict(z,self.b,self.c,self.g)


if __name__=='__main__':unittest.main(verbosity=2)
