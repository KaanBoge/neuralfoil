"""Synthetic/adversarial checker tests; no producer traversal imported."""
import unittest,copy,sys,math,time
from pathlib import Path
import relation_checker as c
sys.path.insert(0,str(c.ROOT/'tree_range_refinement'))
from test_pilot_v2 import E,Q,arrays,DT
import numpy as np
MAX=sys.float_info.max
def model():
    tree=np.zeros(3,dtype=DT);tree[0]['feature_idx']=16;tree[0]['num_threshold']=-math.ulp(0.);tree[0]['left']=1;tree[0]['right']=2
    tree[1]['is_leaf']=tree[2]['is_leaf']=1;tree[1]['value']=10.;tree[2]['value']=1.
    return E.SequentialHist(arrays([tree]),required_stages=1)
def point(box):
    x=c.oracle.feasible(box)['witness'];assert x is not None;return x
def checkpoint(split=False):
    box=[(-MAX,MAX)]*62
    row={'id':0,'box':box,'status':'R_NONEMPTY','witness':point(box),'lower':'1','upper':'1','cuts':[(16,-math.ulp(0.))]}
    x={'format':'RELATION_RANGE_CHECKPOINT_V1','domain':copy.deepcopy(c.DOMAIN),'frontier':[row],'trace':[],'lower':'1','upper':'1','splits':0,'product_boxes':1,'r_nonempty_boxes':1,'r_empty_boxes':0}
    if split:
        left=box.copy();left[16]=(-MAX,-math.ulp(0.));right=box.copy();right[16]=(-0.,MAX)
        x.update(frontier=[{'id':1,'box':left,'status':'R_EMPTY','witness':None,'lower':None,'upper':None,'cuts':[]},{'id':2,'box':right,'status':'R_NONEMPTY','witness':point(right),'lower':'1','upper':'1','cuts':[]}],trace=[{'parent':0,'feature':16,'threshold':-math.ulp(0.),'children':[1,2]}],splits=1,product_boxes=2,r_empty_boxes=1)
    return x
class Tests(unittest.TestCase):
    def replay(self,x,**kw):
        m=model();return c.replay(x,m.stages,m.initial,Q.sequential_range,**kw)
    def test_root_prunes_impossible_leaf(self):self.assertEqual(self.replay(checkpoint())['upper'],'1')
    def test_empty_child_retained(self):self.assertEqual(self.replay(checkpoint(True))['r_empty_boxes'],1)
    def test_json_roundtrip(self):
        import json
        self.assertEqual(self.replay(json.loads(json.dumps(checkpoint(True))))['boxes'],2)
    def test_domain_tamper(self):
        for k,v in [('id','wrong'),('finite_binary64',1),('guard_source_sha256','bad'),('dimensions',62.)]:
            x=checkpoint();x['domain'][k]=v
            with self.assertRaises(ValueError):self.replay(x)
    def test_unknown_fields(self):
        for target in ['top','row']:
            x=checkpoint();(x if target=='top' else x['frontier'][0])['unknown']=1
            with self.assertRaises(ValueError):self.replay(x)
    def test_forged_empty(self):
        x=checkpoint(True);r=x['frontier'][1];r.update(status='R_EMPTY',witness=None,lower=None,upper=None,cuts=[]);x.update(r_nonempty_boxes=0,r_empty_boxes=2)
        with self.assertRaises(ValueError):self.replay(x)
    def test_missing_empty_box(self):
        x=checkpoint(True);x['frontier']=x['frontier'][1:];x.update(product_boxes=1,r_empty_boxes=0)
        with self.assertRaises(ValueError):self.replay(x)
    def test_bad_witness(self):
        for change in ['relation','membership','none']:
            x=checkpoint(True);w=x['frontier'][1]['witness']
            if change=='relation':w[16]=1.
            elif change=='membership':w[16]=-1.;w[0]=1.
            else:x['frontier'][1]['witness']=None
            with self.assertRaises(ValueError):self.replay(x)
    def test_wrong_range(self):
        x=checkpoint();x['frontier'][0]['upper']='10';x['upper']='10'
        with self.assertRaises(ValueError):self.replay(x)
    def test_wrong_adjacency(self):
        x=checkpoint(True);x['frontier'][1]['box'][16]=(math.ulp(0.),MAX)
        with self.assertRaises(ValueError):self.replay(x)
    def test_cut_schema(self):
        for cut in [(True,0.),(62,0.),(0,float('nan'))]:
            x=checkpoint();x['frontier'][0]['cuts']=[cut]
            with self.assertRaises(ValueError):self.replay(x)
    def test_count_bool_refused(self):
        x=checkpoint();x['product_boxes']=True
        with self.assertRaises(ValueError):self.replay(x)
    def test_deadline(self):
        with self.assertRaises(TimeoutError):self.replay(checkpoint(),deadline=time.monotonic()-1)
    def test_input_immutable(self):
        x=checkpoint(True);before=copy.deepcopy(x);self.replay(x);self.assertEqual(x,before)
    def test_forged_empty_with_other_active_box(self):
        x=checkpoint(True);x['trace'][0].update(feature=0,threshold=0.)
        x['frontier'][0]['box']=[(-MAX,MAX)]*62;x['frontier'][0]['box'][0]=(-MAX,0.)
        x['frontier'][1]['box']=[(-MAX,MAX)]*62;x['frontier'][1]['box'][0]=(math.ulp(0.),MAX)
        x['frontier'][1]['witness']=point(x['frontier'][1]['box'])
        with self.assertRaisesRegex(ValueError,'forged domain status'):self.replay(x)
    def test_order_relation_on_path(self):
        # A split on min-coordinate18 below a lower bound on both operands is impossible.
        tree=np.zeros(3,dtype=DT);tree[0]['feature_idx']=18;tree[0]['num_threshold']=-math.ulp(0.);tree[0]['left']=1;tree[0]['right']=2
        tree[1]['is_leaf']=tree[2]['is_leaf']=1;tree[1]['value']=10.;tree[2]['value']=1.
        # Full root has possible negative operands, so neither leaf may be dropped.
        m=E.SequentialHist(arrays([tree]),required_stages=1);x=checkpoint();x['frontier'][0].update(lower='1',upper='10',cuts=[(18,-math.ulp(0.))]);x['upper']='10'
        self.assertEqual(c.replay(x,m.stages,m.initial,Q.sequential_range)['upper'],'10')
    def test_outward_stage_cancellation(self):
        trees=[]
        for value in [2.**53,1.,-2.**53]:
            t=np.zeros(1,dtype=DT);t[0]['is_leaf']=1;t[0]['value']=value;trees.append(t)
        m=E.SequentialHist(arrays(trees),required_stages=3);v=Q.sequential_range(m.initial,[[float(t[0]['value'])] for t in trees]);x=checkpoint()
        x['lower']=x['frontier'][0]['lower']=str(v['lower']);x['upper']=x['frontier'][0]['upper']=str(v['upper']);x['frontier'][0]['cuts']=[]
        self.assertEqual(c.replay(x,m.stages,m.initial,Q.sequential_range)['lower'],str(v['lower']))
if __name__=='__main__':unittest.main(verbosity=2)
