"""NumPy-only feature-level retrospective union research predictor."""
from numbers import Real
import numpy as np

KEYS=['union_component__simplex8_re_l1__1','union_component__capacity__hist62_regularized__1',
      'union_component__capacity__extra62_mixed__1','union_component__capacity__extra24_mixed__1']

def validate_weights(weights):
    if not isinstance(weights,dict) or set(weights)!=set(KEYS):raise ValueError('Wrong component registry')
    if any(not isinstance(v,Real) or isinstance(v,(bool,np.bool_)) for v in weights.values()):raise ValueError('Real numeric weights required')
    w=np.array([weights[k] for k in KEYS],dtype=float)
    if not np.isfinite(w).all() or (w<0).any() or abs(w.sum()-1)>1e-10:raise ValueError('Finite nonnegative simplex weights required')

def _tree(tree,x):
    feature=np.asarray(tree['feature'],dtype=int);threshold=np.asarray(tree['threshold'],dtype=float)
    left=np.asarray(tree['left'],dtype=int);right=np.asarray(tree['right'],dtype=int)
    leaf=np.asarray(tree['leaf'],dtype=bool);value=np.asarray(tree['value'],dtype=float)
    nodes=np.zeros(len(x),dtype=int)
    for _ in range(len(leaf)):
        rows=np.flatnonzero(~leaf[nodes])
        if not len(rows):break
        at=nodes[rows];nodes[rows]=np.where(x[rows,feature[at]]<=threshold[at],left[at],right[at])
    else:raise ValueError('Malformed nonterminating tree')
    return value[nodes]

def _hist(spec,x):
    result=np.full(len(x),spec['baseline'],dtype=float)
    for tree in spec['trees']:result+=_tree(tree,x)
    return result

def _forest(spec,x):
    # sklearn forest validation casts the feature matrix to float32 BEFORE traversal.
    with np.errstate(over='ignore'):x32=x.astype(np.float32)
    if not np.isfinite(x32).all():raise ValueError('Features overflow float32 forest input')
    result=np.zeros(len(x),dtype=float)
    for tree in spec['trees']:result+=_tree(tree,x32)
    return result/len(spec['trees'])

def predict(artifact,features,inference_gate,return_components=False):
    if artifact.get('schema')!='retrospective-neuralfoil-union-v1':raise ValueError('Unsupported schema')
    weights=artifact['weights'];validate_weights(weights)
    base=np.asarray(features['BASE_CD'],dtype=float);gate=np.asarray(inference_gate)
    if base.ndim!=1 or not np.isfinite(base).all() or (base<=0).any():raise ValueError('Finite positive BASE_CD vector required')
    if gate.dtype!=bool or gate.shape!=base.shape:raise ValueError('Explicit boolean gate vector required')
    n=len(base);arrays={k:np.asarray(features[k],dtype=float) for k in ['X62','all_model_CD','Re']}
    for k,shape in [('X62',(n,62)),('all_model_CD',(n,8)),('Re',(n,))]:
        if arrays[k].shape!=shape or not np.isfinite(arrays[k]).all():raise ValueError('Invalid '+k+' shape/values')
    if (arrays['all_model_CD']<=0).any() or (arrays['Re']<=0).any():raise ValueError('Positive core CD and Re required')
    lo,hi=artifact['simplex']['endpoints'];t=np.clip((np.log10(arrays['Re'])-lo)/max(hi-lo,1e-12),0,1)
    core=arrays['all_model_CD']*1e4;design=np.column_stack([core*(1-t[:,None]),core*t[:,None]])
    simplex=np.clip(design@np.asarray(artifact['simplex']['coef'])/1e4,.5*base,2*base)
    def corrected(raw):return np.clip(base*(1+np.clip(raw,-.5,1)),.5*base,2*base)
    parts={KEYS[0]:simplex,KEYS[1]:corrected(_hist(artifact['hist62'],arrays['X62'])),
           KEYS[2]:corrected(_forest(artifact['extra62'],arrays['X62'])),
           KEYS[3]:corrected(_forest(artifact['extra24'],arrays['X62'][:,:24]))}
    result=np.where(gate,sum(weights[k]*parts[k] for k in KEYS),base)
    if not np.isfinite(result).all() or (result<=0).any():raise ValueError('Invalid result')
    if return_components:return result,{k:np.where(gate,v,base) for k,v in parts.items()}
    return result
