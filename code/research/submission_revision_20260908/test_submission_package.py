"""Synthetic temporary-file tests, without study data or model execution."""
from pathlib import Path
import json
import tempfile
import unittest
import verify_submission_package as v


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='nf-package-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = self.root / 'example.txt'
        p.write_text('synthetic test only\n')
        self.files = {'example.txt': {'bytes': p.stat().st_size, 'sha256': v.sha(p)}}
        self.freeze()

    def freeze(self):
        p = self.root / 'MANIFEST.json'
        p.write_text(json.dumps({'schema': 'neuralfoil_private_submission_v1', 'files': self.files}))
        self.digest = v.sha(p)

    def test_success(self):
        self.assertEqual(v.verify(self.root, self.digest)['files_authenticated'], 1)

    def test_mutation_rejected(self):
        (self.root / 'example.txt').write_text('modified')
        with self.assertRaises(ValueError): v.verify(self.root, self.digest)

    def test_missing_rejected(self):
        (self.root / 'example.txt').unlink()
        with self.assertRaises(ValueError): v.verify(self.root, self.digest)

    def test_unlisted_rejected(self):
        (self.root / 'extra.txt').write_text('extra')
        with self.assertRaises(ValueError): v.verify(self.root, self.digest)

    def test_bad_digest_rejected(self):
        with self.assertRaises(ValueError): v.verify(self.root, '0' * 64)

    def test_symlink_rejected(self):
        (self.root / 'link.txt').symlink_to(self.root / 'example.txt')
        with self.assertRaises(ValueError): v.verify(self.root, self.digest)

    def test_unsafe_names_rejected(self):
        for name in ['../escape', '/absolute', 'C:/drive', 'a\\b', 'a//b', './a']:
            with self.subTest(name=name), self.assertRaises(ValueError): v.safe_name(name)

    def test_duplicate_manifest_key_rejected(self):
        p = self.root / 'MANIFEST.json'
        p.write_text('{"schema":"neuralfoil_private_submission_v1","files":{},"files":{}}')
        with self.assertRaises(ValueError): v.verify(self.root, v.sha(p))


if __name__ == '__main__':
    unittest.main()
