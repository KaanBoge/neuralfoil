import io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd
import integrity,export_support as s,build_replay

class ExportSupport(unittest.TestCase):
    def test_members_lazy_and_restoration(self):
        stream=io.BytesIO();np.savez(stream,a=np.arange(3),unused=np.arange(2))
        raw=stream.getvalue();original=(np.load,pd.read_csv)
        with s.ReaderTrace({'synthetic.npz':integrity.sha(raw)}) as tr:
            with np.load(io.BytesIO(raw),allow_pickle=False) as z:
                self.assertEqual(z.files,['a','unused']);np.testing.assert_array_equal(z['a'],[0,1,2])
            self.assertEqual([x['name'] for x in tr.events[0]['members']],['a'])
        self.assertEqual((np.load,pd.read_csv),original)
    def test_csv_exact_bytes(self):
        raw=b'x,y\n1,2\n'
        with s.ReaderTrace({'synthetic.csv':integrity.sha(raw)}) as tr:
            self.assertEqual(pd.read_csv(io.BytesIO(raw)).iloc[0,1],2)
        self.assertEqual(tr.events[0]['rows'],1)
    def test_tamper_restores(self):
        original=(np.load,pd.read_csv)
        with self.assertRaises(ValueError):
            with s.ReaderTrace({'synthetic.csv':integrity.sha(b'x\n1\n')}):pd.read_csv(io.BytesIO(b'x\n2\n'))
        self.assertEqual((np.load,pd.read_csv),original)
    def test_path_bytes_bound_before_parse(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'input.csv';p.write_bytes(b'x\n1\n');h=integrity.sha(p.read_bytes())
            with s.ReaderTrace({str(p):h}):
                p.write_bytes(b'x\n9\n')
                with self.assertRaises(ValueError):pd.read_csv(p)
    def attempt(self,exc,partial=False):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'out.zip';args=SimpleNamespace(output=str(p),registry_sha256='synthetic',approval='synthetic',approval_sha256='synthetic')
            def fail():
                if partial:p.write_bytes(b'partial zip')
                raise exc
            with self.assertRaises(type(exc)):s.run_attempt(args,fail)
            r=json.loads(Path(str(p)+'.failure.json').read_bytes())
            self.assertEqual(r['partial_archive_preserved'],partial)
            self.assertIn('started_UTC',r);self.assertIn('finished_UTC',r)
            if partial:self.assertEqual(p.read_bytes(),b'partial zip')
            with self.assertRaises(FileExistsError):s.run_attempt(args,lambda:None)
    def test_failure_exclusive(self):self.attempt(ValueError('synthetic failure'))
    def test_timeout_receipt(self):self.attempt(TimeoutError('synthetic timeout'))
    def test_partial_preserved(self):self.attempt(OSError('synthetic write failure'),True)
    def test_approval_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);reg={'implementation_sha256':{}}
            raw=json.dumps(reg).encode();(root/'REGISTRY_v3.json').write_bytes(raw)
            approval=root/'approval.json';approved=json.dumps({'registry_sha256':integrity.sha(raw),'authorized_phases':['export']}).encode()
            approval.write_bytes(approved+b' ')
            args=SimpleNamespace(registry_sha256=integrity.sha(raw),approval=approval,approval_sha256=integrity.sha(approved))
            with patch.object(build_replay,'HERE',root):
                with self.assertRaises(ValueError):build_replay.authorize(args)

if __name__=='__main__':unittest.main()
