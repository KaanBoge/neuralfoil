"""Synthetic metadata only. No scientific package inventory or assembly."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import prepare_v8 as p

def fixture(root):
    edition=root/p.EDITION;edition.mkdir(parents=True)
    helper=edition/'helper.py';helper.write_text('# synthetic helper')
    c={'schema':'v8-final-qa-1','finalization_authorized':True,'edition':p.EDITION,'content_contract':p.COUNTS,'evidence':[{'role':r,'path':'synthetic/'+r+'.json','sha256':'a'*64} for r in p.NEW_ROLES]+[{'role':'ancillary','path':str(helper),'sha256':p.digest(helper.read_bytes())}],'documents':{k:{'pages':n} for k,n in [('main',30),('supplement',80)]}}
    cp=edition/'config.json';cp.write_text(json.dumps(c))
    qa={'status':'PASS_TECHNICAL_PREPARATION','files':{'helper.py':p.digest(helper.read_bytes()),'config.json':p.digest(cp.read_bytes())},'config_path':'config.json','config_sha256':p.digest(cp.read_bytes()),'helper_sha256':p.digest(helper.read_bytes()),'documents':{k:{'pages':n,'counts':p.COUNTS[k],'visual':[{'page':i} for i in range(1,n+1)]} for k,n in [('main',30),('supplement',80)]}}
    return qa,c,cp

class Tests(unittest.TestCase):
    def test_authorization_before_enumeration(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()
            with patch.object(p,'qa_contract') as q:
                with self.assertRaises(FileNotFoundError):p.prepare(root,'absent-approval','a'*64,'new.json')
                q.assert_not_called()
    def test_explicit_authorization_contract(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();a={'authorized_phase':'prepare_private_package_v5_inventory_for_v8','qa':'not-read','qa_sha256':'a'*64,'builder_sha256':p.digest(Path(p.__file__).read_bytes()),'packager_sha256':p.TOOL_SHA,'selection':'not-read','selection_sha256':'b'*64,'guide_sha256':{n:'c'*64 for n in p.GUIDES},'output':'new.json','max_payload_bytes':p.CAP}
            ap=root/'approval.json';ap.write_text(json.dumps(a));p.authorization(root,ap,p.digest(ap.read_bytes()),root/'new.json')
            for k,v in [('authorized_phase','draft'),('builder_sha256','0'*64),('max_payload_bytes',p.CAP+1),('output','other.json'),('guide_sha256',{})]:
                bad={**a,k:v};ap.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):p.authorization(root,ap,p.digest(ap.read_bytes()),root/'new.json')
    def test_qa_pass_and_draft_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();qa,c,cp=fixture(root);p.qa_contract(root,qa)
            c['finalization_authorized']=False;cp.write_text(json.dumps(c));h=p.digest(cp.read_bytes());qa['files']['config.json']=h;qa['config_sha256']=h
            with self.assertRaisesRegex(ValueError,'authorized V8'):p.qa_contract(root,qa)
    def test_counts_pages_reviews_helper(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();qa,c,cp=fixture(root)
            for path,value in [('counts',[16,133,4,4]),('pages',29),('visual',[{'page':1}]*30)]:
                bad=copy.deepcopy(qa);bad['documents']['main'][path]=value
                with self.assertRaises(ValueError):p.qa_contract(root,bad)
            bad=copy.deepcopy(qa);del bad['files']['helper.py']
            with self.assertRaisesRegex(ValueError,'helper QA'):p.qa_contract(root,bad)
    def test_config_and_helper_mutations(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();qa,c,cp=fixture(root);cp.write_text('{}')
            with self.assertRaises(ValueError):p.qa_contract(root,qa)
            cp.write_text(json.dumps(c))
            (root/p.EDITION/'helper.py').write_text('# changed')
            with self.assertRaises(ValueError):p.qa_contract(root,qa)
    def test_forbidden_scopes(self):
        for n in ['x/all_context_plan/report.json','x/downstream/COMPLETE.json','x/inference_benchmark/report.json','x/Volume4/a.csv','x/.venv/a','x/venv_fit/a','x/site-packages/a','x/cache/a']:
            with self.assertRaises(ValueError):p.permitted(n)
        p.permitted('evidence/paired_sole_model/actual_producer_attempt_1/certificate.json')
    def test_path_escape_and_collision(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve()
            with self.assertRaises(ValueError):p.relative(root,'../escape')
            (root/'existing.json').write_text('{}')
            with self.assertRaises(FileExistsError):p.prepare(root,'approval-not-read','a'*64,'existing.json')
    def test_historical_aliases_and_archives(self):
        rows=[{'target':'reproduction/'+a+'.zip','role':'private_archive','sha256':'a'*64,'bytes':1,'id':a,'source':'mutable-original.zip'} for a in p.ARCHIVES]
        rows += [{'target':'authoring_provenance/source.py','role':'authoring_source','sha256':'b'*64,'bytes':1,'source':'mutable.py'}]
        files={r['target']:{'sha256':r['sha256'],'bytes':1} for r in rows}
        for i in range(334-len(files)):files['unused/'+str(i)]={'sha256':'c'*64,'bytes':1}
        result=p.historical_records({'files':rows},{'files':files})
        self.assertTrue(all(r['source'].startswith(p.OLD+'/') for r in result))
        self.assertEqual(result[-1]['target'],'historical/v4/authoring_provenance/source.py')
        self.assertTrue(all(r['legacy_member']==r['target'] for r in result if r['role']=='private_archive'))
        files[rows[0]['target']]['sha256']='d'*64
        with self.assertRaises(ValueError):p.historical_records({'files':rows},{'files':files})
    def test_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):p.parse('{"x":1,"x":2}')

if __name__=='__main__':unittest.main()
