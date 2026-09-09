"""Small safe archive/header and metadata mocks only. No proof replay."""
import argparse
import io
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
import replay as r


def archive(object_member=False):
    values={k:np.zeros(0,dtype='i8') for k in r.MEMBERS}
    values['initial']=np.array([0.],dtype='f8')
    if object_member:values['nodes']=np.array([object()],dtype=object)
    out=io.BytesIO();np.savez(out,**values);return out.getvalue()


class ReplayMocks(unittest.TestCase):
    def test_exact_safe_headers(self):
        ledger=[];n=r.zip_headers(archive(),ledger)
        self.assertGreater(n,0);self.assertEqual(len(ledger),7)
        self.assertTrue(all(x['operation']=='NPY_header_validation' for x in ledger))

    def test_object_refused_before_payload(self):
        with self.assertRaises(ValueError):r.zip_headers(archive(True),[])

    def test_duplicate_or_wrong_members(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('../initial.npy',b'no payload')
        with self.assertRaises(ValueError):r.zip_headers(out.getvalue(),[])

    def test_truncated_npy(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for k in r.MEMBERS:z.writestr(k+'.npy',b'\x93NUMPY\x01\x00\xff\xff')
        with self.assertRaises((ValueError,EOFError)):r.zip_headers(out.getvalue(),[])

    def test_expanded_admission_before_headers(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for i,k in enumerate(r.MEMBERS):z.writestr(k+'.npy',b'0'*(4*2**20+1 if i==0 else 0))
        with self.assertRaises(MemoryError):r.zip_headers(out.getvalue(),[])

    def test_exact_approval_scope(self):
        a=dict(phase='eight_tree_independent_replay',registry_sha256='a'*64,entrypoint_sha256='b'*64,
               model_sha256=r.MODEL,old_certificate_sha256=r.OLD_CERT,old_replay_complete_sha256=r.OLD_RC,
               domain='FINITE_X62_V1',seconds=900,workers=1,owned_cap=256*2**20,output_cap=64*2**20,
               python='3.13.9',output='actual_replay_attempt_1',actual_execution_authorized=True,
               source_review_sha256='c'*64,producer_complete_sha256='d'*64,certificate_sha256='e'*64)
        r.strict_approval(a,'a'*64,'b'*64)
        for k,v in [('extra',1),('seconds',901),('model_sha256','f'*64),('output','other'),('actual_execution_authorized',False)]:
            b=dict(a);b[k]=v
            with self.assertRaises(ValueError):r.strict_approval(b,'a'*64,'b'*64)

    def test_whole_entry_deadline_before_input(self):
        args=argparse.Namespace(registry_sha256='a'*64,approval_sha256='b'*64)
        with tempfile.TemporaryDirectory() as td,patch.object(r,'HERE',Path(td).resolve()),patch.object(r.signal,'signal'),patch.object(r.signal,'getsignal'),patch.object(r.signal,'setitimer') as timer:
            with self.assertRaises(FileNotFoundError):r.execute(args)
            self.assertEqual(timer.call_args_list[0].args,(signal.ITIMER_REAL,900))
            self.assertEqual(timer.call_args_list[-1].args,(signal.ITIMER_REAL,0))

    def test_no_producer_arithmetic_import(self):
        import ast
        tree=ast.parse(Path(r.__file__).read_text())
        names=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any('prototype' in n or 'adapter' in n or 'producer' in n for n in names))
        self.assertEqual(set(r.HELPERS),{'io','checker','old_checker','primitive'})


if __name__=='__main__':unittest.main()
