"""Fixed experimental residual MLP, no import-time data I/O."""
import time,warnings,signal
import numpy as np
from sklearn.neural_network import MLPRegressor

SEEDS=(824,825,826)
def balanced_weights(groups,sources):
    pairs=list(zip(sources.tolist(),groups.tolist()));counts={};members={}
    for s,g in pairs:counts[s,g]=counts.get((s,g),0)+1;members.setdefault(s,set()).add(g)
    w=np.array([1/(counts[p]*len(members[p[0]])) for p in pairs]);return w/w.mean()

def transform(x,center,scale):
    valid=scale>0
    return np.where(valid,np.clip((x-center)/np.where(valid,scale,1),-3.,3.),0.)

def fit(d,idx,seed,timeout_seconds=180):
    if seed not in SEEDS:raise ValueError('Undeclared seed')
    x=np.asarray(d['X62'][idx],dtype=float);base=np.asarray(d['BASE_CD'][idx],dtype=float);y=np.asarray(d['MEAS_CD'][idx],dtype=float)
    if x.shape!=(len(idx),62) or not len(idx) or not np.isfinite(x).all() or not np.isfinite(base).all() or not np.isfinite(y).all() or (base<=0).any():raise ValueError('Invalid training data')
    center=np.median(x,axis=0);q=np.quantile(x,[.05,.95],axis=0);scale=q[1]-q[0]
    rawtarget=(y-base)/base;target=np.clip(rawtarget,-.5,1.)
    w=(1+balanced_weights(d['group'][idx],d['source'][idx]))/2*base**2;w/=w.mean()
    estimator=MLPRegressor(hidden_layer_sizes=(16,),activation='tanh',solver='lbfgs',loss='squared_error',alpha=10,max_iter=1000,max_fun=2000,tol=1e-7,random_state=seed,early_stopping=False)
    started=time.monotonic();records=[]
    def alarm(signum,frame):raise TimeoutError('Fixed 180-second fit resource guard')
    previous=signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,timeout_seconds)
    try:
        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter('always');estimator.fit(transform(x,center,scale),target,sample_weight=w)
    except Exception as error:
        error.fit_diagnostics={'seed':seed,'seconds':time.monotonic()-started,'warnings':[str(r.message) for r in records],'iterations':int(getattr(estimator,'n_iter_',0))}
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    diagnostics={'seed':seed,'seconds':time.monotonic()-started,'iterations':int(estimator.n_iter_),'loss':float(estimator.loss_),
                 'warnings':[{'category':r.category.__name__,'message':str(r.message)} for r in records],
                 'hit_iteration_limit':bool(estimator.n_iter_>=1000),'target_clipped_rows':int((rawtarget!=target).sum()),'constant_columns':int((scale==0).sum()),'train_rows':len(idx)}
    return {'family':'neural62','seed':seed,'center':center,'scale':scale,'model':estimator,'diagnostics':diagnostics}

def predict(model,d,idx):
    x=np.asarray(d['X62'][idx],dtype=float);base=np.asarray(d['BASE_CD'][idx],dtype=float)
    if x.shape!=(len(idx),62) or not np.isfinite(x).all() or not np.isfinite(base).all() or (base<=0).any():raise ValueError('Invalid inference inputs')
    if not len(idx):return np.empty(0)
    raw=model['model'].predict(transform(x,model['center'],model['scale']))
    return np.clip(base*(1+np.clip(raw,-.5,1.)),.5*base,2*base)
