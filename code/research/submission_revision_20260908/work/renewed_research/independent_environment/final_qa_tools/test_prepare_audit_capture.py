import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path

PREPARER=Path(__file__).resolve().parents[4]/'renewed_manuscript_v7/prepare_package_inputs.py'
spec=importlib.util.spec_from_file_location('preparer',PREPARER)
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class CaptureGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.config=self.root/'approved.json'
        self.config.write_text(json.dumps({'finalization_authorized':True,'evidence':[]}))
        self.qa={'config_path':'approved.json','config_sha256':p.sha(self.config)}
        self.pins={self.config:('approved.json',p.sha(self.config))}
    def tearDown(self):self.temp.cleanup()
    def test_actual_authorized_config(self):
        self.assertEqual(p.authenticated_config(self.qa,self.pins,self.root)[0],self.config)
    def test_missing_config_pin(self):
        with self.assertRaises(ValueError):p.authenticated_config(self.qa,{},self.root)
    def test_config_changed(self):
        self.config.write_text('{}')
        with self.assertRaises(ValueError):p.authenticated_config(self.qa,self.pins,self.root)
    def test_draft_rejected_even_rehashed(self):
        self.config.write_text('{"finalization_authorized":false}')
        self.qa['config_sha256']=p.sha(self.config);self.pins[self.config]=('approved.json',p.sha(self.config))
        with self.assertRaises(ValueError):p.authenticated_config(self.qa,self.pins,self.root)
    def test_explicit_helper_only(self):
        f=self.root/'frozen_v2.py';f.write_text('# pinned')
        self.qa['helper_sha256']=p.sha(f);self.pins[f]=('frozen_v2.py',p.sha(f))
        config={'evidence':[{'path':'frozen_v2.py','sha256':p.sha(f)}]}
        self.assertEqual(p.authenticated_helper(self.qa,self.pins,config,self.root),f)
        with self.assertRaises(ValueError):p.authenticated_helper(self.qa,self.pins,{'evidence':[]},self.root)
    def test_helper_mutation(self):
        f=self.root/'frozen.py';f.write_text('# pinned')
        h=p.sha(f);self.qa['helper_sha256']=h;self.pins[f]=('frozen.py',h)
        f.write_text('# changed')
        with self.assertRaises(ValueError):
            p.authenticated_helper(self.qa,self.pins,{'evidence':[{'path':'frozen.py','sha256':h}]},self.root)
    def test_registry_finite_and_authentic(self):
        self.assertEqual(len(p.ASSEMBLY_AUDIT_FILES),25)
        self.assertEqual(len({r['target'] for r in p.ASSEMBLY_AUDIT_FILES}),25)
        for r in p.ASSEMBLY_AUDIT_FILES:
            f=p.PROJECT/r['source']
            self.assertEqual(p.sha(f),r['sha256'])
            self.assertNotIn('site-packages',f.parts)
            self.assertNotIn(f.suffix,{'.pkl','.npz','.npy'})

if __name__=='__main__':unittest.main()
