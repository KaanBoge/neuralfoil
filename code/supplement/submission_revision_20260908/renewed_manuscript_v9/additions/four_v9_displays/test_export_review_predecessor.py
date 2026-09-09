"""Manufactured records only; no project science inputs are opened."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import export as e

def fixture():
    panels=['view_'+str(i) for i in range(31)]
    scalars=[json.dumps(dict(candidate=l,context=c,bound=dict(encoding='signed-hex-v1',numerator='1',denominator='2'),t=.125,groups=10,rows=40)).encode() for l in e.LABELS for c in e.CONTEXTS]
    tables={n:[] for n in e.TABLE_NAMES}
    for l in e.LABELS:
        tables['candidate_summary.csv'].append(dict(candidate=l,minimum='-2.12500000000000001'))
        tables['decisions.csv'].append(dict(candidate=l,advance='False'))
        for p in panels:
            r=dict(candidate=l,panel=p,rows='40')
            for b in ['xlarge_CD','mean8_CD']:r.update({b+'_improvement_percent':'-1.2345678901234567',b+'_worse_rows':'3'})
            tables['panel_metrics.csv'].append(r)
            for ref in e.REFERENCES+['xlarge_CD','mean8_CD']:tables['harm_metrics.csv'].append(dict(candidate=l,panel=p,reference=ref,worse_rows='3'))
        for ref in e.REFERENCES:
            for a in ['20260906','20260908']:tables['bootstrap.csv'].append(dict(candidate=l,reference=ref,assignment=a,draws='20000',seed='2026090831',remaining_MAE_reduction_percent='1.2345665',conditional_95pct_lower='-2.123456789012345678',conditional_95pct_upper='3.123456789012345678'))
    return scalars,{n:e.csv_bytes(v) for n,v in tables.items()},panels

class Tests(unittest.TestCase):
    def test_inventory_and_exact_source(self):
        s,t,p=fixture();before=copy.deepcopy((s,t,p));out=e.prepare(s,t,p)
        self.assertEqual((s,t,p),before)
        self.assertEqual(json.loads(out['display_cells.json'])['F3'][0][2],'+1.234566 [-2.123457, +3.123457]')
        self.assertEqual(len(json.loads(out['scalar_records.json'])),32)
        for n,b in t.items():self.assertEqual(out['source_'+n],b);self.assertEqual(e.csv_rows(out[n]),e.csv_rows(b))
        self.assertEqual(len(json.loads(out['display_cells.json'])['F1']),16)
        self.assertEqual(len(json.loads(out['display_cells.json'])['F2']),31)
        self.assertEqual(len(json.loads(out['display_cells.json'])['F3']),20)
        self.assertIn(b'False',out['decisions.csv']);self.assertIn(b'-1.235 (3)',out['TABLES.md'])
    def test_half_even_and_nonfinite(self):
        self.assertEqual(e.decimal('1.0000005'),'1.000000');self.assertEqual(e.decimal('1.0000015'),'1.000002')
        self.assertEqual(e.decimal('-1.0000005'),'-1.000000')
        for v in ['NaN','Infinity','-Infinity']:
            with self.assertRaises(ValueError):e.decimal(v)
    def test_rational_codec(self):
        self.assertEqual(e.rational_display(dict(encoding='signed-hex-v1',numerator='1',denominator='2')),'0.500000')
        for a,b in [('2','4'),('-0','1'),('0x1','2'),('1','0')]:
            with self.assertRaises(ValueError):e.rational(dict(encoding='signed-hex-v1',numerator=a,denominator=b))
    def test_missing_duplicate_and_wrong_reference(self):
        s,t,p=fixture()
        for changed in [s[:-1],s[:-1]+s[:1]]:
            with self.assertRaises(ValueError):e.prepare(changed,t,p)
        rows=e.csv_rows(t['bootstrap.csv']);rows[0]['reference']='unknown';t['bootstrap.csv']=e.csv_bytes(rows)
        with self.assertRaises(ValueError):e.prepare(s,t,p)
    def test_wrong_bootstrap_and_scalar(self):
        s,t,p=fixture();rows=e.csv_rows(t['bootstrap.csv']);rows[0]['seed']='2';t['bootstrap.csv']=e.csv_bytes(rows)
        with self.assertRaises(ValueError):e.prepare(s,t,p)
        s,t,p=fixture();v=json.loads(s[0]);v['t']=1.1;s[0]=json.dumps(v).encode()
        with self.assertRaises(ValueError):e.prepare(s,t,p)
    def test_paths_and_authentication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();raw=b'text';(root/'x').write_bytes(raw);i=e.Intake(root)
            self.assertEqual(i.read('x',e.sha(raw)),raw)
            with self.assertRaises(ValueError):i.read('x','0'*64)
            for n in ['../x','/x','a/../x','a\\x']:
                with self.assertRaises(ValueError):e.safe(root,n)
            (root/'x').write_bytes(b'changed')
            with self.assertRaises(ValueError):i.finish()
    def test_no_implicit_authorization(self):
        for cfg in [{},{'export_authorized':False}]:
            with self.assertRaises(ValueError):e.binding(cfg)
    def test_source_only(self):
        import ast
        tree=ast.parse(Path(e.__file__).read_text())
        imports={n.names[0].name for n in ast.walk(tree) if isinstance(n,ast.Import)}
        self.assertFalse(imports&{'numpy','pandas','sklearn','neuralfoil'})
    def test_mock_complete_chain_and_exclusive_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();here=root/'exporter';here.mkdir()
            def put(name,value):
                raw=value if isinstance(value,bytes) else json.dumps(value).encode();p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);return e.sha(raw)
            sources={n:put('exporter/'+n,b'# manufactured source') for n in ['export.py','test_export.py']}
            registry=put(e.STUDY+'/REGISTRY.json',{'four_tree':{'replay_sha256':'a'*64}})
            cfg=dict(schema='FOUR_V9_SAVED_DISPLAY_V1',export_authorized=True,source_sha256=sources,registry_sha256=registry,certificate_replay_sha256='a'*64,phases={},audits={},panel_order=fixture()[2])
            scalars,tables,_=fixture();previous='a'*64
            for phase in e.PHASES:
                outputs={}
                if phase=='calibrate':
                    for raw in scalars:
                        v=json.loads(raw);name=f"calibrator_{v['candidate']}_{v['context']}.json";outputs[name]=put(e.STUDY+'/'+phase+'/'+name,raw)
                if phase=='assess':outputs={n:put(e.STUDY+'/'+phase+'/'+n,b) for n,b in tables.items()}
                apath=phase+'_approval.json';ap=put(apath,dict(phase=phase,registry_sha256=registry,predecessor_sha256=previous,actual_execution_authorized=True))
                h=put(e.STUDY+'/'+phase+'/COMPLETE.json',dict(status='COMPLETE',phase=phase,registry_sha256=registry,approval_sha256=ap,summary={'predecessor_sha256':previous},outputs=outputs))
                cfg['phases'][phase]=dict(complete_sha256=h,approval_path=apath,approval_sha256=ap)
                audit=phase+'_audit.md';cfg['audits'][phase]=dict(path=audit,sha256=put(audit,b'Synthetic approved audit'),root_reviewed_pass=True);previous=h
            pin=put('binding.json',cfg)
            with patch.object(e,'HERE',here),patch.object(e,'RESEARCH',root):
                e.run(root/'binding.json',pin)
                manifest=json.loads((here/'attempt_1/MANIFEST.json').read_text())
                self.assertEqual(manifest['counts']['bootstrap'],40)
                for n,h in manifest['output_sha256'].items():self.assertEqual(e.sha((here/'attempt_1'/n).read_bytes()),h)
                with self.assertRaises(FileExistsError):e.run(root/'binding.json',pin)
            bad=copy.deepcopy(cfg);bad['phases']['score']['complete_sha256']='0'*64
            with self.assertRaises(ValueError):e.phase_chain(bad,e.Intake(root))

if __name__=='__main__':unittest.main()
