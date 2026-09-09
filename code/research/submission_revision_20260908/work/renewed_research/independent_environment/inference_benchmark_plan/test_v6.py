"""V6 source-only process/clock/receipt mocks; no scientific materialization."""
import ast,json,subprocess,types,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import watchdog_v6 as w
import runner_v6 as r

class Proc:
    pid=1
    def __init__(self,terminal=True,exitcode=0):self.returncode=None;self.terminal=terminal;self.exitcode=exitcode;self.waits=[];self.actions=[]
    def poll(self):return self.returncode
    def wait(self,timeout=None):
        self.waits.append(timeout)
        if self.returncode is not None:return self.returncode
        if self.terminal:self.returncode=self.exitcode;return self.returncode
        raise subprocess.TimeoutExpired('mock-child',timeout)
    def terminate(self):self.actions.append('terminate');self.returncode=-15
    def kill(self):self.actions.append('kill');self.returncode=-9

def unavailable():return w.RSSUnavailable({'reason':'empty','stdout':w.text(''),'stderr':w.text('no-process'),'returncode':1,'poll_before':None,'poll_after':None})
def monitor(proc,**kw):
    state={'n':0}
    def rss(p):
        state['n']+=1
        if state['n']==1:return 10
        raise unavailable()
    args=dict(start=0,max_seconds=600,max_rss=100,size=lambda:0,max_size=100,clock=lambda:1,sleep=lambda x:None,rss=rss);args.update(kw)
    return w.monitor(proc,**args)

