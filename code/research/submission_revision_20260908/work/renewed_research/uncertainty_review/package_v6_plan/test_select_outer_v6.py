"""Manufactured full role inventory; no real QA/payload/input enumeration."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import select_outer_v6 as g
import prepare_v6 as p
import stream_common as c

class Tests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def file(self,n,b=b'x'):
        f=self.root/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b);return c.digest(b)
    def legacy(self):
        rows=[]
        def add(n,role,**extra):
            self.file(p.OLD+'/'+n);rows.append({'source':'mutable/original','target':n,'role':role,'sha256':c.digest(b'x'),'bytes':1,**extra})
        for ident in sorted(p.ARCHIVES):add('reproduction/'+ident+'.zip','private_archive',id=ident)
        add('historical/v4/evidence/earlier.md','scientific_evidence');add('quality/environment.json','environment_receipt')
        for i in range(387):add('quality/old_'+str(i)+'.json','review')
        for i in range(35):add('superseded/figure_'+str(i)+'.png','figure')
        files={r['target']:{'sha256':r['sha256'],'bytes':r['bytes']} for r in rows};files['INPUT_MANIFEST.json']={'sha256':'a'*64,'bytes':1}
        self.assertEqual(len(rows),432);return {'files':rows},{'files':files}
    def fixture(self):
        old_input,old=self.legacy();qfiles={}
        def qa_file(n,b=b'x'):
            src=p.EDITION+'/'+n;h=self.file(src,b);qfiles[n]=h;return {'path':str(self.root/src),'sha256':h}
        config={'schema':'v9-final-qa-1','edition':p.EDITION,'finalization_authorized':True,'content_contract':p.COUNTS,'external_readonly_pins':{}}
        configspec=qa_file('work/config.json',c.encode(config));documents={}
        for kind,n in [('main',33),('supplement',101)]:
            artifacts={k:qa_file(kind+'.'+k) for k in ['pdf','docx','source']}
            if kind=='supplement':artifacts['reading_source']=qa_file(kind+'.reading.md')
            documents[kind]={'pages':n,'counts':p.COUNTS[kind],'visual':[{'page':i} for i in range(1,n+1)],'artifacts':artifacts}
        for stem in g.FIGURES:
            for ext in ['png','pdf','svg']:qa_file('figures/'+stem+'.'+ext)
        for n in ['work/review.md','work/ledger.json']:qa_file(n)
        qa={'status':'PASS_TECHNICAL_PREPARATION','files':qfiles,'external_readonly_files':{},'config_path':'work/config.json','config_sha256':configspec['sha256'],'documents':documents,'review_files':['work/review.md','work/ledger.json']}
        a={'inputs':{},'guide_pins':{},'helper_pins':{},'required_source_pins':{},'source_pins':{},'provenance':[]}
        for k in g.INPUTS:
            src=p.EDITION+'/work/'+k+'.json';h=self.file(src,c.encode({'synthetic':k}));a['inputs'][k]={'source':src,'sha256':h}
        a['inputs']['config']={'source':p.EDITION+'/work/config.json','sha256':configspec['sha256']}
        a['inputs']['qa']={'source':p.EDITION+'/work/qa.json','sha256':self.file(p.EDITION+'/work/qa.json',c.encode(qa))}
        for n in g.GUIDE_ROLES:a['guide_pins'][n]=self.file(p.EDITION+'/work/package_documents/'+n,b'historical/v4/evidence/')
        for n in g.HELPERS:a['helper_pins'][n]=self.file(p.EDITION+'/work/package_documents/'+n)
        for src in p.REQUIRED_SOURCES:a['required_source_pins'][src]=self.file(src)
        for n in g.AUTH_SOURCES:
            src=str(Path(p.TOOL).parent/n);a['source_pins'][src]=self.file(src)
        return a,{'qa':qa,'config':config},old_input,old
    def test_full_manufactured_inventory(self):
        a,d,oi,om=self.fixture();s=g.build_rows(self.root,a,d,oi,om);rows=s['files']
        self.assertEqual(sum(r['role']=='private_archive' for r in rows),9)
        self.assertEqual(sum(r['role']=='figure' for r in rows),18)
        self.assertEqual(sum(r['role']=='source_image_alias' for r in rows),6)
        self.assertEqual(sum(r['role']=='review' for r in rows),2)
        self.assertEqual(sum(r['role']=='technical_qa' for r in rows),1)
        self.assertEqual(sum(r['role']=='legacy_evidence' for r in rows),388)
        self.assertIn('historical/v4/evidence/earlier.md',{r['target'] for r in rows})
        self.assertNotIn('historical/v5/historical/v4/evidence/earlier.md',{r['target'] for r in rows})
        for n in g.HELPERS:self.assertIn('reproduction/v9_evidence/'+n,{r['target'] for r in rows})
        self.assertIn('tools/package_v6.py',{r['target'] for r in rows})
        p.validate_records(rows)
    def test_no_old_technical_roles_leak(self):
        oi,om=self.legacy();oi['files'][10]['role']='technical_qa'
        self.assertFalse(any(r['role']=='technical_qa' for r in g.legacy_rows(oi,om)))
    def test_legacy_count_or_hash_changes_fail(self):
        oi,om=self.legacy();bad=copy.deepcopy(oi);bad['files'].pop()
        with self.assertRaises(ValueError):g.legacy_rows(bad,om)
        om['files'][oi['files'][0]['target']]['sha256']='0'*64
        with self.assertRaises(ValueError):g.legacy_rows(oi,om)
    def test_missing_review_or_page_fails(self):
        a,d,oi,om=self.fixture()
        for field,val in [('pages',32),('visual',[{'page':1}]*33)]:
            bad=copy.deepcopy(d);bad['qa']['documents']['main'][field]=val
            with self.assertRaises(ValueError):g.build_rows(self.root,a,bad,oi,om)
        bad=copy.deepcopy(d);bad['qa']['review_files'].append('work/review.md')
        with self.assertRaises(ValueError):g.build_rows(self.root,a,bad,oi,om)
    def test_current_qa_hash_mismatch(self):
        a,d,oi,om=self.fixture();d['qa']['documents']['main']['artifacts']['pdf']['sha256']='a'*64
        with self.assertRaises(ValueError):g.build_rows(self.root,a,d,oi,om)
    def test_original_supplement_reading_role(self):
        a,d,oi,om=self.fixture();s=g.build_rows(self.root,a,d,oi,om)
        r=next(r for r in s['files'] if r['role']=='supplement_source')
        self.assertTrue(r['source'].endswith('supplement.reading.md'))
    def test_authority_before_metadata(self):
        with patch.object(c.Reader,'check',side_effect=ValueError('no approval')) as check:
            with self.assertRaises(ValueError):g.run(self.root,'approval.json','a'*64,'selection.json')
            self.assertEqual(check.call_count,1)
    def test_collision_preserved(self):
        self.file('selection.json')
        with patch.object(c.Reader,'check') as check:
            with self.assertRaises(FileExistsError):g.run(self.root,'approval.json','a'*64,'selection.json')
            check.assert_not_called()
    def test_missing_or_wrong_transport_receipts(self):
        with self.assertRaises(ValueError):g.receipt_chain({'inputs':{'archive':{'sha256':'a'*64}}},{'extraction_receipt':{},'writer_receipt':{},'create_approval':{},'verify_approval':{}})
    def chain(self):
        a={'inputs':{k:{'source':k+'.json','sha256':c.digest(k.encode())} for k in g.INPUTS},'helper_pins':{k:c.digest(k.encode()) for k in g.HELPERS}}
        ah=a['inputs']['archive']['sha256'];sh=a['inputs']['addon_selection']['sha256'];mh=a['inputs']['addon_manifest']['sha256']
        sel={'claim':'SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE','files':[{'target':'one','sha256':'a'*64,'bytes':4}]}
        m={'schema':'v9-saved-evidence-1','selection_sha256':sh,'claim':sel['claim'],'files':{'one':{'sha256':'a'*64,'bytes':4}}}
        wr={'status':'CREATED_STREAMED_EVIDENCE_EXTRACTION_PENDING','archive_sha256':ah,'archive_bytes':123,'manifest_sha256':mh,'scientific_execution':False,'selection_sha256':sh,'approval_sha256':a['inputs']['create_approval']['sha256'],'source_pins':{}}
        ex={**wr,'status':'VERIFIED_STREAMED_EVIDENCE','approval_sha256':a['inputs']['verify_approval']['sha256'],'writer_receipt_sha256':a['inputs']['writer_receipt']['sha256'],'files':1,'verified_payload_bytes':4,'disk_files_reopened':2}
        ca={'phase':'CREATE','execution_authorized':True,'selection_sha256':sh,'source_pins':{}}
        va={**ca,'phase':'VERIFY_EXTRACT','writer_receipt_sha256':a['inputs']['writer_receipt']['sha256'],'writer_approval_sha256':a['inputs']['create_approval']['sha256'],'archive_sha256':ah}
        rr={'status':'PASS_SAVED_FILE_INTEGRITY','archive_sha256':ah,'manifest_sha256':mh,'source_sha256':a['helper_pins']['verify_saved_evidence.py'],'test_sha256':a['helper_pins']['test_verify_saved_evidence.py'],'files':1,'expanded_bytes':4+len(c.encode(m)),'archive_bytes':123,'extracted_selected_files_checked':True,'scientific_code_executed':False,'extra_extracted_files_not_checked':True}
        return a,dict(extraction_receipt=ex,writer_receipt=wr,create_approval=ca,verify_approval=va,addon_selection=sel,addon_manifest=m,standalone_reader_receipt=rr)
    def test_valid_transport_chain(self):
        a,d=self.chain();g.receipt_chain(a,d)
    def test_reader_status_identity_counts_and_bool_strict(self):
        a,d=self.chain()
        for k,v in [('status','FAIL'),('archive_sha256','0'*64),('source_sha256','0'*64),('files',2),('expanded_bytes',4),('extracted_selected_files_checked',1),('scientific_code_executed',True)]:
            bad=copy.deepcopy(d);bad['standalone_reader_receipt'][k]=v
            with self.assertRaises(ValueError):g.receipt_chain(a,bad)
    def test_manifest_and_extraction_counts_exact(self):
        a,d=self.chain()
        for k in ['files','verified_payload_bytes','disk_files_reopened']:
            bad=copy.deepcopy(d);bad['extraction_receipt'][k]+=1
            with self.assertRaises(ValueError):g.receipt_chain(a,bad)
        d['addon_manifest']['files']['one']['bytes']=5
        with self.assertRaises(ValueError):g.receipt_chain(a,d)
    def test_explicit_provenance_and_collision(self):
        a,d,oi,om=self.fixture();h=self.file('review/source.md')
        a['provenance']=[{'source':'review/source.md','target':'quality/provenance/source.md','sha256':h}]
        s=g.build_rows(self.root,a,d,oi,om)
        self.assertEqual(sum(r['role']=='package_provenance' for r in s['files']),1)
        a['provenance'][0]['target']='tools/package_v6.py'
        with self.assertRaises(ValueError):g.build_rows(self.root,a,d,oi,om)

if __name__=='__main__':unittest.main()
