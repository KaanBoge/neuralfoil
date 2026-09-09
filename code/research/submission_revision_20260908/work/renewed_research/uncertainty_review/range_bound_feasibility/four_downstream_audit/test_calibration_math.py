"""Synthetic-only review tests; never invokes the saved phase entrypoint."""
import unittest,ast
from pathlib import Path
from fractions import Fraction as F
import audit_common as ac
import calibration_math as cm
class Tests(unittest.TestCase):
    def setUp(self):
        b={'phase':'calibrate','root_saved_audit_authorized':True,'complete_sha256':'1'*64,'approval_sha256':'2'*64,'registry_sha256':'3'*64,'predecessor_sha256':'4'*64,'seconds':900,'workers':1}
        self.a=ac.Access(b);self.m=cm.load(self.a)
    def test_source_only_load(self):
        self.assertEqual(len(self.a.inputs),2)
        self.assertNotIn('main',self.m)
        self.assertNotIn('HERE',self.m)
    def test_hoeffding_and_corruption(self):
        B=F(1,3);means={'a':F(0),'b':F(1,100)};mean=F(1,200)
        U=min(B,mean+B*self.m['sqrt_upper'](self.m['log_upper']()/4))
        t=self.m['down'](min(F(1),F(1,100)/U))
        s={'group_means':means,'exact_mean':mean,'bound':B,'rows':5,'groups':2,'upper':U,'t':t}
        self.assertEqual(cm.verify(s,B,mean,means,5,'H',self.m),(U,t))
        with self.assertRaises(AssertionError):cm.verify(dict(s,upper=U+F(1,100)),B,mean,means,5,'H',self.m)
    def test_degenerate_fails_closed(self):
        with self.assertRaises(ValueError):cm.verify({},F(0),F(0),{},0,'H',self.m)
    def test_KL_requires_scope_flag_manufactured_witness(self):
        # Pure schema fixture with manufactured interval oracles, not a claim
        # that these fake transcendental bounds are mathematically certified.
        B=F(1,3);t=self.m['down'](F(3,100));lo=1-F(1,2**64)
        mocked=dict(self.m,log_interval=lambda x:(F(1),F(1)),log_upper=lambda:F(2),sqrt_upper=lambda x:F(1),kl_interval=lambda q,p:(F(0),F(0)))
        r={'q_exact':F(0),'q_upper':F(0),'q_rounding_gap':F(0),'groups':1,'budget_lower':F(1),'budget_upper':F(1),'lower':lo,'upper':F(1),'iterations':64,'stop':'step_limit','lower_kl_interval':[F(0),F(0)],'upper_kl_interval':None}
        w={'root_at_upward_mean':r,'mean_exact':F(0),'kl_upper_before_hoeffding_min':B,'lower_endpoint_scope':'root_at_q_upper_only','upper_endpoint_scope':'conservative_for_q_exact'}
        s={'group_means':{'a':F(0)},'exact_mean':F(0),'bound':B,'rows':1,'groups':1,'upper':B,'t':t,'matched_hoeffding_upper':B,'matched_hoeffding_t':t,'root_witness':w}
        with self.assertRaises(KeyError):cm.verify(s,B,F(0),{'a':F(0)},1,'KL',mocked)
        self.assertEqual(cm.verify(dict(s,conditional_not_certified=True),B,F(0),{'a':F(0)},1,'KL',mocked),(B,t))
    def test_exact_loss_weighting(self):
        loss,means,mean=ac.group_positive_losses([1.,1.,1.],[2.,2.,1.],[1.,1.,1.],[1.,1.,1.],['a','a','b'])
        self.assertEqual(loss,[F(1),F(1),F(0)])
        self.assertEqual(mean,F(1,2))
    def test_downward_rational(self):
        for x in (F(1,3),F(1,100),F(0),F(1)):
            self.assertLessEqual(F(self.m['down'](x)),x)
    def test_endpoint_intervals(self):
        lo,hi=self.m['log_interval'](F(20));self.assertLess(lo,hi)
        self.assertEqual(self.m['kl_interval'](F(1,4),F(1,4)),(F(0),F(0)))
    def test_runner_has_no_auto_call_at_import(self):
        source=Path(__file__).with_name('audit_calibration.py').read_text()
        tree=ast.parse(source)
        self.assertEqual([n.test.left.id for n in tree.body if isinstance(n,ast.If) and isinstance(n.test,ast.Compare)],['__name__'])
if __name__=='__main__':unittest.main()
