import io,json,os,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import adapter as a,certificates,study,study_inputs as si

class Tests(unittest.TestCase):
    def test_module_restore_success_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'m.py';p.write_text('value=3\n');sentinel=types.ModuleType('saved');sys.modules['adapter_test_saved']=sentinel
            with a.modules({'adapter_test_saved':(p,a.sha(p.read_bytes()))},[]) as m:self.assertEqual(m['adapter_test_saved'].value,3)
            self.assertIs(sys.modules['adapter_test_saved'],sentinel)
            p.write_text('raise ValueError("intentional")\n')
            with self.assertRaises(ValueError):
                with a.modules({'adapter_test_new':(p,a.sha(p.read_bytes()))},[]):pass
            self.assertNotIn('adapter_test_new',sys.modules);sys.modules.pop('adapter_test_saved')
    def test_context_registry(self):
        rows=json.loads((a.HERE/'CONTEXTS.json').read_bytes())
        m={'files':{r['member']:r['sha256'] for r in rows},'trees':[{'context':r['context'],'branch':'proper','capped':r['member'],'upper_free':r['member'].replace('capped','upper_free')} for r in rows]}
        a.verify_contexts(rows,m)
        for mutate in ['missing','duplicate','hash','member']:
            x=json.loads(json.dumps(rows))
            if mutate=='missing':x.pop()
            if mutate=='duplicate':x[-1]=x[0]
            if mutate=='hash':x[0]['sha256']='0'*64
            if mutate=='member':x[0]['member']=x[1]['member']
            with self.assertRaises(ValueError):a.verify_contexts(x,m)
    def test_no_final_dispatch(self):
        args=types.SimpleNamespace(context='final')
        with self.assertRaises(ValueError):certificates.child(args)
    def test_context_stage0(self):
        from fractions import Fraction
        def dec(x):return Fraction(x)
        old={'records':[{'context':'a','range':{'lower':{'numerator':'-1','denominator':'2'},'upper':{'numerator':'1','denominator':'2'}},'B_structural':{'numerator':'1','denominator':'2'}}],'accessed_tree_sha256':{'x':'h'}}
        c={'stage0':{'lower':'-1/2','upper':'1/2','B':'1/2'}}
        a.stage0_equal(c,old,{'context':'a','member':'x','sha256':'h'},dec)
        with self.assertRaises(ValueError):a.stage0_equal(c,old,{'context':'b','member':'x','sha256':'h'},dec)
        with self.assertRaises(ValueError):a.stage0_equal(c,old,{'context':'a','member':'x','sha256':'bad'},dec)
    def test_disk_preflight(self):
        with patch('adapter.shutil.disk_usage',return_value=types.SimpleNamespace(free=a.LOGICAL_CAP-1)):
            with self.assertRaises(OSError):a.disk_preflight(a.HERE)
        with patch('adapter.shutil.disk_usage',return_value=types.SimpleNamespace(free=a.LOGICAL_CAP)):
            self.assertEqual(a.disk_preflight(a.HERE)['reserved_logical_bytes'],a.LOGICAL_CAP)
    def test_fresh_process(self):
        code,out,err,error=certificates.run_child([sys.executable,'-B','-c','import os;print(os.getpid())'],5)
        self.assertIsNone(error)
        self.assertEqual(code,0);self.assertNotEqual(int(out),os.getpid())
    def test_timeout_failure(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'attempt'
            with self.assertRaises(TimeoutError):a.attempt(p,{},lambda *_:time.sleep(.1),seconds=.01)
            self.assertTrue((p/'FAILURE.json').exists())
            with self.assertRaises(FileExistsError):a.attempt(p,{},lambda *_:{})
    def test_forbidden_phase(self):
        buf=io.BytesIO();np.savez(buf,BASE_CD=np.array([1.]),MEAS_CD=np.array([2.]))
        for phase in ['preflight','score','assess']:
            r=si.Reader({'calibration/a.npz':buf.getvalue()},phase,'synthetic',[])
            with self.assertRaises(ValueError):r.arrays('calibration/a.npz',['MEAS_CD'])
        r=si.Reader({'scalars/a.json':b'{}'},'preflight','synthetic',[])
        with self.assertRaises(ValueError):r.json('scalars/a.json')
        with self.assertRaises(ValueError):r.csv('prediction_csv/a.csv')
    def test_npz_actual_member_ledger(self):
        buf=io.BytesIO();np.savez(buf,BASE_CD=np.array([1.]),MEAS_CD=np.array([2.]))
        ledger=[];r=si.Reader({'calibration/a.npz':buf.getvalue()},'preflight','synthetic',ledger)
        r.arrays('calibration/a.npz',['BASE_CD']);self.assertEqual([x['member'] for x in ledger if x['operation']=='NPZ materialization'],['BASE_CD'])
    def test_role_overlap(self):
        r={'proper_groups':['a'],'calibration_groups':['b'],'test_groups':['c'],'proper_indices':[1],'calibration_indices':[2],'test_indices':[3]}
        si.verify_roles(r);r['test_indices']=[2]
        with self.assertRaises(ValueError):si.verify_roles(r)
    def test_overlay_preservation(self):
        label=si.LABELS[0]
        frame=pd.DataFrame({'split':['group_a']*2,'nf2_row_id':[4,3],'mean8_CD':[1.,2.],'int':pd.Series([1,2],dtype='int32'),'bool':[True,False],'old':[.1,.2]})
        f=pd.DataFrame({'nf2_row_id':[3,4],'BASE_CD':[2.,1.],label:[.4,.3],label+'__effective_fraction':[0.,0.],label+'__strength':[.5,.5],label+'__intervened':[True,True]})
        out=si.typed_overlay(frame.copy(),{'group_a':f},[label]);pd.testing.assert_frame_equal(out[frame.columns],frame,check_exact=True)
        self.assertEqual(list(out[label]),[.3,.4])
        f['nf2_row_id']=[3,3]
        with self.assertRaises(ValueError):si.typed_overlay(frame.copy(),{'group_a':f},[label])
    def test_external_order(self):
        label=si.LABELS[0];frame=pd.DataFrame({'split':['SG_exposed']*2,'mean8_CD':[1.,1.]})
        f=pd.DataFrame({'indices':[1,0],'BASE_CD':[1.,1.]})
        with self.assertRaises(AssertionError):si.typed_overlay(frame,{'SG_exposed':f},[label])
    def test_exact_reference_key_compare(self):
        old=pd.DataFrame({'candidate':['a','b'],'assignment':[1,1],'reference':['r','r'],'value':[1.,2.]})
        study.exact_key_parity(old,old.iloc[::-1],['candidate','assignment','reference'])
        bad=old.copy();bad.loc[0,'value']+=1e-12
        with self.assertRaises(AssertionError):study.exact_key_parity(old,bad,['candidate','assignment','reference'])
    def test_failure_context_blocks_cal(self):
        bad={'status':'COMPLETE','registry_sha256':'x','phase':'certificates_replay','outputs':{},'summary':{'contexts':{}}}
        with patch('adapter.json_read',return_value=bad):
            with self.assertRaises(ValueError):study.complete('certificates_replay','p','x',[])
    def test_old_bootstrap_reference_parity(self):
        path=a.ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/fresh_extraction_v1/code/metrics.py'
        pin='f029c9e61e29a20b6232dd21f2b891b5e4a01c3351cf5c92e1a7518eaa1c1fb4'
        with a.modules({'synthetic_metrics':(path,pin)},[]) as modules:
            m=modules['synthetic_metrics'];m.LABELS=si.OLD_KL+list(m.LABELS);m.REFERENCES=list(si.OLD_REFS)
            oldlabels=list(m.LABELS);size=8371
            f=pd.DataFrame({'split':np.repeat(['group_20260906_fold_0','group_20260908_fold_0'],size),'nf2_row_id':np.tile(np.arange(size),2),'group':np.tile(np.arange(size)%93,2),'measured_CD':np.full(size*2,.01)})
            for i,label in enumerate(oldlabels+si.LABELS):f[label]=.015+i*.0001+np.arange(size*2)*1e-10
            old=m.bootstrap(f)
            m.LABELS=si.LABELS+oldlabels;m.REFERENCES=list(si.REFS)
            new=m.bootstrap(f);keep=new.candidate.isin(oldlabels)&new.reference.isin(si.OLD_REFS)
            study.exact_key_parity(old,new[keep],['candidate','assignment','reference'])
            self.assertEqual(len(old),238);self.assertEqual(len(new),342)
    def test_unchanged_pure_sources(self):
        self.assertEqual(a.sha((a.SOLE/'producer.py').read_bytes()),'dc28448fb05b99c2c6ec9b8d87aa3dfde1b4b77f4b997ce64946a546b5edab69')
        self.assertEqual(a.sha((a.ROOT/'uncertainty_review/range_bound_feasibility/paired_checker.py').read_bytes()),'33e04358f4ac925b79f5022880c128bd6b0e55016c8e45262e2db8a5ea4bf30b')

if __name__=='__main__':unittest.main()
