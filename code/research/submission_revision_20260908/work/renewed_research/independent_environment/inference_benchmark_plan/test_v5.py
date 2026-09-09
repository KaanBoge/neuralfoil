"""Synthetic reference-contract tests. No project scientific input access."""
import ast,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import oracle_v5 as oracle
import measurement_v5 as measurement
import loader_v5,runner_v5
from serving import ROUTES,COHORTS
from timing import schedule

def portable(artifact,x,b,a,gate,label):
    c=b.copy();strength=np.zeros_like(b);return c.copy(),strength
def native(policy,b,c,a,gate):return c.copy(),np.zeros_like(b)

class OracleTests(unittest.TestCase):
    def test_oracle_and_profile_restoration(self):
        b=np.ones(2);old=sys.getprofile()
        o=oracle.CanonicalOracle(portable,native,{'policies':{'unpenalized_transfer':{}}})
        v=o.evaluate({'X62':np.zeros((2,62)),'BASE_CD':b,'all_model_CD':np.ones((2,8))},np.array([True,False]),b.copy())
        oracle.exact(v,{'CD':b,'strength':np.zeros(2)})
        self.assertIs(sys.getprofile(),old)
        with self.assertRaisesRegex(ValueError,'saved native core'):o.evaluate({'X62':np.zeros((2,62)),'BASE_CD':b,'all_model_CD':np.ones((2,8))},np.ones(2,dtype=bool),b+1)
        self.assertIs(sys.getprofile(),old)
    def test_native_mismatch_rejected(self):
        o=oracle.CanonicalOracle(portable,lambda p,b,c,a,gate:(c+1,np.zeros_like(b)),{'policies':{'unpenalized_transfer':{}}})
        with self.assertRaises(ValueError):o.evaluate({'X62':np.zeros((1,62)),'BASE_CD':np.ones(1),'all_model_CD':np.ones((1,8))},np.ones(1,dtype=bool),np.ones(1))
    def test_bits_shape_dtype_and_inventory(self):
        for a,b in [(np.array([0.]),np.array([-0.])),(np.ones(1),np.ones(1,dtype='float32')),(np.ones(1),np.ones((1,1)))]:
            with self.assertRaises(ValueError):oracle.same(a,b)
        d=oracle.inventory(np.array([1.,np.nextafter(1.,2.)]),np.ones(2))
        self.assertFalse(d['bit_exact']);self.assertEqual(d['max_ulp'],1);self.assertEqual(d['differences'][0]['row_index'],1)
        self.assertEqual(float.fromhex(d['differences'][0]['current_hex']),np.nextafter(1.,2.))

def fixture(bad=False):
    serv=types.SimpleNamespace(workload={});refs={}
    for c in COHORTS:
        b=np.ones(2);g=np.array([True,False]);features={'BASE_CD':b,'XLARGE_CD':b,'X62':np.zeros((2,62)),'all_model_CD':np.ones((2,8))}
        serv.workload[c]={'alpha':np.zeros(2),'gate':g}
        z={'core':b,'anchor':b,'gate':g}
        for route in ROUTES[3:]:
            z.update({route:b,route+'__strength':np.zeros(2),route+'__effective_fraction':np.zeros(2),route+'__intervened':np.zeros(2,dtype=bool)})
        refs[c]={'features':features,'original':np.nextafter(b,2.),'original_core':b,'native':z,'kl':z,'oracle':oracle.CanonicalOracle(portable,native,{'policies':{'unpenalized_transfer':{}}})}
    def request(route,diagnostics=False):
        out={}
        for c in COHORTS:
            b=refs[c]['features']['BASE_CD']
            if route in ROUTES[:2]:v={'raw_CD':b,'quantized_CD':b}
            else:
                v={'CD':b+(1 if bad and route==ROUTES[2] else 0),'strength':np.zeros(2)}
                if route in ROUTES[3:]:v.update({'effective_fraction':np.zeros(2),'intervened':np.zeros(2,dtype=bool)})
                if diagnostics:
                    v.update(refs[c]['features'])
                    if route in ROUTES[3:]:v.update({'core':b,'anchor':b,'gate':serv.workload[c]['gate']})
            out.update({c+'/'+k:a.copy() for k,a in v.items()})
        return out
    serv.request=request;return serv,refs

