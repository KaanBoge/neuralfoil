import json,tempfile,unittest
from pathlib import Path
import finalize_v9 as q
import io,zipfile
from pypdf.generic import DictionaryObject,NameObject,ArrayObject

class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.p=q.Pins(self.root)
    def tearDown(self):self.tmp.cleanup()
    def file(self,name,value):
        p=self.root/name;p.write_text(value);return {'path':name,'sha256':q.sha(p)}
    def visual(self):
        png=self.file('page.png','PNG witness fixture');pdf=self.file('doc.pdf','PDF witness fixture');report=self.file('review.md','Individually reviewed page 1 PASS')
        data={'pdf_sha256':pdf['sha256'],'pages':[{'page':1,'result':'PASS','individually_viewed_original_resolution':True,'png_sha256':png['sha256']}]}
        ledger=self.file('ledger.json',json.dumps(data))
        entry={'ledger':ledger,'record_pointer':'/pages/0','reviewed_page':1,'report':report,'reviewed_png':png,'reviewed_pdf':pdf}
        return entry,data
    def test_pin(self):self.p.pin(self.file('a','a'))
    def test_bad_hash(self):
        s=self.file('a','a');s['sha256']='0'*64
        with self.assertRaises(ValueError):self.p.pin(s)
    def test_mutation(self):
        self.p.pin(self.file('a','a'));(self.root/'a').write_text('b')
        with self.assertRaises(ValueError):self.p.reread()
    def test_escape(self):
        with self.assertRaises(ValueError):self.p.path('../outside')
    def test_symlink(self):
        self.file('a','a');(self.root/'link').symlink_to(self.root/'a')
        with self.assertRaises(ValueError):self.p.pin({'path':'link','sha256':q.sha(self.root/'a')})
    def test_visual_identity(self):
        e,_=self.visual();self.assertEqual(q.visual_page(self.p,self.root/'page.png',e)['lineage'],'full_png_byte_identity')
    def test_visual_changed_body(self):
        e,_=self.visual();self.file('new.png','different')
        with self.assertRaises(ValueError):q.visual_page(self.p,self.root/'new.png',e)
    def test_visual_not_seen(self):
        e,d=self.visual();d['pages'][0]['individually_viewed_original_resolution']=False;e['ledger']=self.file('ledger.json',json.dumps(d))
        with self.assertRaises(ValueError):q.visual_page(self.p,self.root/'page.png',e)
    def test_visual_wrong_pdf(self):
        e,d=self.visual();d['pdf_sha256']='0'*64;e['ledger']=self.file('ledger.json',json.dumps(d))
        with self.assertRaises(ValueError):q.visual_page(self.p,self.root/'page.png',e)
    def test_visual_wrong_page(self):
        e,_=self.visual();e['reviewed_page']=2
        with self.assertRaises(ValueError):q.visual_page(self.p,self.root/'page.png',e)
    def test_visual_missing_report(self):
        e,_=self.visual();(self.root/'review.md').unlink()
        with self.assertRaises(ValueError):q.visual_page(self.p,self.root/'page.png',e)
    def test_visual_no_pass(self):
        e,d=self.visual();d['pages'][0]['result']='PENDING';e['ledger']=self.file('ledger.json',json.dumps(d))
        with self.assertRaises(ValueError):q.visual_page(self.p,self.root/'page.png',e)
    def test_incomplete_config_no_output(self):
        self.file('config.json',json.dumps({'schema':'v8-final-qa-1','project_root':str(self.root),'documents':{}}))
        with self.assertRaises(ValueError):q.run(self.root/'config.json',self.root/'qa.json')
        self.assertFalse((self.root/'qa.json').exists())
    def test_collision(self):
        self.file('qa.json','original');self.file('config.json',json.dumps({'schema':'v8-final-qa-1','project_root':str(self.root)}))
        with self.assertRaises(ValueError):q.run(self.root/'config.json',self.root/'qa.json')
        self.assertEqual((self.root/'qa.json').read_text(),'original')
    def test_json_pointer(self):self.assertEqual(q.pointer({'a':[{'x':2}]},'/a/0/x'),2)
    def reader(self,embedded):
        font=DictionaryObject({NameObject('/Subtype'):NameObject('/TrueType'),NameObject('/BaseFont'):NameObject('/Fixture')})
        if embedded:font[NameObject('/FontDescriptor')]=DictionaryObject({NameObject('/FontFile2'):DictionaryObject()})
        resources=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        return type('Reader',(),{'pages':[{'/Resources':resources}]})()
    def test_unembedded_font_rejected(self):
        with self.assertRaises(ValueError):q.embedded_fonts(self.reader(False))
    def test_embedded_font(self):self.assertEqual(q.embedded_fonts(self.reader(True)),['/Fixture'])
    def test_empty_fonts_rejected(self):
        with self.assertRaises(ValueError):q.embedded_fonts(type('Reader',(),{'pages':[{}]})())

