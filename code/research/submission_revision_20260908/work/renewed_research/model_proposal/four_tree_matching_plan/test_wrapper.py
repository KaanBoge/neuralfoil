"""Synthetic publication/approval tests only; no scientific files opened."""
import io,json,os,tempfile,time,unittest,zipfile
from pathlib import Path
from unittest import mock
import numpy as np
import io_support as s
import run,producer,fixtures

class Tests(unittest.TestCase):
    def temporary(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);return Path(t.name).resolve()
    def test_streamed_exact_json_and_retained_partial(self):
        out=self.temporary()/'out';st=s.Store(out,time.monotonic()+30);data={'x':[1,2,3],'s':'µ'};pin,n=st.write_json('x.json',data)
        self.assertEqual((out/'x.json').read_bytes(),json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode());self.assertEqual((out/'x.json').read_bytes(),(out/'x.json.partial').read_bytes());self.assertEqual(st.used(),2*n)
        with self.assertRaises(FileExistsError):st.write_json('x.json',{})
    def test_storage_refuses_before_exceeding(self):
        out=self.temporary()/'out';st=s.Store(out,time.monotonic()+30,cap=80,reserve=20)
        with self.assertRaises(OSError):st.write_json('large.json',{'s':'x'*100})
        self.assertLessEqual(st.used(),60);self.assertFalse((out/'large.json').exists());self.assertTrue((out/'large.json.partial').exists())
    def test_deadline_before_publication(self):
        out=self.temporary()/'out';st=s.Store(out,time.monotonic()-1)
        with self.assertRaises(TimeoutError):st.write_json('x.json',{})
        self.assertFalse((out/'x.json').exists())
    def test_failure_reserve(self):
        out=self.temporary()/'out';st=s.Store(out,time.monotonic()-1,cap=100,reserve=80);st.write_json('FAILURE.json',{'error':'x'},emergency=True);self.assertLess(st.used(),100)
    def test_interrupted_json_retains_no_final(self):
        out=self.temporary()/'out';st=s.Store(out,time.monotonic()+30)
        with self.assertRaises(ValueError):st.write_json('x.json',{'a':'x'*20000,'z':float('nan')})
        self.assertFalse((out/'x.json').exists());self.assertTrue((out/'x.json.partial').exists());self.assertGreater((out/'x.json.partial').stat().st_size,0)
    def test_changed_accepted_output_rejected(self):
        out=self.temporary()/'out';st=s.Store(out,time.monotonic()+30);st.write_json('x.json',{'a':1});(out/'x.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):st.verify_outputs([])
    def test_symlink_rejected(self):
        out=self.temporary();(out/'link').symlink_to(out,target_is_directory=True)
        with self.assertRaises(ValueError):s.Store(out/'link'/'new',time.monotonic()+30)
    def test_exact_approval_scope(self):
        a={'phase':run.PHASE,'registry_sha256':'0'*64,'model_sha256':run.MODEL_SHA,'domain':'FINITE_X62_V1','seconds':900,'workers':1,'owned_cap':128*2**20,'output_cap':64*2**20,'real_execution_authorized':True,'output':'attempt_1','source_review_sha256':'2'*64,'synthetic_gate_sha256':'3'*64,'checker_registry_sha256':'4'*64}
        run.strict_approval(a,'0'*64)
        for k,v in [('phase','score'),('workers',True),('real_execution_authorized',False),('domain','R'),('output','../elsewhere'),('seconds',901)]:
            with self.subTest(k=k),self.assertRaises(ValueError):run.strict_approval(dict(a,**{k:v}),'0'*64)
        with self.assertRaises(ValueError):run.strict_approval(dict(a,extra=1),'0'*64)
    def test_npz_synthetic_member_inventory(self):
        a=fixtures.pack([]);b=io.BytesIO();np.savez_compressed(b,**a);ledger=[];got=run.load_arrays(b.getvalue(),producer,ledger)
        self.assertEqual(len(ledger),7)
        for k in a:np.testing.assert_array_equal(a[k],got[k])
        b=io.BytesIO();np.savez_compressed(b,**a,extra=np.zeros(1))
        with self.assertRaises(ValueError):run.load_arrays(b.getvalue(),producer,[])
    def test_bad_registry_stops_before_array_intake(self):
        root=self.temporary();(root/'REGISTRY_SOURCE_V1.json').write_bytes(b'{}')
        with mock.patch.object(run,'HERE',root),mock.patch.object(run,'load_arrays',side_effect=AssertionError('array access')) as loader:
            with self.assertRaises(ValueError):run.execute(type('Args',(),{'registry_sha256':'0'*64,'approval_sha256':'1'*64})())
            loader.assert_not_called()
    def test_owned_accounting_monotone_and_cap(self):
        x=producer.memory_plan();y=producer.memory_plan(array_bytes=123,input_bytes=456,source_bytes=789)
        self.assertEqual(y['estimated_owned_bytes']-x['estimated_owned_bytes'],6*123+2*456+4*789);self.assertLess(x['estimated_owned_bytes'],128*2**20)
    def test_duplicate_and_nonfinite_json_refused(self):
        for raw in [b'{"a":1,"a":2}',b'{"x":NaN}']:
            with self.assertRaises(ValueError):s.parse(raw,[],'synthetic')
    def test_cold_gate_required_and_fixed(self):
        review={'status':'PASS_SOURCE_REVIEW','registry_sha256':'0'*64,'checker_registry_sha256':'4'*64};gate={'status':'PASS_FIXED_135000_GATE','registry_sha256':'0'*64,'checker_registry_sha256':'4'*64,'pair_classifications':135000,'producer':{'seconds':1.,'owned_estimate':100,'logical_output_bytes':100},'checker':{'seconds':1.,'owned_estimate':100,'logical_output_bytes':100}}
        run.gate_scope(review,gate,'0'*64)
        for change in [{'status':'FAIL'},{'pair_classifications':90000},{'producer':{'seconds':121.,'owned_estimate':100,'logical_output_bytes':100}}]:
            with self.assertRaises(ValueError):run.gate_scope(review,dict(gate,**change),'0'*64)
if __name__=='__main__':unittest.main()
