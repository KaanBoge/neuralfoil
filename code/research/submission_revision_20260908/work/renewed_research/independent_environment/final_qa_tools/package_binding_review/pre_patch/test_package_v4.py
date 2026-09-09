import copy,json,tempfile,unittest
from pathlib import Path
import package_v4 as p


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()/'project';self.root.mkdir()
        data=b'fixture only, not a manuscript';(self.root/'input.txt').write_bytes(data)
        self.records=[]
        roles=['main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source',
               'readme','navigation','permissions','author_checklist','technical_qa','environment_receipt']
        for role in roles:self.records.append({'source':'input.txt','target':role+'.txt','role':role,'bytes':len(data),'sha256':p.digest(data)})
        for id in ['old','new']:
            self.records.append({'source':'input.txt','target':id+'.zip','role':'private_archive','id':id,
                                 'bytes':len(data),'sha256':p.digest(data),**({'legacy_member':'old.zip'} if id=='old' else {})})
        self.records.append({'source':'input.txt','target':'figure.svg','role':'figure','id':'example','format':'svg','bytes':len(data),'sha256':p.digest(data)})
        b=json.dumps({'files':{'old.zip':{'sha256':p.digest(data)}}}).encode();(self.root/'legacy.json').write_bytes(b)
        self.m={'schema':'private_submission_inputs_v4','technical_approval':'APPROVED_FOR_PRIVATE_ASSEMBLY',
                'human_author_approval':False,'public_release':False,'package_name':'fixture_v4','max_payload_bytes':100000,
                'requirements':{'figure_ids':['example'],'figure_formats':['svg'],'archive_ids':['old','new'],'legacy_archive_ids':['old']},
                'legacy_witness':{'source':'legacy.json','sha256':p.digest(b)},'files':self.records}
        self.path=self.root/'inputs.json';self.pin=self.write()
    def tearDown(self):self.tmp.cleanup()
    def write(self):
        b=json.dumps(self.m).encode();self.path.write_bytes(b);return p.digest(b)
    def test_full_fixture_assemble_extract(self):
        out=self.root.parent/'fixture_v4';r=p.assemble(self.root,self.path,self.pin,out)
        z=out.with_name(out.name+'.zip');v=p.extract(z,r['archive_sha256'],r['manifest_sha256'],self.root.parent/'extract')
        self.assertEqual(v['status'],'PASS_INTEGRITY_ONLY')
    def test_manifest_pin(self):
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,'0'*64)
    def test_no_approval(self):
        self.m['technical_approval']='PENDING';pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_changed_source(self):
        (self.root/'input.txt').write_bytes(b'changed')
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,self.pin)
    def test_original_archive_change(self):
        self.records[12]['sha256']='0'*64;pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_traversal(self):
        self.records[0]['target']='../outside';pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_symlink(self):
        (self.root/'alias').symlink_to(self.root/'input.txt');self.records[0]['source']='alias';pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_duplicate_target(self):
        self.records[0]['target']=self.records[1]['target'].upper();pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_missing_figure(self):
        self.m['requirements']['figure_ids'].append('missing');pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_env_denied(self):
        (self.root/'venv_fit').mkdir();(self.root/'venv_fit/input.txt').write_bytes((self.root/'input.txt').read_bytes())
        self.records[0]['source']='venv_fit/input.txt';pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_conda_receipt_filename_allowed(self):
        (self.root/'conda_closure.json').write_bytes((self.root/'input.txt').read_bytes())
        self.records[11]['source']='conda_closure.json';pin=self.write()
        p.validate_inputs(self.root,self.path,pin)
    def test_conda_environment_directory_denied(self):
        (self.root/'conda_forward').mkdir();(self.root/'conda_forward/payload').write_bytes((self.root/'input.txt').read_bytes())
        self.records[11]['source']='conda_forward/payload';pin=self.write()
        with self.assertRaises(ValueError):p.validate_inputs(self.root,self.path,pin)
    def test_overwrite_denied(self):
        out=self.root.parent/'fixture_v4';out.mkdir()
        with self.assertRaises(FileExistsError):p.assemble(self.root,self.path,self.pin,out)
    def test_unlisted_file(self):
        out=self.root.parent/'fixture_v4';r=p.assemble(self.root,self.path,self.pin,out);(out/'extra').write_bytes(b'x')
        with self.assertRaises(ValueError):p.verify(out,r['manifest_sha256'])
    def test_extract_bad_pin(self):
        out=self.root.parent/'fixture_v4';r=p.assemble(self.root,self.path,self.pin,out)
        with self.assertRaises(ValueError):p.extract(out.with_name(out.name+'.zip'),'0'*64,r['manifest_sha256'],self.root.parent/'new')
    def test_duplicate_json_key(self):
        with self.assertRaises(ValueError):p.parse(b'{"x":1,"x":2}')
    def test_control_characters(self):
        for c in ['\n','\r','\t','\x00','\x7f','\x85']:
            with self.assertRaises(ValueError):p.safe('name'+c+'.txt')
    def test_output_ancestor_symlink(self):
        link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):p.assemble(self.root,self.path,self.pin,link/'fixture_v4')
        self.assertFalse((self.root/'fixture_v4').exists())
    def test_extraction_ancestor_symlink(self):
        link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):p.extract(self.root/'missing.zip','0'*64,'0'*64,link/'extract')
        self.assertFalse((self.root/'extract').exists())


if __name__=='__main__':unittest.main(verbosity=2)
