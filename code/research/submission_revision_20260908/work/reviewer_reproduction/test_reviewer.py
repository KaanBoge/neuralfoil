"""Synthetic wrapper tests only: no project labels, forward inference, or fitting."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
import reviewer as r


class ReviewerTests(unittest.TestCase):
    def archive(self, root, extra=None):
        path = root / 'test.zip'
        data = b'fixed synthetic data'
        manifest = {'files': {'data.txt': r.sha_bytes(data)}}
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('fixture/data.txt', data)
            z.writestr('fixture/manifest.json', json.dumps(manifest))
            if extra:
                z.writestr(extra, b'x')
        return path

    def test_valid_archive_and_hash_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.archive(Path(tmp))
            self.assertEqual(r.authenticate_archive(path, r.sha(path), 'fixture', 'manifest.json')['files_checked'], 1)
            with self.assertRaises(ValueError):
                r.authenticate_archive(path, '0' * 64, 'fixture', 'manifest.json')

    def test_internal_hash_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('fixture/data.txt', b'changed')
                z.writestr('fixture/manifest.json', json.dumps({'files': {'data.txt': '0' * 64}}))
            with self.assertRaises(ValueError):
                r.authenticate_archive(path, r.sha(path), 'fixture', 'manifest.json')

    def test_unsafe_and_unmanifested_members(self):
        for name in ['../escape', '/absolute', 'fixture/../escape', 'fixture/extra', 'C:/bad', 'fixture\\bad']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = self.archive(Path(tmp), name)
                with self.assertRaises(ValueError):
                    r.authenticate_archive(path, r.sha(path), 'fixture', 'manifest.json')

    def test_output_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'new'
            r.new_directory(path)
            with self.assertRaises(ValueError):
                r.new_directory(path)
            f = path / 'report.json'
            r.write_json(f, {'original': True})
            with self.assertRaises(FileExistsError):
                r.write_json(f, {'overwritten': True})
            self.assertEqual(json.loads(f.read_text()), {'original': True})

    def comparisons(self):
        return {'comparisons': [{'cohort': list(r.COHORTS)[i % 3], 'stage': 'synthetic', 'key': str(i),
                                'unequal_elements': 0, 'max_abs_difference': 0.0} for i in range(55)]}

    def test_exact_parity_and_mismatch_rejection(self):
        result = self.comparisons()
        self.assertEqual(r.check_feature_parity(result)['status'], 'PASS')
        for key, value in [('unequal_elements', 1), ('max_abs_difference', 1e-20),
                           ('max_abs_difference', float('nan')), ('max_abs_difference', float('inf'))]:
            bad = copy.deepcopy(result)
            bad['comparisons'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                r.check_feature_parity(bad)
        with self.assertRaises(ValueError):
            r.check_feature_parity({'comparisons': result['comparisons'][:-1]})
        bad = copy.deepcopy(result)
        bad['comparisons'][1] = bad['comparisons'][0]
        with self.assertRaises(ValueError):
            r.check_feature_parity(bad)

    def arrays(self):
        return {k: np.ones((2, 62) if k == 'X62' else ((2, 8) if k == 'all_model_CD' else (2,)), dtype='float64') for k in r.KEYS}

    def test_exact_bridge_and_reject_value_shape_dtype_nonfinite(self):
        good = self.arrays()
        r.check_arrays(good, copy.deepcopy(good), 2)
        for kind in ['value', 'shape', 'dtype', 'nan']:
            bad = copy.deepcopy(good)
            if kind == 'value': bad['X62'][0, 0] = np.nextafter(1., 2.)
            if kind == 'shape': bad['X62'] = bad['X62'][:1]
            if kind == 'dtype': bad['X62'] = bad['X62'].astype('float32')
            if kind == 'nan': bad['X62'][0, 0] = np.nan
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                r.check_arrays(bad, good, 2)

    def test_extracts_only_authenticated_relative_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'archives').mkdir()
            path = self.archive(root / 'archives')
            original = r.ARCHIVES
            r.ARCHIVES = {'test.zip': ('fixture', 'manifest.json')}
            try:
                destination = r.new_directory(root / 'extracted')
                r.extract_authenticated(root, destination, {'archives': {'test.zip': {'sha256': r.sha(path)}}})
                self.assertEqual((destination / 'fixture/data.txt').read_bytes(), b'fixed synthetic data')
                with self.assertRaises(FileExistsError):
                    r.extract_authenticated(root, destination, {'archives': {'test.zip': {'sha256': r.sha(path)}}})
            finally:
                r.ARCHIVES = original


if __name__ == '__main__':
    unittest.main()
