"""Manufactured integrity fixtures only, no research imports."""
import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('supplement_verifier',Path(__file__).resolve().parents[1]/'tools/verify_source_supplement.py')
V=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(V)

class SourceSupplementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.path=self.root/'code/supplement/example.py';self.path.parent.mkdir(parents=True)
        self.path.write_bytes(b'x = 1\n')
        self.m={'schema':'reviewed-source-supplement-v1','file_count':1,'files':[{'target':'code/supplement/example.py','published_sha256':hashlib.sha256(self.path.read_bytes()).hexdigest(),'published_bytes':6}]}
        self.save()
    def tearDown(self):self.tmp.cleanup()
    def save(self):(self.root/'code/supplement-manifest.json').write_text(json.dumps(self.m))
    def test_valid(self):self.assertEqual(V.verify(self.root),1)
    def test_mutation(self):
        self.path.write_bytes(b'x = 2\n')
        with self.assertRaises(ValueError):V.verify(self.root)
    def test_unlisted(self):
        (self.path.parent/'extra.py').write_bytes(b'')
        with self.assertRaises(ValueError):V.verify(self.root)
    def test_escape(self):
        self.m['files'][0]['target']='code/supplement/../escape.py';self.save()
        with self.assertRaises(ValueError):V.verify(self.root)
    def test_symlink(self):
        self.path.unlink();self.path.symlink_to(self.root/'absent.py')
        with self.assertRaises(ValueError):V.verify(self.root)
    def test_count(self):
        self.m['file_count']=2;self.save()
        with self.assertRaises(ValueError):V.verify(self.root)

if __name__=='__main__':unittest.main()
