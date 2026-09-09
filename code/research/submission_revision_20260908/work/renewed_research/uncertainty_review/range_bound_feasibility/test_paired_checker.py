"""Independent synthetic fixtures; no model files or producer imports."""
import copy
from fractions import Fraction as F
import math
import hashlib
import ast
import inspect
import unittest
import numpy as np
import paired_checker as c

DT=np.dtype([(k,'f8' if k in ('value','num_threshold') else 'i8') for k in
 ('value','num_threshold','is_leaf','feature_idx','left','right','missing_go_to_left','is_categorical')])

def fixture(trees=2,feature=0,threshold=0.):
    rows=np.zeros(3*trees,dtype=DT)
    for i in range(trees):
        a=rows[3*i:3*i+3];a[0]['feature_idx']=feature;a[0]['num_threshold']=threshold
        a[0]['left']=1;a[0]['right']=2;a[1:]['is_leaf']=1
        a[1]['value']=-.25;a[2]['value']=.5
    x={'initial':np.array([0.]),'nodes':rows,'nodes_offsets':np.arange(0,3*trees+1,3,dtype=np.int64)}
    for n in ('raw_left_cat_bitsets','binned_left_cat_bitsets'):
        x[n]=np.array([],dtype=np.uint32);x[n+'_offsets']=np.zeros(trees+1,dtype=np.int64)
    return x

SYNTHETIC_SHA=hashlib.sha256(b'independent-paired-checker-synthetic400-stumps-v1').hexdigest()

def certificate(x):
    initial,trees=c.inventory(x)
    trees=[sorted(t,key=lambda z:z[0]['leaf']) for t in trees]
    paths=[z[0] for t in trees for z in t]
    old=(F(initial),F(initial))
    for tree in trees:old=c.propagate(*old,[(c.hx(z[0]['value']),) for z in tree])
    o=c.oracle();domains={};summary={};total=0
    for domain,identity in (('D','FINITE_X62_V1'),('R','FINITE_X62_ABS_MINMAX_NUMERIC_V1')):
        current=(F(initial),F(initial));blocks=[];attempts=feasible=0
        for j in range(200):
            pairs=[];seq=[];before=current
            for a in trees[2*j]:
                for b in trees[2*j+1]:
                    box=c.intersect(a[1],b[1]);point=None
                    if a[1] is None or b[1] is None:status='path_empty'
                    elif box is None:status='intersection_empty'
                    else:
                        point=[p[0] for p in box] if domain=='D' else o.feasible(box)['witness']
                        status='feasible' if point is not None else 'R_infeasible'
                    pairs.append({'leaves':[a[0]['leaf'],b[0]['leaf']],'status':status,
                                  'witness':[point[k].hex() for k in c.SIX] if point is not None else None})
                    attempts+=1
                    if status=='feasible':seq.append((c.hx(a[0]['value']),c.hx(b[0]['value'])));feasible+=1
            current=c.propagate(*current,seq)
            blocks.append({'block':j,'stages':[2*j,2*j+1],'pairs':pairs,'incoming':list(map(c.encode,before)),'outgoing':list(map(c.encode,current))})
        domains[domain]={'id':identity,'blocks':blocks}
        summary[domain]={'lower':c.encode(current[0]),'upper':c.encode(current[1]),'B':c.encode(c.structural(*current)),
                         'attempted_pairs':attempts,'feasible_pairs':feasible};total+=attempts
    return {'schema':'PAIRED_TREE_CERTIFICATE_V1','model_sha256':SYNTHETIC_SHA,'initial':initial.hex(),
      'paths':paths,'domains':domains,'stage0':{'lower':c.encode(old[0]),'upper':c.encode(old[1]),'B':c.encode(c.structural(*old))},
      'summary':summary,'counts':{'stages':400,'blocks_per_domain':200,'paths':len(paths),'path_edges':sum(len(p['edges']) for p in paths),'attempted_pairs':total}}

