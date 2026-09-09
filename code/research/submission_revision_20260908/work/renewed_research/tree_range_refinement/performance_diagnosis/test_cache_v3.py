"""Synthetic parity and conservative accounting tests, never real trees."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pilot_engine_v2 as old
from pilot_runner_v2 import exclusive_json
from pilot_checker import replay
from test_pilot_v2 import E,Q,arrays,stump,DT
import engine_v3 as new
from cache_v3 import Sealed,Prefix,thaw,FrozenMap
import numpy as np


def fixture(count=6):
    trees=[]
    for k in range(count):
        tree=np.zeros(15,dtype=DT)
        for j in range(15):
            if j>=7:tree[j]['is_leaf']=1;tree[j]['value']=((k+j)%17-8)/1024.
            else:
                depth=(j+1).bit_length()-1
                tree[j]['feature_idx']=(k+depth)%62;tree[j]['num_threshold']=(j%3-1)/2.
                tree[j]['left']=2*j+1;tree[j]['right']=2*j+2
        trees.append(tree)
    return E.SequentialHist(arrays(trees),required_stages=count)


def canonical(x):
    if isinstance(x,dict):return {k:canonical(v) for k,v in x.items()}
    if isinstance(x,set):return sorted(canonical(v) for v in x)
    if isinstance(x,(tuple,list)):return [canonical(v) for v in x]
    return x


class Tests(unittest.TestCase):
    def test_every_visit_equivalent_graph_and_checkpoint(self):
        model=fixture();oldstates=[];newstates=[];oldgraphs=[];newgraphs=[];checks=[]
        class Reference(old.Limits):
            def check(self,transient=(),visit=False):
                if visit:oldgraphs.append(canonical(copy.deepcopy((self.persistent,transient))))
                return super().check(transient,visit)
        def audit(estimate,reference,visit,graph):
            self.assertGreaterEqual(estimate,reference);checks.append((estimate,reference))
            if visit:newgraphs.append(canonical(graph))
        oldresult=old.refine(model.stages,model.initial,Q.sequential_range,Reference(model.stages),oldstates.append,splits=4)
        limits=new.Limits(model.stages,audit=audit)
        newresult=new.refine(model.stages,model.initial,Q.sequential_range,limits,newstates.append,splits=4)
        self.assertEqual(oldresult,newresult);self.assertEqual(oldstates,newstates)
        self.assertEqual(oldgraphs,newgraphs);self.assertGreater(len(checks),limits.visits)
        for state in newstates:replay(state,model.stages,model.initial,Q.sequential_range)

    def test_graph_sealed_from_source_alias(self):
        shared=[1.,2.];obj={'a':shared,'b':shared};s=Sealed.make(obj);before=s.charge
        shared.append(9.);obj['c']=[]
        self.assertEqual(thaw(s.value),{'a':[1.,2.],'b':[1.,2.]});self.assertEqual(s.charge,before)
        with self.assertRaises(Exception):s.charge=0
        with self.assertRaises(TypeError):s.value['a'][0]=0.

    def test_mutable_unsupported_type_rejected(self):
        with self.assertRaises(TypeError):Sealed.make({'a':set([1])})

    def test_fake_frozen_container_cannot_alias(self):
        values=[1.,2.];s=Sealed.make(FrozenMap((('x',values),)))
        values.append(3.);self.assertEqual(thaw(s.value),{'x':[1.,2.]})
        with self.assertRaises(TypeError):Sealed({'x':values},10**9)
        with self.assertRaises(ValueError):Sealed(s.value,0)

    def test_publication_callback_cannot_poison_cache(self):
        model=fixture(2);expected=[];actual=[]
        old.refine(model.stages,0.,Q.sequential_range,old.Limits(model.stages),expected.append,splits=4)
        def callback(x):
            actual.append(copy.deepcopy(x));x['frontier'][0]['lower']='-99999'
            x['trace']=();x['frontier'][0]['box']=()
        new.refine(model.stages,0.,Q.sequential_range,new.Limits(model.stages),callback,splits=4)
        self.assertEqual(expected,actual)

    def test_prefix_capacity_and_aliases(self):
        prefix=Prefix();reference=[]
        for n in (0,1,2,7,8,9,16,17,64,65):
            row=[]
            for j in range(n):row.append(float(j%3))
            ref=list(row);reference.append(ref);prefix.append(row)
            self.assertGreaterEqual(prefix.charge(),old.owned_size(reference))
            row.append(1000.)
            self.assertEqual(list(prefix)[-1],tuple(ref))

    def test_every_transition_and_overlap(self):
        model=fixture(1);checks=[]
        def audit(a,b,*_):self.assertGreaterEqual(a,b);checks.append(a)
        limits=new.Limits(model.stages,audit=audit)
        shared=[1.,2.];sealed=Sealed.make({'box':shared,'same':shared})
        for child_count in (0,1,2,8):
            children=[sealed]*child_count;limits.install(sealed,children)
            prefix=Prefix()
            for n in range(10):
                leaves=[float(i) for i in range(n)];prefix.append(leaves)
                limits.check(active=({'same':shared},leaves,[shared]),prefix=prefix,
                             extra=(shared,shared),sealed_extra=(sealed,))
        self.assertEqual(len(checks),40)

    def test_durable_serialization_and_interruption(self):
        model=fixture(2)
        with tempfile.TemporaryDirectory() as d:
            out=[]
            def publish(x):
                p=Path(d)/('state%d.json'%x['splits']);exclusive_json(p,x);out.append(p)
            new.refine(model.stages,0.,Q.sequential_range,new.Limits(model.stages),publish,splits=1)
            for p in out:replay(json.loads(p.read_text()),model.stages,0.,Q.sequential_range)
            def fail(chunk):raise KeyboardInterrupt()
            p=Path(d)/'bad.json'
            with self.assertRaises(KeyboardInterrupt):exclusive_json(p,json.loads(out[-1].read_text()),serialization_interrupt=fail)
            self.assertFalse(p.exists());self.assertTrue(Path(str(p)+'.partial').exists())

    def test_child_failure_keeps_root(self):
        model=fixture(1);published=[];limit=new.Limits(model.stages,visits=16)
        with self.assertRaises(old.Budget):new.refine(model.stages,0.,Q.sequential_range,limit,published.append)
        self.assertEqual(len(published),1);self.assertEqual(published[0]['splits'],0)
        replay(published[0],model.stages,0.,Q.sequential_range)

    def test_root_failure_no_checkpoint(self):
        model=fixture(1);published=[]
        with self.assertRaises(old.Budget):new.refine(model.stages,0.,Q.sequential_range,new.Limits(model.stages,visits=1),published.append)
        self.assertEqual(published,[])

    def test_no_weaker_memory_limit(self):
        model=fixture(1)
        with self.assertRaises(old.Budget):new.refine(model.stages,0.,Q.sequential_range,new.Limits(model.stages,memory=1),lambda x:None)


if __name__=='__main__':unittest.main(verbosity=2)
