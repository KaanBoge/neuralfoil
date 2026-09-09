"""Synthetic arrays only. No real exported tree, outcome or feature file reads."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pilot_adapter as adapter
import pilot_engine as engine
import pilot_checker as checker
from pilot_runner import exclusive_json

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent/'model_proposal/range_bound_feasibility'


def pure_module(name, path, pin):
    if adapter.sha(path) != pin:
        raise ValueError('pure source pin')
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


Q = pure_module('q', PRIOR/'qualified_numerics.py', '76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a')
E = pure_module('e', PRIOR/'stage1_v2/evaluator.py', '562279b3b636910098bf6f5e1bf2af790998a085d4233fa90975fdbdfcbf4705')
DT = np.dtype([('value','f8'),('is_leaf','u1'),('feature_idx','i8'),('num_threshold','f8'),
               ('left','i8'),('right','i8'),('missing_go_to_left','u1'),('is_categorical','u1')])


def stump(left=0., right=10., threshold=0.):
    return np.array([(0.,0,0,threshold,1,2,0,0), (left,1,0,0.,0,0,0,0),
                     (right,1,0,0.,0,0,0,0)], dtype=DT)


def arrays(stages):
    a = {'initial': np.array([0.]), 'nodes': np.concatenate(stages),
         'nodes_offsets':np.cumsum([0]+[len(t) for t in stages],dtype=np.int64)}
    for k in ('raw_left_cat_bitsets','binned_left_cat_bitsets'):
        a[k]=np.empty((0,8),dtype=np.uint32)
        a[k+'_offsets']=np.zeros(len(stages)+1,dtype=np.int64)
    return a


class Tests(unittest.TestCase):
    def setUp(self):
        self.model = E.SequentialHist(arrays([stump(),stump(10.,0.)]),required_stages=2)

    def states(self, **kw):
        out=[]
        limits=engine.Limits(self.model.stages, **kw)
        engine.refine(self.model.stages,0.,Q.sequential_range,limits,lambda x:out.append(copy.deepcopy(x)),splits=2)
        return out

    def test_tightens_and_independent_replay(self):
        out=self.states()
        self.assertEqual((Fraction(out[0]['lower']),Fraction(out[0]['upper'])),(0,20))
        self.assertEqual((Fraction(out[-1]['lower']),Fraction(out[-1]['upper'])),(10,10))
        self.assertEqual(checker.replay(out[-1],self.model.stages,0.,Q.sequential_range)['boxes'],2)

    def test_root_budget_no_new_publication(self):
        out=[]
        with self.assertRaises(engine.Budget):
            engine.refine(self.model.stages,0.,Q.sequential_range,engine.Limits(self.model.stages,visits=1),out.append)
        self.assertEqual(out,[])

    def test_child_budget_retains_prior(self):
        out=[]
        with self.assertRaises(engine.Budget):
            engine.refine(self.model.stages,0.,Q.sequential_range,engine.Limits(self.model.stages,visits=7),lambda x:out.append(copy.deepcopy(x)))
        self.assertEqual(len(out),1)
        checker.replay(out[0],self.model.stages,0.,Q.sequential_range)

    def test_memory_estimate_fail_closed(self):
        with self.assertRaises(engine.Budget):self.states(memory=1)

    def test_time_fail_closed(self):
        with self.assertRaises(engine.Budget):self.states(seconds=0)

    def test_missing_frontier_rejected(self):
        s=self.states()[-1];s['frontier']=s['frontier'][:-1]
        with self.assertRaises(ValueError):checker.full_cover(s)

    def test_duplicate_frontier_rejected(self):
        s=self.states()[-1];s['frontier']=(s['frontier'][0],s['frontier'][0])
        with self.assertRaises(ValueError):checker.full_cover(s)

    def test_gap_rejected(self):
        s=self.states()[-1];b=list(s['frontier'][0]['box']);b[0]=(-engine.MAX,-1.);s['frontier'][0]['box']=b
        with self.assertRaises(ValueError):checker.full_cover(s)

    def test_wrong_tie_rejected(self):
        s=self.states()[-1];b=list(s['frontier'][1]['box']);b[0]=(0.,engine.MAX);s['frontier'][1]['box']=b
        with self.assertRaises(ValueError):checker.full_cover(s)

    def test_bound_tamper_rejected(self):
        s=self.states()[-1];s['frontier'][0]['lower']='11'
        with self.assertRaises(ValueError):checker.replay(s,self.model.stages,0.,Q.sequential_range)

    def test_global_tamper_rejected(self):
        s=self.states()[-1];s['upper']='9'
        with self.assertRaises(ValueError):checker.replay(s,self.model.stages,0.,Q.sequential_range)

    def test_fake_history_rejected(self):
        s=self.states()[-1];s['trace'][0]['parent']=100
        with self.assertRaises(ValueError):checker.full_cover(s)

    def test_unknown_checkpoint_key(self):
        s=self.states()[-1];s['trusted']=True
        with self.assertRaises(ValueError):checker.full_cover(s)

    def test_impossible_path(self):
        t=np.array([(0,0,0,0,1,4,0,0),(0,0,0,1,2,3,0,0),(2,1,0,0,0,0,0,0),(1000,1,0,0,0,0,0,0),(3,1,0,0,0,0,0,0)],dtype=DT)
        self.model=E.SequentialHist(arrays([t]),required_stages=1)
        s=self.states()[0]
        self.assertEqual(Fraction(s['upper']),3)
        checker.replay(s,self.model.stages,0.,Q.sequential_range)

    def test_category_rejected(self):
        a=arrays([stump()]);a['nodes']['is_categorical'][0]=1
        with self.assertRaises(ValueError):E.SequentialHist(a,required_stages=1)

    def test_nonlocal_child_rejected(self):
        a=arrays([stump()]);a['nodes']['left'][0]=99
        with self.assertRaises(ValueError):E.SequentialHist(a,required_stages=1)

    def test_shared_child_rejected(self):
        a=arrays([stump()]);a['nodes']['right'][0]=1
        with self.assertRaises(ValueError):E.SequentialHist(a,required_stages=1)

    def test_nan_threshold_rejected(self):
        a=arrays([stump()]);a['nodes']['num_threshold'][0]=np.nan
        with self.assertRaises(ValueError):E.SequentialHist(a,required_stages=1)

    def test_publication_interrupt_preserves_partial(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'checkpoint.json'
            def abort():raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):exclusive_json(p,{'old':True},abort)
            self.assertFalse(p.exists());self.assertTrue(Path(str(p)+'.partial').exists())

    def test_publication_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'checkpoint.json';exclusive_json(p,{'old':True})
            with self.assertRaises(FileExistsError):exclusive_json(p,{'old':False})
            self.assertEqual(json.loads(p.read_text()),{'old':True})

    def test_hash_rejection_before_registry_decode(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.json';p.write_text('not json')
            with self.assertRaisesRegex(ValueError,'registry hash'):adapter.authenticate(p,'0'*64)

    def test_source_no_array_access_at_import(self):
        self.assertEqual(adapter.KEYS,{'initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets'})


if __name__=='__main__':unittest.main(verbosity=2)
