import unittest
import numpy as np
import robust_models as r


class RobustTests(unittest.TestCase):
    def test_reflection_involution(self):
        x = r.v2.load_data()['X24']
        np.testing.assert_array_equal(x, r.reflect(r.reflect(x)))
        np.testing.assert_allclose(r.invariant(x), r.invariant(r.reflect(x)), rtol=0, atol=0)

    def test_models_and_label_isolation(self):
        d = r.v2.load_data()
        te = r.v2.old.group_folds(d['group'], 5, 20260906)[0]
        tr, test = np.flatnonzero(~te), np.flatnonzero(te)
        for family in r.FAMILIES:
            model = r.fit(family, d, tr)
            p = r.predict(model, d, test)
            base = d['BASE_CD'][test]
            self.assertTrue(np.isfinite(p).all())
            self.assertTrue(((p>=.5*base)&(p<=2*base)).all())
            altered = dict(d)
            altered['MEAS_CD'] = np.full_like(d['MEAS_CD'], np.nan)
            np.testing.assert_array_equal(p, r.predict(model, altered, test))
            if not family.startswith('gate_'):
                reflected = dict(d)
                reflected['X24'] = r.reflect(d['X24'])
                np.testing.assert_allclose(p, r.predict(model, reflected, test), atol=1e-14, rtol=0)


if __name__=='__main__': unittest.main()
