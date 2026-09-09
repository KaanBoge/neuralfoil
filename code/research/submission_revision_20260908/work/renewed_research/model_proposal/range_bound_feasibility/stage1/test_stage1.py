"""Synthetic tests only; no Inputs() or fitted-tree loading."""
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import numpy as np
from evaluator import SequentialHist
import numerics as n
import run_stage1 as run
import assess_stage1 as assessment

DT=np.dtype([('value','f8'),('is_leaf','u1'),('feature_idx','u4'),('num_threshold','f8'),
             ('left','u4'),('right','u4'),('missing_go_to_left','u1'),('is_categorical','u1')])
def synthetic():
    nodes=np.zeros(3,dtype=DT)
    nodes['left'][0]=1;nodes['right'][0]=2;nodes['num_threshold'][0]=.2
    nodes['is_leaf'][1:]=1;nodes['value'][1:]=[-.1,.3]
    return {'initial':np.array([.05]),'nodes':nodes,'nodes_offsets':np.array([0,3]),
            'raw_left_cat_bitsets':np.empty((0,8),dtype='u4'),'raw_left_cat_bitsets_offsets':np.array([0,0]),
            'binned_left_cat_bitsets':np.empty((0,8),dtype='u4'),'binned_left_cat_bitsets_offsets':np.array([0,0])}