class Tests(unittest.TestCase):
    def test_terminal_race_provisional_and_reaped(self):
        p=Proc();d=monitor(p)
        self.assertIsNone(d['failure']);self.assertTrue(d['terminal_unavailable_recovered']);self.assertTrue(d['receipt_self_peak_required']);self.assertEqual(d['valid_RSS_samples'],1)
        self.assertEqual(p.waits[0],.05);self.assertEqual(d['RSS_diagnostics'][0]['observation']['stderr']['text'],'no-process')
    def test_truly_live_unavailable_rejects_and_reaps(self):
        p=Proc(False);d=monitor(p)
        self.assertIn('remains live',d['failure']);self.assertEqual(p.actions,['terminate']);self.assertIsNotNone(p.returncode)
    def test_no_prior_sample_rejected(self):
        p=Proc();d=monitor(p,rss=lambda p:(_ for _ in ()).throw(unavailable()))
        self.assertIn('without prior valid sample',d['failure']);self.assertFalse(d['terminal_unavailable_recovered'])
    def test_nonzero_terminal_rejected(self):
        self.assertIn('nonzero terminal exit',monitor(Proc(exitcode=2))['failure'])
    def test_remaining_grace_and_deadline(self):
        p=Proc();d=monitor(p,max_seconds=1,clock=lambda:.99)
        self.assertIsNone(d['failure']);self.assertAlmostEqual(p.waits[0],.01)
        d=monitor(Proc(),max_seconds=1,clock=lambda:1)
        self.assertIn('no terminal observation budget',d['failure'])
    def test_post_grace_budget(self):
        state={'now':0.}
        class Late(Proc):
            def wait(self,timeout=None):
                result=super().wait(timeout);state['now']=2.;return result
        d=monitor(Late(),max_seconds=1,clock=lambda:state['now'])
        self.assertIn('wall budget',d['failure'])
        state={'size':0}
        class Large(Proc):
            def wait(self,timeout=None):
                result=super().wait(timeout);state['size']=101;return result
        self.assertIn('output size',monitor(Large(),size=lambda:state['size'])['failure'])
    def test_query_timeout_always_fails_and_diagnostics_survive(self):
        p=Proc(False)
        def run(*a,**kw):
            self.assertEqual(kw['timeout'],2);raise subprocess.TimeoutExpired('ps',2,output='partial',stderr='problem')
        d=monitor(p,rss=lambda p:w.rss_bytes(p,run=run,clock=lambda:1))
        self.assertIn('RSS query failed',d['failure']);self.assertFalse(d['terminal_unavailable_recovered']);self.assertEqual(d['RSS_diagnostics'][0]['observation']['stdout']['text'],'partial');self.assertEqual(p.actions,['terminate'])
    def test_query_raw_and_truncation(self):
        p=Proc()
        for code,out,reason in [(1,'','bad_return_code'),(0,'','empty'),(0,'oops','nondecimal'),(0,'0','nonpositive')]:
            with self.assertRaises(w.RSSUnavailable) as cm:w.rss_bytes(p,run=lambda *a,**kw:types.SimpleNamespace(returncode=code,stdout=out,stderr='e'*5000),clock=lambda:1)
            o=cm.exception.observation;self.assertEqual(o['reason'],reason);self.assertTrue(o['stderr']['truncated']);self.assertEqual(len(o['stderr']['text']),4096)
    def test_sampled_threshold_and_invalid_sample(self):
        self.assertIn('RSS stop threshold',monitor(Proc(False),rss=lambda p:101)['failure'])
        for v in [None,0,-1,float('nan'),True]:self.assertIn('invalid RSS sample',monitor(Proc(False),rss=lambda p:v)['failure'])
    def test_cleanup_error_preserves_query(self):
        class Broken(Proc):
            def terminate(self):raise RuntimeError('mock-terminate-error')
        p=Broken(False);d=monitor(p)
        self.assertIn('remains live',d['failure']);self.assertEqual(d['RSS_diagnostics'][0]['event'],'RSS_unavailable');self.assertTrue(any('error' in x for x in d['cleanup_events']));self.assertEqual(p.actions,['kill'])
    def test_diagnostic_capacity_fails_closed(self):
        with patch.object(w,'MAX_EVENTS',0):d=monitor(Proc(False))
        self.assertIn('diagnostic ledger capacity',d['failure'])
    def test_child_peak_and_full_receipt_bindings(self):
        registry={'reference_contract':'canonical','max_rss_bytes':100}
        c={'status':'PASS','phase':'cold','route':'route','predecessor_sha256':'prev','approval_sha256':'approval','registry_sha256':'registry','reference_contract':'canonical','self_ru_maxrss_bytes':50,'ru_maxrss_units':'bytes on explicitly required macOS'}
        def check(d):r.validate_child_receipt(d,'cold','route','prev','approval','registry',registry)
        check(c)
        for v in [0,-1,101,float('nan'),float('inf'),float('-inf'),True,'50',None]:
            with self.assertRaises(ValueError):check({**c,'self_ru_maxrss_bytes':v})
        for key in ['phase','route','predecessor_sha256','approval_sha256','registry_sha256','reference_contract','ru_maxrss_units']:
            with self.assertRaises(ValueError):check({**c,key:'wrong'})
        bad=dict(c);del bad['self_ru_maxrss_bytes']
        with self.assertRaises(ValueError):check(bad)
    def test_science_child_and_budget_ast_unchanged(self):
        h=Path(__file__).parent
        def fn(file,name):return next(n for n in ast.parse((h/file).read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
        self.assertEqual(ast.dump(fn('runner_v5.py','child')),ast.dump(fn('runner_v6.py','child')))
        self.assertEqual(ast.dump(fn('watchdog_v3.py','budget')),ast.dump(fn('watchdog_v6.py','budget')))
    def test_v6_parent_first_pin_and_monitor_guard_inherited(self):
        h=Path(__file__).parent;s=(h/'runner_v6.py').read_text()
        for literal in ["if result['failure']:raise RuntimeError",'validate_child_receipt(c,phase,route,predecessor,sha(ab),sha(rb),r)',"for n,h in accepted.items():check_budget();accept(out/n,h)","pending.rename(out/'COMPLETE.json')"]:self.assertIn(literal,s)
        self.assertLess(s.index('validate_child_receipt(c,phase,route,predecessor,sha(ab),sha(rb),r)'),s.index('accept(receipt)'))
    def test_successful_sample_real_query_units(self):
        self.assertEqual(w.rss_bytes(Proc(),run=lambda *a,**kw:types.SimpleNamespace(returncode=0,stdout=' 42\n',stderr=''),clock=lambda:1),42*1024)
    def test_v6_collision_and_first_accepted_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp).resolve()/'record.json';r.write(f,{'first':True});pins={};r.accept_output(f,pins)
            with self.assertRaises(FileExistsError):r.write(f,{'second':True})
            f.write_text('{}')
            with self.assertRaises(ValueError):r.accept_output(f,pins)
    def test_v6_bootstrap_restores_error(self):
        import sys,provenance_v2
        old=sys.modules['provenance_v2']
        with self.assertRaises(ValueError):r.execute_sources({'provenance_v2.py':b'raise ValueError("mock")'})
        self.assertIs(sys.modules['provenance_v2'],old)
    def test_v6_postexit_and_relative_diagnostics(self):
        p=Proc();p.returncode=0
        self.assertIn('wall budget',monitor(p,max_seconds=1,clock=lambda:2)['failure'])
        self.assertIn('output size',monitor(p,size=lambda:101)['failure'])
        d=monitor(Proc(False),start=5,clock=lambda:6,rss=lambda p:w.rss_bytes(p,run=lambda *a,**kw:types.SimpleNamespace(returncode=1,stdout='',stderr=''),clock=lambda:6))
        obs=d['RSS_diagnostics'][0]['observation'];self.assertEqual(obs['started_monotonic_since_parent_start'],1)

if __name__=='__main__':unittest.main()
