"""Negative tests against minimal package fixtures, no experiment/calibration."""
import json,tempfile,unittest
from pathlib import Path
import replay


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'package';self.root.mkdir()
        (self.root/'member.txt').write_bytes(b'original')
        self.manifest={'schema':'private_incremental_replay_v1','members':{'member.txt':replay.digest(b'original')}}
        self.pin=self.write()
    def tearDown(self):self.tmp.cleanup()
    def write(self):
        b=json.dumps(self.manifest).encode();(self.root/'manifest.json').write_bytes(b);return replay.digest(b)
    def test_valid(self):self.assertEqual(replay.authenticate(self.root,self.pin)[1]['member.txt'],b'original')
    def test_wrong_manifest(self):
        with self.assertRaises(ValueError):replay.authenticate(self.root,'0'*64)
    def test_modified_member(self):
        (self.root/'member.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.pin)
    def test_missing_member(self):
        (self.root/'member.txt').unlink()
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.pin)
    def test_traversal(self):
        self.manifest['members']={'../member.txt':'0'*64};pin=self.write()
        with self.assertRaises(ValueError):replay.authenticate(self.root,pin)
    def test_absolute_member(self):
        self.manifest['members']={'/member.txt':'0'*64};pin=self.write()
        with self.assertRaises(ValueError):replay.authenticate(self.root,pin)
    def test_symlink(self):
        p=self.root/'member.txt';p.unlink();other=Path(self.tmp.name)/'other';other.write_bytes(b'original');p.symlink_to(other)
        with self.assertRaises(ValueError):replay.authenticate(self.root,self.pin)
    def test_read_once_snapshot(self):
        _,buffers=replay.authenticate(self.root,self.pin);(self.root/'member.txt').write_bytes(b'changed')
        self.assertEqual(buffers['member.txt'],b'original')
    def test_refuse_overwrite(self):
        out=Path(self.tmp.name)/'out';replay.reserve_output(out,self.root)
        with self.assertRaises(FileExistsError):replay.reserve_output(out,self.root)
    def test_refuse_package_output(self):
        with self.assertRaises(ValueError):replay.reserve_output(self.root/'out',self.root)


if __name__=='__main__':unittest.main(verbosity=2)