class CommentParts(unittest.TestCase):
    def check(self, entries):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:
            for name,raw in entries:z.writestr(name,raw)
        stream.seek(0)
        with zipfile.ZipFile(stream) as z:q.check_comment_parts(z)
    def xml(self,body='',attrs=''):
        return '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'+attrs+'>'+body+'</w:comments>'
    def test_no_comments(self):self.check([])
    def test_empty_standard(self):self.check([('word/comments.xml',self.xml())])
    def test_whitespace_standard(self):self.check([('word/comments.xml',self.xml(' \n\t '))])
    def test_actual_comment(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml',self.xml('<w:comment/>'))])
    def test_fake_root(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml','<comments/>')])
    def test_attributes(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml',self.xml(attrs=' w:id="1"'))])
    def test_malformed(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml','<')])
    def test_extended(self):
        with self.assertRaises(ValueError):self.check([('word/commentsExtended.xml',self.xml())])
    def test_nonwhitespace(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml',self.xml('text'))])
    def test_xml_comment_child(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml',self.xml('<!-- hidden -->'))])
    def test_processing_instruction_child(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml',self.xml('<?x y?>'))])
    def test_dtd(self):
        with self.assertRaises(ValueError):self.check([('word/comments.xml','<!DOCTYPE x>'+self.xml())])


class ReadingPair(unittest.TestCase):
    source=b'# Supplement\n\n## Contents\n\nNAVIGATION_PLACEHOLDER\n\n# S1 Methods\n\nBody\n\n# References\n'
    labels={'S1 Methods':'S1 Methods','References':'References'}
    pages={'S1 Methods':2,'References':67}
    expected=b'# Supplement\n\n## Contents\n\n| Section | PDF page |\n| --- | ---: |\n| S1 Methods | 2 |\n| References | 67 |\n\n# S1 Methods\n\nBody\n\n# References\n'
    def test_exact_pair(self):
        self.assertEqual(q.reading_source_bytes('supplement',self.source,self.labels,self.pages),self.expected)
        q.check_reading_pair('supplement',self.source,self.expected,self.labels,self.pages)
    def test_main_token_rejected(self):
        with self.assertRaises(ValueError):q.reading_source_bytes('main',self.source,{},self.pages)
    def test_duplicate_token(self):
        with self.assertRaises(ValueError):q.reading_source_bytes('supplement',self.source+b'\nNAVIGATION_PLACEHOLDER\n',self.labels,self.pages)
    def test_nonstandalone(self):
        with self.assertRaises(ValueError):q.reading_source_bytes('supplement',self.source.replace(b'NAVIGATION_PLACEHOLDER',b'x NAVIGATION_PLACEHOLDER'),self.labels,self.pages)
    def test_other_marker(self):
        with self.assertRaises(ValueError):q.reading_source_bytes('supplement',self.source+b'TODO',self.labels,self.pages)
    def test_wrong_toc(self):
        with self.assertRaises(ValueError):q.check_reading_pair('supplement',self.source,self.expected,self.labels,{**self.pages,'References':66})
    def test_edited_reading(self):
        with self.assertRaises(ValueError):q.check_reading_pair('supplement',self.source,self.expected.replace(b'Body',b'Edited'),self.labels,self.pages)
    def test_missing_mapping(self):
        with self.assertRaises(ValueError):q.reading_source_bytes('supplement',self.source,{'References':'References'},self.pages)
    def test_main_unchanged(self):
        self.assertEqual(q.reading_source_bytes('main',b'Clean\n',{},{}),b'Clean\n')



class V9Contract(unittest.TestCase):
    def config(self):
        evidence=[]
        for r in sorted(q.ROLES):
            e={'role':r,'assertions':[{'pointer':'/status','equals':'explicit fixture'}],
               'maps':[{'pointer':p,'base':'.'} for p in q.REQUIRED_MAPS.get(r,set())],
               'scalar_pins':[{'pointer':p,'path':'fixture'} for p in q.REQUIRED_SCALAR_PINS.get(r,set())],
               'record_lists':[{'pointer':p,'base':'.'} for p in q.REQUIRED_RECORD_LISTS.get(r,set())]}
            if r in q.V9_ROLES and not (e['maps'] or e['scalar_pins'] or e['record_lists']):
                e['maps']=[{'pointer':'/outputs','base':'.'}]
            if r.endswith('downstream_chain'):e['phase_chain']=[{'phase':p} for p in ['preflight','calibrate','score','assess']]
            evidence.append(e)
        return {'schema':'v9-final-qa-1','finalization_authorized':True,'documents':{'main':{},'supplement':{}},
                'v8_sources':{'main':{},'supplement':{}},'evidence':evidence,
                'content_contract':{'main':[18,140,4,4],'supplement':[50,350,44,2],'references':23}}
    def test_explicit_contract(self):q.validate_config(self.config())
    def test_counts_not_frozen_in_source(self):
        c=self.config()['content_contract'];q.check_counts('main',c['main'],c)
        with self.assertRaises(ValueError):q.check_counts('main',[17,133,4,4],c)
        for value in [True,0,-1,1.0]:
            d=json.loads(json.dumps(c));d['main'][0]=value
            with self.assertRaises(ValueError):q.contract(d)
    def test_reference_prefix(self):
        old='\n\n'.join('[%d] Original reference %d'%(i,i) for i in range(1,22))
        new=old+'\n\n[22] New primary one\n\n[23] New primary two\n'
        q.reference_prefix(old,new,23)
        for text,n in [(new.replace('Original reference 1','Edited reference 1'),23),(new,21),(new.replace('[23]','[24]'),23)]:
            with self.assertRaises(ValueError):q.reference_prefix(old,text,n)
    def test_missing_roles_maps_chain_and_authority(self):
        for r in q.V9_ROLES:
            c=self.config();c['evidence']=[e for e in c['evidence'] if e['role']!=r]
            with self.assertRaises(ValueError):q.validate_config(c)
        for role,key in [('v9_assembly','maps'),('v9_assembly','scalar_pins'),('four_tree_downstream_chain','phase_chain')]:
            c=self.config();next(e for e in c['evidence'] if e['role']==role)[key]=[]
            with self.assertRaises(ValueError):q.validate_config(c)
        c=self.config();c['finalization_authorized']=False
        with self.assertRaises(ValueError):q.validate_config(c)
        c=self.config();c['evidence'].append({'role':'eight_tree_result'})
        with self.assertRaises(ValueError):q.validate_config(c)
    def test_original_guards_ast(self):
        import ast
        def funcs(name):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse((Path(__file__).parent/name).read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        old=funcs('finalize_v8.py');new=funcs('finalize_v9.py')
        changed={'check_counts','check_references','validate_config','document','run'}
        for n in old.keys()-changed:self.assertEqual(old[n],new[n],n)
    def test_phase_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();pins=q.Pins(root)
            def put(name,obj):
                p=root/name;p.write_text(json.dumps(obj));return {'path':name,'sha256':q.sha(p)}
            rows=[];pred='a'*64
            for phase in ['preflight','calibrate','score','assess']:
                payload=put(phase+'_out',{'synthetic':True})
                ap=put(phase+'_approval',dict(actual_execution_authorized=True,phase=phase,registry_sha256='b'*64,predecessor_sha256=pred))
                receipt=put(phase+'_complete',dict(status='COMPLETE',phase=phase,approval_sha256=ap['sha256'],registry_sha256='b'*64,summary={'predecessor_sha256':pred},outputs={payload['path']:payload['sha256']}))
                rows.append(dict(receipt,phase=phase,approval=ap,expected_predecessor=pred,output_base='.'));pred=receipt['sha256']
            q.phase_chain(pins,rows)
            bad=json.loads(json.dumps(rows));bad[1]['expected_predecessor']='c'*64
            with self.assertRaises(ValueError):q.phase_chain(pins,bad)
            first=json.loads((root/'preflight_complete').read_text());first['status']='FAILURE'
            bad=json.loads(json.dumps(rows));bad[0].update(put('failed',first))
            with self.assertRaises(ValueError):q.phase_chain(pins,bad)
    def test_frozen_v8_distinct_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();pins=q.Pins(root)
            for n in ['main','supplement','config','helper']:(root/n).write_text('fixture')
            sources={k:{'path':k,'sha256':q.sha(root/k)} for k in ['main','supplement']}
            d={'status':'PASS_TECHNICAL_PREPARATION','old_scientific_files':563,'files':{n:q.sha(root/n) for n in ['main','supplement','config','helper']},'config_path':'config','config_sha256':q.sha(root/'config'),'helper_sha256':q.sha(root/'helper')}
            e={'maps':[{'pointer':'/files','base':'.'}]}
            q.frozen_v8(pins,e,d,{'v8_sources':sources})
            d['old_scientific_files']=0
            with self.assertRaises(ValueError):q.frozen_v8(pins,e,d,{'v8_sources':sources})
    def test_assembly_exact_role_base_and_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();pins=q.Pins(root);docs={}
            for k in ['main','supplement']:
                p=root/(k+'.complete.md');p.write_text(k);docs[k]={'source':{'path':p.name,'sha256':q.sha(p)}}
            d={'status':'ASSEMBLED_NOT_RENDERED_OR_VISUALLY_VERIFIED','outputs':{k+'.complete.md':v['source']['sha256'] for k,v in docs.items()},'asset_sha256':{'figures/f'+str(i)+ext:'a'*64 for i in range(6) for ext in ['.png','.pdf','.svg']},'counts':{'references_each':23}}
            e={'maps':[{'pointer':'/outputs','base':'.'}]};c={'documents':docs,'content_contract':{'references':23}}
            q.v9_assembly(pins,e,d,c)
            with self.assertRaises(ValueError):q.v9_assembly(pins,{'maps':[{'pointer':'/outputs','base':'wrong'}]},d,c)
            d['asset_sha256'].pop('figures/f0.png')
            with self.assertRaises(ValueError):q.v9_assembly(pins,e,d,c)

if __name__=='__main__':unittest.main()
