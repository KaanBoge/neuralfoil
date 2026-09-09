import copy, io, json, math, tempfile, time, unittest, zipfile
from pathlib import Path
from fractions import Fraction
import numpy as np
import fixtures, producer, runner, support as s

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.deps=s.dependencies([])
    def test_fraction_large(self):
        q=Fraction(2**20000+1,2**19999+3);self.assertEqual(s.unfraction(s.fraction(q)),q)
    def test_fraction_bad(self):
        for n,d in [('0X1','0x2'),('0x01','0x2'),('-0x0','0x1'),('0x2','0x4'),('0x1','-0x2')]:
            with self.assertRaises(ValueError):s.unfraction({'encoding':'signed_hex_fraction_v1','numerator':n,'denominator':d})
    def test_boundary_paths(self):
        e={'node':0,'feature':0,'threshold':sysmax().hex(),'branch':'R'}
        self.assertIsNone(producer.path_box([e]))
        e['threshold']=(-0.).hex();b=producer.path_box([e]);self.assertEqual(b[0][0],math.ldexp(1.,-1074))
        e['branch']='L';self.assertEqual(producer.path_box([e])[0][1],0.)
    def test_contradiction(self):
        es=[{'node':0,'feature':0,'threshold':'0x0.0p+0','branch':'L'},{'node':1,'feature':0,'threshold':'0x0.0p+0','branch':'R'}]
        self.assertIsNone(producer.path_box(es))
    def test_full_small_inventory(self):
        a=fixtures.small_arrays();before={k:v.copy() for k,v in a.items()}
        c=producer.construct(a,self.deps,s.Budget(),model_sha=s.digest(b'synthetic-small'))
        self.assertEqual(c['counts']['attempted_pairs'],1600)
        for d in ('D','R'):
            self.assertEqual(c['summary'][d]['feasible_pairs'],400)
            self.assertEqual(len(c['domains'][d]['blocks'][0]['pairs']),4)
        for k in a:self.assertTrue(np.array_equal(a[k],before[k]))
    def test_empty_paths_retained(self):
        a=fixtures.small_arrays(threshold=sysmax())
        c=producer.construct(a,self.deps,s.Budget(),model_sha=s.digest(b'synthetic-empty'))
        self.assertEqual(sum(p['empty'] for p in c['paths']),400)
        self.assertEqual(c['summary']['D']['feasible_pairs'],200)
    def test_relation_reject(self):
        a=fixtures.small_arrays(feature=16,threshold=-1.)
        c=producer.construct(a,self.deps,s.Budget(),model_sha=s.digest(b'synthetic-R'))
        self.assertEqual(c['summary']['R']['feasible_pairs'],200)
        self.assertIn('R_infeasible',{r['status'] for r in c['domains']['R']['blocks'][0]['pairs']})
    def test_cycle(self):
        a=fixtures.small_arrays();a['nodes'][0]['left']=0
        with self.assertRaises(ValueError):producer.construct(a,self.deps,s.Budget())
    def test_bad_dtype(self):
        a=fixtures.small_arrays();a['initial']=a['initial'].astype('f4')
        with self.assertRaises(ValueError):producer.construct(a,self.deps,s.Budget())
    def test_categorical(self):
        a=fixtures.small_arrays();a['nodes'][0]['is_categorical']=1
        with self.assertRaises(ValueError):producer.construct(a,self.deps,s.Budget())
    def test_budget(self):
        with self.assertRaises(MemoryError):s.Budget().check(128*2**20+1)
        with self.assertRaises(TimeoutError):s.Budget(0).check()
    def test_npz_ledger(self):
        a=fixtures.small_arrays();buf=io.BytesIO();np.savez(buf,**a);ledger=[]
        b=runner.load_arrays(buf.getvalue(),ledger)
        self.assertEqual([r['member'] for r in ledger],list(s.MEMBERS));self.assertEqual(len(b),7)
        buf=io.BytesIO();np.savez(buf,extra=np.array([1]),**a)
        with self.assertRaises(ValueError):runner.load_arrays(buf.getvalue(),[])
    def test_auth_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'x';p.write_bytes(b'a')
            with self.assertRaises(ValueError):s.read_pinned(p,s.digest(b'b'),[])
    def test_approval(self):
        a={'phase':'paired_tree_producer','registry_sha256':'r','model_sha256':s.MODEL_SHA,'domains':['D','R'],'seconds':900,'workers':1,'real_execution_authorized':True}
        runner.check_approval(a,'r');a['workers']=True
        with self.assertRaises(ValueError):runner.check_approval(a,'r')
    def test_failure_partial(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td).resolve()/'attempt'
            def fail(p,l,o):
                s.exclusive(p/'retained.json',{'x':1});raise ValueError('synthetic failure')
            with self.assertRaises(ValueError):runner.protected_attempt(out,{},fail)
            self.assertTrue((out/'FAILURE.json').exists());self.assertTrue((out/'retained.json').exists())
            with self.assertRaises(FileExistsError):runner.protected_attempt(out,{},fail)
    def test_timeout_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td).resolve()/'attempt'
            with self.assertRaises(TimeoutError):runner.protected_attempt(out,{},lambda *_:time.sleep(.1),seconds=.01)
            self.assertIn('hard phase guard',(out/'FAILURE.json').read_text())
    def test_serialization_partial_and_nooverwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve()/'cert.json'
            with self.assertRaises(ValueError):runner.large_exclusive(p,{'a':1,'z':math.nan})
            self.assertFalse(p.exists());self.assertTrue(Path(str(p)+'.partial').exists())
            q=p.with_name('ok.json');runner.large_exclusive(q,{'a':1})
            with self.assertRaises(FileExistsError):runner.large_exclusive(q,{'a':2})
            self.assertEqual(json.loads(q.read_text()),{'a':1})
    def test_symlink_and_control(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td).resolve();(p/'link').symlink_to(p,target_is_directory=True)
            with self.assertRaises(ValueError):s.safe_path(p/'link'/'new')
            with self.assertRaises(ValueError):s.safe_path(p/'bad\nname')
    def test_runtime(self):s.runtime()

def sysmax():return float.fromhex('0x1.fffffffffffffp+1023')

if __name__=='__main__':unittest.main()
