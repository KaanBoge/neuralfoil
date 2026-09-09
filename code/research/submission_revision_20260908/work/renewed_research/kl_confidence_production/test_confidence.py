"""Synthetic values only; no original study data or model access."""
from fractions import Fraction as F
import unittest
import confidence as c


class ProductionConfidence(unittest.TestCase):
    def check_invariants(self, values, bound):
        r = c.calibrate_kl_groups(values, bound)
        self.assertLessEqual(r['upper'], r['matched_hoeffding_upper'])
        self.assertGreaterEqual(c.n.q.rat(r['t']), c.n.q.rat(r['matched_hoeffding_t']))
        self.assertLessEqual(c.n.q.rat(r['t'])*r['upper'], F(1, 100))
        self.assertEqual(r['groups'], len(values))
        return r

    def test_deterministic_branches(self):
        for values in ([], [F(0)], [F(0)]*3):
            r = self.check_invariants(values, F(0))
            self.assertEqual(r['t'], 1.)
            self.assertEqual(r['upper'], 0)
            self.assertIsNone(r['root_witness'])
        r = self.check_invariants([], F(1, 2))
        self.assertEqual(r['upper'], F(1, 2))
        self.assertIsNone(r['root_witness'])

    def test_fixed_synthetic_cases(self):
        for values, bound in [([F(0)]*9, F(1, 2)),
                              ([F(1, 64)]*24, F(1, 3)),
                              ([F(0), F(1, 16), F(1, 8)], F(1, 4)),
                              ([F(1, 2)]*2, F(1, 2))]:
            with self.subTest(groups=len(values), bound=bound):
                r = self.check_invariants(values, bound)
                w = r['root_witness']
                self.assertEqual(w['mean_exact'], sum(values, F(0))/len(values))
                self.assertEqual(w['lower_endpoint_scope'], 'root_at_q_upper_only')
                self.assertEqual(w['upper_endpoint_scope'], 'conservative_for_q_exact')
                self.assertEqual(r['upper'], min(w['kl_upper_before_hoeffding_min'],
                                                  r['matched_hoeffding_upper']))

    def test_scalar_and_inward_prediction(self):
        r = c.fit_kl_scalar([1., 1.], [1.25, 1.25], [1.125, 1.125],
                            [1., 1.5], ['a', 'b'], F(1, 4))
        self.assertEqual(r['group_means'], {'a': F(1, 8), 'b': F(0)})
        self.assertEqual(r['exact_mean'], F(1, 16))
        for h, endpoint in [(1.125, 1.25), (1., .75), (1., 1.)]:
            p = c.n.q.inward_predict(h, endpoint, r['t'])
            if h != endpoint:
                theta = (c.n.q.rat(p)-c.n.q.rat(h))/(c.n.q.rat(endpoint)-c.n.q.rat(h))
                self.assertLessEqual(theta, c.n.q.rat(r['t']))
                self.assertGreaterEqual(theta, 0)
            else:
                self.assertEqual(p, h)

    def test_invalid(self):
        for values, bound in [([F(1)], F(0)), ([], F(-1)),
                              ([F(-1)], F(1)), ([F(2)], F(1)),
                              ([0.], F(1)), ([True], F(1)), ([], .5)]:
            with self.subTest(values=values, bound=bound):
                with self.assertRaises((TypeError, ValueError)):
                    c.calibrate_kl_groups(values, bound)
        with self.assertRaises(ValueError):
            c.fit_kl_scalar([1.], [], [1.], [1.], ['a'], F(1))


if __name__ == '__main__':
    unittest.main()
