"""Synthetic-only preparation tests; no edition document or scientific intake."""
import copy
import tempfile
import unittest
from pathlib import Path
import prepare_v9_final_config as p

def binding():
    return dict(schema='v9-draft-preparation-binding-1', preparation_authorized=True,
        finalization_authorized=False, source_pins={},
        visual={k:{str(n):{} for n in range(1,v['pages']+1)} for k,v in p.SELECTORS.items()},
        toc_labels={'S1 Test':'Test','References':'References'},
        assembly_audit=dict(path=p.AUDIT_PATH,sha256=p.AUDIT_SHA,role='v9_assembly_audit',
                            assertions=copy.deepcopy(p.AUDIT_ASSERTIONS)),
        assembly_review=dict(path='review.md',sha256='b'*64,role='ancillary'),
        assembly_binding_pointer='/assembly_sha256',
        output_config=p.EDITION+'/work/ROOT_FINAL_QA_CONFIG_DRAFT_test.json')

class Tests(unittest.TestCase):
    def test_contract(self):
        p.validate_binding(binding())
        self.assertEqual(sum(x['pages'] for x in p.SELECTORS.values()),134)
        self.assertEqual(p.CONTENT,dict(main=[17,133,4,4],supplement=[43,343,44,2],references=23))
        for row in p.SELECTORS.values():
            for key in ('source','build','layout','page_map','docx','pdf'):
                self.assertRegex(row[key],r'^[0-9a-f]{64}$')

    def test_no_finalization_authority(self):
        for key,value in [('finalization_authorized',True),('preparation_authorized',False),('preparation_authorized',1)]:
            b=binding(); b[key]=value
            with self.assertRaises(ValueError):p.validate_binding(b)

    def test_missing_visual(self):
        for kind in p.SELECTORS:
            b=binding();del b['visual'][kind]['1']
            with self.assertRaises(ValueError):p.validate_binding(b)

    def test_missing_review_or_binding(self):
        for key,value in [('assembly_audit',None),('assembly_review',None),('assembly_binding_pointer',''),('toc_labels',{})]:
            b=binding();b[key]=value
            with self.assertRaises(ValueError):p.validate_binding(b)

    def test_audit_fail_missing_and_nonstatus_rejected(self):
        for assertions in ([],[{'pointer':'/result','equals':'FAIL'}],
                           [{'pointer':'/status','equals':'PASS'}],[{'pointer':'/unrelated','equals':1}],
                           [{'pointer':'/result','equals':'PASS'},{'pointer':'/result','equals':'FAIL'}]):
            b=binding();b['assembly_audit']['assertions']=assertions
            with self.assertRaises(ValueError):p.validate_binding(b)
        for key,value in [('path','other.json'),('sha256','0'*64)]:
            b=binding();b['assembly_audit'][key]=value
            with self.assertRaises(ValueError):p.validate_binding(b)

    def test_unselected_path_and_extra_fields(self):
        for path in ('../config.json',p.EDITION+'/work/FINAL.json',p.EDITION+'/other/ROOT_FINAL_QA_CONFIG_DRAFT_x.json'):
            b=binding();b['output_config']=path
            with self.assertRaises(ValueError):p.validate_binding(b)
        b=binding();b['invented_approval']=True
        with self.assertRaises(ValueError):p.validate_binding(b)

    def test_legacy_and_history_preservation(self):
        legacy=[{'role':'legacy','path':'old','sha256':'a'*64}]
        added=[{'role':'added','path':'new','sha256':'b'*64}]
        f=dict(legacy_old_qa_unmodified={'old':'qa'},legacy_evidence_unmodified=legacy,
               added_evidence=added,history_pins=[dict(path='failed.json',sha256='c'*64,role='historical_failed_review_not_pass')])
        s=dict(finalization_authorized=False,content_contract=p.CONTENT,old_qa={'old':'qa'},
               evidence=legacy+added+[dict(role='v9_assembly'),dict(role='v9_assembly_audit')])
        old=copy.deepcopy((s,f))
        c=p.assemble_draft(s,f,binding(),{'main':{},'supplement':{}},{'role':'v9_assembly'},[],'d'*64)
        self.assertIs(c['finalization_authorized'],False)
        self.assertEqual(c['evidence'][:2],legacy+added)
        self.assertEqual(c['evidence'][3]['assertions'],[{'pointer':'/result','equals':'PASS'}])
        self.assertEqual(c['evidence'][-1]['role'],'ancillary')
        self.assertNotIn('assertions',c['evidence'][-1])
        self.assertEqual((s,f),old)
        s['evidence'][0]={'role':'changed'}
        with self.assertRaises(ValueError):p.assemble_draft(s,f,binding(),{}, {},[],'d'*64)

    def test_pinned_helper_and_deterministic_reading(self):
        h=p.helper()
        source=b'# Supplement\n\nNAVIGATION_PLACEHOLDER\n\n# S1 Test\nunchanged 1.234\n# References\n[1] test\n'
        labels={'S1 Test':'Test','References':'References'};pages={'S1 Test':2,'References':4}
        result=h.reading_source_bytes('supplement',source,labels,pages)
        self.assertEqual(result,source.replace(b'NAVIGATION_PLACEHOLDER',b'| Section | PDF page |\n| --- | ---: |\n| Test | 2 |\n| References | 4 |'))
        for bad in (source.replace(b'NAVIGATION_PLACEHOLDER',b'TODO'),source+b'\nNAVIGATION_PLACEHOLDER\n'):
            with self.assertRaises(ValueError):h.reading_source_bytes('supplement',bad,labels,pages)

    def test_pins_reject_mutation_and_escape(self):
        h=p.helper()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); file=root/'source.txt';file.write_bytes(b'synthetic')
            pins=h.Pins(root);pins.pin(p.spec(file,p.digest(file.read_bytes())))
            file.write_bytes(b'changed')
            with self.assertRaises(ValueError):pins.reread()
            with self.assertRaises(ValueError):pins.path('../escaped')

    def test_exclusive_draft_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp)/'reading.md';o=Path(temp)/'draft.json'
            with self.assertRaises(ValueError):p.publish_draft(r,o,b'x',{'finalization_authorized':True})
            self.assertFalse(r.exists())
            p.publish_draft(r,o,b'exact reading',{'finalization_authorized':False})
            before=(r.read_bytes(),o.read_bytes())
            with self.assertRaises(ValueError):p.publish_draft(r,o,b'changed',{'finalization_authorized':False})
            self.assertEqual(before,(r.read_bytes(),o.read_bytes()))

    def test_visual_witness_must_be_actual(self):
        h=p.helper()
        import json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data={'page.png':b'pixels','doc.pdf':b'pdf','review.md':b'actual observation'}
            for name,raw in data.items():(root/name).write_bytes(raw)
            row=dict(page=1,result='PASS',individually_viewed_original_resolution=False,png_sha256=p.digest(b'pixels'))
            (root/'ledger.json').write_text(json.dumps({'pdf_sha256':p.digest(b'pdf'),'pages':[row]}))
            pin=lambda name:p.spec(root/name,p.digest((root/name).read_bytes()))
            entry=dict(ledger=pin('ledger.json'),record_pointer='/pages/0',reviewed_page=1,
                       report=pin('review.md'),reviewed_png=pin('page.png'),reviewed_pdf=pin('doc.pdf'))
            with self.assertRaises(ValueError):h.visual_page(h.Pins(root),root/'page.png',entry)

if __name__=='__main__':unittest.main()
