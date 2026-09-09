"""Synthetic source/typed-frame/numerical-difference tests; no real export/replay."""
import ast,io,json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
import frame_codec as f
import build_replay as b
import replay

class ReplaySources(unittest.TestCase):
    def test_mixed_typed_frame_roundtrip(self):
        frame=pd.DataFrame({'mixed':np.array([None,np.nan,True,3,1.25,'3'],dtype=object),
            'flag':np.array([True,False]*3),'float':np.array([0.,-0.,1.,np.inf,-np.inf,np.nan])})
        a,s=f.pack(frame);pd.testing.assert_frame_equal(frame,f.unpack(a,s),check_exact=True)
        self.assertTrue(all(not x.dtype.hasobject for x in a.values()))
    def test_frame_rejects_object_payload(self):
        with self.assertRaises(ValueError):f.pack(pd.DataFrame({'x':[object()]}))
    def test_ast_extraction_identity(self):
        raw=b'def square(x):\n    return x*x\n'
        witness=[];source=b.extract_functions(raw,['square'],witness,'synthetic')
        self.assertEqual(ast.dump(ast.parse(source)),ast.dump(ast.parse(raw)))
        self.assertEqual(witness[0]['permitted_adapter'],'unchanged AST')
    def test_near_zero_sign_discrepancy_retained(self):
        actual=pd.DataFrame({'candidate':['same'],'benefit':[1e-17],'bootstrap_fraction_benefit_positive':[1.]})
        expected=pd.DataFrame({'candidate':['same'],'benefit':[0.],'bootstrap_fraction_benefit_positive':[0.]}).to_csv(index=False).encode()
        delta=replay.compare('synthetic',actual,expected)
        self.assertEqual(len(delta),2)
        self.assertEqual({r['column'] for r in delta},{'benefit','bootstrap_fraction_benefit_positive'})
    def test_changed_boolean_decision_fails(self):
        with self.assertRaises(AssertionError):replay.compare('decision',pd.DataFrame({'pass':[True]}),b'pass\nFalse\n')
    def test_packaged_production_arithmetic_on_synthetic_only(self):
        # Source bytes only; no calibration/model/feature input file is read.
        qraw=(Path(__file__).resolve().parents[2]/'qualified_numerics.py').read_bytes()
        nraw=(Path(__file__).resolve().parents[1]/'numerics.py').read_bytes()
        q=b.module('qualified_numerics',qraw,'synthetic-source-qualified.py');w=[]
        source='from qualified_numerics import *\nimport qualified_numerics as q\n'
        source+=b.extract_functions(qraw,['exact_group_means','synthetic_confidence'],w,'q',
            {'exact_group_means':'group_means_exact','synthetic_confidence':'calibrate_exact_groups'})
        source+=b.extract_functions(nraw,['fit_scalar','predictions'],w,'n')
        policy=b.module('synthetic_packaged_policy',source.encode(),'synthetic-policy.py')
        c,h,g=q.guarded_core([1.,2.],[.3,-.2],[True,True])
        model=policy.fit_scalar([1.,2.],c,h,[1.,2.],['a','b'],q.GENERIC_BOUND)
        p,e=policy.predictions(model,np.array([1.,2.]),c,h,g)
        self.assertEqual(len(p),2);self.assertTrue(np.isfinite(p).all())

if __name__=='__main__':unittest.main(verbosity=2)
