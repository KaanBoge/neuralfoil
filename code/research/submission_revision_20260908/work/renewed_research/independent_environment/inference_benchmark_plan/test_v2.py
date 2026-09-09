"""Fixed synthetic V2 regressions. No model/coordinate/reference materialization."""
import io,json,sys,tempfile,types,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
import numpy as np
import provenance_v2 as p,watchdog_v2 as w,measurement_v2 as m,runner_v2 as r
from serving import ROUTES,COHORTS

class Fake:
    pid=1
    def __init__(self):self.returncode=None;self.terminated=False;self.killed=False;self.reaped=False
    def poll(self):return self.returncode
    def terminate(self):self.terminated=True;self.returncode=-15
    def kill(self):self.killed=True;self.returncode=-9
    def wait(self,timeout=None):self.reaped=True;return self.returncode
class Tests(unittest.TestCase):
    def test_monitor_unavailable(self):
        child=Fake()
        def rss(proc):raise RuntimeError('unavailable')
        d=w.monitor(child,0,600,100,lambda:0,100,clock=lambda:1,sleep=lambda x:None,rss=rss)
        self.assertIsNone(d['peak_sampled_RSS_bytes']);self.assertFalse(d['RSS_available']);self.assertTrue(child.terminated and child.reaped)
    def test_monitor_timeout(self):
        child=Fake();d=w.monitor(child,0,1,100,lambda:0,100,clock=lambda:2,sleep=lambda x:None,rss=lambda x:1)
        self.assertIn('wall',d['failure']);self.assertTrue(child.reaped)
    def test_monitor_size(self):
        child=Fake();d=w.monitor(child,0,600,100,lambda:101,100,clock=lambda:1,sleep=lambda x:None,rss=lambda x:1)
        self.assertIn('size',d['failure']);self.assertTrue(child.reaped)
    def test_monitor_memory(self):
        child=Fake();d=w.monitor(child,0,600,100,lambda:0,100,clock=lambda:1,sleep=lambda x:None,rss=lambda x:101)
        self.assertIn('RSS',d['failure']);self.assertTrue(child.reaped)
    def test_ps_bad_result_alive(self):
        for code,text in [(1,'100'),(0,''),(0,'0'),(0,'broken')]:
            with self.assertRaises(RuntimeError):w.rss_bytes(Fake(),lambda *a,**kw:types.SimpleNamespace(returncode=code,stdout=text))
    def test_ps_race_finished(self):
        child=Fake();child.returncode=0
        self.assertIsNone(w.rss_bytes(child,lambda *a,**kw:types.SimpleNamespace(returncode=1,stdout='')))
    def test_kill_reap(self):
        class Stuck(Fake):
            def terminate(self):self.terminated=True
            def wait(self,timeout=None):
                if self.returncode is None:raise subprocess.TimeoutExpired('synthetic',timeout)
                self.reaped=True;return self.returncode
        child=Stuck();w.stop(child);self.assertTrue(child.terminated and child.killed and child.reaped)
    def test_context_source_restored(self):
        name='synthetic_bench_module';original=types.ModuleType(name);sys.modules[name]=original
        access=p.Access('.',{'files':{},'archives':{},'arrays':{}})
        with self.assertRaises(ValueError):
            with p.modules(access) as run:run(name,b'raise ValueError("synthetic")','synthetic.py')
        self.assertIs(sys.modules[name],original);sys.modules.pop(name)
    def test_bootstrap_restores_on_failure(self):
        original=sys.modules['provenance_v2']
        with self.assertRaises(ValueError):r.execute_sources({'provenance_v2.py':b'raise ValueError("synthetic")'})
        self.assertIs(sys.modules['provenance_v2'],original)
    def test_array_allowlist_and_ledger(self):
        out=io.BytesIO();np.savez(out,allowed=np.ones(2),MEAS_CD=np.array([object()],object))
        a=p.Access('.',{'files':{},'archives':{},'arrays':{'x.npz':['allowed']}})
        values=a.arrays(out.getvalue(),'x.npz',['allowed']);self.assertEqual(a.events[0]['dtype'],'float64')
        with self.assertRaises(ValueError):a.arrays(out.getvalue(),'x.npz',['MEAS_CD'])
    def test_hash_mutation_finish(self):
        with tempfile.TemporaryDirectory() as d:
            d=str(Path(d).resolve())
            file=Path(d)/'x';file.write_bytes(b'one')
            a=p.Access(d,{'files':{'x':p.sha(b'one')},'archives':{},'arrays':{}});a.file('x');file.write_bytes(b'two')
            with self.assertRaises(ValueError):a.finish()
    def test_dtype_exact(self):
        with self.assertRaises(ValueError):m.same(np.ones(1,dtype=np.float32),np.ones(1),'dtype')
    def test_input_mutation(self):
        s=types.SimpleNamespace(workload={c:{'alpha':np.ones(1)} for c in COHORTS});v=m.snapshot(s);s.workload[COHORTS[0]]['alpha'][0]=2
        with self.assertRaises(ValueError):m.unchanged(s,v)
    def test_output_positive_rows_boolean(self):
        s=types.SimpleNamespace(workload={c:{'alpha':np.ones(1)} for c in COHORTS})
        good={c+'/CD':np.ones(1) for c in COHORTS};m.valid(s,good)
        for field,value in [('CD',np.zeros(1)),('CD',np.ones(2)),('CD',np.array([float('nan')])),('gate',np.ones(1))]:
            bad=dict(good);bad[COHORTS[0]+'/'+field]=value
            with self.assertRaises(ValueError):m.valid(s,bad)
    def test_online_timer_order(self):
        order=[]
        class S:
            workload={c:{'alpha':np.ones(1)} for c in COHORTS}
            def request(self,route):
                from fractions import Fraction
                order.append('Fraction');return {c+'/CD':np.array([float(Fraction(1,3))]) for c in COHORTS}
        s=S();expected={c+'/CD':np.array([1/3]) for c in COHORTS}
        def clock():order.append('clock');return len(order)
        m.measured(s,ROUTES[0],expected,clock);self.assertEqual(order,['clock','Fraction','clock'])
    def test_collision(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'record';r.write(path,{'status':'first'})
            with self.assertRaises(FileExistsError):r.write(path,{'status':'second'})
    def test_scopes_static_after_freeze(self):
        # Read JSON-only registry if present; no artifact or array bytes opened.
        file=Path(__file__).parent/'REGISTRY_v2.json'
        if not file.exists():return
        registry=json.loads(file.read_text())
        for route in ROUTES[:2]:
            s=registry['scopes'][route];self.assertEqual(s['archives'],{})
            self.assertTrue(all('feature_reproduction/addon/' in n for n in s['files']))
            self.assertTrue(all(keys==['alpha','Re','airfoil'] for keys in s['arrays'].values()))
        self.assertEqual(len(registry['schedule']),49)
    def test_approval_strict_contract(self):
        registry={'runtime':sys.executable,'max_seconds':600,'max_request_seconds':60,'max_rss_bytes':2*1024**3,'max_output_bytes':1024**3,'routes':list(ROUTES),'schedule':[[0,x] for x in ROUTES],'cold_repeats':1,'warmups':2,'warm_repeats':7,'workers':1,'sources':{}}
        rb=json.dumps(registry).encode()
        good={**{k:v for k,v in registry.items() if k!='sources'},'authorized_phase':'one_fixed_inference_benchmark_v2','registry_sha256':p.sha(rb),'host_other_scientific_jobs_stopped':True,'output':'/private/tmp/synthetic-not-created'}
        def attempt(value):
            ab=json.dumps(value).encode();args=types.SimpleNamespace(approval='/private/tmp/synthetic-approval-not-created',approval_sha256=p.sha(ab),output=good['output'])
            with patch.object(r,'raw',lambda path:ab if str(path)==args.approval else rb),patch.dict(r.os.environ,{k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']}),patch.object(r.platform,'system',lambda:'Darwin'):
                return r.authorize(args)
        attempt(good)
        for key,value in [('workers',True),('max_seconds',601),('routes',list(reversed(ROUTES))),('authorized_phase','replay'),('host_other_scientific_jobs_stopped',False),('extra','unexpected')]:
            bad={**good,key:value}
            with self.assertRaises(ValueError):attempt(bad)
if __name__=='__main__':unittest.main()
