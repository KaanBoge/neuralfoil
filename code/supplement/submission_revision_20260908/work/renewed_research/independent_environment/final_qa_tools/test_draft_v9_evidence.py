import tempfile,unittest
from pathlib import Path
import draft_v9_evidence as d
class Tests(unittest.TestCase):
    def test_metadata_only_and_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();(root/'x.json').write_text('{}');a=d.Draft(root)
            a.read('x.json',d.digest(b'{}'))
            for n in ['x.npz','x.csv','x.pkl','../escape.json']:
                with self.assertRaises(ValueError):a.read(n)
            (root/'x.json').write_text('{"changed":true}')
            with self.assertRaises(ValueError):a.finish()
    def test_map_schema(self):
        a=d.Draft(Path('.'));e={}
        a.maps(e,{'outputs':{'file':'a'*64}},[('outputs','base')])
        self.assertEqual(e['maps'],[{'pointer':'/outputs','base':'base'}])
        for obj in [{},{'alias':{'path':'file','sha256':'a'*64}}]:
            with self.assertRaises(ValueError):a.maps({}, {'outputs':obj}, [('outputs','base')])
    def test_pointer_alias(self):self.assertEqual(d.pointer('a/b~c'),'a~1b~0c')
    def test_source_has_no_discovery_or_scientific_reader(self):
        text=Path(d.__file__).read_text()
        for forbidden in ['.glob(','.rglob(','np.load','read_csv','pickle.load','subprocess']:
            self.assertNotIn(forbidden,text)
if __name__=='__main__':unittest.main()
