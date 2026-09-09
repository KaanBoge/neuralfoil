"""Manufactured authoring fixtures only. No real V9 assembly or renderer."""
from pathlib import Path
import copy,json,tempfile,unittest
import assemble_submission as a

def fixture(root):
    rev=Path('submission_revision_20260908');v9=rev/'renewed_manuscript_v9';v8=rev/'renewed_manuscript_v8'
    inputs={}
    def put(key,relative,raw):
        if isinstance(raw,str):raw=raw.encode()
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        inputs[key]={'path':str(relative),'sha256':a.sha(raw)}
    refs='# References\n\n'+''.join(f'[{i}] Fixed reference {i}.\n\n' for i in range(1,22))
    def table(label,index):return f'Table {label}. Preserved caption.\n\n| Label | Numeric |\n|---|---|\n| Row {index} | {index}.012300 |\n\n'
    main='# Main\n\n'+''.join(table(str(i),i) for i in range(1,5))+''.join(f'![figure {i}](figures/figure_{i}.png)\n\n' for i in range(1,5))+refs
    supp='# Supplement\n\nNAVIGATION_PLACEHOLDER\n\n| Uncaptioned | Fixed |\n|---|---|\n| A | 0.5 |\n\n'+''.join(table('S'+str(i),i) for i in range(1,36))+''.join(f'![figure {i}](figures/figure_{i}.png)\n\n' for i in range(5,7))+refs
    for key,prefix,name,text in [('main',v9,'manuscript.md',main),('supplement',v9,'supplement.md',supp),('v8_main',v8,'main.complete.md',main),('v8_supplement',v8,'supplement.complete.md',supp)]:put(key,prefix/name,text)
    put('refined',v9/'additions/refined_results.md','# S12 Results\n\n@@PAIRED_TABLES@@\n\n@@FOUR_TREE_DOWNSTREAM@@\n')
    put('runtime',v9/'additions/runtime.md','# S13 Runtime\n\n@@TIMING_TABLES@@\n')
    tokens={}
    for token,prefix,key in [('@@PAIRED_TABLES@@','P','paired'),('@@FOUR_TREE_DOWNSTREAM@@','F','four'),('@@TIMING_TABLES@@','T','timing')]:
        text=''.join(table(prefix+str(i),i+40) for i in range(1,4))
        if prefix=='P':text=text.replace('Row 42','A: SG exposed/eligible only/W new challenge')
        put(key,rev/('work/displays/'+key+'.md'),text)
        tokens[token]={'input':key,'caption_renames':[[prefix+str(i+1),target] for i,target in enumerate(a.TOKENS[token])],'p2_label_map':[['A: ','A '],['SG exposed','SG'],['eligible only/','Eligible '],['W new challenge','W'],['/',' ']] if prefix=='P' else []}
    assets=[]
    for i in range(1,7):
        for ext in ['png','pdf','svg']:
            key=f'asset_{i}_{ext}';assets.append(key);put(key,v9/f'figures/figure_{i}.{ext}',b'synthetic image bytes')
    evidence={}
    for key in sorted(a.EVIDENCE):evidence[key]=key;put(key,rev/f'work/evidence/{key}.json','{}')
    cfg={'schema':'V9_FINITE_ASSEMBLY_V1','version':'v1','inputs':inputs,'roles':{k:k for k in ['main','supplement','v8_main','v8_supplement']},'additions':['refined','runtime'],'tokens':tokens,'assets':assets,'evidence':evidence,'predecessor':None}
    return cfg,root/v9

