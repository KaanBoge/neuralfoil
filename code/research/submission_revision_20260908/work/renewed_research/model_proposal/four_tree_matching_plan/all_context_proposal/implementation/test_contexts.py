"""Small source/metadata mocks only; no original array access."""
import unittest,tempfile,time,sys,json,copy,types,os,importlib.util
from pathlib import Path
from unittest import mock
import context_support as s,entry,processes
class Tests(unittest.TestCase):
    def temp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);return Path(t.name).resolve()
    def table(self):
        rows=[];m={'trees':[],'files':{}}
        for i,c in enumerate(s.CONTEXTS):
            p=f'arrays/tree_{2*i+1:02d}_capped.npz';m['trees'].append({'context':c,'branch':'proper','capped':p,'upper_free':p.replace('_capped','_upper_free')});m['files'][p]=str(i);rows.append({'context':c,'member':p,'model_sha256':str(i)})
        return rows,m
    def test_sixteen_expanded(self):
        r,m=self.table();s.validate_contexts(r,m)
        for broken in [r[:-1],r[::-1],r+[r[0]]]:
            with self.assertRaises(ValueError):s.validate_contexts(broken,m)
    def test_wrong_branch_and_model(self):
        r,m=self.table();r[0]['model_sha256']='wrong'
        with self.assertRaises(ValueError):s.validate_contexts(r,m)
        r,m=self.table();m['trees'][1]['branch']='full'
        with self.assertRaises(ValueError):s.validate_contexts(r,m)
    def test_strict_approval(self):
        a={'phase':'certificates_produce','registry_sha256':'a'*64,'contexts':s.CONTEXTS,'domain':'FINITE_X62_V1','workers':1,'seconds':900,'child_seconds':900,'producer_owned_cap':128*2**20,'checker_owned_cap':256*2**20,'child_output_cap':s.CHILD_CAP,'combined_output_cap':s.CAP,'actual_execution_authorized':True}
        s.strict_approval(a,'a'*64,'certificates_produce')
        for k,v in [('workers',True),('domain','R'),('actual_execution_authorized',False),('contexts',s.CONTEXTS[:-1])]:
            with self.assertRaises(ValueError):s.strict_approval(dict(a,**{k:v}),'a'*64,'certificates_produce')
    def test_replay_needs_predecessor(self):
        with self.assertRaises(ValueError):s.strict_approval({},'a'*64,'certificates_replay')
    def test_no_existing_output_mutation(self):
        p=self.temp()/'x';p.write_bytes(b'x');before=p.read_bytes()
        with self.assertRaises(FileExistsError):p.open('xb')
        self.assertEqual(p.read_bytes(),before)
    def test_symlink_and_tamper(self):
        p=self.temp();(p/'x').write_bytes(b'x');(p/'link').symlink_to(p/'x')
        with self.assertRaises(ValueError):s.read(p/'link',s.sha(b'x'),[])
        with self.assertRaises(ValueError):s.read(p/'x','0'*64,[])
    def test_failure_barrier(self):
        with self.assertRaises(ValueError):entry.verify_phase({'status':'FAILED'},s,[],'a'*64,{})
    def test_aggregate_preallocation(self):
        with mock.patch.object(s,'usage',return_value=s.CAP-s.CHILD_CAP),self.assertRaises(OSError):s.reserve()
    def test_deadline_before_launch(self):
        with mock.patch.object(processes.subprocess,'Popen') as p,self.assertRaises(TimeoutError):processes.run([],self.temp(),'x',time.monotonic()-1,s)
        p.assert_not_called()
    def test_tiny_child_logs(self):
        p=self.temp()
        with mock.patch.object(s,'usage',return_value=0):processes.run([sys.executable,'-B','-c',"print('fixed')"],p,'one',time.monotonic()+5,s)
        self.assertEqual((p/'one.stdout.txt').read_text(),'fixed\n')
    def test_duplicate_json(self):
        with self.assertRaises(ValueError):s.parse(b'{"x":1,"x":2}')
    def test_source_boot_stops_before_science(self):
        p=self.temp();(p/'REGISTRY_v3.json').write_bytes(b'{}')
        with mock.patch.object(entry,'HERE',p),self.assertRaises(ValueError):entry.boot(type('Args',(),{'registry_sha256':'a'*64})())
    def test_two_context_producer_dispatch_mock(self):
        root=self.temp();out=root/'implementation';out.mkdir();phase=out/'certificates_produce';phase.mkdir()
        io_path=s.ROOT/'model_proposal/four_tree_matching_plan/io_support.py';spec=importlib.util.spec_from_file_location('test_only_io',io_path);io=importlib.util.module_from_spec(spec);spec.loader.exec_module(io)
        token={'parent_pid':os.getppid(),'registry_sha256':'a'*64,'approval_sha256':'b'*64,'phase':'certificates_produce'}
        rows=[];seen=[]
        for i,c in enumerate(s.CONTEXTS[:2]):
            member=f'arrays/tree_{2*i+1:02d}_capped.npz';path=root/'independent_environment/bounds_extraction'/member;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'synthetic-not-npz')
            rows.append({'context':c,'member':member,'model_sha256':str(i)*64})
        class Budget:
            def __init__(self,*a):self.peak=100
            def check(self,*a):pass
        def construct(arrays,budget,**kw):
            seen.append(kw['model_sha']);return {'counts':{},'stage0':{},'original_adjacent':{},'final':{}}
        producer=types.SimpleNamespace(Budget=Budget,memory_plan=lambda *a:{'estimated_owned_bytes':100},construct=construct)
        loader=types.SimpleNamespace(load_arrays=lambda *a:{'mock':True})
        reg={'contexts':rows,'metadata':{'stage0':{'path':'stage.json','sha256':'c'*64}},'external_sources':{'producer':{'path':'producer.py'},'producer_entry':{'path':'run.py'}}}
        sources={'mock.py':b'mock'};ext={'producer':b'p','producer_entry':b'l'}
        def read(path,*args):return json.dumps(token).encode() if Path(path).name=='TOKEN.json' else b'{}'
        with mock.patch.object(s,'HERE',out),mock.patch.object(entry,'HERE',out),mock.patch.object(entry,'ROOT',root),mock.patch.object(s,'read',side_effect=read),mock.patch.object(s,'reserve'),mock.patch.object(s,'compare'),mock.patch.object(s,'stream'),mock.patch.object(s,'authenticate'),mock.patch.object(s,'module',side_effect=lambda b,*a:producer if b==b'p' else loader),mock.patch.object(entry,'boot',return_value=(reg,sources,ext,s,io,{},[])):
            for c in s.CONTEXTS[:2]:
                args=types.SimpleNamespace(context=c,phase='certificates_produce',registry_sha256='a'*64,approval_sha256='b'*64,token_sha256='t')
                entry.child(args);r=json.loads((phase/c/'COMPLETE.json').read_bytes());self.assertEqual(r['context'],c);self.assertEqual(r['status'],'COMPLETE')
        self.assertEqual(seen,['0'*64,'1'*64])
    def test_owned_timeout_no_retry(self):
        p=self.temp()
        with mock.patch.object(s,'usage',return_value=0),self.assertRaises(TimeoutError):processes.run([sys.executable,'-B','-c','import time;time.sleep(5)'],p,'timeout',time.monotonic()+.05,s)
        self.assertTrue((p/'timeout.stdout.txt').exists())
    def test_parent_explicit_aggregate_cap_child_unchanged(self):
        import ast
        tree=ast.parse(Path(entry.__file__).read_text());parent=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='parent_work');child=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='child')
        parent_calls=[x for x in ast.walk(parent) if isinstance(x,ast.Call) and isinstance(x.func,ast.Call) and isinstance(x.func.func,ast.Attribute) and x.func.func.attr=='store_type']
        child_calls=[x for x in ast.walk(child) if isinstance(x,ast.Call) and isinstance(x.func,ast.Call) and isinstance(x.func.func,ast.Attribute) and x.func.func.attr=='store_type']
        self.assertEqual(len(parent_calls),1);self.assertTrue(any(k.arg=='cap' and ast.unparse(k.value)=='s.CAP' for k in parent_calls[0].keywords));self.assertEqual(len(child_calls),1);self.assertFalse(any(k.arg=='cap' for k in child_calls[0].keywords))
    def io_module(self):
        spec=importlib.util.spec_from_file_location('source_only_io_test',s.ROOT/'model_proposal/four_tree_matching_plan/io_support.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def test_alarm_wraps_boot_and_restores(self):
        args=types.SimpleNamespace();events=[]
        with mock.patch.object(entry.signal,'getsignal',return_value='previous'),mock.patch.object(entry.signal,'signal',side_effect=lambda *a:events.append(('handler',a))),mock.patch.object(entry.signal,'setitimer',side_effect=lambda *a:events.append(('timer',a))),mock.patch.object(entry,'parent_work',side_effect=lambda a:(_ for _ in ()).throw(TimeoutError('mock bootstrap deadline'))):
            with self.assertRaises(TimeoutError):entry.parent(args)
        self.assertEqual(events[1][1][1],900);self.assertEqual(events[-2][1][1],0);self.assertEqual(events[-1][1][1],'previous')
    def test_stream_checks_expired_deadline(self):
        p=self.temp()/'x';p.write_bytes(b'fixed')
        with mock.patch.object(s,'DEADLINE',time.monotonic()-1),self.assertRaises(TimeoutError):s.stream(p,s.sha(b'fixed'),[])
    def parent_fixture(self,fail=False):
        root=self.temp();out=root/'implementation';out.mkdir();io=self.io_module();calls=[];inherited={'context':'final','status':'INHERITED_AUTHENTICATED'}
        args=types.SimpleNamespace(phase='certificates_produce',registry_sha256='a'*64,approval_sha256='b'*64)
        def run(command,path,name,deadline,support):
            calls.append(name)
            if fail and len(calls)==2:raise RuntimeError('fixed child failure')
            d=path/name;d.mkdir();(d/'COMPLETE.json').write_text(json.dumps({'status':'COMPLETE','context':name,'registry_sha256':'a'*64,'approval_sha256':'b'*64,'summary':{'fixed':1},'outputs':{}}))
        realread=s.read
        def read(path,pin,ledger,*rest):
            return b'{}' if Path(path).name=='manifest.json' or 'APPROVAL' in Path(path).name else realread(path,pin,ledger,*rest)
        reg={'contexts':[],'metadata':{'manifest':{'path':'manifest.json','sha256':'m'}}}
        with mock.patch.object(entry,'HERE',out),mock.patch.object(entry,'ROOT',root),mock.patch.object(s,'HERE',out),mock.patch.object(entry,'boot',return_value=(reg,{'processes.py':b'mock'}, {},s,io,{},[])),mock.patch.object(s,'read',side_effect=read),mock.patch.object(s,'validate_contexts'),mock.patch.object(s,'reserve'),mock.patch.object(s,'authenticate'),mock.patch.object(s,'module',return_value=types.SimpleNamespace(run=run)),mock.patch.object(s,'inherited',return_value=inherited) as inh:
            if fail:
                with self.assertRaises(RuntimeError):entry.parent(args)
                statuses=json.loads((out/args.phase/'CONTEXT_STATUS.json').read_bytes());self.assertEqual(statuses[s.CONTEXTS[0]],'COMPLETE');self.assertEqual(statuses[s.CONTEXTS[1]],'FAILED');self.assertTrue(all(statuses[c]=='NOT_RUN' for c in s.CONTEXTS[2:]));inh.assert_not_called()
            else:
                entry.parent(args);r=json.loads((out/args.phase/'COMPLETE.json').read_bytes());self.assertEqual(r['contexts']['final'],inherited);self.assertEqual(r['fresh_contexts'],15);inh.assert_called_once()
        return calls
    def test_first_failure_stops_later_contexts(self):self.assertEqual(len(self.parent_fixture(True)),2)
    def test_final_inherited_not_dispatched(self):self.assertEqual(self.parent_fixture(False),s.CONTEXTS[:-1])
    def test_replay_dispatch_model_identity_and_wrong_chain(self):
        io=self.io_module()
        for bad in (False,True):
            root=self.temp();out=root/'implementation';out.mkdir();phase=out/'certificates_replay';phase.mkdir();c=s.CONTEXTS[0];modelsha='d'*64;member='arrays/tree_01_capped.npz';model=root/'independent_environment/bounds_extraction'/member;model.parent.mkdir(parents=True);model.write_bytes(b'fake')
            cp=out/'certificates_produce'/c;cp.mkdir(parents=True);(cp/'certificate.json').write_bytes(b'{}')
            summary={'counts':{},'stage0':{},'original_adjacent':{},'final':{}};item={'complete_sha256':'p','summary':summary};prior={'contexts':{c:item}};pc={'model_sha256':'wrong' if bad else modelsha,'registry_sha256':'a'*64,'summary':summary,'outputs':{'certificate.json':'cert'}}
            token={'parent_pid':os.getppid(),'registry_sha256':'a'*64,'approval_sha256':'b'*64,'phase':'certificates_replay'}
            def read(path,*unused):
                path=Path(path)
                if path.name=='TOKEN.json':v=token
                elif path.name=='COMPLETE.json':v=pc if path.parent.name==c else prior
                else:v={}
                return json.dumps(v).encode()
            checks=[];loader=types.SimpleNamespace(MODEL_SHA=None,independent_arrays=lambda raw,ledger:checks.append(('loader',loader.MODEL_SHA)) or {})
            checker=types.SimpleNamespace(INPUT_CAP=64*2**20,owned_estimate=lambda *a:100,parse_certificate=lambda *a,**k:({},1),check=lambda *a,**k:checks.append(('checker',k['expected_model_sha'])) or dict(summary))
            reg={'contexts':[{'context':c,'model_sha256':modelsha,'member':member}],'metadata':{'stage0':{'path':'stage0.json','sha256':'s'}},'external_sources':{'checker':{'path':'checker.py'},'checker_entry':{'path':'replay.py'}}}
            with mock.patch.object(entry,'HERE',out),mock.patch.object(entry,'ROOT',root),mock.patch.object(s,'HERE',out),mock.patch.object(entry,'boot',return_value=(reg,{}, {'checker':b'c','checker_entry':b'l'},s,io,{'producer_complete_sha256':'prior'},[])),mock.patch.object(s,'read',side_effect=read),mock.patch.object(s,'stream'),mock.patch.object(s,'reserve'),mock.patch.object(s,'compare'),mock.patch.object(s,'authenticate'),mock.patch.object(s,'verify_outputs'),mock.patch.object(s,'module',side_effect=lambda b,*a:checker if b==b'c' else loader):
                a=types.SimpleNamespace(context=c,phase='certificates_replay',registry_sha256='a'*64,approval_sha256='b'*64,token_sha256='t')
                if bad:
                    with self.assertRaises(ValueError):entry.child(a)
                    self.assertEqual(checks,[])
                else:entry.child(a);self.assertEqual(checks,[('loader',modelsha),('checker',modelsha)])
if __name__=='__main__':unittest.main()