class Stage1(unittest.TestCase):
    def test_threshold_and_float64(self):
        m=SequentialHist(synthetic(),1);x=np.zeros((3,62))
        x[:,0]=[np.nextafter(.2,-np.inf),.2,np.nextafter(.2,np.inf)]
        np.testing.assert_array_equal(m.predict_raw(x),[.05-.1,.05-.1,.05+.3])
        with self.assertRaises(ValueError):m.predict_raw(x.astype('f4'))
    def test_permutations_chunks_empty(self):
        m=SequentialHist(synthetic(),1);x=np.zeros((20,62));x[:,0]=np.arange(20)/20
        expected=m.predict_raw(x);order=np.arange(20)[::-1]
        np.testing.assert_array_equal(m.predict_raw(x[order]),expected[order])
        np.testing.assert_array_equal(np.r_[m.predict_raw(x[:7]),m.predict_raw(x[7:])],expected)
        self.assertEqual(m.predict_raw(np.empty((0,62))).shape,(0,))
    def test_mutation_isolated(self):
        a=synthetic();m=SequentialHist(a,1);a['nodes']['value'][:]=10
        self.assertEqual(m.predict_raw(np.zeros((1,62)))[0],.05-.1)
    def test_400_order(self):
        a=synthetic();a['nodes']=np.tile(a['nodes'],400);a['nodes_offsets']=np.arange(401)*3
        for k in ['raw_left_cat_bitsets_offsets','binned_left_cat_bitsets_offsets']:a[k]=np.zeros(401,int)
        m=SequentialHist(a);expected=.05
        for _ in range(400):expected+=-.1
        self.assertEqual(m.predict_raw(np.zeros((1,62)))[0],expected)
    def test_bad_topologies(self):
        for field,value in [('left',0),('right',1),('right',4),('feature_idx',62),('is_categorical',1),('missing_go_to_left',2)]:
            a=synthetic();a['nodes'][field][0]=value
            with self.assertRaises(ValueError):SequentialHist(a,1)
        a=synthetic();a['nodes']['is_leaf'][0]=1
        with self.assertRaises(ValueError):SequentialHist(a,1)
    def test_bad_features(self):
        m=SequentialHist(synthetic(),1)
        for x in [np.zeros((1,61)),np.full((1,62),np.nan),np.full((1,62),np.inf)]:
            with self.assertRaises(ValueError):m.predict_raw(x)
    def test_production_AST(self):
        self.assertEqual(len(n.GROUP_AST),64);self.assertEqual(len(n.CONFIDENCE_AST),64)
        for values in [[],[n.q.F(0)]*10,[n.q.F(1,8)]*10]:
            self.assertEqual(n.calibrate_exact_groups(values,n.q.GENERIC_BOUND),n.q.synthetic_confidence(values,n.q.GENERIC_BOUND))
    def test_matched_procedure_only_bound_differs(self):
        b=np.array([1.,2.,3.]);c,h,g=n.q.guarded_core(b,[.3,.4,-.2],[True]*3)
        y=np.array([1.,2.1,3.]);ids=['a','a','b']
        a=n.fit_scalar(b,c,h,y,ids,n.q.F(1,3));z=n.fit_scalar(b,c,h,y,ids,n.q.GENERIC_BOUND)
        self.assertEqual(a['group_means'],z['group_means']);self.assertGreaterEqual(a['t'],z['t'])
    def test_exact_loss_large_targets(self):
        b=np.array([1.]);c,h,g=n.q.guarded_core(b,[.3],[True])
        for y in [-np.finfo(float).max,np.finfo(float).max]:
            z=n.fit_scalar(b,c,h,[y],['a'],n.q.GENERIC_BOUND)
            self.assertLessEqual(z['exact_mean'],n.q.GENERIC_BOUND)
    def test_prediction_inward_and_guard(self):
        b=np.array([1.,2.**-501]);c,h,g=n.q.guarded_core(b,[.7,.7],[True,True])
        p,e=n.predictions({'t':.123},b,c,h,g)
        self.assertEqual(p[1],b[1]);self.assertEqual(e[1],0)
        self.assertLessEqual((n.q.rat(p[0])-n.q.rat(h[0]))/(n.q.rat(c[0])-n.q.rat(h[0])),n.q.rat(.123))
    def test_bound_rejection(self):
        with self.assertRaises(ValueError):n.fit_scalar([1.],[2.],[1.5],[0.],['a'],n.q.F(1,4))
        with self.assertRaises(ValueError):n.fit_scalar([1.],[1.],[1.],[1.],[''],n.q.F(1,4))
    def test_refuse_overwrite_and_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'record.json';run.write_json(p,{'v':1})
            with self.assertRaises(FileExistsError):run.write_json(p,{'v':2})
            with self.assertRaises(ValueError):run.read_checked(p,'0'*64)
    def test_approval_phase_and_pin_barrier(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td);here=parent/'synthetic';here.mkdir()
            draft=parent/'STAGE1_PROTOCOL_DRAFT.md';draft.write_bytes(b'synthetic protocol')
            manifest={'source_sha256':{},'protocol_draft_sha256':run.sha(draft.read_bytes())}
            run.write_json(here/'IMPLEMENTATION_FREEZE.json',manifest)
            mh=run.sha((here/'IMPLEMENTATION_FREEZE.json').read_bytes())
            approval=here/'approval.json';run.write_json(approval,{'implementation_sha256':mh,'authorized_phases':['parity']})
            args=SimpleNamespace(implementation_sha256=mh,approval=approval,
                                 approval_sha256=run.sha(approval.read_bytes()),phase='calibrate')
            with patch.object(run,'HERE',here):
                with self.assertRaises(ValueError):run.authorize(args)
                args.phase='parity';self.assertEqual(run.authorize(args),manifest)
                draft.write_bytes(b'tampered')
                with self.assertRaises(ValueError):run.authorize(args)
    def test_parity_barrier_authenticates_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            here=Path(td);d=here/'precalibration';d.mkdir()
            payload=d/'synthetic.npz';payload.write_bytes(b'synthetic-not-a-real-array')
            run.write_json(d/'PARITY_PASS.json',{'status':'EXACT_PRELOSS_PARITY_PASS','target_members_materialized':False,
                'source_input_sha256':{},'artifact_sha256':{payload.name:run.sha(payload.read_bytes())}})
            with patch.object(run,'HERE',here):
                self.assertEqual(run.read_parity()[0]['status'],'EXACT_PRELOSS_PARITY_PASS')
                payload.write_bytes(b'tampered')
                with self.assertRaises(ValueError):run.read_parity()
    def test_bad_bitsets_and_stage_count(self):
        a=synthetic()
        with self.assertRaises(ValueError):SequentialHist(a)
        a['raw_left_cat_bitsets']=np.ones((1,8),dtype='u4')
        with self.assertRaises(ValueError):SequentialHist(a,1)
    def test_initial_dtype_rejected(self):
        a=synthetic();a['initial']=a['initial'].astype('f4')
        with self.assertRaises(ValueError):SequentialHist(a,1)
    def test_assessment_checks_new_freeze_before_old_data(self):
        with tempfile.TemporaryDirectory() as td:
            here=Path(td);(here/'results').mkdir();(here/'predictions').mkdir()
            run.write_json(here/'results/freeze.json',{'calibrator_count':31})
            run.write_json(here/'predictions/complete.json',{
                'freeze_sha256':run.sha((here/'results/freeze.json').read_bytes())})
            with (patch.object(run,'HERE',here),patch.object(run,'read_parity',return_value=({},'synthetic')),
                  patch.object(run,'json_checked') as old_loader):
                with self.assertRaises(ValueError):assessment.assess(here/'unused')
                old_loader.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