class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.cfg,self.here=fixture(self.root)
    def tearDown(self):self.tmp.cleanup()
    def rewrite(self,key,transform):
        spec=self.cfg['inputs'][key];p=self.root/spec['path'];b=transform(p.read_text()).encode();p.write_bytes(b);spec['sha256']=a.sha(b)
    def test_complete_fixture_preserves_all_old_bytes_and_numbers(self):
        outputs,report=a.compose(self.cfg,self.root)
        self.assertEqual(report['old_table_preservation']['main']['pipe_tables'],4);self.assertEqual(report['old_table_preservation']['supplement']['pipe_tables'],36)
        self.assertIn(b'| A SG Eligible W | 42.012300 |',outputs['supplement.complete.md'])
        self.assertEqual(outputs['supplement.complete.md'].count(b'Table S44.'),1)
    def test_missing_four_block_and_duplicate_token_fail(self):
        self.rewrite('refined',lambda s:s.replace('@@FOUR_TREE_DOWNSTREAM@@',''))
        with self.assertRaisesRegex(ValueError,'token must'):a.compose(self.cfg,self.root)
        self.rewrite('refined',lambda s:s+'@@FOUR_TREE_DOWNSTREAM@@\n@@FOUR_TREE_DOWNSTREAM@@')
        with self.assertRaisesRegex(ValueError,'token must'):a.compose(self.cfg,self.root)
    def test_old_numeric_cell_and_caption_change_rejected(self):
        self.rewrite('main',lambda s:s.replace('1.012300','1.012301'))
        with self.assertRaisesRegex(ValueError,'old table'):a.compose(self.cfg,self.root)
    def test_reference_change_rejected(self):
        self.rewrite('main',lambda s:s.replace('Fixed reference 1.','Changed reference 1.'))
        with self.assertRaisesRegex(ValueError,'reference bytes'):a.compose(self.cfg,self.root)
    def test_only_fixed_label_and_caption_maps(self):
        self.cfg['tokens']['@@PAIRED_TABLES@@']['p2_label_map'].append(['42','0'])
        with self.assertRaisesRegex(ValueError,'unapproved label'):a.compose(self.cfg,self.root)
    def test_numeric_first_column_is_not_normalizable_label(self):
        text=''.join(f'Table P{i}. Caption\n\n| Key | Value |\n|---|---|\n| 1/2 | 4.00 |\n\n' for i in range(1,4))
        with self.assertRaisesRegex(ValueError,'numeric first'):a.render_block(text,self.cfg['tokens']['@@PAIRED_TABLES@@'],'@@PAIRED_TABLES@@')
    def test_todo_and_navigation_scope_rejected(self):
        self.rewrite('runtime',lambda s:s+'\nTODO\n')
        with self.assertRaisesRegex(ValueError,'unresolved'):a.compose(self.cfg,self.root)
        with self.assertRaises(ValueError):a.clean('NAVIGATION_PLACEHOLDER','main')
    def test_hash_missing_asset_and_unsafe_path_rejected(self):
        self.cfg['inputs']['main']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'input hash'):a.compose(self.cfg,self.root)
        with self.assertRaises(ValueError):a.path(self.root,'../outside')
    def test_versioned_publish_requires_exact_archived_predecessor(self):
        config=self.here/'config.json';raw=json.dumps(self.cfg).encode();config.write_bytes(raw)
        a.publish(self.cfg,raw,config,self.root,self.here)
        first=self.here/'work/assembly_versions/v1';self.assertTrue((first/'ASSEMBLY.json').exists())
        with self.assertRaises(FileExistsError):a.publish(self.cfg,raw,config,self.root,self.here)
        pins={n:a.sha((first/n).read_bytes()) for n in ['main.complete.md','supplement.complete.md','ASSEMBLY.json']}
        self.cfg.update(version='v2',predecessor={'version':'v1','sha256':pins});raw=json.dumps(self.cfg).encode();config.write_bytes(raw)
        a.publish(self.cfg,raw,config,self.root,self.here)
        self.assertEqual(a.sha((first/'ASSEMBLY.json').read_bytes()),pins['ASSEMBLY.json'])
    def test_wrong_predecessor_alias_rejected_without_new_snapshot(self):
        self.cfg.update(version='v2',predecessor={'version':'v1','sha256':{k:'0'*64 for k in ['main.complete.md','supplement.complete.md','ASSEMBLY.json']}})
        config=self.here/'config.json';raw=json.dumps(self.cfg).encode();config.write_bytes(raw)
        with self.assertRaises((ValueError,FileNotFoundError)):a.publish(self.cfg,raw,config,self.root,self.here)
        self.assertFalse((self.here/'work/assembly_versions/v2').exists())
if __name__=='__main__':unittest.main()
