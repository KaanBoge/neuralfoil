"""Synthetic role/serialization tests; no estimator or LP fitting."""
import unittest
import numpy as np
import replay as r


class ReplayTests(unittest.TestCase):
    def test_group_fold_identity_partition(self):
        groups=np.array(['a','a','b','c','c','d','e','f'])
        masks=r.group_folds(groups,3,20260907)
        np.testing.assert_array_equal(np.sum(masks,axis=0),np.ones(len(groups)))
        for m in masks: self.assertFalse(set(groups[m])&set(groups[~m]))

    def test_source_roles_purge_shared_identity(self):
        d={'BASE_CD':np.ones(6),'group':np.array(['shared','shared','b','c','d','e']),
           'source':np.array(['vol1','stec8','stec8','vol2','vol2','stec8'])}
        tr,te=r.roles(d,'strict_source_vol1')
        np.testing.assert_array_equal(te,[0]);np.testing.assert_array_equal(tr,[2,3,4,5])
        self.assertFalse(set(d['group'][tr])&set(d['group'][te]))

    def test_augmented_policy_isolates_excluded_labels(self):
        d={'BASE_CD':np.ones(5),'MEAS_CD':np.arange(5,dtype=float)+1,
           'all_model_CD':np.ones((5,8)),'group':np.array(['a','b','c','d','e']),
           'source':np.array(['a','a','b','b','a'])}
        gi=np.array([0,1,2]);ti=np.array([0,2]);gc=np.ones(3);tc=np.ones(2)
        a=r.policy_inputs(d,gi,gc,ti,tc)
        d['MEAS_CD'][3:]=np.nan;b=r.policy_inputs(d,gi,gc,ti,tc)
        for key in ['base','core','y','weights','all_model_CD']: np.testing.assert_array_equal(a[key],b[key])
        self.assertAlmostEqual(a['weights'][:3].sum(),.5);self.assertAlmostEqual(a['weights'][3:].sum(),.5)
        self.assertEqual(len(a['feature_reference'][0]),3)

    def test_csv_boundary_is_explicit(self):
        values=np.array([.010000000000000023,.03141592653589793,.004567890123456789])
        serialized=r.csv_roundtrip(values)
        self.assertTrue(np.isfinite(serialized).all())
        self.assertEqual(serialized.shape,values.shape)
        self.assertTrue(np.any(serialized!=values))
        np.testing.assert_array_equal(r.csv_roundtrip(values),serialized)


if __name__=='__main__': unittest.main()
