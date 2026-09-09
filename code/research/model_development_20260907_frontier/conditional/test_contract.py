"""Numerical routing/convexity tests independent of benchmark outcomes."""
import unittest
import numpy as np
from conditional_stack import basis, predict, COMPONENTS, VARIANTS


class ContractTests(unittest.TestCase):
    def test_basis_bounds_and_alpha_reflection(self):
        re=np.array([1e3,1e4,1e5,1e6,1e7])
        alpha=np.array([-20.,-12.,0.,6.,25.])
        for variant in VARIANTS:
            a=basis(variant,re,alpha,[4.,6.])
            np.testing.assert_array_equal(a,basis(variant,re,-alpha,[4.,6.]))
            self.assertTrue((a>=0).all())
            np.testing.assert_allclose(a.sum(axis=1),1.,atol=1e-15)

    def test_constant_corners_equal_global_and_fallback(self):
        rng=np.random.default_rng(20260907)
        matrix=rng.uniform(.005,.02,(17,len(COMPONENTS)))
        center=rng.dirichlet(np.ones(len(COMPONENTS)))
        re=np.geomspace(1e4,1e7,17);alpha=np.linspace(-20,20,17)
        base=matrix[:,0]
        for variant in VARIANTS:
            corners=4 if variant=="re_alpha4" else 2
            model={"variant":variant,"corner_weights":np.tile(center,(corners,1)),"re_endpoints":[4.,6.]}
            got=predict(model,matrix,re,alpha)
            np.testing.assert_allclose(got,matrix@center,atol=1e-17)
            self.assertTrue((got>=matrix.min(axis=1)-1e-15).all())
            self.assertTrue((got<=matrix.max(axis=1)+1e-15).all())
            np.testing.assert_array_equal(predict(model,matrix,re,alpha,base,np.zeros(17,dtype=bool)),base)


if __name__=="__main__":unittest.main()