class IntegrationTests(unittest.TestCase):
    def test_v5_approval_contract_and_old_approval_rejection(self):
        r={'runtime':sys.executable,'max_seconds':600,'max_request_seconds':60,'max_rss_bytes':2*1024**3,'max_output_bytes':1024**3,'routes':list(ROUTES),'schedule':schedule(),'cold_repeats':1,'warmups':2,'warm_repeats':7,'workers':1,'sources':{},'reference_contract':oracle.CONTRACT}
        r['schedule']=list(r['schedule']);rb=json.dumps(r).encode()
        good={**{k:v for k,v in r.items() if k!='sources'},'authorized_phase':'one_fixed_inference_benchmark_v5','registry_sha256':runner_v5.sha(rb),'host_other_scientific_jobs_stopped':True,'output':'/private/tmp/synthetic-unused'}
        # Normalize the synthetic schedule through JSON just as an actual approval.
        good=json.loads(json.dumps(good))
        def attempt(v):
            ab=json.dumps(v).encode();a=types.SimpleNamespace(approval='/private/tmp/mock-approval',approval_sha256=runner_v5.sha(ab),output=good['output'])
            with patch.object(runner_v5,'raw',lambda p:ab if str(p)==a.approval else rb),patch.object(runner_v5.platform,'system',return_value='Darwin'),patch.dict(runner_v5.os.environ,{k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}):return runner_v5.authorize(a)
        attempt(good)
        for k,v in [('reference_contract','archive_exact'),('authorized_phase','one_fixed_inference_benchmark_v4'),('max_seconds',601),('workers',True)]:
            with self.assertRaises(ValueError):attempt({**good,k:v})
        bad=dict(good);del bad['reference_contract']
        with self.assertRaises(ValueError):attempt(bad)
    def test_separate_archive_inventory_and_frozen_oracle(self):
        serv,refs=fixture();values,inventory=measurement.preflight(serv,refs)
        self.assertEqual(len(values),7)
        for c in COHORTS:self.assertEqual(inventory[c]['different_rows'],2)
        events=[];counts=measurement.warm(serv,values,events.append)
        self.assertEqual(counts,{'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49});self.assertEqual(len(events),49)
    def test_candidate_mismatch_is_not_new_reference(self):
        serv,refs=fixture(True)
        with self.assertRaises(ValueError):measurement.preflight(serv,refs)
    def test_timed_path_bit_mismatch(self):
        serv,refs=fixture();values,_=measurement.preflight(serv,refs)
        values[ROUTES[2]][COHORTS[0]+'/CD'][0]=np.nextafter(1.,2.)
        with self.assertRaises(ValueError):measurement.measured(serv,ROUTES[2],values[ROUTES[2]])
    def test_child_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve();ab=b'a';rb=b'r'
            r={'reference_contract':oracle.CONTRACT,'scopes':{k:{'files':{},'archives':{},'arrays':{}} for k in ['all',*ROUTES]},'routes':list(ROUTES),'max_request_seconds':60}
            values={k:{'synthetic_CD':np.ones(1)} for k in ROUTES}
            def load(*a,access=None,**kw):return types.SimpleNamespace(request=lambda *a,**kw:{}),{}, {},access,{}
            def warm(s,v,emit):
                for repeat,route in schedule():emit({'repeat':repeat,'route':route,'seconds':0.,'output_rows':497})
                return {'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49}
            def args(phase,route=None,pred=None):return types.SimpleNamespace(phase=phase,route=route,project='/mock',output=str(out),predecessor_sha256=pred)
            with patch.object(loader_v5,'load',side_effect=load),patch.object(loader_v5,'finish'),patch.object(measurement,'preflight',return_value=(values,{'synthetic':True})),patch.object(measurement,'measured',return_value=0.),patch.object(measurement,'warm',side_effect=warm),patch.object(runner_v5,'finish_bootstrap'):
                runner_v5.child(args('preflight'),{},r,{},ab,rb,[])
                raw=(out/'preflight_COMPLETE.json').read_bytes();p=json.loads(raw)
                self.assertIsNone(p['route']);self.assertIn('ARCHIVE_COMPARISONS.json',p['outputs']);self.assertEqual(p['reference_contract'],oracle.CONTRACT)
                pred=runner_v5.sha(raw)
                for route in ROUTES:
                    runner_v5.child(args('cold',route,pred),{},r,{},ab,rb,[])
                    self.assertEqual(json.loads((out/('cold_'+route+'_COMPLETE.json')).read_text())['route'],route)
                runner_v5.child(args('warm',pred=pred),{},r,{},ab,rb,[])
                self.assertIsNone(json.loads((out/'warm_COMPLETE.json').read_text())['route'])
    def test_inherited_parent_and_measurement_math(self):
        h=Path(__file__).parent
        def func(name,file):return next(n for n in ast.parse((h/file).read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
        for name in ['measured','warm','snapshot','unchanged','valid']:
            self.assertEqual(ast.dump(func(name,'measurement_v3.py')),ast.dump(func(name,'measurement_v5.py')))
        old=ast.unparse(func('parent','runner_v4.py')).replace('runner_v4.py','runner_v5.py').replace("{'status': 'COMPLETE_REQUIRES_INDEPENDENT_REVIEW'","{'reference_contract': r['reference_contract'], 'status': 'COMPLETE_REQUIRES_INDEPENDENT_REVIEW'")
        self.assertEqual(old,ast.unparse(func('parent','runner_v5.py')))
    def test_scoped_freeze(self):
        import freeze_v5
        h=Path(__file__).parent;old=json.loads((h/'REGISTRY_v4.json').read_text());new=freeze_v5.build(old)
        for route in ROUTES:self.assertEqual(old['scopes'][route],new['scopes'][route])
        self.assertEqual(new['reference_contract'],oracle.CONTRACT)
        self.assertEqual(set(new['scopes']['all']['files'])-set(old['scopes']['all']['files']),set(freeze_v5.ADDED))

if __name__=='__main__':unittest.main()
