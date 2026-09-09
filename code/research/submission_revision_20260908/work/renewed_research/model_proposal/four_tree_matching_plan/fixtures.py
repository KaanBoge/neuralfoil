"""Synthetic valid numeric trees; never reads real model/feature/label data."""
import numpy as np
DTYPE=np.dtype([('value','f8'),('is_leaf','u1'),('feature_idx','u4'),('num_threshold','f8'),('left','u4'),('right','u4'),('missing_go_to_left','u1'),('is_categorical','u1')])
def constant(v=0.):
    a=np.zeros(1,dtype=DTYPE);a['is_leaf']=1;a['value']=float(v);return a
def stump(left,right,feature=0,threshold=0.):
    a=np.zeros(3,dtype=DTYPE);a[0]['left']=1;a[0]['right']=2;a[0]['feature_idx']=feature;a[0]['num_threshold']=threshold;a[1:]['is_leaf']=1;a[1]['value']=left;a[2]['value']=right;return a
def chain(values,feature=0,thresholds=None):
    n=len(values);ts=list(range(n-1)) if thresholds is None else thresholds
    a=np.zeros(2*n-1,dtype=DTYPE)
    for k in range(n-1):
        a[2*k]['feature_idx']=feature;a[2*k]['num_threshold']=ts[k];a[2*k]['left']=2*k+1;a[2*k]['right']=2*k+2;a[2*k+1]['is_leaf']=1;a[2*k+1]['value']=values[k]
    a[-1]['is_leaf']=1;a[-1]['value']=values[-1];return a
def pack(trees,initial=0.):
    trees=list(trees)+[constant() for _ in range(400-len(trees))]
    return {'initial':np.array([initial],dtype='f8'),'nodes':np.concatenate(trees),'nodes_offsets':np.array([0]+list(np.cumsum([len(t) for t in trees])),dtype='i8'),'raw_left_cat_bitsets':np.zeros((0,8),dtype='u4'),'raw_left_cat_bitsets_offsets':np.zeros(401,dtype='i8'),'binned_left_cat_bitsets':np.zeros((0,8),dtype='u4'),'binned_left_cat_bitsets_offsets':np.zeros(401,dtype='i8')}
def cross_cancellation():return pack([stump(0,1),stump(0,1),stump(0,-1),stump(0,-1)])
def onehot():return pack([chain([float(k==j) for k in range(4)],thresholds=[-1.,0.,1.]) for j in range(4)])
def rounding_counterexample():return pack([constant(2.**53),constant(1.),constant(-2.**53),constant(0.)])
def performance_arrays():
    # Explicit cold gate only; NEVER invoked by the ordinary test suite.
    return pack([chain([((s+k)%17-8)/1024 for k in range(15)],feature=20+s%42,thresholds=list(range(-7,7))) for s in range(400)])
def evaluate(arrays,point):
    a=float(arrays['initial'][0]);nodes=arrays['nodes'];off=arrays['nodes_offsets']
    for start,end in zip(off,off[1:]):
        t=nodes[int(start):int(end)];j=0
        while not t[j]['is_leaf']:j=int(t[j]['left'] if point[int(t[j]['feature_idx'])]<=t[j]['num_threshold'] else t[j]['right'])
        a=a+float(t[j]['value'])
    return a
