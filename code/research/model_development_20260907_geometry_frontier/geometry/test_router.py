"""Synthetic router contracts only; never accesses project observations."""
import unittest
import numpy as np
import pandas as pd
import router

class RouterTests(unittest.TestCase):
    def test_label_free_permutation_and_convexity(self):
        rng=np.random.default_rng(824); k=rng.normal(size=(32,18));r=np.linspace(1e5,5e5,32);a=np.linspace(-10,10,32)
        for variant in router.VARIANTS:
            m=router.build_router(variant,k,r,a); rev=router.build_router(variant,k[::-1],r[::-1],a[::-1])
            self.assertEqual(m,rev)
            phi=router.basis(m,k,r,a);np.testing.assert_allclose(phi.sum(axis=1),1)
            n=len(m['prototypes']);m.update(corner_weights=np.tile([.25,.75],(n,1)).tolist(),components=['a','b'])
            base=np.ones(32)*.01;c=np.column_stack([base,base*2]);g=np.arange(32)%2==0
            p=router.predict(m,c,k,r,a,base,g)
            np.testing.assert_allclose(p[g],.0175);np.testing.assert_array_equal(p[~g],base[~g])
    def test_lp_known_solution(self):
        rng=np.random.default_rng(2);k=rng.normal(size=(24,18));r=np.ones(24)*1e5;a=np.zeros(24)
        frame=pd.DataFrame({'a':np.ones(24)*.01,'b':np.ones(24)*.02,'measured_CD':np.ones(24)*.015,
                            'mean8_CD':np.ones(24)*.01,'xlarge_CD':np.ones(24)*.02})
        panels={'group_pooled':(np.arange(24),np.ones(24)/24)}
        m=router.build_router('geometry4',k,r,a)
        m=router.fit_variant(frame,panels,np.array([.5,.5]),m,k,r,a,['a','b'])
        p=router.predict(m,frame[['a','b']].to_numpy(),k,r,a,frame.mean8_CD.to_numpy(),np.ones(24,bool))
        np.testing.assert_allclose(p,.015,atol=1e-10)
    def test_degenerate_fails(self):
        with self.assertRaises(ValueError):router.build_router('geometry4',np.zeros((10,18)),np.ones(10),np.zeros(10))

if __name__=='__main__':unittest.main()
