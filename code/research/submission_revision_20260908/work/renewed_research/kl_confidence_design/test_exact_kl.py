"""Only synthetic exact-rational and high-precision diagnostic checks."""
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
import unittest
import exact_kl as k


def decimal(value):
    return D(value.numerator)/D(value.denominator)


class Enclosures(unittest.TestCase):
    def test_log_sign_and_range(self):
        with localcontext() as ctx:
            ctx.prec = 180
            for value in [F(1), F(2), F(20), F(1,20), F(3,2), F(2**100), F(1,2**100), F(17,31)]:
                lo, hi = k.log_interval(value)
                diagnostic = decimal(value).ln()
                self.assertLessEqual(decimal(lo), diagnostic)
                self.assertLessEqual(diagnostic, decimal(hi))

    def test_kl_interval(self):
        with localcontext() as ctx:
            ctx.prec = 180
            for q, u in [(F(0), F(1,3)), (F(1,5), F(2,3)), (F(1,2), F(1,2)), (F(9,10), F(99,100))]:
                lo, hi = k.kl_interval(q,u)
                qd, ud = decimal(q), decimal(u)
                diagnostic = (qd*(qd/ud).ln() if q else D(0))+(1-qd)*((1-qd)/(1-ud)).ln()
                self.assertLessEqual(decimal(lo), diagnostic)
                self.assertLessEqual(diagnostic, decimal(hi))

    def test_mean_rounding_and_huge_fraction(self):
        for q in [F(0), F(1), F(1,3), F(1,2**129), F(2**20000-1,3*2**20000)]:
            qu = k.ceil_mean(q)
            self.assertLessEqual(q,qu)
            self.assertLess(qu-q,F(1,2**128))
            self.assertEqual((qu*2**128).denominator,1)

    def test_root_certificates(self):
        for q, m in [(F(0),24),(F(1,32),24),(F(1,2),9),(F(1),24)]:
            result = k.upper_root(q,m)
            self.assertLessEqual(q,result['upper'])
            self.assertLessEqual(result['upper'],1)
            if result['upper_kl_interval'] is not None:
                self.assertGreaterEqual(result['upper_kl_interval'][0],result['budget_upper'])
            if q < 1:
                self.assertLessEqual(result['lower_kl_interval'][1],result['budget_lower'])

    def test_bad_inputs(self):
        for q in [F(-1),F(2)]:
            with self.assertRaises(ValueError):k.ceil_mean(q)
        for q in [0.1,True,'1/2']:
            with self.assertRaises(TypeError):k.ceil_mean(q)
        for n in [0,-1,1.0,True]:
            with self.assertRaises(ValueError):k.upper_root(F(1,2),n)
        for x in [F(0),F(-1)]:
            with self.assertRaises(ValueError):k.log_interval(x)
        with self.assertRaises(ValueError):k.kl_interval(F(1,2),F(1,3))
        with self.assertRaises(ValueError):k.kl_interval(F(1,2),F(1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
