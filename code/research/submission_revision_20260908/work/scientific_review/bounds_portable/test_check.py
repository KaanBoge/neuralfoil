import hashlib, json, tempfile, unittest
from pathlib import Path
import numpy as np
from check import floor_bound, verify, rational_matches
from fractions import Fraction as F

class Tests(unittest.TestCase):
    def test_floor_exact(self):
        z={'BASE_CD':np.ones(9),'MEAS_CD':np.arange(9,dtype=float),'group':np.arange(9)}
        self.assertEqual(floor_bound(z),(9,9,F(6)))
    def test_nonpositive_base(self):
        with self.assertRaises(ValueError):floor_bound({'BASE_CD':np.zeros(9),'MEAS_CD':np.ones(9),'group':np.arange(9)})
    def test_exact_rational_not_display(self):
        with self.assertRaises(ValueError):rational_matches(F(1,3),{'numerator':'2','denominator':'6'})
    def test_manifest_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json';p.write_text('{}')
            h=hashlib.sha256(p.read_bytes()).hexdigest();p.write_text('{ }')
            with self.assertRaisesRegex(ValueError,'manifest authentication'):verify(d,h)
    def test_payload_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'payload';p.write_bytes(b'original')
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            m=root/'manifest.json';m.write_text(json.dumps({'files':{'payload':h}}))
            trusted=hashlib.sha256(m.read_bytes()).hexdigest();p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'file authentication'):verify(d,trusted)
    def test_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json';p.write_text(json.dumps({'files':{'../outside':'0'*64}}))
            with self.assertRaisesRegex(ValueError,'unsafe'):verify(d,hashlib.sha256(p.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
