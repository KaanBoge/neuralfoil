"""Source-only manufactured phase, namespace, numeric and storage checks."""
from pathlib import Path
from fractions import Fraction as F
import hashlib,sys,types,unittest,tempfile
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
            p=Path(t);old=p/'old';new=p/'new';old.mkdir();new.mkdir();(old/'fixed').write_bytes(b'x'*80)
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
if __name__=='__main__':unittest.main()
