"""Synthetic large-rational codec checks only; preserves Python's integer limit."""
from fractions import Fraction as F
from pathlib import Path
import json
import sys
import tempfile
import unittest
import run_stage1 as r

class Serialization(unittest.TestCase):
    def test_large_signed_roundtrip(self):
        before=sys.get_int_max_str_digits()
        # Over 4,300 decimal digits; construction/hex conversion requires no limit change.
        for value in [F(10**5001+1,2**18000+1),-F(10**5001+1,2**18000+1),F(0)]:
            record=r.encode(value)
            self.assertEqual(record['encoding'],'signed-hex-v1')
            self.assertEqual(r.fraction(json.loads(json.dumps(record))),value)
        self.assertEqual(sys.get_int_max_str_digits(),before)
    def test_legacy_decimal(self):
        for v in [F(0),F(-7,13),F(1,2**256)]:
            self.assertEqual(r.fraction({'numerator':str(v.numerator),'denominator':str(v.denominator)}),v)
    def test_noncanonical_hex(self):
        valid={'encoding':'signed-hex-v1','numerator':'-a','denominator':'b'}
        self.assertEqual(r.fraction(valid),F(-10,11))
        bad=[{'numerator':s} for s in ['-0','00','+a','A','0xa',' a','a\n','-00','']]
        bad += [{'denominator':s} for s in ['0','-b','+b','0b','B',' b','b\n','']]
        bad += [{'encoding':'hex'},{'extra':'x'},{'numerator':1},{'denominator':11},
                {'numerator':'2','denominator':'4'}]
        for replacement in bad:
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):r.fraction(valid|replacement)
    def test_noncanonical_legacy(self):
        for record in [{'numerator':'01','denominator':'2'}, {'numerator':'-0','denominator':'1'},
                       {'numerator':'2','denominator':'4'}, {'numerator':'1','denominator':'0'},
                       {'numerator':'1','denominator':'-2'}]:
            with self.assertRaises(ValueError):r.fraction(record)
    def test_no_partial_file(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'must_not_exist.json'
            with self.assertRaises(TypeError):r.write_json(path,{'valid':F(1,3),'bad':object()})
            self.assertFalse(path.exists())
            with self.assertRaises(ValueError):r.write_json(path,{'bad':float('nan')})
            self.assertFalse(path.exists())
    def test_no_overwrite_large_file(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'rational.json';v=F(10**5001+1,2**18000+1)
            r.write_json(path,{'value':v});before=path.read_bytes()
            self.assertEqual(r.fraction(json.loads(before)['value']),v)
            with self.assertRaises(FileExistsError):r.write_json(path,{'value':F(1)})
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main(verbosity=2)
