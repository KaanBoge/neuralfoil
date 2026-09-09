"""Fixed small synthetic frames and source-AST checks, no scientific inputs."""
import ast,hashlib,unittest
import numpy as np
import pandas as pd
import assessment_equations as eqs
from audit_assessment import unpack,overlay,REFS,OLD_REFS,summary_schema,ac
class Tests(unittest.TestCase):
    def summary_fixture(self):
        labels=list(ac.NEW)+['old_'+str(i) for i in range(19)]
        return labels,{'decisions':pd.DataFrame({'candidate':list(ac.NEW)}),'candidate_summary':pd.DataFrame({'candidate':labels})}
    def test_summary21_decisions2(self):
        labels,t=self.summary_fixture();summary_schema(t,labels)
    def test_summary_missing_old(self):
        labels,t=self.summary_fixture();t['candidate_summary']=t['candidate_summary'].iloc[:-1]
        with self.assertRaises(ValueError):summary_schema(t,labels)
    def test_summary_duplicate(self):
        labels,t=self.summary_fixture();t['candidate_summary'].loc[20,'candidate']=labels[19]
        with self.assertRaises(ValueError):summary_schema(t,labels)
    def test_decision_missing_new(self):
        labels,t=self.summary_fixture();t['decisions'].loc[1,'candidate']='old_0'
        with self.assertRaises(ValueError):summary_schema(t,labels)
    def test_summary_extra(self):
        labels,t=self.summary_fixture();t['candidate_summary'].loc[21,'candidate']='extra'
        with self.assertRaises(ValueError):summary_schema(t,labels)
    def test_exact_review_source_transform(self):
        raw=eqs.SOURCE.read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),eqs.SHA)
        tree=eqs.prepare(raw);compile(tree,'<synthetic source check>','exec');text=ast.unparse(tree)
        self.assertNotIn('read_csv',text);self.assertNotIn('read_bytes',text)
        for number in (651,3906,420,7812,20000,2026090831):self.assertIn(str(number),text)
        self.assertIn('2e-10',text);self.assertIn('2e-12',text)
    def test_refs_fixed(self):
        self.assertEqual(len(REFS),10);self.assertEqual(len(OLD_REFS),9);self.assertEqual(len(set(REFS)),10)
    def test_typed_object(self):
        schema={'columns':[{'name':'x','key':'v','dtype':'object'}]}
        arr={'v':np.array(['','name','1','3',float(.25).hex()]),'v_kind':np.array([0,1,2,3,4])}
        f=unpack(schema,arr,np,pd);self.assertEqual(f.x.tolist(),[None,'name',True,3,.25]);self.assertEqual(f.x.dtype,object)
    def test_typed_reject_extra_member(self):
        with self.assertRaises(ValueError):unpack({'columns':[{'name':'x','key':'v','dtype':'float64'}]},{'v':np.array([1.]),'extra':np.array([2.])},np,pd)
    def test_typed_reject_bad_bool(self):
        with self.assertRaises(ValueError):unpack({'columns':[{'name':'x','key':'v','dtype':'object'}]},{'v':np.array(['True']),'v_kind':np.array([2])},np,pd)
    def fixture(self):
        frame=pd.DataFrame({'split':['group_1']*2,'nf2_row_id':[1,2],'mean8_CD':[1.,2.],'old':[3.,4.]})
        source=pd.DataFrame({'nf2_row_id':[2,1],'BASE_CD':[2.,1.],'new':[2.5,1.5],'new__effective_fraction':[.2,.1],'new__strength':[.6,.55],'new__intervened':[True,True]})
        return frame,source
    def test_overlay_reorder_preserve(self):
        frame,source=self.fixture();old=frame.copy();overlay(frame,['new'],lambda s:source.to_csv(index=False).encode(),np,pd)
        pd.testing.assert_frame_equal(frame[old.columns],old,check_exact=True);self.assertEqual(frame.new.tolist(),[1.5,2.5])
    def test_overlay_duplicate_ids_rejected(self):
        frame,source=self.fixture();source.nf2_row_id=[1,1]
        with self.assertRaises(ValueError):overlay(frame,['new'],lambda s:source.to_csv(index=False).encode(),np,pd)
    def test_overlay_external_order_rejected(self):
        frame,source=self.fixture();frame['split']='SG_exposed';source['indices']=[1,0]
        with self.assertRaises(AssertionError):overlay(frame,['new'],lambda s:source.to_csv(index=False).encode(),np,pd)
    def test_overlay_old_field_collision(self):
        frame,source=self.fixture()
        with self.assertRaises(ValueError):overlay(frame,['old'],lambda s:source.to_csv(index=False).encode(),np,pd)
if __name__=='__main__':unittest.main()
