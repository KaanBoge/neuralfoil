"""Two fixed training-only smooth interaction models; no import-time I/O."""
import warnings
import numpy as np
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import QuantileRegressor
from scipy.optimize import OptimizeWarning

FAMILIES=['kernel24_l1','kernel62_l1']

def balanced_weights(groups,sources):
    pairs=list(zip(sources.tolist(),groups.tolist()));counts={};members={}
    for s,g in pairs:
        counts[s,g]=counts.get((s,g),0)+1;members.setdefault(s,set()).add(g)
    w=np.array([1/(counts[p]*len(members[p[0]])) for p in pairs]);return w/w.mean()

def transform(x,center,scale):
    return np.clip((x-center)/scale,-3.,3.)

def fit(family,d,idx):
    if family not in FAMILIES:raise ValueError(family)
    key='X24' if family=='kernel24_l1' else 'X62'
    x=np.asarray(d[key][idx],dtype=float);base=np.asarray(d['BASE_CD'][idx]);y=np.asarray(d['MEAS_CD'][idx])
    if len(x)<128 or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(base).all() or not (base>0).all():raise ValueError('Invalid training inputs')
    center=np.median(x,axis=0);q=np.quantile(x,[.05,.95],axis=0);scale=q[1]-q[0];scale=np.where(scale>0,scale,1.)
    kernel=Nystroem(kernel='rbf',gamma=3/x.shape[1],n_components=128,random_state=824,n_jobs=1)
    z=kernel.fit_transform(transform(x,center,scale))
    target=np.clip((y-base)/base,-.5,1.)
    w=(1+balanced_weights(d['group'][idx],d['source'][idx]))/2*base;w/=w.mean()
    estimator=QuantileRegressor(quantile=.5,alpha=1e-5,fit_intercept=True,solver='highs',solver_options={'threads':1})
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',category=OptimizeWarning,message='Unrecognized options detected')
        estimator.fit(z,target,sample_weight=w)
    return {'family':family,'feature_key':key,'center':center,'scale':scale,'kernel':kernel,'model':estimator}

def predict(model,d,idx):
    x=np.asarray(d[model['feature_key']][idx],dtype=float);base=np.asarray(d['BASE_CD'][idx])
    if not np.isfinite(x).all() or not np.isfinite(base).all() or not (base>0).all():raise ValueError('Invalid inference inputs')
    if not len(idx):return np.empty(0)
    raw=model['model'].predict(model['kernel'].transform(transform(x,model['center'],model['scale'])))
    pred=base*(1+np.clip(raw,-.5,1.))
    return np.clip(pred,.5*base,2*base)
