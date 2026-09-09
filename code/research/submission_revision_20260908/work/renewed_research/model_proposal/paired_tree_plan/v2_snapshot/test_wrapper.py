import io,json,math,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import support as s, runner, replay_wrapper as w, fixtures, producer

class Tests(unittest.TestCase):
    def test_named_manifest(self):
        r={'context':'final','branch':'proper','capped':'arrays/tree_31_capped.npz','upper_free':'arrays/tree_31_upper_free.npz'}
        m={'files':{r['capped']:s.MODEL_SHA},'trees':[r]};runner.named_manifest(m)
        m['files']={'other':s.MODEL_SHA}
        with self.assertRaises(ValueError):runner.named_manifest(m)
        m['files']={r['capped']:s.MODEL_SHA};m['trees']=[r,r]
        with self.assertRaises(ValueError):runner.named_manifest(m)
    def test_phase_and_predecessor(self):
        a={'phase':'paired_tree_replay','registry_sha256':'a'*64,'model_sha256':s.MODEL_SHA,'domains':['D','R'],'seconds':900,'workers':1,'real_execution_authorized':True,'certificate_sha256':'b'*64,'producer_complete_sha256':'c'*64,'producer_registry_sha256':'a'*64}
        w.approval_scope(a,'a'*64)
        c={'status':'COMPLETE','phase':'paired_tree_producer','registry_sha256':'a'*64,'model_sha256':s.MODEL_SHA,'outputs':{'certificate.json':'b'*64}}
        w.predecessor(c,a);c['outputs']['certificate.json']='d'*64
        with self.assertRaises(ValueError):w.predecessor(c,a)
        for key,value in [('phase','paired_tree_producer'),('seconds',900.),('workers',True),('producer_registry_sha256','d'*64)]:
            b=dict(a);b[key]=value
            with self.assertRaises(ValueError):w.approval_scope(b,'a'*64)
    def test_reader_restoration(self):
        raw=b'# synthetic oracle';pin=s.digest(raw);old=Path.read_bytes;ledger=[]
        with self.assertRaises(RuntimeError):
            with w.oracle_reader(raw,pin,ledger):
                self.assertEqual((s.ROOT/w.ORACLE).read_bytes(),raw)
                with self.assertRaises(ValueError):(s.HERE/'other').read_bytes()
                raise RuntimeError('intentional')
        self.assertIs(Path.read_bytes,old);self.assertEqual(len(ledger),1)
    def test_preallocation_gate(self):
        raw=b'"empty":'*6000+b'"threshold":'*47600+b'"leaves":'*90000
        r=w.memory_plan(raw,1000)
        self.assertGreater(r['estimated_owned_peak_bytes'],w.LIMIT)
        with self.assertRaises(w.MemoryBudgetError):w.enforce_memory(r)
    def test_memory_refusal_before_parser(self):
        raw=b'"empty":'*6000+b'"threshold":'*47600+b'"leaves":'*90000
        buf=io.BytesIO();np.savez(buf,**fixtures.small_arrays())
        with tempfile.TemporaryDirectory() as td:
            with patch.object(w,'parse_json',side_effect=AssertionError('must not parse')):
                with self.assertRaises(w.MemoryBudgetError):w.replay_buffers(raw,buf.getvalue(),b'',b'','',[],{},Path(td).resolve(),'0'*64,time.monotonic()+10)
    def test_parse_ledger(self):
        ledger=[];self.assertEqual(w.parse_json(b'{"a":1}',ledger,'x'),{'a':1})
        self.assertEqual(ledger[0]['kind'],'json_parse')
    def test_small_integration(self):
        # Only synthetic trees; independent checker identity pinned at read time
        # by the declared source SHA passed by the synthetic gate driver.
        a=fixtures.small_arrays();sha=s.digest(b'wrapper-small-synthetic')
        c=producer.construct(a,s.dependencies([]),s.Budget(),model_sha=sha)
        raw=s.encoded(c);buf=io.BytesIO();np.savez(buf,**a)
        checker=s.read_pinned(s.ROOT/w.CHECKER,w.CHECKER_SHA,[])
        oracle=s.read_pinned(s.ROOT/w.ORACLE,'e9c94a3105ab4305c430ec8e3c14bfbc880eebe1df2cbef9ba15a5ac0dcf0a11',[])
        ledger=[]
        with tempfile.TemporaryDirectory() as td:
            cert,result,plan=w.replay_buffers(raw,buf.getvalue(),checker,oracle,s.digest(oracle),ledger,{},Path(td).resolve(),sha,time.monotonic()+120)
        self.assertEqual(result['status'],'PASS_INDEPENDENT_ADJACENT_PAIR_REPLAY')
        self.assertEqual(sum(r['kind']=='npz_materialize' for r in ledger),7)
        self.assertEqual(sum(r['kind']=='json_parse' for r in ledger),1)
        self.assertEqual(sum(r['kind']=='source_execute_read' for r in ledger),1)

if __name__=='__main__':unittest.main()
