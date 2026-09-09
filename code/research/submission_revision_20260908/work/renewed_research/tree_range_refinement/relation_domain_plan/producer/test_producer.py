"""Synthetic producer/checker integration; never loads actual model arrays."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import engine
from domain import guarded_prediction,stamp
from schema import validate
from runner import exclusive_json
from test_cache_v3 import fixture
from test_pilot_v2 import E,Q,arrays,stump
from pilot_engine_v2 import Budget

ROOT=Path(__file__).resolve().parent
RESEARCH=ROOT.parents[2]


def load(path,pin):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('synthetic dependency hash')
    m=types.ModuleType(path.stem);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__);return m


ORACLE=load(RESEARCH/'feature_relation_certification/exact_oracle.py','35fa867b21c5beed6521f5238560561e18eb0e55a20f443ab4a8c60d91374712')
GUARD=load(RESEARCH/'feature_relation_certification/relations.py','1f175bdfe40e0e13451963bb4752e2d5903592f0f92c07246038c96e1b8c0127')
CHECKER=load(RESEARCH/'uncertainty_review/range_bound_feasibility/relation_checker.py','3fd1c9f810cd1562875ec2153ea81796c8456a2445287af8c6db40a142b0e8a8')


def relation_fixture(count=1):
    trees=[]
    for _ in range(count):
        tree=stump(1000.,0.,-.5);tree['feature_idx'][0]=16;trees.append(tree)
    return E.SequentialHist(arrays(trees),required_stages=count)


def run(model,splits=1,audit=None,**limits):
    states=[];lim=engine.Limits(model.stages,audit=audit,**limits)
    result=engine.refine(model.stages,model.initial,Q.sequential_range,lim,states.append,
                         splits=splits,oracle=ORACLE.feasible_witness)
    return result,states,lim


class Tests(unittest.TestCase):
    def test_empty_product_child_retained_and_replayed(self):
        result,states,limits=run(relation_fixture())
        s=result[0];self.assertEqual(s['product_boxes'],2);self.assertEqual(s['r_empty_boxes'],1)
        self.assertEqual(s['lower'],'0');self.assertEqual(s['upper'],'0')
        self.assertGreater(limits.infeasible_queries,0)
        for s in states:self.assertEqual(CHECKER.replay(s,relation_fixture().stages,0.,Q.sequential_range)['status'],'PASS_RESTRICTED_DOMAIN_REPLAY')

    def test_fresh_disk_roundtrip(self):
        model=fixture(3);_,states,_=run(model,splits=4)
        with tempfile.TemporaryDirectory() as d:
            for s in states:
                p=Path(d)/('c%d.json'%s['splits']);exclusive_json(p,s)
                CHECKER.replay(json.loads(p.read_text()),model.stages,0.,Q.sequential_range)

    def test_forged_empty_rejected_by_independent_checker(self):
        model=fixture(1);s=run(model)[0][0]
        if len(s['frontier'])<2:self.fail('fixture must split')
        row=s['frontier'][0];row.update(status='R_EMPTY',witness=None,lower=None,upper=None,cuts=())
        s['r_empty_boxes']+=1;s['r_nonempty_boxes']-=1
        with self.assertRaises(ValueError):CHECKER.replay(s,model.stages,0.,Q.sequential_range)

    def test_domain_and_boolean_type_rejection(self):
        s=run(relation_fixture())[0][0]
        for change in ({'id':'FULL_DOMAIN'},{'finite_binary64':1},{'guard_source_sha256':'0'*64}):
            x=copy.deepcopy(s);x['domain'].update(change)
            with self.assertRaises(ValueError):validate(x)
            with self.assertRaises(ValueError):CHECKER.replay(x,relation_fixture().stages,0.,Q.sequential_range)

    def test_empty_fields_strict(self):
        s=run(relation_fixture())[0][0]
        row=next(x for x in s['frontier'] if x['status']=='R_EMPTY');row['lower']='0'
        with self.assertRaises(ValueError):validate(s)

    def test_invalid_witness_and_counts(self):
        s=run(relation_fixture())[0][0]
        row=next(x for x in s['frontier'] if x['status']=='R_NONEMPTY');w=[1.]*62;w[16]=2.;row['witness']=tuple(w)
        with self.assertRaises(ValueError):validate(s)
        x=run(relation_fixture())[0][0];x['product_boxes']=True
        with self.assertRaises(ValueError):validate(x)

    def test_noncanonical_rational_rejected(self):
        x=run(relation_fixture())[0][0];x['lower']='0/1'
        with self.assertRaises(ValueError):validate(x)

    def test_binary64_checked_before_root_oracle(self):
        model=relation_fixture();oracle=mock.Mock()
        with mock.patch('domain.struct.calcsize',return_value=4):
            with self.assertRaises(RuntimeError):engine.refine(model.stages,0.,Q.sequential_range,engine.Limits(model.stages),lambda s:None,oracle=oracle)
        oracle.assert_not_called()

    def test_oracle_unknown_is_error_not_empty(self):
        model=relation_fixture()
        with self.assertRaises(ValueError):engine.refine(model.stages,0.,Q.sequential_range,engine.Limits(model.stages),lambda s:None,oracle=lambda box:'unknown')

    def test_runtime_guard_exact_identity_fallback(self):
        x=[0.]*62;b=.0123456789
        self.assertEqual(guarded_prediction(x,b,.02,True,GUARD.relation_guard),.02)
        x[16]=1.
        self.assertIs(guarded_prediction(x,b,float('nan'),True,GUARD.relation_guard),b)
        self.assertIs(guarded_prediction([float('nan')]*62,b,float('nan'),False,GUARD.relation_guard),b)
        with self.assertRaises(ValueError):guarded_prediction(x,b,.02,1,GUARD.relation_guard)

    def test_root_budget_retains_no_candidate(self):
        model=relation_fixture();states=[]
        with self.assertRaises(Budget):engine.refine(model.stages,0.,Q.sequential_range,engine.Limits(model.stages,visits=1),states.append,oracle=ORACLE.feasible_witness)
        self.assertEqual(states,[])

    def test_all_empty_snapshot_is_error(self):
        row={'id':0,'box':((-engine.MAX,engine.MAX),)*62,'status':'R_EMPTY','witness':None,'lower':None,'upper':None,'cuts':()}
        with self.assertRaises(ValueError):engine.make_snapshot((row,),())

    def test_interruption_retains_completed_checkpoint(self):
        model=relation_fixture();_,states,_=run(model)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.json';exclusive_json(p,states[0]);old=p.read_bytes()
            def stop(chunk):raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):exclusive_json(Path(d)/'new.json',states[-1],serialization_interrupt=stop)
            self.assertEqual(p.read_bytes(),old)
            CHECKER.replay(json.loads(old),model.stages,0.,Q.sequential_range)

    def test_every_instrumented_estimate_conservative(self):
        checks=[]
        def audit(new,original,*_):self.assertGreaterEqual(new,original);checks.append(new-original)
        _,_,lim=run(fixture(3),splits=4,audit=audit)
        self.assertGreater(len(checks),lim.visits)


if __name__=='__main__':unittest.main(verbosity=2)
