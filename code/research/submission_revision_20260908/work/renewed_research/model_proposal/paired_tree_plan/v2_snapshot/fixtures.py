"""Fixed synthetic trees only; no disk data, labels, or experimental features."""
import numpy as np
from support import MEMBERS

DTYPE=np.dtype([('value','f8'),('is_leaf','u1'),('feature_idx','u4'),('num_threshold','f8'),('left','u4'),('right','u4'),('missing_go_to_left','u1'),('is_categorical','u1')])

def performance_arrays():
    trees=[]
    for stage in range(400):
        t=np.zeros(29,dtype=DTYPE)
        for k in range(14):
            t[2*k]['feature_idx']=20+(stage%42)
            t[2*k]['num_threshold']=k-7
            t[2*k]['left']=2*k+1;t[2*k]['right']=2*k+2
            t[2*k+1]['is_leaf']=1;t[2*k+1]['value']=((stage+k)%17-8)/1024
        t[28]['is_leaf']=1;t[28]['value']=((stage+14)%17-8)/1024
        trees.append(t)
    return pack(trees)

def pack(trees):
    return {'initial':np.array([0.],dtype='f8'),'nodes':np.concatenate(trees),
            'nodes_offsets':np.array([0]+list(np.cumsum([len(t) for t in trees])),dtype='i8'),
            'raw_left_cat_bitsets':np.zeros((0,8),dtype='u4'),'binned_left_cat_bitsets':np.zeros((0,8),dtype='u4'),
            'raw_left_cat_bitsets_offsets':np.zeros(401,dtype='i8'),'binned_left_cat_bitsets_offsets':np.zeros(401,dtype='i8')}

def small_arrays(feature=0,threshold=0.):
    trees=[]
    for stage in range(400):
        t=np.zeros(3,dtype=DTYPE);t[0]['feature_idx']=feature;t[0]['num_threshold']=threshold
        t[0]['left']=1;t[0]['right']=2;t[1:]['is_leaf']=1
        t[1]['value']=-1/1024;t[2]['value']=1/1024
        trees.append(t)
    return pack(trees)
