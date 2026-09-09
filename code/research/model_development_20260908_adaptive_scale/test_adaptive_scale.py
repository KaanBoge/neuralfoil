"""Synthetic, outcome-free checks; running this file does not train any model."""
import copy
import unittest
import numpy as np
import adaptive_scale as a


class Tests(unittest.TestCase):
    def model(self, q=.2):
        m = a.calibrate(np.ones(19), np.ones(19), np.ones(19),
                        np.ones(19) + q, np.array([str(i) for i in range(19)]))
        m['q'] = q
        return m

    def test_rank(self):
        self.assertEqual([a.rank(n) for n in [0, 8, 9, 12, 17, 19, 20, 24]], [1, 9, 9, 12, 17, 18, 19, 23])

    def test_targets_weights(self):
        b = np.array([1., 2., 3., 4.]); y = np.array([1., 2.2, 3.6, 5.2])
        g = np.array(['a','a','b','c']); s=np.array(['s','s','s','t'])
        t,w=a.training_arrays(y,b,b,g,s)
        np.testing.assert_allclose(t,np.log([1e-6,.1,.2,.3]),atol=1e-14)
        np.testing.assert_allclose(w, [.75,.75,1.,1.5])
        _,w2=a.training_arrays(y*2,b,b,g,s); np.testing.assert_array_equal(w,w2)

    def test_group_max(self):
        g=np.repeat(np.array([str(i) for i in range(10)]),2)
        c=np.ones(20); s=np.ones(20)*2; y=c+np.arange(20)
        m=a.calibrate(c,c,s,y,g)
        np.testing.assert_array_equal(m['group_scores'],np.arange(1,20,2)/2)
        self.assertEqual(m['q'],9.5)

    def test_tied_scores(self):
        m=a.calibrate(np.ones(10),np.ones(10),np.ones(10),np.ones(10)*2,np.array([str(i) for i in range(10)]))
        self.assertEqual(m['q'],1.)

    def test_empty_byte_ids_rejected(self):
        with self.assertRaises(ValueError):
            a.calibrate([1.],[1.],[1.],[1.],np.array([b'']))
        with self.assertRaises(ValueError):
            a.training_arrays([1.],[1.],[1.],np.array([b'a']),np.array([b'']))

    def test_small_unbounded(self):
        m=a.calibrate(np.ones(2),np.ones(2),np.ones(2),np.ones(2),np.array(['a','b']))
        p=a.project(m,np.ones(2),np.ones(2),np.ones(2),np.array([.1,9.]),np.ones(2,bool))
        np.testing.assert_array_equal(p['prediction'],[.1,9.]); self.assertTrue(np.isinf(p['upper']).all())

    def test_projection_and_fallback(self):
        c=np.ones(4); baseline=np.array([.1,1,2,4.]); gate=np.array([True,True,True,False])
        p=a.project(self.model(),c,c,c,baseline,gate)
        np.testing.assert_array_equal(p['prediction'],[.8,1,1.2,4.])
        self.assertTrue(np.isneginf(p['lower'][-1]))

    def test_nonharm(self):
        rng=np.random.default_rng(14); c=np.ones(500); s=rng.uniform(.1,2,500); b=c; baseline=rng.uniform(.01,3,500)
        p=a.project(self.model(),c,b,s,baseline,np.ones(500,bool))
        y=p['lower']+(p['upper']-p['lower'])*rng.random(500)
        self.assertTrue(np.all(np.abs(p['prediction']-y)<=np.abs(baseline-y)+1e-15))

    def test_scale_invariance(self):
        c=np.ones(19); s=np.linspace(.2,2,19); y=c+np.arange(19)/30; g=np.array([str(i) for i in range(19)])
        m=a.calibrate(c,c,s,y,g); m2=a.calibrate(c,c,s*7,y,g)
        p=a.project(m,c,c,s,c*2,np.ones(19,bool)); p2=a.project(m2,c,c,s*7,c*2,np.ones(19,bool))
        np.testing.assert_allclose(p['prediction'],p2['prediction'],atol=1e-15,rtol=0)
        np.testing.assert_allclose(p['upper'],p2['upper'],atol=1e-15,rtol=0)

    def test_order_batch_empty(self):
        m=self.model(); c=np.ones(4); s=np.arange(1.,5); b=np.array([.1,1,2,3]); g=np.array([True,False,True,True])
        p=a.project(m,c,c,s,b,g); order=np.array([3,1,0,2]); p2=a.project(m,c[order],c[order],s[order],b[order],g[order])
        np.testing.assert_array_equal(p2['prediction'],p['prediction'][order])
        for i in range(4): np.testing.assert_array_equal(a.project(m,c[i:i+1],c[i:i+1],s[i:i+1],b[i:i+1],g[i:i+1])['prediction'],p['prediction'][i:i+1])
        self.assertEqual(len(a.project(m,[],[],[],[],np.array([],bool))['prediction']),0)

    def test_invalid_numeric(self):
        for bad in [[0.],[-1.],[np.nan],[np.inf],['1'],[True],[[1.]]]:
            with self.assertRaises(ValueError): a.scale_cd([1.],bad)
        for raw in [[1000.],[-1000.]]:
            with self.assertRaises(ValueError): a.positive_exp(raw)
        with self.assertRaises(ValueError): a.scale_cd([1e308],[1e308])
        with self.assertRaises(ValueError): a.project(self.model(),[1],[1],[1],[1],[1])
        with self.assertRaises(ValueError): a.project(self.model(1e308),[1],[2],[2],[1],np.array([True]))

    def test_metadata(self):
        for key,val in [('schema','old'),('rank',9),('q',-1),('unbounded',True),('scale_CD','mean8')]:
            m=copy.deepcopy(self.model());m[key]=val
            with self.assertRaises(ValueError):a.project(m,[1],[1],[1],[1],np.array([True]))

    def test_feature_only_predict(self):
        class Constant:
            def predict(self,x):return np.zeros(len(x))
        m={'schema':a.SCHEMA,'feature_key':'X62','model':Constant()}
        np.testing.assert_array_equal(a.predict(m,np.zeros((2,62))),[1,1])
        with self.assertRaises(ValueError):a.predict(m,np.zeros((2,61)))
        self.assertEqual(len(a.predict(m,np.zeros((0,62)))),0)


if __name__=='__main__':unittest.main()
