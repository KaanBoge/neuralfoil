import io,json,sys,tempfile,types,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import diagnostic as d
import run
class Tests(unittest.TestCase):
    def test_ulp_and_signed_zero(self):
        x=np.array([1.,-1.,0.]);y=np.array([np.nextafter(1.,2.),np.nextafter(-1.,0.),-0.])
        r=d.compare(x,y);self.assertEqual(r['different_count'],3);self.assertEqual(r['max_ULPs'],1)
        self.assertFalse(r['bitwise_equal']);self.assertEqual(d.compare(x,x)['max_ULPs'],0)
    def test_shape_dtype_not_accepted(self):
        self.assertFalse(d.compare(np.ones(2),np.ones((2,1)))['same_shape_dtype'])
        self.assertFalse(d.compare(np.ones(2),np.ones(2,dtype='float32'))['same_shape_dtype'])
    def test_layout_preserved(self):
        x=np.asfortranarray(np.ones((2,3)));self.assertTrue(d.layout(x)['F']);self.assertFalse(d.layout(x)['C'])
    def test_npz_selective_and_invalid(self):
        values={k:np.ones((2,62) if k=='X62' else (2,8) if k=='all_model_CD' else (2,),dtype=bool if k=='gate' else float) for k in d.KEYS}
        def payload():
            buf=io.BytesIO();np.savez(buf,**{'SG_exposed_'+k:v for k,v in values.items()},MEAS_CD=np.array(['not loaded']));return buf.getvalue()
        ledger=[];d.arrays(payload(),ledger,n=2)
        self.assertEqual([r['member'] for r in ledger],['SG_exposed_'+k for k in d.KEYS])
        values['BASE_CD'][0]=np.nan
        with self.assertRaises(ValueError):d.arrays(payload(),[],n=2)
    def test_capture_unchanged_and_restore(self):
        def f(x):
            raw=x+1;return raw*2
        old=sys.getprofile();expected=f(np.ones(2));result,cap,layout=d.capture(lambda:f(np.ones(2)),f)
        np.testing.assert_array_equal(result,expected);np.testing.assert_array_equal(cap['raw'],[2,2]);self.assertIs(sys.getprofile(),old)
        with self.assertRaises(ValueError):d.capture(lambda:(_ for _ in ()).throw(ValueError('synthetic')),f)
        self.assertIs(sys.getprofile(),old)
    def test_module_restore(self):
        with self.assertRaises(ValueError):
            with d.modules({'onlysynthetic':(Path('s.py'),b'raise ValueError("synthetic")')},[]):pass
        self.assertNotIn('onlysynthetic',sys.modules)
    def test_hash_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve();(p/'a').write_bytes(b'test');(p/'link').symlink_to(p/'a')
            with self.assertRaises(ValueError):d.read(p/'a','0'*64,[])
            with self.assertRaises(ValueError):d.read(p/'link',d.sha(b'test'),[])
    def test_serialization_exclusive_cap(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()
            with self.assertRaises(ValueError):d.save(p,'DIAGNOSTICS.json',{'x':float('nan')})
            self.assertFalse((p/'DIAGNOSTICS.json').exists())
            d.save(p,'DIAGNOSTICS.json',{})
            with self.assertRaises(FileExistsError):d.save(p,'DIAGNOSTICS.json',{})
            with self.assertRaises(ValueError):d.save(p,'evil.json',{})
            with patch.object(d,'CAP',2**20):
                with self.assertRaises(ValueError):d.save(p,'ACCESS.json',{})
    def test_approval_before_data(self):
        with tempfile.TemporaryDirectory() as td,patch.object(run,'HERE',Path(td).resolve()):
            p=Path(td).resolve();reg={'sources':{},'runtime':run.runtime(),'members':[]};raw=json.dumps(reg).encode();(p/'REGISTRY.json').write_bytes(raw)
            bad=json.dumps({'actual_execution_authorized':False}).encode();(p/'approval').write_bytes(bad)
            args=types.SimpleNamespace(registry_sha256=d.sha(raw),approval=p/'approval',approval_sha256=d.sha(bad))
            with self.assertRaises(ValueError):run.main(args)
            self.assertTrue((p/'actual_attempt_1/FAILURE.json').exists())
            with self.assertRaises(FileExistsError):run.main(args)
    def test_synthetic_equation_path(self):
        # Only reviewed source buffers plus a two-leaf synthetic model, no fitted JSON.
        project=run.PROJECT
        paths={'sg_prepared':project/'model_development_20260907_geometry_frontier/engineering/fast_inference/prepared.py','sg_portable':project/'model_development_20260907_risk_policy/portable/predictor.py','sg_native':project/'model_development_20260907_risk_policy/risk_policy.py'}
        pins={'sg_prepared':'811d32e06f5848d139b58d9923cc43d7676e91c8f5140fe9c33050393104f244','sg_portable':'d97950364c0fb201a93715e90f1558912b6682df0bbfb4b8074452a331f4fb6a','sg_native':'dbe6a91fa744d16652b02f15296349407e1567ed328308a79cdbf5375abd9ab8'}
        buffers={k:(p,d.read(p,pins[k],[])) for k,p in paths.items()}
        tree={'feature':[0,0,0],'threshold':[0.,0.,0.],'left':[1,0,0],'right':[2,0,0],'leaf':[False,True,True],'value':[0.,.1,.2]}
        artifact={'schema':'experimental-risk-policy-package-v1','core':{'schema':'neuralfoil-feature-correction-v1','engine':'relative_hist','feature_key':'X62','strength':1.,'hist':{'baseline':0.,'features':62,'trees':[tree]}},'policies':{k:{'schema':'bilinear_half_anchor_harm_v1','endpoints':[[0.,0.],[1.,1.]],'corners':[.5,.6,.7,.8]} for k in ['risk_transfer','unpenalized_transfer','risk_group']}}
        x=np.ones((2,62));b=np.ones(2);a=np.ones((2,8));g=np.array([True,False]);core=np.full(2,1.2)
        with d.modules(buffers,[]) as mods:
            expected=mods['sg_native'].predict(artifact['policies']['unpenalized_transfer'],b,core,a,g)[0]
            result=d.evaluate(dict(X62=x,BASE_CD=b,all_model_CD=a,gate=g,CORE_CD=core,unpenalized_transfer=expected),artifact,mods)
        self.assertTrue(result['comparisons']['prepared_vs_portable_CD']['bitwise_equal']);self.assertTrue(result['false_gate_fallback_exact'])
if __name__=='__main__':unittest.main()
