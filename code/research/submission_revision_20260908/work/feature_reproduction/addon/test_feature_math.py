import unittest
import numpy as np
import feature_math as f
from regenerate_portable import algebra

class FeatureTests(unittest.TestCase):
    def test_literal_decimal_format(self):
        from regenerate_portable import quant
        a=np.array([.01234549,.01234551,-.123455])
        self.assertTrue(np.array_equal(quant(a,6),[float(format(v,'.6f')) for v in a]))
    def test_shapes_and_baseline(self):
        cd=np.tile(np.arange(1,9)*.002,(3,1));cl=np.zeros_like(cd)
        st=dict(t=.1,tx=.3,c=.01,cx=.4,leR=.02,teA=12.)
        d=algebra(np.array([-2.,0.,2.]),np.full(3,2e5),cd,cl,np.ones(3),np.ones(3),np.zeros(3),np.zeros(3),[st]*3)
        self.assertEqual(d['X24'].shape,(3,24));self.assertTrue(np.array_equal(d['BASE_CD'],cd.mean(axis=1)))
        self.assertTrue(np.array_equal(d['X24'][:,16],[2,0,2]))
    def test_transition_order(self):
        x=np.zeros((2,24));mat={k:np.tile(np.arange(1,6),(2,1)).astype(float) for k in f.FIELDS}
        v=f.supplement(x,mat)
        self.assertEqual(v.shape,(2,44));self.assertTrue(np.array_equal(v[:,:24],x))
        self.assertAlmostEqual(v[0,24],np.log(1/3));self.assertEqual(v[0,25],-2)
        self.assertAlmostEqual(v[0,39],np.log(5/3))
    def test_reference_dtype_safe(self):
        from pathlib import Path
        for path in (Path(__file__).parent/'data').glob('*.npz'):
            with np.load(path,allow_pickle=False) as z:
                for k in z.files:
                    self.assertNotEqual(z[k].dtype.kind,'O')
                    self.assertNotIn('meas',k.lower())
if __name__=='__main__':unittest.main()
