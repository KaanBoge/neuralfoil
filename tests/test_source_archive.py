"""Integrity checks only; never discover or import archived research tests."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('source_verifier', ROOT / 'tools/verify_source_archive.py')
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class SourceArchive(unittest.TestCase):
    def test_real_manifest(self):
        self.assertGreater(verifier.verify(ROOT), 0)

    def test_rejects_mutation_extra_file_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'code/research'
            folder.mkdir(parents=True)
            source = folder / 'synthetic.py'
            raw = b'# artificial source integrity fixture\n'
            source.write_bytes(raw)
            entry = {'target': 'code/research/synthetic.py',
                     'published_sha256': hashlib.sha256(raw).hexdigest(),
                     'published_bytes': len(raw)}
            manifest = root / 'code/research-manifest.json'
            manifest.write_text(json.dumps({'file_count': 1, 'files': [entry]}))
            self.assertEqual(verifier.verify(root), 1)
            source.write_bytes(raw + b'# changed\n')
            with self.assertRaises(ValueError):
                verifier.verify(root)
            source.write_bytes(raw)
            extra = folder / 'unexpected.txt'
            extra.write_text('artificial extra member')
            with self.assertRaises(ValueError):
                verifier.verify(root)
            extra.unlink()
            entry['target'] = 'code/research/../../escape.py'
            manifest.write_text(json.dumps({'file_count': 1, 'files': [entry]}))
            with self.assertRaises(ValueError):
                verifier.verify(root)


if __name__ == '__main__':
    unittest.main()
