import unittest
from fractions import Fraction as F
from audit_displays import rounding
class Tests(unittest.TestCase):
    def test_half_even(self):
        self.assertEqual(rounding('1.2345645',6),'1.234564')
        self.assertEqual(rounding('1.2345655',6),'1.234566')
    def test_negative_signed_zero(self):
        self.assertEqual(rounding('-0.0000001',6,True),'-0.000000')
        self.assertEqual(rounding('0',3,True),'+0.000')
    def test_rational(self):self.assertEqual(rounding(F(1,3),6),'0.333333')
    def test_nonfinite(self):
        with self.assertRaises(ValueError):rounding('NaN',6)
if __name__=='__main__':unittest.main()
