"""Exact finite synthetic coverage checks, not an empirical airfoil study."""
from fractions import Fraction as F
from functools import lru_cache
from math import comb
import unittest
import exact_kl as k


@lru_cache(maxsize=128)
def endpoint(numerator, denominator, groups):
    return k.upper_root(F(numerator, denominator), groups)['upper']


class FiniteCoverage(unittest.TestCase):
    def test_exact_bernoulli_failure_probability(self):
        for m in [1, 2, 9, 24]:
            endpoints = [endpoint(count, m, m) for count in range(m+1)]
            self.assertEqual(endpoints, sorted(endpoints))
            for p in [F(0),F(1,1000),F(1,100),F(1,20),F(1,5),F(1,2),F(9,10),F(99,100),F(1)]:
                failure = sum((F(comb(m,count))*p**count*(1-p)**(m-count)
                               for count, upper in enumerate(endpoints) if p > upper), F(0))
                self.assertLessEqual(failure,F(1,20))

    def test_exact_three_point_failure_probability(self):
        # X takes 0, 1/2, 1; this checks fractional bounded losses directly.
        m = 6
        endpoints = [endpoint(total,2*m,m) for total in range(2*m+1)]
        for probabilities in [(F(4,5),F(1,10),F(1,10)),
                              (F(1,3),F(1,3),F(1,3)),
                              (F(99,100),F(1,200),F(1,200)),
                              (F(0),F(1),F(0)),
                              (F(1,10),F(1,10),F(4,5))]:
            self.assertEqual(sum(probabilities),1)
            distribution = {0:F(1)}
            for unused in range(m):
                next_distribution = {}
                for total, probability in distribution.items():
                    for value, mass in enumerate(probabilities):
                        next_distribution[total+value] = next_distribution.get(total+value,F(0))+probability*mass
                distribution = next_distribution
            self.assertEqual(sum(distribution.values()),1)
            mean = probabilities[1]/2+probabilities[2]
            failure = sum((mass for total,mass in distribution.items() if mean > endpoints[total]),F(0))
            self.assertLessEqual(failure,F(1,20))


if __name__ == '__main__':
    unittest.main(verbosity=2)
