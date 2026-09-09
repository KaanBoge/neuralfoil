"""Synthetic-only tests; no project data or labels are opened."""
import copy
import json
import unittest
import numpy as np
from risk_policy import fit, predict


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.b = np.full(24,.01)
        self.c = np.full(24,.02)
        self.a = np.repeat(self.b[:,None],8,axis=1)
        self.w = np.ones(24)

    def train(self, y, penalty=1, **kw):
        return fit(self.b,self.c,y,self.a,self.w,penalty,**kw)

    def test_known_optimum_and_roundtrip(self):
        for target, expected in [(.01,0),(.0125,.25),(.02,1)]:
            m = self.train(np.full(24,target))
            p,s = predict(json.loads(json.dumps(m,allow_nan=False)),self.b,self.c,self.a,np.ones(24,bool))
            np.testing.assert_allclose(s,expected,atol=1e-9)
            np.testing.assert_allclose(p,target,atol=1e-11)
            self.assertEqual(m['diagnostics']['solver_status'],[0,0])
            self.assertLess(m['diagnostics']['maximum_constraint_violation'],1e-8)

    def test_direct_loss_and_fallback(self):
        rng=np.random.default_rng(824)
        b=rng.uniform(.005,.025,80); c=b*rng.uniform(.5,2,80)
        a=b[:,None]*rng.uniform(.8,1.2,(80,8)); y=b*rng.uniform(.6,1.7,80)
        w=rng.uniform(.1,3,80)
        for lam in [0,1]:
            m=fit(b,c,y,a,w,lam)
            p,s=predict(m,b,c,a,np.ones(80,bool))
            e=np.abs(p-y)*1e4; h=np.maximum(e-np.abs((b+c)/2-y)*1e4,0)
            self.assertAlmostEqual(np.average(e+lam*h,weights=w),m['diagnostics']['actual_objective_counts'],places=9)
            self.assertTrue(np.all((s>=0)&(s<=1)))
            self.assertTrue(np.all(p>=np.minimum(b,c)-1e-15))
            pf,sf=predict(m,b,c,a,np.zeros(80,bool))
            np.testing.assert_array_equal(pf,b); np.testing.assert_array_equal(sf,0)

    def test_zero_delta_prefers_half_and_reference(self):
        m=fit(self.b,self.b,self.b,self.a,self.w,1)
        np.testing.assert_allclose(m['corners'],.5,atol=1e-10)
        ref=(self.b[:3],self.c[:3],self.a[:3])
        m=self.train(self.b,feature_reference=ref)
        self.assertEqual(m['diagnostics']['feature_reference_rows'],3)
        self.assertEqual(m['endpoints'],[[0.,1.],[0.,1.]])

    def test_bad_inputs_and_artifacts_even_false_gate(self):
        m=self.train(self.b)
        for bad in [float('nan'),float('inf'),-float('inf'),'0.5',-.1,1.1]:
            corrupt=copy.deepcopy(m); corrupt['corners'][0]=bad
            with self.assertRaises(ValueError): predict(corrupt,self.b,self.c,self.a,np.zeros(24,bool))
        for gate in [np.zeros(24,int),np.zeros(23,bool)]:
            with self.assertRaises(ValueError): predict(m,self.b,self.c,self.a,gate)
        for bad in [np.nan,np.inf,-1,0]:
            w=self.w.copy(); w[0]=bad
            with self.assertRaises(ValueError): fit(self.b,self.c,self.b,self.a,w,1)
        for penalty in [np.nan,np.inf,-1,'1']:
            with self.assertRaises(ValueError): self.train(self.b,penalty)
        bad_y=self.b.copy(); bad_y[0]=np.nan
        with self.assertRaises(ValueError): self.train(bad_y)
        with self.assertRaises(ValueError): predict(m,self.b,self.c,self.a[:,:7],np.zeros(24,bool))
        corrupt=copy.deepcopy(m); corrupt['endpoints'][1][0]=-1
        with self.assertRaises(ValueError): predict(corrupt,self.b,self.c,self.a,np.zeros(24,bool))


if __name__=='__main__':
    unittest.main()
