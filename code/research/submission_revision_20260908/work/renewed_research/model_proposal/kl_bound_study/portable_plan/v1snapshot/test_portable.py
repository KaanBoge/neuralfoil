"""Synthetic portability checks; no actual parent or KL archive reads."""
import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import shared,integrity
class Portable(unittest.TestCase):
    def test_counts_distinct(self):self.assertEqual(shared.COUNTS['harm_metrics'],17*31*9);self.assertEqual(shared.COUNTS['bootstrap'],17*2*7)
    def test_ast_body_copy(self):
        text,w=shared.extract(b'def f(x):\n    return x+1\n',['f']);self.assertEqual(shared.module('synthetic',text).f(1),2);self.assertIn('f',w)
    def test_object_rejected(self):
        b=io.BytesIO();np.savez(b,x=np.array([object()],object))
        with self.assertRaises(ValueError):shared.arrays(b.getvalue(),[],'synthetic')
    def test_only_requested_members(self):
        b=io.BytesIO();np.savez(b,x=np.arange(2),y=np.array([object()],object));log=[]
        self.assertEqual(shared.arrays(b.getvalue(),log,'s',['x'])['x'].tolist(),[0,1]);self.assertEqual(len(log),1)
    def test_archive_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'x.zip';r=integrity.build_private_zip({'x':b'synthetic'},p)
            with self.assertRaises(ValueError):integrity.verified_members(p,'bad',r['manifest_sha256'])
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'x.zip';integrity.build_private_zip({'x':b'synthetic'},p)
            with self.assertRaises(FileExistsError):integrity.build_private_zip({'x':b'other'},p)
    def frame(self,fraction):return pd.DataFrame({'candidate':['calibrated_incremental_harm_001'],'reference':['qualified_generic_harm_001'],'assignment':[20260906],'bootstrap_fraction_benefit_positive':[fraction]})
    def test_known_zero_only(self):
        with patch.dict(shared.COUNTS,{'bootstrap':1}):
            d=shared.compare_tables('bootstrap',self.frame(.6031),self.frame(.66475).to_csv(index=False).encode())
            self.assertTrue(d[0]['known_zero_sign_diagnostic']);self.assertTrue(d[0]['requires_review'])
            d=shared.compare_tables('bootstrap',self.frame(.7),self.frame(.66475).to_csv(index=False).encode())
            self.assertFalse(d[0]['known_zero_sign_diagnostic'])
    def test_tiny_difference_retained(self):
        a=pd.DataFrame({'value':[1.+1e-12]});b=pd.DataFrame({'value':[1.]})
        with patch.dict(shared.COUNTS,{'synthetic':1}):
            d=shared.compare_tables('synthetic',a,b.to_csv(index=False).encode());self.assertEqual(len(d),1);self.assertTrue(d[0]['within_inherited_audit_tolerance'])
    def test_boolean_strict(self):
        with patch.dict(shared.COUNTS,{'synthetic':1}):
            with self.assertRaises(AssertionError):shared.compare_tables('synthetic',pd.DataFrame({'advance':[True]}),b'advance\nFalse\n')
    def test_bad_paths(self):
        for s in ['../a','/a','a\\b','a\nb']:
            with self.assertRaises(ValueError):integrity.member_name(s)
if __name__=='__main__':unittest.main()
