import io
import json
import os
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import storage as s


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.old = self.root / 'old'
        self.out = self.root / 'new'
        self.old.mkdir(); self.out.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def budget(self, cap=10000, reserve=1000):
        return s.Budget([self.old, self.out], self.out,
                        ['a', 'b', 'FAILURE.json'], cap, reserve)

    def test_boundary_and_reserve(self):
        (self.old / 'certificate').write_bytes(b'x' * 40)
        b = self.budget(100, 10)
        b.bytes(self.out / 'a', b'x' * 50)
        with self.assertRaises(OSError): b.bytes(self.out / 'b', b'x')
        self.assertFalse((self.out / 'b').exists())
        b.bytes(self.out / 'FAILURE.json', b'1234567890', emergency=True)
        self.assertEqual(b.usage(), 100)

    def test_old_hardlinks_each_count(self):
        (self.old / 'a').write_bytes(b'abc')
        os.link(self.old / 'a', self.old / 'b')
        self.assertEqual(self.budget().usage(), 6)

    def test_roots_paths_and_collision(self):
        b = self.budget()
        for p in [self.out / '../bad', self.old / 'a', self.out / 'unknown']:
            with self.assertRaises(ValueError): b.bytes(p, b'a')
        b.bytes(self.out / 'a', b'a')
        with self.assertRaises(FileExistsError): b.bytes(self.out / 'a', b'a')
        with self.assertRaises(ValueError): s.Budget([self.root, self.out], self.out, ['a'])
        (self.old / 'link').symlink_to(self.out / 'a')
        with self.assertRaises(ValueError): b.usage()

    def test_absent_root_and_special(self):
        b = s.Budget([self.old, self.out, self.root / 'absent'], self.out, ['a'])
        self.assertEqual(b.usage(), 0)
        os.mkfifo(self.old / 'pipe')
        with self.assertRaises(ValueError): b.usage()

    def test_npz_bytes_and_members(self):
        z = {'float': np.array([0., -0., 1.e300]), 'bool': np.array([True, False]),
             'ints': np.arange(12, dtype=np.int64).reshape(3, 4)}
        before = {k: v.copy() for k, v in z.items()}
        old = io.BytesIO(); np.savez_compressed(old, **z)
        self.budget().npz(self.out / 'a', z)
        self.assertEqual((self.out / 'a').read_bytes(), old.getvalue())
        with np.load(self.out / 'a', allow_pickle=False) as f:
            self.assertEqual(f.files, list(z))
            for k in z:
                self.assertEqual(f[k].dtype, z[k].dtype)
                self.assertEqual(f[k].shape, z[k].shape)
                np.testing.assert_array_equal(f[k], z[k])
                np.testing.assert_array_equal(z[k], before[k])

    def test_csv_exact(self):
        frame = pd.DataFrame({'f': [0., -0., np.nan, np.inf, -np.inf, 1.e-300, 1.e300],
                              's': ['a,b', 'quote"', 'ü', 'a\nb', '', None, 'last']})
        frame.to_csv(self.old / 'reference', index=False, mode='x')
        self.budget().csv(self.out / 'a', frame)
        self.assertEqual((self.out / 'a').read_bytes(), (self.old / 'reference').read_bytes())

    def test_json_variants(self):
        def encode(v):
            return {'encoding': 'signed-hex-v1', 'numerator': format(v.numerator, 'x'),
                    'denominator': format(v.denominator, 'x')}
        codec = type('Codec', (), {'encode': staticmethod(encode)})
        obj = {'x': Fraction(-1, 7), 'zero': -0.0}
        self.budget().scalar(self.out / 'a', obj, codec)
        self.assertEqual((self.out / 'a').read_bytes(),
                         (json.dumps(obj, default=encode, indent=2, allow_nan=False) + '\n').encode())
        self.budget().json(self.out / 'b', {'ü': 1, 'a': -0.0})
        self.assertEqual((self.out / 'b').read_bytes(),
                         json.dumps({'ü': 1, 'a': -0.0}, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())

    def test_header_rewrite_and_partial_overflow(self):
        b = self.budget(100, 10)
        with b.binary(self.out / 'a') as f:
            f.write(b'x' * 80); f.seek(0); f.write(b'y' * 10)
            self.assertEqual(b.usage(), 80)
            f.seek(0, 2)
            with self.assertRaises(OSError): f.write(b'z' * 11)
            with self.assertRaises(ValueError): f.seek(100)
        self.assertEqual((self.out / 'a').stat().st_size, 80)

    def test_short_write(self):
        b = self.budget()
        with b.binary(self.out / 'a') as f:
            underlying = f.file
            class Short:
                def fileno(self): return underlying.fileno()
                def tell(self): return underlying.tell()
                def write(self, raw): return underlying.write(raw[:1])
                def flush(self): return underlying.flush()
                def close(self): return underlying.close()
            f.file = Short()
            with self.assertRaisesRegex(OSError, 'short write'): f.write(b'abcdef')
        self.assertEqual((self.out / 'a').read_bytes(), b'a')

    def test_interruption_and_fsync(self):
        b = self.budget()
        with self.assertRaises(KeyboardInterrupt):
            with b.binary(self.out / 'a') as f:
                f.write(b'partial'); raise KeyboardInterrupt()
        self.assertEqual(b.usage(), 7)
        with patch('storage.os.fsync', side_effect=OSError('synthetic fsync')):
            with self.assertRaises(OSError): b.bytes(self.out / 'b', b'retained')
        self.assertTrue((self.out / 'b').exists())

    def test_verify_mutation_growth(self):
        b = self.budget(100, 10); b.bytes(self.out / 'a', b'abc')
        (self.out / 'a').write_bytes(b'xyz')
        with self.assertRaises(ValueError): b.verify()
        (self.old / 'late').write_bytes(b'x' * 90)
        with self.assertRaises(OSError): b.verify()

    def test_bounded_failure_no_repr(self):
        class Bad(Exception):
            def __repr__(self): raise AssertionError('must not stringify')
        v = s.failure_payload({'phase': 'score'}, Bad(), {'a': 'x'}, [None] * 2000)
        self.assertLess(len(json.dumps(v)), 1024)
        self.assertFalse(v['access_ledger_complete'])

    def test_prewrite_before_actual_write(self):
        b = self.budget(100, 10)
        with b.binary(self.out / 'a') as f:
            underlying = f.file
            class Spy:
                def fileno(self): return underlying.fileno()
                def tell(self): return underlying.tell()
                def write(self, raw): raise AssertionError('write must not occur')
                def flush(self): return underlying.flush()
                def close(self): return underlying.close()
            f.file = Spy()
            with self.assertRaises(OSError): f.write(b'x' * 91)

    def test_actual_csv_npz_overflow_retained(self):
        b = self.budget(200, 100)
        with self.assertRaises(OSError):
            b.csv(self.out / 'a', pd.DataFrame({'x': ['abc' * 100]}))
        self.assertTrue((self.out / 'a').exists())
        self.assertLessEqual(b.usage(), 100)
        with self.assertRaises(OSError): b.npz(self.out / 'b', {'x': np.arange(100)})
        self.assertTrue((self.out / 'b').exists())
        self.assertLessEqual(b.usage(), 100)

    def test_no_serialization_failure_creates_json(self):
        b = self.budget()
        with self.assertRaises(ValueError): b.json(self.out / 'a', {'x': float('nan')})
        self.assertFalse((self.out / 'a').exists())

    def test_reserve_handles_failed_ledger(self):
        b = self.budget(2048, 1024)
        with self.assertRaises(OSError): b.json(self.out / 'a', list(range(10000)))
        self.assertFalse((self.out / 'a').exists())
        payload = s.failure_payload({'phase': 'assess'}, OSError(), {}, list(range(10000)))
        b.json(self.out / 'FAILURE.json', payload, emergency=True)
        self.assertLess(b.usage(), 1024)


if __name__ == '__main__': unittest.main()