class Tests(unittest.TestCase):
    def test_underflow_arithmetic_uses_runtime_operands(self):
        fn=ast.parse(inspect.getsource(c.runtime))
        assigned={node.targets[0].id:node.value for node in ast.walk(fn)
                  if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)}
        for name,op,operands in [('sub',ast.Mult,('normal','half')),('twice',ast.Add,('smallest','smallest'))]:
            value=assigned[name]
            self.assertIsInstance(value,ast.BinOp);self.assertIsInstance(value.op,op)
            self.assertEqual((value.left.id,value.right.id),operands)
        c.runtime()
    def test_paths_and_opposite_pair(self):
        a,p=c.inventory(fixture(),2)
        self.assertEqual([r[0]['leaf'] for r in p[0]],[1,2])
        self.assertIsNone(c.intersect(p[0][0][1],p[1][1][1]))
    def test_maxfinite_empty_path_retained(self):
        _,p=c.inventory(fixture(threshold=c.MAX),2)
        self.assertEqual(len(p[0]),2);self.assertTrue(p[0][1][0]['empty'])
    def test_cycle_duplicate_and_unreachable(self):
        for child in (0,1,3):
            x=fixture();x['nodes'][0]['right']=child
            with self.assertRaises(ValueError):c.inventory(x,2)
    def test_bad_offsets_and_dtype(self):
        x=fixture();x['nodes_offsets']=np.array([0,3,2**64-1],dtype=np.uint64)
        with self.assertRaises(ValueError):c.inventory(x,2)
        x=fixture();x['initial']=x['initial'].astype('f4')
        with self.assertRaises(ValueError):c.inventory(x,2)
    def test_missing_and_extra_member(self):
        x=fixture();del x['initial']
        with self.assertRaises(ValueError):c.inventory(x,2)
        x=fixture();x['extra']=np.array([1])
        with self.assertRaises(ValueError):c.inventory(x,2)
    def test_deadline_and_production_stage_count(self):
        with self.assertRaises(TimeoutError):c.inventory(fixture(),2,0)
        with self.assertRaises(ValueError):c.inventory(fixture())
    def test_signedzero_and_subnormal(self):
        box=((-c.MAX,c.MAX),)*62
        l=c.restrict(box,0,-0.,'L');r=c.restrict(box,0,-0.,'R')
        self.assertEqual(l[0][1],0.);self.assertEqual(r[0][0],2.**-1074)
        self.assertIsNone(c.intersect(l,r))
    def test_repeated_feature_contradiction_keeps_descendant(self):
        x=fixture(2);rows=[]
        for _ in range(2):
            t=np.zeros(5,dtype=DT);t[0]['left']=1;t[0]['right']=4
            t[1]['left']=2;t[1]['right']=3;t[2:]['is_leaf']=1
            rows.append(t)
        x['nodes']=np.concatenate(rows);x['nodes_offsets']=np.array([0,5,10])
        _,paths=c.inventory(x,2)
        self.assertEqual(len(paths[0]),3)
        self.assertTrue(next(row for row,box in paths[0] if row['leaf']==3)['empty'])
    def test_r_case_rejection(self):
        box=list(((-c.MAX,c.MAX),)*62);box[16]=(-2.,-1.)
        self.assertFalse(c.oracle().feasible(box)['feasible'])
        box[16]=(0.,0.)
        self.assertTrue(c.oracle().feasible(box)['feasible'])
    def test_exact_codec(self):
        for x in (F(0),F(-7,8),F(1,2**1074)):self.assertEqual(c.rational(c.encode(x)),x)
        x=c.encode(F(1));x['denominator']='0x2'
        self.assertEqual(c.rational(x),F(1,2))
        x['numerator']='0x2'
        with self.assertRaises(ValueError):c.rational(x)
    def test_ordered_arithmetic(self):
        lo,hi=c.propagate(F(1),F(1),[(2.**-53,-1.)])
        self.assertEqual(lo,0);self.assertEqual(hi,F(1,2**52))
        for values in ((.5,-.25),(-.25,.5)):
            a,b=c.propagate(F(0),F(0),[values]);self.assertEqual(a,F(.25));self.assertEqual(a,b)
    def test_overflow_fail(self):
        with self.assertRaises(ValueError):c.propagate(F(c.MAX),F(c.MAX),[(c.MAX,0.)])
    def test_readonly_inputs_unchanged(self):
        x=fixture();prior={k:v.tobytes() for k,v in x.items()}
        for a in x.values():a.setflags(write=False)
        c.inventory(x,2)
        self.assertEqual(prior,{k:v.tobytes() for k,v in x.items()})

