"""Synthetic repositories only: python -B -m unittest discover -s tests -p test_source_catalog.py."""
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_source_catalog import CATALOG, EXTENSIONS, FILENAMES, catalog, encode, git, role
from verify_source_catalog import verify


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name).resolve()
        git(self.repo, 'init', '-q')

    def tearDown(self):
        self.temp.cleanup()

    def put(self, path, data=b'x\n', stage=True):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if stage:
            git(self.repo, 'add', '--', path)

    def publish(self):
        self.put(CATALOG, encode(catalog(self.repo)))

    def test_complete_deterministic_extensions_and_directories(self):
        for i, ext in enumerate(EXTENSIONS):
            self.put(f'vendor/dependencies/.hidden/f{i}{ext.upper()}', bytes([i]))
        self.put('README.md', b'not source')
        self.put('untracked.py', stage=False)
        first = catalog(self.repo)
        self.assertEqual(len(first['files']), len(EXTENSIONS))
        self.assertEqual(first, catalog(self.repo))
        self.assertEqual(first['excluded_source_paths'], [])
        self.publish()
        self.assertEqual(verify(self.repo), len(EXTENSIONS))

    def test_index_not_unstaged_bytes(self):
        self.put('a.py', b'original')
        self.put('a.py', b'edited', stage=False)
        self.assertEqual(catalog(self.repo)['files'][0]['sha256'], hashlib.sha256(b'original').hexdigest())
        self.publish()
        with self.assertRaises(subprocess.CalledProcessError):
            verify(self.repo)

    def test_stale_missing_and_tampered(self):
        self.put('a.py')
        self.publish()
        self.put('b.js')
        with self.assertRaises(ValueError):
            verify(self.repo)
        self.publish()
        self.assertEqual(verify(self.repo), 2)
        self.put(CATALOG, b'{}\n')
        with self.assertRaises(ValueError):
            verify(self.repo)

    def test_unusual_filename(self):
        self.put('code/research/a\t space\nü.PY', b'\0\xff')
        self.publish()
        self.assertEqual(verify(self.repo), 1)

    def test_assume_unchanged_cannot_hide_source_edit(self):
        self.put('a.py', b'original')
        self.publish()
        git(self.repo, 'update-index', '--assume-unchanged', 'a.py')
        self.put('a.py', b'changed!', stage=False)
        with self.assertRaises(ValueError):
            verify(self.repo)

    def test_counts_and_exact_hash(self):
        self.put('a.py', b'123')
        self.put('b.PY', b'45')
        self.put('index.html', b'6')
        value = catalog(self.repo)
        self.assertEqual(value['counts'], {'files': 3, 'bytes': 6,
                         'by_language': {'Python': {'files': 2, 'bytes': 5},
                                         'HTML': {'files': 1, 'bytes': 1}}})
        self.assertEqual(value['files'][0]['sha256'], hashlib.sha256(b'123').hexdigest())

    def test_build_names_and_configuration(self):
        for index, name in enumerate(FILENAMES):
            # Distinct folders also exercise case-sensitive names on macOS volumes.
            self.put(f'third_party/{index}/' + name)
        self.put('.github/workflows/check.YML')
        self.put('config.yaml')
        self.put('cmake/a.cmake')
        self.put('not-selected/MAKEFILE')
        value = catalog(self.repo)
        self.assertEqual(len(value['files']), len(FILENAMES) + 3)
        self.assertTrue(all(row['role'] == 'build/configuration' for row in value['files']))
        self.publish()
        self.assertEqual(verify(self.repo), len(FILENAMES) + 3)

    def test_symlink_rejected(self):
        self.put('target.txt')
        (self.repo / 'alias.py').symlink_to('target.txt')
        git(self.repo, 'add', 'alias.py')
        with self.assertRaises(ValueError):
            catalog(self.repo)

    def test_submodule_rejected(self):
        tree = git(self.repo, 'mktree', input=b'').decode().strip()
        # A fixed manufactured commit object avoids user identity/config dependence.
        commit = git(self.repo, 'hash-object', '-t', 'commit', '-w', '--stdin',
                     input=f'tree {tree}\nauthor Test <test@example.invalid> 0 +0000\ncommitter Test <test@example.invalid> 0 +0000\n\nfixture\n'.encode()).decode().strip()
        git(self.repo, 'update-index', '--add', '--cacheinfo', f'160000,{commit},opaque')
        with self.assertRaises(ValueError):
            catalog(self.repo)

    def test_roles(self):
        for path, expected in [('code/research/a.py', 'research archive'),
                               ('code/additional/a.py', 'supplementary research source'),
                               ('tools/a.py', 'public checks/utilities'),
                               ('study/a.py', 'historical study source'),
                               ('index.html', 'embedded-data HTML/report'),
                               ('research.js', 'browser UI')]:
            self.assertEqual(role(path), expected)


if __name__ == '__main__':
    unittest.main()
