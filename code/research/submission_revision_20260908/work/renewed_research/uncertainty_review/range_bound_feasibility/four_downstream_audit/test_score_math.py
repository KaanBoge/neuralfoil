"""Fixed synthetic prediction checks only; no archives or saved scalar reads."""
import unittest,math,ast
from fractions import Fraction as F
from pathlib import Path
from score_math import prediction
class Tests(unittest.TestCase):
    def test_both_directions_and_strength_boundaries(self):
        for b,c,h in [(1.,1.5,1.25),(1.,.5,.75),(2.**-500,2.**-499,1.5*2.**-500),(2.**500,1.5*2.**500,1.25*2.**500)]:
            for t in (0.,1.,.01,1/3,math.nextafter(1.,0.)):
                p,e=prediction(b,c,h,True,t);theta=(F(p)-F(h))/(F(c)-F(h))
                self.assertTrue(0<=theta<=F(t));self.assertEqual(e,float(theta))
                ideal=F(h)+F(t)*(F(c)-F(h))
                if p!=float(ideal):self.assertEqual(p,math.nextafter(float(ideal),h))
    def test_false_gate_and_equal_endpoint(self):
        self.assertEqual(prediction(1.,2.,1.5,False,.5),(1.,0.))
        self.assertEqual(prediction(1.,1.5,1.5,True,.5),(1.5,0.))
    def test_adjacent_endpoint_inward(self):
        c=math.nextafter(1.,2.)
        self.assertEqual(prediction(1.,c,1.,True,.5),(1.,0.))
    def test_bad_inputs(self):
        for t in (-1.,2.,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):prediction(1.,2.,1.5,True,t)
        with self.assertRaises(ValueError):prediction(1.,2.,1.5,'False',.5)
        with self.assertRaises(ValueError):prediction(0.,2.,1.5,True,.5)
    def test_no_automatic_phase_intake(self):
        tree=ast.parse(Path(__file__).with_name('audit_score.py').read_text())
        self.assertEqual([n.test.left.id for n in tree.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare)],['__name__'])
if __name__=='__main__':unittest.main()
