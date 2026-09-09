"""Independent manufactured negatives; never enumerate actual payloads."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]/'uncertainty_review/package_v6_plan'))
from test_select_outer_v6 import Tests as Fixture
import select_outer_v6 as g

class Review(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def test_remaining_reader_identity_and_types(self):
        a,d=self.f.chain()
        for key,value in [('test_sha256','0'*64),('manifest_sha256','0'*64),('archive_bytes',124),('files',True),('extra_extracted_files_not_checked',False)]:
            bad=copy.deepcopy(d);bad['standalone_reader_receipt'][key]=value
            with self.assertRaises(ValueError):g.receipt_chain(a,bad)
    def test_predecessor_and_source_conflicts(self):
        a,d=self.f.chain()
        for obj,key,value in [('verify_approval','writer_approval_sha256','0'*64),('extraction_receipt','writer_receipt_sha256','0'*64),('create_approval','execution_authorized',False),('writer_receipt','source_pins',{'wrong':'0'*64})]:
            bad=copy.deepcopy(d);bad[obj][key]=value
            with self.assertRaises(ValueError):g.receipt_chain(a,bad)
    def test_provenance_shape_path_and_collision(self):
        a,d,oi,om=self.f.fixture();h=self.f.file('review.md')
        for spec in [{'source':'review.md','target':'quality/x','sha256':h,'discovered':True}, {'source':'review.md','target':'../escaped','sha256':h}, {'source':'review.md','target':'MANIFEST.json','sha256':h}]:
            a['provenance']=[spec]
            with self.assertRaises(ValueError):g.build_rows(self.f.root,a,d,oi,om)
    def test_external_map_drift(self):
        a,d,oi,om=self.f.fixture();d['config']['external_readonly_pins']={'/unlisted.py':'a'*64}
        with self.assertRaises(ValueError):g.build_rows(self.f.root,a,d,oi,om)

if __name__=='__main__':unittest.main()
