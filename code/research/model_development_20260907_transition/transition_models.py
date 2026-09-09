"""Fixed transition sensitivity models, no fitting or file reads on import."""
import numpy as np
from scipy import sparse
from scipy.optimize import linprog
from sklearn.ensemble import HistGradientBoostingRegressor
import develop_v2 as v2

FAMILIES=['transition_mixed','transition_balanced','transition_simplex','geometry42_mixed','joint62_mixed']


def fit(family,d,idx):
    base,y=d['BASE_CD'][idx],d['MEAS_CD'][idx]
    w=v2.old.balanced_weights(d['group'][idx],d['source'][idx])
    if family!='transition_balanced': w=(1+w)/2
    if family=='transition_simplex':
        x=d['ncrit_CD'][idx]*1e4
        n,p=x.shape
        a=sparse.vstack([sparse.hstack([x,-sparse.eye(n)]),sparse.hstack([-x,-sparse.eye(n)])],format='csr')
        eq=sparse.csr_matrix(np.r_[np.ones(p),np.zeros(n)][None,:])
        result=linprog(np.r_[np.zeros(p),w/w.sum()],A_ub=a,b_ub=np.r_[y*1e4,-y*1e4],A_eq=eq,b_eq=[1.],
            bounds=[(0,1)]*p+[(0,None)]*n,method='highs')
        if not result.success: raise RuntimeError(result.message)
        coef=result.x[:p]
        assert abs(coef.sum()-1)<1e-8 and coef.min()>-1e-8
        return {'family':family,'coef':coef,'objective_drag_counts':float(result.fun)}
    w*=base
    w/=w.mean()
    model=HistGradientBoostingRegressor(loss='absolute_error',max_iter=200,max_leaf_nodes=15,min_samples_leaf=80,
        learning_rate=.05,l2_regularization=1,early_stopping=False,categorical_features=None,random_state=824)
    key={'geometry42_mixed':'X42','joint62_mixed':'X62'}.get(family,'X44')
    model.fit(d[key][idx],np.clip((y-base)/base,-.5,1),sample_weight=w)
    return {'family':family,'model':model,'feature_key':key}


def predict(model,d,idx):
    base=d['BASE_CD'][idx]
    if model['family']=='transition_simplex': pred=d['ncrit_CD'][idx]@model['coef']
    else: pred=v2.correct('relative',model['model'].predict(d[model['feature_key']][idx]),base,1)
    return np.clip(pred,.5*base,2*base)
