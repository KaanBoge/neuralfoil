"""Small source/synthetic wrapper checks; never constructs the full fixture."""
import copy,json,hashlib,tempfile,time,unittest,sys
from pathlib import Path
from unittest import mock
import cold_gate as g
import io_support as s
class Tests(unittest.TestCase):
    def root(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);return Path(t.name).resolve()
    def test_scope(self):
        a={'phase':'four_tree_fixed_cold_gate','registry_sha256':'a'*64,'checker_registry_sha256':'b'*64,'fixture_sha256':g.FIXTURE_SHA,'producer_seconds':120,'checker_seconds':120,'workers':1,'producer_owned_cap':128*2**20,'checker_owned_cap':256*2**20,'aggregate_output_cap':64*2**20,'synthetic_execution_authorized':True,'actual_model_execution_authorized':False}
        g.approval(a,'a'*64,'b'*64)
        for k,v in [('actual_model_execution_authorized',True),('workers',True),('checker_registry_sha256','c'*64),('checker_seconds',121)]:
            with self.assertRaises(ValueError):g.approval(dict(a,**{k:v}),'a'*64,'b'*64)
    def test_small_child_logs_no_science(self):
        root=self.root();elapsed=g.run_child([sys.executable,'-B','-c',"import sys;print('out');print('err',file=sys.stderr)"],root,'small',seconds=5)
        self.assertLess(elapsed,5);self.assertEqual((root/'small.stdout.txt').read_text(),'out\n');self.assertEqual((root/'small.stderr.txt').read_text(),'err\n')
    def test_failed_child_preserves_logs(self):
        root=self.root()
        with self.assertRaises(RuntimeError):g.run_child([sys.executable,'-B','-c',"print('preserved',flush=True);raise SystemExit(2)"],root,'failed',seconds=5)
        self.assertEqual((root/'failed.stdout.txt').read_text(),'preserved\n')
    def test_changed_child_payload(self):
        root=self.root();st=s.Store(root/'producer',time.monotonic()+30);st.write_json('payload.json',{'x':1});pin,_=st.write_json('COMPLETE.json',{'status':'COMPLETE','outputs':dict(st.outputs)})
        g.verify_child(root,'producer',pin,s,[])
        (root/'producer/payload.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):g.verify_child(root,'producer',pin,s,[])
    def test_nested_aggregate_charge(self):
        root=self.root();st=s.Store(root/'child',time.monotonic()+30,cap=120,reserve=20,budget_root=root)
        (root/'parent.log').write_bytes(b'x'*80)
        with self.assertRaises(OSError):st.write_json('x.json',{'a':'x'*30})
    def test_retained_alias_dedup(self):
        a=[1,2,3];self.assertLess(g.deep_owned([a,a]),g.deep_owned([a,list(a)]))
    def test_no_fixture_on_bad_root_approval(self):
        with mock.patch.object(g,'context',side_effect=ValueError('no frozen approval')):
            with self.assertRaises(ValueError):g.execute_parent(type('Args',(),{'registry_sha256':'0'*64})())
if __name__=='__main__':unittest.main()
