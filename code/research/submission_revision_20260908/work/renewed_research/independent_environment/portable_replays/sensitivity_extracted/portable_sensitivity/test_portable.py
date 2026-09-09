"""Synthetic integrity/attempt-boundary tests; no empirical inputs or fits."""
from pathlib import Path
import json,tempfile,unittest
import replay

class Integrity(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix='nf-sensitivity-negative-');self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);(self.root/'sample.txt').write_text('synthetic')
        self.freeze()
    def freeze(self):
        (self.root/'manifest.json').write_text(json.dumps({'schema':replay.EXPECTED_SCHEMA,'files':{'sample.txt':replay.sha(self.root/'sample.txt')}}))
        self.digest=replay.sha(self.root/'manifest.json')
    def test_success(self):self.assertEqual(len(replay.authenticate(self.root,self.digest)['files']),1)
    def test_payload_mutation(self):
        (self.root/'sample.txt').write_text('tamper')
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.digest)
    def test_manifest_mutation(self):
        (self.root/'manifest.json').write_text('{}')
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.digest)
    def test_unlisted_file(self):
        (self.root/'extra').write_text('x')
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.digest)
    def test_symlink(self):
        (self.root/'link').symlink_to(self.root/'sample.txt')
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.digest)
    def test_paths(self):
        for name in ['../x','/x','a//b','./x','C:/x','a\\b']:
            with self.subTest(name=name),self.assertRaises(ValueError):replay.safe(name)
    def test_duplicate_json(self):
        with self.assertRaises(ValueError):replay.unique([('x',1),('x',2)])
    def test_existing_output_preserved(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with self.assertRaises(FileExistsError):replay.run(self.root,'0'*64)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})

if __name__=='__main__':unittest.main(verbosity=2)
