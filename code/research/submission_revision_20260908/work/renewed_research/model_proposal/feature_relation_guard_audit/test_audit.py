import unittest,tempfile,io,json,types
from pathlib import Path
from unittest.mock import patch
import numpy as np
import audit as a
class Audit(unittest.TestCase):
    def matrix(self):
        x=np.zeros((3,62));x[:,0]=[-1,0,2];x[:,16]=abs(x[:,0]);x[:,12]=[1,2,3];x[:,13]=[3,2,1];x[:,18]=np.minimum(x[:,12],x[:,13]);x[:,19]=np.maximum(x[:,12],x[:,13]);return x
    def guard(self,x):return all(np.isfinite(x)) and x[16]==abs(x[0]) and x[18]==min(x[12],x[13]) and x[19]==max(x[12],x[13])
    def raw(self,X):
        b=io.BytesIO();np.savez(b,X62=X,BASE_CD=np.array([object()],object));return b.getvalue()
    def test_true(self):self.assertTrue(all(x['guard'] for x in a.evaluate(self.matrix(),self.guard)))
    def test_violation(self):
        x=self.matrix();x[0,16]=2;self.assertFalse(a.evaluate(x,self.guard)[0]['guard'])
    def test_nonfinite_retained(self):
        x=self.matrix();x[1,61]=float('nan');r=a.evaluate(x,self.guard);self.assertEqual(len(r),3);self.assertFalse(r[1]['all_finite'])
    def test_unused_base_not_materialized(self):
        log=[];X=a.load_features(self.raw(self.matrix()),log,rows=3)
        self.assertEqual(X.shape,(3,62));self.assertEqual([x['member'] for x in log],['X62'])
    def test_wrong_dtype(self):
        with self.assertRaises(ValueError):a.load_features(self.raw(self.matrix().astype(np.float32)),[],rows=3)
    def test_wrong_shape(self):
        with self.assertRaises(ValueError):a.load_features(self.raw(np.zeros((3,61))),[],rows=3)
    def maps(self):return {k:[0,1,1] for k in sorted(a.MAP_KEYS)}
    def test_maps_repeats(self):
        m=a.mappings(json.dumps(self.maps()),rows=3,check_lengths=False);r=a.evaluate(self.matrix(),self.guard);r[1]['guard']=False
        s=a.summarize(r,m);self.assertEqual(s['native/final']['violating_indices_in_original_order'],[1,1])
    def test_indices_rejected(self):
        for bad in [-1,3,True,1.5,'1']:
            m=self.maps();m['native/final']=[bad]
            with self.assertRaises(ValueError):a.mappings(json.dumps(m),rows=3,check_lengths=False)
    def test_wrong_keys(self):
        m=self.maps();m.pop('native/final')
        with self.assertRaises(ValueError):a.mappings(json.dumps(m),rows=3,check_lengths=False)
    def test_wrong_native_lengths(self):
        with self.assertRaises(ValueError):a.mappings(json.dumps(self.maps()),rows=3)
    def test_hash_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'x';p.write_bytes(b'bad')
            with self.assertRaises(ValueError):a.checked(p,a.sha(b'expected'))
    def test_source_approval_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();raw=json.dumps({'source_sha256':{}}).encode();(root/'IMPLEMENTATION_FREEZE.json').write_bytes(raw)
            p=root/'a.json';p.write_bytes(b'{}');args=types.SimpleNamespace(implementation_sha256=a.sha(raw),approval=p,approval_sha256=a.sha(b'wrong'))
            with patch.object(a,'HERE',root):
                with self.assertRaises(ValueError):a.sources(args)
    def test_failure_and_collision(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();args=types.SimpleNamespace(implementation_sha256='test',approval_sha256='test')
            with patch.object(a,'HERE',root),patch.object(a,'sources',return_value=None),patch.object(a,'input_buffers',side_effect=TimeoutError('synthetic')):
                with self.assertRaises(TimeoutError):a.execute(args)
                self.assertTrue((root/'results/FAILURE.json').exists())
                with self.assertRaises(FileExistsError):a.execute(args)
    def test_json_no_partial(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x'
            with self.assertRaises(TypeError):a.write_json(p,object())
            self.assertFalse(p.exists())
if __name__=='__main__':unittest.main()