class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x=fixture(400,16,-.5);cls.cert=certificate(cls.x)
    def test_complete_replay_and_default_actual_binding(self):
        result=c.check(self.cert,self.x,expected_model_sha=SYNTHETIC_SHA)
        self.assertEqual(result['counts']['attempted_pairs'],1600)
        with self.assertRaises(ValueError):c.check(self.cert,self.x)
    def test_minimum_order_exclusion_full_inventory(self):
        x=fixture(400,12,0.)
        for i in range(1,400,2):x['nodes'][3*i]['feature_idx']=18
        z=certificate(x)
        self.assertTrue(any(p['status']=='R_infeasible' for p in z['domains']['R']['blocks'][0]['pairs']))
        c.check(z,x,expected_model_sha=SYNTHETIC_SHA)
    def test_omitted_duplicate_swapped_pair(self):
        for mode in ('omit','duplicate','swap'):
            z=copy.deepcopy(self.cert);p=z['domains']['D']['blocks'][0]['pairs']
            if mode=='omit':p.pop()
            elif mode=='duplicate':p[1]=copy.deepcopy(p[0])
            else:p[0],p[1]=p[1],p[0]
            with self.assertRaises(ValueError):c.check(z,self.x,expected_model_sha=SYNTHETIC_SHA)
    def test_false_r_rejection_and_witness(self):
        for kind in ('status','witness'):
            z=copy.deepcopy(self.cert);p=z['domains']['R']['blocks'][0]['pairs'][-1]
            if kind=='status':p['status']='R_infeasible';p['witness']=None
            else:p['witness'][3]=(-1.).hex()
            with self.assertRaises(ValueError):c.check(z,self.x,expected_model_sha=SYNTHETIC_SHA)
    def test_changed_path_sign_value_id_and_empty(self):
        for field in ('branch','value','leaf','empty'):
            z=copy.deepcopy(self.cert);p=z['paths'][0]
            if field=='branch':p['edges'][0]['branch']='R'
            elif field=='value':p['value']=(.75).hex()
            elif field=='leaf':p['leaf']=2
            else:p['empty']=not p['empty']
            with self.assertRaises(ValueError):c.check(z,self.x,expected_model_sha=SYNTHETIC_SHA)
    def test_endpoint_count_bool_and_domain(self):
        for kind in ('endpoint','count','domain','unknown'):
            z=copy.deepcopy(self.cert)
            if kind=='endpoint':z['domains']['D']['blocks'][0]['outgoing'][0]=c.encode(F(3))
            elif kind=='count':z['counts']['stages']=400.
            elif kind=='domain':z['domains']['R']['id']='FINITE_X62_V1'
            else:z['extra']=1
            with self.assertRaises(ValueError):c.check(z,self.x,expected_model_sha=SYNTHETIC_SHA)
    def test_omitted_stage_and_model_mutation(self):
        z=copy.deepcopy(self.cert);z['domains']['D']['blocks'].pop()
        with self.assertRaises(ValueError):c.check(z,self.x,expected_model_sha=SYNTHETIC_SHA)
        x=copy.deepcopy(self.x);x['nodes'][1]['value']=.6
        with self.assertRaises(ValueError):c.check(self.cert,x,expected_model_sha=SYNTHETIC_SHA)

if __name__=='__main__':unittest.main()
