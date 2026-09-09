"""Only manufactured paths and metadata; no project evidence intake."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import prepare_v6 as p
import plan_inventory as plan

class Tests(unittest.TestCase):
    def row(self):return {'source':'a.txt','target':'evidence/a.txt','role':'scientific_evidence','sha256':'a'*64,'bytes':1}
    def test_paths(self):
        for s in ['../x','/x','a/../b','a\\b','a:b','a//b','a\nx']:
            with self.assertRaises(ValueError):p.safe(s)
    def test_scopes(self):
        for s in ['eight_tree_plan/a','eight-tree/a','x/Volume4/a','x/sealed/a','x/.venv/a','x/conda_live/a']:
            with self.assertRaises(ValueError):p.permitted(s)
        for s in ['x/all_context_plan/a','x/downstream/a','x/conda_create.json','historical/v4/evidence/a']:p.permitted(s)
    def test_collision(self):
        for t in ['evidence/A.txt','evidence/a.txt/child']:
            rows=[self.row(),{**self.row(),'target':t}]
            with self.assertRaises(ValueError):p.validate_records(rows)
    def test_reserved(self):
        with self.assertRaises(ValueError):p.validate_records([{**self.row(),'target':'MANIFEST.json'}])
    def test_size(self):
        for n in [-1,True,1.0,p.PAYLOAD_CAP+1]:
            with self.assertRaises(ValueError):p.validate_records([{**self.row(),'bytes':n}])
        p.validate_records([self.row()])
    def test_json(self):
        for s in ['{"a":1,"a":2}','{"a":NaN}']:
            with self.assertRaises(ValueError):p.parse(s)
    def test_bad_pin(self):
        for h in ['a'*63,'G'*64,None]:
            with self.assertRaises(ValueError):p.pin(h)
    def test_authorization_before_payload(self):
        with tempfile.TemporaryDirectory() as t:
            with patch.object(p.Reads,'json',side_effect=ValueError('missing root approval')) as mock:
                with self.assertRaises(ValueError):p.prepare(Path(t).resolve(),'approval.json','a'*64,'inventory.json')
                self.assertEqual(mock.call_count,1)
    def test_refuses_existing(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t,'inventory.json').write_text('old')
            with patch.object(p.Reads,'json') as mock:
                with self.assertRaises(FileExistsError):p.prepare(Path(t).resolve(),'approval.json','a'*64,'inventory.json')
                mock.assert_not_called()
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();(root/'real').mkdir();(root/'link').symlink_to(root/'real',target_is_directory=True)
            with self.assertRaises(ValueError):p.path(root,'link/new')
    def test_end_reauthentication(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();f=root/'a';f.write_bytes(b'a');r=p.Reads(root);r.check('a',p.digest(b'a'));f.write_bytes(b'b')
            with self.assertRaises(ValueError):r.end()
    def test_pointer_escaping(self):self.assertEqual(plan.pointer({'x/y':{'~':7}},'/x~1y/~0'),7)
    def test_fixed_contract(self):
        self.assertEqual(p.COUNTS,{'main':[17,133,4,4],'supplement':[43,343,44,2],'references':23})
        self.assertEqual(len(p.ARCHIVES),8);self.assertEqual(p.CAP,512*1024**2)

if __name__=='__main__':unittest.main()
