"""Small manufactured end-to-end transport tests. No scientific input files."""
import copy,io,json,stat,struct,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import stream_common as c
import write_evidence as w
import verify_evidence as v

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.patch=patch.object(c,'__file__',str(self.root/'stream_common.py'));self.patch.start()
        for n in c.SOURCES:(self.root/n).write_text('# synthetic source identity '+n)
        (self.root/'proof.txt').write_bytes(b'manufactured\x00payload'*200)
        (self.root/'closure.md').write_text('Synthetic closure review, not science.')
        self.sel={'schema':'v9-evidence-selection-1','claim':'SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE','files':[{'source':'proof.txt','target':'evidence/proof.txt','sha256':c.digest((self.root/'proof.txt').read_bytes()),'bytes':(self.root/'proof.txt').stat().st_size}],'unresolved':[],'closure_review':{'source':'closure.md','sha256':c.digest((self.root/'closure.md').read_bytes())}}
        self.put('selection.json',self.sel)
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def put(self,n,d):
        raw=c.encode(d);(self.root/n).write_bytes(raw);return c.digest(raw)
    def auth(self,phase='CREATE',out='create'):
        a={'schema':'v9-evidence-approval-1','phase':phase,'execution_authorized':True,'source_pins':{n:c.digest((self.root/n).read_bytes()) for n in c.SOURCES},'selection':'selection.json','selection_sha256':c.digest((self.root/'selection.json').read_bytes()),'output':out,'max_seconds':900,'max_expanded_bytes':c.EXPANDED,'max_archive_bytes':c.COMPRESSED,'workers':1}
        if phase=='VERIFY_EXTRACT':
            a.update(archive='create/v9_evidence.zip',archive_sha256=c.digest((self.root/'create/v9_evidence.zip').read_bytes()),writer_receipt='create/COMPLETE.json',writer_receipt_sha256=c.digest((self.root/'create/COMPLETE.json').read_bytes()),writer_approval='create_approval.json',writer_approval_sha256=c.digest((self.root/'create_approval.json').read_bytes()))
        name='create_approval.json' if phase=='CREATE' else 'verify_approval.json';h=self.put(name,a);return name,h
    def create(self):
        n,h=self.auth();return w.run(self.root,n,h,'create')
    def test_roundtrip_and_scope(self):
        result=self.create();self.assertEqual(result['files'],1)
        n,h=self.auth('VERIFY_EXTRACT','extract');r=v.run(self.root,n,h,'extract')
        self.assertEqual(r['status'],'VERIFIED_STREAMED_EVIDENCE');self.assertFalse(r['portable_pipeline_replayed'])
        self.assertEqual((self.root/'proof.txt').read_bytes(),(self.root/'extract/payload/evidence/proof.txt').read_bytes())
    def test_exclusive_no_overwrite(self):
        self.create();n,h=self.auth()
        with self.assertRaises(FileExistsError):w.run(self.root,n,h,'create')
        self.assertFalse((self.root/'create/FAILURE.json').exists())
    def test_selection_unresolved(self):
        self.sel['unresolved']=['x'];self.put('selection.json',self.sel);n,h=self.auth()
        with self.assertRaises(ValueError):w.run(self.root,n,h,'create')
        self.assertFalse((self.root/'create').exists())
    def test_payload_tamper_failure_preserved(self):
        (self.root/'proof.txt').write_bytes(b'x'*self.sel['files'][0]['bytes']);n,h=self.auth()
        with self.assertRaises(ValueError):w.run(self.root,n,h,'create')
        self.assertTrue((self.root/'create/FAILURE.json').is_file());self.assertTrue((self.root/'create/v9_evidence.zip').is_file());self.assertFalse((self.root/'create/COMPLETE.json').exists())
    def test_wrong_approval(self):
        n,h=self.auth();a=c.parse((self.root/n).read_bytes());a['phase']='VERIFY_EXTRACT';h=self.put(n,a)
        with self.assertRaises(ValueError):w.run(self.root,n,h,'create')
    def test_source_mutation_before_payload(self):
        n,h=self.auth();(self.root/'write_evidence.py').write_text('changed')
        with self.assertRaises(ValueError):w.run(self.root,n,h,'create')
        self.assertFalse((self.root/'create').exists())
    def test_archive_tamper(self):
        self.create();n,h=self.auth('VERIFY_EXTRACT','extract');p=self.root/'create/v9_evidence.zip';p.write_bytes(p.read_bytes()+b'x')
        with self.assertRaises(ValueError):v.run(self.root,n,h,'extract')
        self.assertFalse((self.root/'extract').exists())
    def test_writer_failure_marker(self):
        self.create();(self.root/'create/FAILURE.json').write_text('{}');n,h=self.auth('VERIFY_EXTRACT','extract')
        with self.assertRaises(ValueError):v.run(self.root,n,h,'extract')
    def test_receipt_wrong_selection(self):
        self.create();p=self.root/'create/COMPLETE.json';d=c.parse(p.read_bytes());d['selection_sha256']='0'*64;self.put('create/COMPLETE.json',d);n,h=self.auth('VERIFY_EXTRACT','extract')
        with self.assertRaises(ValueError):v.run(self.root,n,h,'extract')
    def test_path_and_typed_sizes(self):
        for change in [{'target':'../escape'},{'target':'MANIFEST.json'},{'source':'eight_tree_plan/a'},{'bytes':True},{'bytes':c.EXPANDED}]:
            s=copy.deepcopy(self.sel);s['files'][0].update(change)
            with self.assertRaises(ValueError):c.records(s)
    def test_collision(self):
        for name in ['evidence/PROOF.txt','evidence/proof.txt/child']:
            s=copy.deepcopy(self.sel);s['files'].append({**s['files'][0],'target':name})
            with self.assertRaises(ValueError):c.records(s)
    def test_stream_highwater(self):
        raw=io.BytesIO();cap=w.CappedFile(raw,c.Clock())
        with patch.object(c,'COMPRESSED',3):
            cap.write(b'abc');cap.seek(0);cap.write(b'x');self.assertEqual(cap.highwater,3)
            with self.assertRaises(ValueError):cap.write(b'abcd')
    def test_deadline_before_authority(self):
        n,h=self.auth()
        with patch.object(c.Clock,'check',side_effect=TimeoutError('synthetic deadline')):
            with self.assertRaises(TimeoutError):w.run(self.root,n,h,'create')
        self.assertFalse((self.root/'create').exists())
    def test_zip_extra_and_symlink(self):
        for name,mode in [('extra',stat.S_IFREG|0o644),('evidence/proof.txt',stat.S_IFLNK|0o777)]:
            b=io.BytesIO()
            with zipfile.ZipFile(b,'w') as z:
                z.writestr(w.info('MANIFEST.json'),b'{}');i=w.info(name);i.external_attr=mode<<16;z.writestr(i,b'x')
            with zipfile.ZipFile(io.BytesIO(b.getvalue())) as z:
                with self.assertRaises(ValueError):v.inventory(z,{'evidence/proof.txt':{'bytes':1,'sha256':'a'*64}})
    def test_reauthentication_failure(self):
        n,h=self.auth()
        with patch.object(c.Reader,'end',side_effect=ValueError('changed at end')):
            with self.assertRaises(ValueError):w.run(self.root,n,h,'create')
        self.assertTrue((self.root/'create/FAILURE.json').exists());self.assertFalse((self.root/'create/COMPLETE.json').exists())
    def test_metadata_cap_and_duplicate(self):
        with self.assertRaises(ValueError):c.parse(b'{"x":1,"x":2}')
        with patch.object(c,'METADATA',3):
            with self.assertRaises(ValueError):c.parse(b'1234')
    def test_zero_byte_payload(self):
        (self.root/'proof.txt').write_bytes(b'');self.sel['files'][0].update(bytes=0,sha256=c.digest(b''));self.put('selection.json',self.sel)
        self.create();n,h=self.auth('VERIFY_EXTRACT','extract');self.assertEqual(v.run(self.root,n,h,'extract')['verified_payload_bytes'],0)
    def test_central_directory_preallocation_gate(self):
        self.create();p=self.root/'create/v9_evidence.zip';v.directory_admission(p)
        raw=p.read_bytes()
        for count,length in [(c.MAX_FILES+2,100),(2,c.METADATA+1)]:
            tail=struct.pack('<4s4H2LH',b'PK\x05\x06',0,0,count,count,length,0,0)
            p.write_bytes(raw[:-22]+tail)
            with self.assertRaises(ValueError):v.directory_admission(p)

if __name__=='__main__':unittest.main()
