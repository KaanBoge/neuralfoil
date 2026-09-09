"""Source-only manufactured phase, namespace, numeric and storage checks."""
from pathlib import Path
from fractions import Fraction as F
import ast,hashlib,sys,types,unittest,tempfile,copy,contextlib
from unittest.mock import patch
import numpy as np
import pandas as pd
import four_barrier as barrier
import run
H=Path(__file__).resolve().parent;R=H.parents[2];OLD=R/'model_proposal/paired_tree_plan/all_context_plan'
def enc(x):
    x=F(x);return {'encoding':'signed_hex_fraction_v1','numerator':hex(x.numerator),'denominator':hex(x.denominator)}
def modules():
    paths={'legacy_adapter':OLD/'adapter.py','storage':H/'storage.py','four_barrier':H/'four_barrier.py','adapter':H/'adapter.py','study_inputs':H/'study_inputs.py','legacy_results':H/'legacy_results.py','study':H/'study.py'}
    return run.loaded({k:(p,p.read_bytes()) for k,p in paths.items()})
class Tests(unittest.TestCase):
    def test_missing_barrier_cannot_freeze(self):
        with self.assertRaises((KeyError,ValueError)):barrier.validate_registry({'four_tree':{}})
    def test_whole_phase_deadline_before_source_bootstrap(self):
        with patch.object(run.time,'monotonic',return_value=10),patch.object(run.signal,'signal'),patch.object(run.signal,'getsignal',return_value='previous'),patch.object(run.signal,'setitimer') as timer,patch.object(run,'execute_bounded',return_value='ok') as work:
            self.assertEqual(run.execute('synthetic'),'ok');work.assert_called_once_with('synthetic',910)
            self.assertEqual(timer.call_args_list[0].args,(run.signal.ITIMER_REAL,900));self.assertEqual(timer.call_args_list[-1].args,(run.signal.ITIMER_REAL,0))
    def test_exact_bound_nesting(self):
        paired={'D':{'lower':enc(-1),'upper':enc(2),'B':enc(1)}}
        s={'original_adjacent':paired['D'],'stage0':{'B':enc(2)},'final':{'B':enc(F(1,2))}}
        barrier.compare(s,paired)
        s['final']['B']=enc(3)
        with self.assertRaises(ValueError):barrier.compare(s,paired)
    def test_strict_rational(self):
        self.assertEqual(barrier.fraction(enc(F(-1,3))),F(-1,3))
        for v in [{'encoding':'signed_hex_fraction_v1','numerator':'0x2','denominator':'0x4'},dict(enc(1),extra=1),dict(enc(1),denominator='0x0')]:
            with self.assertRaises(ValueError):barrier.fraction(v)
    def test_inference_and_pure_helpers_unchanged(self):
        old=ast.parse((R/'model_proposal/paired_tree_plan/all_context_downstream_plan/study.py').read_text());new=ast.parse((H/'study.py').read_text())
        for name in ['score','scalar_match','exact_key_parity','phase_file','complete']:
            pick=lambda tree:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(pick(old)),ast.dump(pick(new)))
        self.assertEqual((H/'storage.py').read_bytes(),(R/'model_proposal/paired_tree_plan/all_context_downstream_plan/storage.py').read_bytes())
        old=ast.parse((OLD/'study_inputs.py').read_text());new=ast.parse((H/'study_inputs.py').read_text())
        for node in old.body:
            if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
                self.assertEqual(ast.dump(node),ast.dump(next(n for n in new.body if isinstance(n,type(node)) and n.name==node.name)))
    def test_fixed_names_and_cumulative_roots(self):
        with modules() as m:
            a=m['adapter'];si=m['study_inputs']
            self.assertEqual(len(si.OLD_REFS),9);self.assertEqual(len(si.REFS),10)
            self.assertEqual(si.REFS[-1],si.PAIRED[1]);self.assertEqual(len(si.LABELS),2)
            roots=a.roots();self.assertEqual(len(roots),len(set(roots)))
            self.assertTrue(any('all_context_downstream_plan/assess' in str(p) for p in roots))
            self.assertTrue(any('all_context_proposal/implementation/certificates_replay' in str(p) for p in roots))
            self.assertEqual(m['storage'].CAP,9*2**28)
            self.assertIn('SCALAR_DIRECTIONS.json',a.names('calibrate'))
    def test_role_exclusion_and_phase_guards(self):
        with modules() as m:
            si=m['study_inputs'];role={k+'_'+suffix:[] for k in ['proper','calibration','test'] for suffix in ['indices','groups']}
            role['proper_indices']=[1];role['calibration_indices']=[1]
            with self.assertRaises(ValueError):si.verify_roles(role)
            for phase in ['preflight','score']:
                reader=si.Reader({},phase,'synthetic',[])
                with self.assertRaises(ValueError):reader.arrays('calibration/a.npz',['MEAS_CD'])
            with self.assertRaises(ValueError):m['legacy_results'].payload({}, {},'assess','bootstrap.csv','calibrate',[])
    def test_storage_prewrite_preserves_old_paths(self):
        with modules() as m,tempfile.TemporaryDirectory() as t:
            p=Path(t).resolve();old=p/'old';new=p/'new';old.mkdir();new.mkdir();(old/'fixed').write_bytes(b'x'*80)
            budget=m['storage'].Budget([old,new],new,{'x'},cap=100,reserve=10)
            with self.assertRaises(OSError):budget.bytes(new/'x',b'y'*11)
            self.assertFalse((new/'x').exists());self.assertEqual((old/'fixed').read_bytes(),b'x'*80)
    def test_342_bootstrap_rows_exact_in_420(self):
        path=R/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/fresh_extraction_v1/code/metrics.py';raw=path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'f029c9e61e29a20b6232dd21f2b891b5e4a01c3351cf5c92e1a7518eaa1c1fb4')
        metric=types.ModuleType('synthetic_metrics');exec(compile(raw,str(path),'exec'),metric.__dict__)
        with modules() as m:
            si=m['study_inputs'];oldlabels=si.PAIRED+si.OLD_KL+metric.LABELS
            size=8371;frame=pd.DataFrame({'split':np.repeat(['group_20260906_fold_0','group_20260908_fold_0'],size),'nf2_row_id':np.tile(np.arange(size),2),'group':np.tile(np.arange(size)%93,2),'measured_CD':np.full(2*size,.01)})
            for j,label in enumerate(oldlabels+si.LABELS):frame[label]=.015+j*.0001+np.arange(2*size)*1e-10
            metric.LABELS=oldlabels;metric.REFERENCES=si.OLD_REFS;old=metric.bootstrap(frame)
            metric.LABELS=si.LABELS+oldlabels;metric.REFERENCES=si.REFS;new=metric.bootstrap(frame)
            m['study'].exact_key_parity(old,new[new.candidate.isin(oldlabels)&new.reference.isin(si.OLD_REFS)],['candidate','assignment','reference'])
            self.assertEqual(len(old),342);self.assertEqual(len(new),420)
    def test_complete_mock_certificate_chain_and_model_tamper(self):
        contexts=['c'+str(i) for i in range(15)]+['final'];root=Path('/private/tmp/manufactured_not_read');folder='certificates'
        f={'root':folder,'registry_sha256':'r','context_support_sha256':'s','producer_sha256':'p','replay_sha256':'v','producer_approval_sha256':'pa','replay_approval_sha256':'va'}
        bounds={'lower':enc(-1),'upper':enc(1),'B':enc(1)}
        summary={'stage0':bounds,'original_adjacent':bounds,'final':dict(bounds,B=enc(F(1,2))),'counts':{'trees':400}}
        inherited={'context':'final','status':'INHERITED_AUTHENTICATED','model_sha256':'mfinal','summary':copy.deepcopy(summary)}
        cr={'sources':{'context_support.py':'s'},'contexts':[{'context':c,'model_sha256':'m'+c} for c in contexts]}
        records={str(root/folder/'REGISTRY_v3.json'):cr}
        for phase,key in [('certificates_produce','producer'),('certificates_replay','replay')]:
            records[str(root/folder/('ROOT_'+phase.upper()+'_APPROVAL.json'))]={'producer_complete_sha256':'p'}
            aggregate={'status':'COMPLETE','phase':phase,'registry_sha256':'r','approval_sha256':f[key+'_approval_sha256'],'contexts':{},'fresh_contexts':15,'inherited_contexts':1,'fits':0,'features_targets_loaded':0,'R_used':False,'producer_complete_sha256':'p','outputs':{}}
            for c in contexts[:-1]:
                s=copy.deepcopy(summary)
                if key=='replay':s.update(producer_complete_sha256='child'+c,certificate_sha256='cert'+c)
                child={'status':'COMPLETE','context':c,'phase':phase,'registry_sha256':'r','approval_sha256':f[key+'_approval_sha256'],'model_sha256':'m'+c,'summary':s,'outputs':{'certificate.json':'cert'+c} if key=='producer' else {}}
                records[str(root/folder/phase/c/'COMPLETE.json')]=child;aggregate['contexts'][c]={'complete_sha256':'child'+c,'summary':s}
            aggregate['contexts']['final']=inherited;records[str(root/folder/phase/'COMPLETE.json')]=aggregate
        support=types.SimpleNamespace(CONTEXTS=contexts,authenticate=lambda *x:None,strict_approval=lambda *x:None,verify_outputs=lambda *x:None,inherited=lambda *x:inherited)
        @contextlib.contextmanager
        def fake_modules(*unused):yield {'four_context_support':support}
        paired={'summary':{'contexts':{c:{'summary':{'D':bounds}} for c in contexts}}}
        jread=lambda path,*unused:records[str(path)]
        result=barrier.authenticate({'four_tree':f},root,None,jread,[],contexts,paired,fake_modules)
        self.assertEqual(len(result['summary']['contexts']),16)
        records[str(root/folder/'certificates_replay'/'c0'/'COMPLETE.json')]['model_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'model binding'):barrier.authenticate({'four_tree':f},root,None,jread,[],contexts,paired,fake_modules)
if __name__=='__main__':unittest.main()
