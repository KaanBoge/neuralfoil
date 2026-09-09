"""Source-only synthesis test; not part of portable runtime dependency."""
from pathlib import Path
from fractions import Fraction as F
from types import SimpleNamespace
from unittest.mock import patch
import unittest,tempfile,json
import shared,build_replay as b,export_support,integrity
class SourceAdapter(unittest.TestCase):
    def test_production_adapter_synthetic(self):
        root=Path(__file__).resolve().parents[3]
        qraw=b.checked(root/'model_proposal/range_bound_feasibility/qualified_numerics.py','76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a')
        q=shared.module('synthetic_q',qraw)
        n=SimpleNamespace(q=q,group_means_exact=q.exact_group_means,calibrate_exact_groups=q.synthetic_confidence)
        raw=b.checked(root/'kl_confidence_design/exact_kl.py','115003c1d6e8a64fc68168f1d0ab3c002e7ff5709589f08e91aa753f450844ae')
        kl=shared.module('synthetic_kl',raw)
        source=b.checked(root/'kl_confidence_production/confidence.py','03c41a6aa79f44bd04fe374953c560db029d2f4a98f8cd1de552ed35657d9ad9')
        adapter,_=shared.extract(source,['production_root_adapter','calibrate_kl_groups','fit_kl_scalar'])
        text='import ast,hashlib,types\nfrom fractions import Fraction as F\n'+adapter+'\ncertified_upper_root,ROOT_AST=production_root_adapter()\n'
        c=shared.module('synthetic_adapter',text,{'kl':kl,'kl_raw':raw,'n':n})
        self.assertEqual(c.calibrate_kl_groups([],F(0))['t'],1.)
        z=c.calibrate_kl_groups([F(0)],F(1,2));self.assertLessEqual(z['upper'],z['matched_hoeffding_upper'])
    def test_approval_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);raw=json.dumps({'sources':{}}).encode();(root/'REGISTRY_v3.json').write_bytes(raw)
            ap=root/'a.json';ap.write_bytes(b'{}');args=SimpleNamespace(registry_sha256=integrity.sha(raw),approval=ap,approval_sha256='wrong')
            with patch.object(b,'HERE',root):
                with self.assertRaises(ValueError):b.authorize(args)
    def test_timeout_partial_retained(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'x.zip';args=SimpleNamespace(output=p,registry_sha256='synthetic',approval='synthetic',approval_sha256='synthetic')
            def fail():p.write_bytes(b'partial');raise TimeoutError('synthetic')
            with self.assertRaises(TimeoutError):export_support.run_attempt(args,fail)
            self.assertEqual(p.read_bytes(),b'partial');self.assertTrue(Path(str(p)+'.failure.json').exists())
    def test_large_hex_codec_source(self):
        import ast
        root=Path(__file__).resolve().parents[2]
        raw=b.checked(root/'range_bound_feasibility/stage1_v2/run_stage1.py','5cb5c4897209465f2526099aae094ddce0fc72b50446f071e955520d97568ec1')
        code,_=shared.extract(raw,['encode','fraction']);c=shared.module('codec_synthetic','from fractions import Fraction as F\n'+code)
        x=F(2**20000+1,2**19999+1);self.assertEqual(c.fraction(c.encode(x)),x)
if __name__=='__main__':unittest.main()
