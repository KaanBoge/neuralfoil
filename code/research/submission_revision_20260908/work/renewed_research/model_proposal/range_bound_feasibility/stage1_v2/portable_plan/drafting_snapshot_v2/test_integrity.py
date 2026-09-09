"""Synthetic-only export-integrity tests; no real project input or replay."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import numpy as np
import integrity as x

class Integrity(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def build(self):
        p=self.root/'synthetic.zip';r=x.build_private_zip({'README.md':b'private synthetic test','arrays/a.bin':b'123'},p)
        return p,r
    def test_roundtrip(self):
        p,r=self.build();out=x.extract_verified(p,r['archive_sha256'],r['manifest_sha256'],self.root/'extract')
        self.assertEqual((out/'arrays/a.bin').read_bytes(),b'123')
    def test_paths(self):
        for name in ['../x','/x','a/../x','a//b','a\\b','C:x','a\nx','a/./b','','.']:
            with self.assertRaises(ValueError):x.member_name(name)
    def test_collision(self):
        for names in [['A','a'],['a','a/b']]:
            with self.assertRaises(ValueError):x.names_ok(names)
    def test_reserved_manifest(self):
        with self.assertRaises(ValueError):x.build_private_zip({'manifest.json':b'bad'},self.root/'x.zip')
    def test_wrong_hash_no_extract(self):
        p,r=self.build();out=self.root/'extract'
        with self.assertRaises(ValueError):x.extract_verified(p,'0'*64,r['manifest_sha256'],out)
        self.assertFalse(out.exists())
    def test_wrong_manifest_no_extract(self):
        p,r=self.build();out=self.root/'extract'
        with self.assertRaises(ValueError):x.extract_verified(p,r['archive_sha256'],'0'*64,out)
        self.assertFalse(out.exists())
    def test_overwrite(self):
        p,r=self.build();before=p.read_bytes()
        with self.assertRaises(FileExistsError):x.build_private_zip({'x':b'new'},p)
        self.assertEqual(p.read_bytes(),before)
        out=self.root/'existing';out.mkdir()
        with self.assertRaises(FileExistsError):x.extract_verified(p,r['archive_sha256'],r['manifest_sha256'],out)
    def test_symlink_ancestor(self):
        real=self.root/'real';real.mkdir();link=self.root/'link';link.symlink_to(real,target_is_directory=True)
        with self.assertRaises(ValueError):x.build_private_zip({'x':b'new'},link/'x.zip')
    def test_object_npz(self):
        stream=io.BytesIO();np.savez(stream,x=np.array([object()],dtype=object))
        with self.assertRaises(ValueError):x.inspect_safe_npz(stream.getvalue(),['x'])
    def test_safe_npz_schema(self):
        stream=io.BytesIO();np.savez(stream,x=np.array([1.,2.]),ids=np.array(['a','b']))
        info=x.inspect_safe_npz(stream.getvalue(),['x','ids']);self.assertEqual(info['x']['shape'],[2])
        with self.assertRaises(ValueError):x.inspect_safe_npz(stream.getvalue(),['x'])
    def test_payload_manifest_mismatch(self):
        p,r=self.build()
        with zipfile.ZipFile(p) as z:data={k:z.read(k) for k in z.namelist()}
        data['arrays/a.bin']=b'corrupt';stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for k,v in data.items():z.writestr(k,v)
        bad=self.root/'bad.zip';bad.write_bytes(stream.getvalue())
        with self.assertRaises(ValueError):x.verified_members(bad,x.sha(bad.read_bytes()),r['manifest_sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
