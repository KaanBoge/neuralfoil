"""Synthetic checks only; no study/source archive is opened."""
import unittest
from fractions import Fraction as F
import audit_common as a
class Tests(unittest.TestCase):
    def binding(self,p):return {'phase':p,'root_saved_audit_authorized':True,'complete_sha256':'a'*64,'approval_sha256':'b'*64,'registry_sha256':'c'*64,'predecessor_sha256':'d'*64,'seconds':900,'workers':1}
    def test_no_implicit_authority(self):
        with self.assertRaises(ValueError):a.Access({})
        b=self.binding('calibrate');b['root_saved_audit_authorized']=False
        with self.assertRaises(ValueError):a.Access(b)
    def test_score_cannot_open_targets(self):
        s=a.Access(self.binding('score'));s.permit_payload('native_without_targets')
        with self.assertRaises(ValueError):s.permit_payload('typed_assessment')
        with self.assertRaises(ValueError):s.permit_payload('calibration_only')
    def test_preflight_forbids_loss_members(self):
        s=a.Access(self.binding('preflight'))
        with self.assertRaises(ValueError):s.permit_payload('frozen_scalar')
        b=self.binding('preflight');b['predecessor_sha256']=None
        with self.assertRaises(ValueError):a.Access(b)
    def test_equal_group_not_equal_row(self):
        loss,groups,mean=a.group_positive_losses([1.,1.,1.],[2.,2.,1.],[1.,1.,1.],[1.,1.,1.],['a','a','b'])
        self.assertEqual(loss,[F(1),F(1),F(0)]);self.assertEqual(mean,F(1,2))
    def test_direction_allows_tU_nonmonotone(self):
        enc=lambda x:{'encoding':'signed-hex-v1','numerator':format(x,'x'),'denominator':'1'}
        d=a.scalar_directions({'upper':enc(1),'t':.75},{'upper':enc(2),'t':.25});self.assertEqual(d,{'U_direction':-1,'t_direction':1,'tU_direction':1})
    def test_subset_exact_and_duplicate(self):
        old=[{'candidate':'old','reference':'ref','value':'1.000'}];new=old+[{'candidate':'new','reference':'ref','value':'2'}]
        self.assertEqual(a.exact_keyed_subset(new,old,['candidate','reference'],{'old'},{'ref'}),1)
        with self.assertRaises(ValueError):a.exact_keyed_subset(old+old,old,['candidate','reference'],{'old'})
    def test_contract_counts(self):
        self.assertEqual(a.COUNTS['bootstrap_rows'],21*2*10);self.assertEqual(a.COUNTS['harm_rows'],21*31*12);self.assertEqual(a.COUNTS['old_bootstrap_rows'],19*2*9)
if __name__=='__main__':unittest.main()
