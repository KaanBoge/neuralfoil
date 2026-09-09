"""Manufactured byte fixtures only; no project evidence is loaded."""
import copy
import hashlib
import io
import json
from pathlib import Path
import signal
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import verify_saved_evidence as v


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.archive = self.root / 'manufactured.zip'
        self.content = b'Synthetic\x00opaque bytes.' * 300
        self.manifest = {'schema': 'v9-saved-evidence-1', 'selection_sha256': 'a' * 64,
                         'claim': 'SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE',
                         'files': {'evidence/a.bin': {'bytes': len(self.content), 'sha256': sha(self.content)}}}

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, manifest=None, rows=None):
        raw = json.dumps(self.manifest if manifest is None else manifest).encode()
        if rows is None:
            rows = [('evidence/a.bin', self.content, stat.S_IFREG | 0o644)]
        with zipfile.ZipFile(self.archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('MANIFEST.json', raw)
            for name, value, mode in rows:
                item = zipfile.ZipInfo(name)
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = mode << 16
                z.writestr(item, value)
        return sha(self.archive.read_bytes()), sha(raw)

    def test_roundtrip_without_execution_or_writes(self):
        a, m = self.create()
        original = self.archive.read_bytes()
        result = v.verify(self.archive, a, m)
        self.assertEqual(result['status'], 'PASS_SAVED_FILE_INTEGRITY')
        self.assertFalse(result['scientific_code_executed'])
        self.assertEqual(self.archive.read_bytes(), original)
        self.assertEqual(set(p.name for p in self.root.iterdir()), {'manufactured.zip'})

    def test_archive_and_manifest_tamper(self):
        a, m = self.create()
        for ah, mh in [('0' * 64, m), (a, '0' * 64)]:
            with self.assertRaises(ValueError):
                v.verify(self.archive, ah, mh)

    def test_member_content_tamper(self):
        a, m = self.create(rows=[('evidence/a.bin', b'X' * len(self.content), stat.S_IFREG)])
        with self.assertRaisesRegex(ValueError, 'content mismatch'):
            v.verify(self.archive, a, m)

    def test_extracted_actual_disk_and_mutation(self):
        a, m = self.create()
        extracted = self.root / 'payload'
        (extracted / 'evidence').mkdir(parents=True)
        (extracted / 'MANIFEST.json').write_bytes(json.dumps(self.manifest).encode())
        (extracted / 'evidence/a.bin').write_bytes(self.content)
        (extracted / 'unrelated.txt').write_text('Intentionally outside selected inventory')
        result = v.verify(self.archive, a, m, extracted)
        self.assertTrue(result['extra_extracted_files_not_checked'])
        (extracted / 'evidence/a.bin').write_bytes(b'X' * len(self.content))
        with self.assertRaisesRegex(ValueError, 'Extracted content mismatch'):
            v.verify(self.archive, a, m, extracted)

    def test_traversal_duplicate_symlink_and_extra(self):
        for rows in [[('../escape', b'x', stat.S_IFREG)],
                     [('evidence/a.bin', self.content, stat.S_IFLNK | 0o777)],
                     [('evidence/a.bin', self.content, stat.S_IFREG), ('extra', b'x', stat.S_IFREG)],
                     [('evidence/a.bin', self.content, stat.S_IFREG), ('EVIDENCE/A.BIN', b'x', stat.S_IFREG)]]:
            a, m = self.create(rows=rows)
            with self.assertRaises(ValueError):
                v.verify(self.archive, a, m)

    def test_nonadjacent_parent_collision(self):
        rows = [(n, b'x', stat.S_IFREG) for n in ['foo', 'foo-bar', 'foo/a']]
        a, m = self.create(rows=rows)
        with self.assertRaisesRegex(ValueError, 'File-directory collision'):
            v.verify(self.archive, a, m)

    def test_lying_eocd_count(self):
        self.create()
        data = bytearray(self.archive.read_bytes())
        struct.pack_into('<HH', data, len(data) - 14, 1, 1)
        self.archive.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'count disagreement'):
            v.central_directory(self.archive, lambda: None)

    def test_preallocation_directory_cap(self):
        self.create()
        with patch.object(v, 'MAX_FILES', 0):
            with self.assertRaises(ValueError):
                v.central_directory(self.archive, lambda: None)

    def test_typed_size_and_scope(self):
        for value in [True, -1, 1.0, v.MAX_EXPANDED + 1]:
            m = copy.deepcopy(self.manifest)
            m['files']['evidence/a.bin']['bytes'] = value
            a, h = self.create(m)
            with self.assertRaises(ValueError):
                v.verify(self.archive, a, h)
        m = copy.deepcopy(self.manifest)
        m['claim'] = 'UNIVERSAL_ACCURACY'
        a, h = self.create(m)
        with self.assertRaises(ValueError):
            v.verify(self.archive, a, h)

    def test_deadline_restores_timer(self):
        a, m = self.create()
        prior = signal.getsignal(signal.SIGALRM)
        with patch.object(v, 'MAX_SECONDS', 0):
            with self.assertRaises(TimeoutError):
                v.verify(self.archive, a, m)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.assertEqual(signal.getsignal(signal.SIGALRM), prior)

    def test_stream_overrun_and_bad_json(self):
        with self.assertRaises(ValueError):
            v.stream_hash(io.BytesIO(b'abcd'), 3, lambda: None)
        with self.assertRaises(ValueError):
            v.unique_pairs([('a', 1), ('a', 2)])

    def test_symlink_extracted_member(self):
        a, m = self.create()
        extracted = self.root / 'payload'
        (extracted / 'evidence').mkdir(parents=True)
        (extracted / 'MANIFEST.json').write_bytes(json.dumps(self.manifest).encode())
        original = self.root / 'original.bin'
        original.write_bytes(self.content)
        (extracted / 'evidence/a.bin').symlink_to(original)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            v.verify(self.archive, a, m, extracted)


if __name__ == '__main__':
    unittest.main()
