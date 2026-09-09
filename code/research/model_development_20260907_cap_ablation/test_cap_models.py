"""Synthetic tests only: no project data or external outcomes."""
import unittest
from unittest.mock import patch
import numpy as np
import cap_models as m


class CapTests(unittest.TestCase):
    def test_targets_and_weights(self):
        b = np.array([1., 2., 3.]); y = b*np.array([.25, 1., 4.])
        g = np.array(['a','a','b']); s=np.array(['x','x','y'])
        v=(1+m.balanced_weights(g,s))/2
        for family, expected in [('capped',[-.5,0,1]),('upper_free',[-.5,0,3]),
                                  ('positive_log',np.log([.25,1,4]))]:
            t,w=m.training_arrays(family,b,y,g,s)
            np.testing.assert_array_equal(t,expected)
            ew=v*(y if family=='positive_log' else b);ew/=ew.mean()
            np.testing.assert_array_equal(w,ew)

    def test_prediction_bounds(self):
        b=np.ones(3);r=np.array([-4.,0,4.])
        np.testing.assert_array_equal(m.transform('capped',r,b),[.5,1,2])
        np.testing.assert_array_equal(m.transform('upper_free',r,b),[.5,1,5])
        np.testing.assert_array_equal(m.transform('positive_log',r,b),np.exp(r))

    def test_half_cd_space(self):
        b=np.array([1.]);c=m.transform('positive_log',np.log([4.]),b)
        np.testing.assert_array_equal(m.half(c,b),[2.5])

    def test_exp_overflow_and_underflow(self):
        for raw in [1000.,-1000.]:
            with self.assertRaises(ValueError):m.transform('positive_log',[raw],[1.])
        with self.assertRaises(ValueError):m.transform('upper_free',[1e308],[1e308])

    def test_invalid_arrays(self):
        for base in [[0.],[-1.],[np.nan],[np.inf]]:
            with self.assertRaises(ValueError):m.transform('upper_free',[1.],base)
        for y in [[0.],[-1.],[np.nan]]:
            with self.assertRaises(ValueError):m.training_arrays('positive_log',[1.],y,['g'],['s'])
        with self.assertRaises(ValueError):m.transform('invalid',[0.],[1.])
        with self.assertRaises(ValueError):m.transform('capped',[0.,1.],[1.])

    def test_feature_only_prediction_and_row_order(self):
        class Fake:
            def predict(self,x):return x[:,0]
        d={'X62':np.zeros((3,62)),'BASE_CD':np.array([.01,.02,.03])}
        d['X62'][:,0]=[0.,1.,3.];model={'family':'upper_free','model':Fake()}
        p=m.predict(model,d,np.arange(3));order=np.array([2,0,1])
        np.testing.assert_array_equal(m.predict(model,d,order),p[order])
        np.testing.assert_array_equal(m.predict(model,d,np.array([],int)),[])

    def test_fit_contract_no_real_fitting(self):
        d={'X62':np.zeros((3,62)),'BASE_CD':np.array([1.,2.,3.]),
           'MEAS_CD':np.array([.25,2.,12.]),'group':np.array(['a','a','b']),
           'source':np.array(['s','s','t'])}
        for family in m.FAMILIES:
            with patch.object(m,'HistGradientBoostingRegressor') as cls:
                result=m.fit(family,d,np.array([0,2]))
                cls.assert_called_once_with(**m.PARAMETERS)
                args,kw=cls.return_value.fit.call_args
                t,w=m.training_arrays(family,d['BASE_CD'][[0,2]],d['MEAS_CD'][[0,2]],d['group'][[0,2]],d['source'][[0,2]])
                np.testing.assert_array_equal(args[1],t);np.testing.assert_array_equal(kw['sample_weight'],w)
                self.assertEqual(result['family'],family)


if __name__=='__main__':unittest.main()
