"""Finite manufactured QA/config fixtures; no real payload reads."""
import ast
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import package_v6 as p

OLD=Path(__file__).resolve().parents[2]/'package_v4_tools'

class ExternalContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve()
        self.root=self.base/'project';self.root.mkdir()
        self.ext=self.base/'installed.py';self.ext.write_text('synthetic installed dependency')
        self.h=p.digest(self.ext.read_bytes());self.extmap={str(self.ext):self.h}
        self.config=dict(finalization_authorized=True,external_readonly_pins=self.extmap)
        self.qa=dict(status='PASS_TECHNICAL_PREPARATION',files={os.path.relpath(self.ext,self.root):self.h},
                     review_files=[],documents={},external_readonly_files=self.extmap,config_path='config.json')
        self.manifest={'qa_binding':{'edition':'.','source':'qa.json'},'files':[dict(role='technical_qa',source='qa.json',target='qa.json')]}
    def tearDown(self):self.tmp.cleanup()
    def prepare(self):
        raw=json.dumps(self.config).encode();(self.root/'config.json').write_bytes(raw)
        self.qa['config_sha256']=p.digest(raw);self.qa['files']['config.json']=p.digest(raw)
        raw=json.dumps(self.qa).encode();self.manifest['qa_binding']['sha256']=p.digest(raw)
        self.manifest['files'][0]['sha256']=p.digest(raw)
        return {'qa.json':raw}
    def run_binding(self):return p.qa_binding(self.root,self.manifest,self.prepare())
    def test_full_qa_preserved_and_dependency_not_payload(self):
        buffers=self.prepare();before=dict(buffers)
        p.qa_binding(self.root,self.manifest,buffers)
        self.assertEqual(buffers,before);self.assertEqual(set(buffers),{'qa.json'})
    def test_wrong_external_hash(self):
        self.ext.write_text('changed')
        with self.assertRaisesRegex(ValueError,'External hash'):self.run_binding()
    def test_unlisted_external(self):
        self.qa['external_readonly_files']={};self.config['external_readonly_pins']={}
        with self.assertRaisesRegex(ValueError,'Unlisted external'):self.run_binding()
    def test_map_mismatch(self):
        self.config['external_readonly_pins']={}
        with self.assertRaisesRegex(ValueError,'map mismatch'):self.run_binding()
    def test_unused_external_grant(self):
        self.qa['files'].pop(os.path.relpath(self.ext,self.root))
        with self.assertRaisesRegex(ValueError,'full QA inventory'):self.run_binding()
    def test_config_not_authenticated(self):
        buffers=self.prepare();(self.root/'config.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):p.qa_binding(self.root,self.manifest,buffers)
    def test_config_not_in_qa(self):
        buffers=self.prepare();q=json.loads(buffers['qa.json']);q['files']['config.json']='0'*64
        buffers['qa.json']=json.dumps(q).encode()
        with self.assertRaisesRegex(ValueError,'Config absent'):p.qa_binding(self.root,self.manifest,buffers)
    def test_config_not_authorized(self):
        self.config['finalization_authorized']=False
        with self.assertRaisesRegex(ValueError,'not authorized'):self.run_binding()
    def test_file_symlink(self):
        other=self.base/'same';other.write_bytes(self.ext.read_bytes());self.ext.unlink();self.ext.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'Symlink'):self.run_binding()
    def test_ancestor_symlink(self):
        alias=self.base/'alias';alias.symlink_to(self.base,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Symlink'):p.external_readonly_file(str(alias/'installed.py'),self.h)
    def test_qa_alias_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.ext)
        self.qa['files'].pop(os.path.relpath(self.ext,self.root));self.qa['files']['alias']=self.h
        with self.assertRaisesRegex(ValueError,'Symlink'):self.run_binding()
    def test_bad_canonical_paths_and_directory(self):
        for s in ['relative',str(self.base)+'/./installed.py',str(self.base)+'//installed.py',str(self.ext)+'/',str(self.ext)+'\n',str(self.base)]:
            with self.assertRaises(ValueError):p.external_readonly_file(s,self.h)
    def test_external_may_not_be_packaged_via_qa_key(self):
        self.manifest['files'].append(dict(role='environment_receipt',source='config.json',target='dependency.py',qa_key=os.path.relpath(self.ext,self.root),sha256=self.h))
        with self.assertRaisesRegex(ValueError,'Unknown QA key'):self.run_binding()
    def test_external_source_path_still_rejected(self):
        with self.assertRaises(ValueError):p.source(self.root,str(self.ext))
    def test_end_reauthentication_mutation(self):
        original=p.external_readonly_file;calls=[]
        def change_after_first(*a):
            result=original(*a);calls.append(1)
            if len(calls)==1:self.ext.write_text('mutated after initial authentication')
            return result
        with patch.object(p,'external_readonly_file',change_after_first):
            with self.assertRaisesRegex(ValueError,'External hash'):self.run_binding()
        self.assertEqual(len(calls),1)
    def test_scientific_and_packaging_functions_unchanged(self):
        old=(OLD/'package_v4.py').read_bytes()
        self.assertEqual(hashlib.sha256(old).hexdigest(),'d3ce20b1d959487cc2c4f5c7b35a3d2ca36ab11a3e6f6434d654e664f601f141')
        def functions(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
        a,b=functions(old),functions(Path(p.__file__).read_bytes())
        self.assertEqual(set(b)-set(a),{'external_readonly_file','external_qa_contract'})
        self.assertEqual([n for n in a if a[n]!=b[n]],['qa_binding'])

def load_tests(loader,tests,pattern):
    # Exact original fixtures rebound only to the successor module; original
    # __file__ retained for their pre-existing source-only preparer test.
    source=(OLD/'test_package_v4.py').read_text()
    module=types.ModuleType('inherited_package_v4_tests');module.__file__=str(OLD/'test_package_v4.py')
    source=source.replace('import package_v4 as p','import package_v6 as p')
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    tests.addTests(loader.loadTestsFromTestCase(module.Tests))
    return tests

if __name__=='__main__':unittest.main(verbosity=2)
