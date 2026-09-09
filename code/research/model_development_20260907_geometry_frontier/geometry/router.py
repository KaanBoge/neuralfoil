"""Frozen geometry-RBF simplex routers; no file I/O or model fitting on import."""
import time
import warnings
import numpy as np
from scipy import sparse
from scipy.optimize import linprog, OptimizeWarning

VARIANTS={'geometry4':(4,.5,False),'geometry8':(8,.5,False),
          'geometry_condition4':(4,.5,True),'geometry8_free':(8,2.,False)}


def raw_features(variant,k18,re,alpha):
    k=np.asarray(k18,dtype=float); r=np.asarray(re,dtype=float); a=np.asarray(alpha,dtype=float)
    if k.ndim!=2 or k.shape[1]!=18 or r.shape!=(len(k),) or a.shape!=r.shape:
        raise ValueError('Expected K18(n,18), Re(n), alpha(n)')
    if not np.isfinite(k).all() or not np.isfinite(r).all() or not np.isfinite(a).all() or np.any(r<=0):
        raise ValueError('Finite features and positive Re required')
    return np.column_stack((k,np.log10(r),np.abs(a))) if VARIANTS[variant][2] else k


def transform(model,raw):
    z=(raw-np.asarray(model['median']))/np.asarray(model['scale'])
    z[:,np.asarray(model['constant'],bool)]=0
    return z*np.asarray(model['distance_factors'])


def distances(z,centers):
    return np.sum((z[:,None,:]-centers[None,:,:])**2,axis=2)


def build_router(variant,k18,re,alpha):
    raw=np.unique(raw_features(variant,k18,re,alpha),axis=0)
    count,radius,condition=VARIANTS[variant]
    median=np.median(raw,axis=0); q=np.quantile(raw,[.25,.75],axis=0); iqr=q[1]-q[0]
    factors=np.r_[np.full(18,1/np.sqrt(36)),np.full(2,.5)] if condition else np.full(18,1/np.sqrt(18))
    model={'schema':'geometry-rbf-simplex-v1','variant':variant,'radius':radius,
           'median':median.tolist(),'scale':np.where(iqr>0,iqr,1).tolist(),
           'constant':(iqr==0).tolist(),'distance_factors':factors.tolist()}
    z=transform(model,raw)
    if len(np.unique(z,axis=0))<count: raise ValueError('Insufficient unique effective prototype points')
    chosen=[int(np.argmin(np.sum((z-z.mean(axis=0))**2,axis=1)))]
    nearest=distances(z,z[chosen]).ravel()
    for _ in range(count-1):
        chosen.append(int(np.argmax(nearest)))
        nearest=np.minimum(nearest,distances(z,z[chosen[-1:]]).ravel())
    positive=np.sqrt(nearest[nearest>0]); h=float(np.median(positive)) if len(positive) else 1.
    model.update(prototypes=z[chosen].tolist(),prototype_raw=raw[chosen].tolist(),bandwidth=h,
                 unique_raw_vectors=len(raw),prototype_indices=chosen)
    return model


def basis(model,k18,re,alpha):
    raw=raw_features(model['variant'],k18,re,alpha)
    z=transform(model,raw); d=distances(z,np.asarray(model['prototypes']))
    logits=-d/(2*model['bandwidth']**2); logits-=logits.max(axis=1,keepdims=True)
    phi=np.exp(logits); phi/=phi.sum(axis=1,keepdims=True)
    if not np.isfinite(phi).all(): raise ValueError('Nonfinite routing weights')
    return phi


def predict(model,components,k18,re,alpha,base,gate):
    c=np.asarray(components,dtype=float); b=np.asarray(base,dtype=float); g=np.asarray(gate)
    w=np.asarray(model['corner_weights'],dtype=float)
    if c.shape!=(len(b),len(model['components'])) or g.dtype!=bool or g.shape!=b.shape:
        raise ValueError('Component/boolean gate shape mismatch')
    if not np.isfinite(c).all() or not np.isfinite(b).all() or np.any(c<=0) or np.any(b<=0):
        raise ValueError('Positive finite CD inputs required')
    if not np.isfinite(w).all() or np.any(w<0) or not np.allclose(w.sum(axis=1),1,rtol=0,atol=1e-10):
        raise ValueError('Invalid simplex weights')
    row=basis(model,k18,re,alpha)@w
    pred=np.sum(c*row,axis=1)
    return np.where(g,pred,b)


def lp(*args,**kwargs):
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected.*',category=OptimizeWarning)
        return linprog(*args,method='highs-ipm',options={'threads':1},**kwargs)

def fit_variant(frame, panels, center, model, k18, re, alpha, component_names):
    start = time.monotonic()
    COMPONENTS = component_names
    phi = basis(model, k18, re, alpha)
    core = frame[COMPONENTS].to_numpy()*1e4
    x = np.column_stack([core*phi[:,i,None] for i in range(phi.shape[1])])
    y = frame.measured_CD.to_numpy()*1e4
    n,p = x.shape
    k,b = len(COMPONENTS),phi.shape[1]
    # variables: p corner weights, n absolute errors, p L1 auxiliaries, ratio.
    size = p+n+p+1
    zero = sparse.csr_matrix((n,p+1))
    a = sparse.vstack([sparse.hstack([sparse.csr_matrix(x),-sparse.eye(n),zero]),
                       sparse.hstack([-sparse.csr_matrix(x),-sparse.eye(n),zero])],format="csr")
    rhs = [y,-y]
    constraints = sparse.lil_matrix((len(panels)*2+2*p+b,size))
    panel_info = []
    counter = 0
    for baseline in ["xlarge_CD","mean8_CD"]:
        be = np.abs(frame[baseline].to_numpy()*1e4-y)
        for name,(idx,weights) in panels.items():
            denominator = float(weights@be[idx])
            assert denominator > 0
            constraints[counter,p+idx] = weights/denominator
            constraints[counter,-1] = -1
            panel_info.append((name,baseline,denominator))
            counter += 1
    other_rhs = [0.]*counter
    target = np.tile(center,b)
    for j in range(p):
        constraints[counter,j],constraints[counter,p+n+j] = 1,-1
        other_rhs.append(target[j]);counter += 1
        constraints[counter,j],constraints[counter,p+n+j] = -1,-1
        other_rhs.append(-target[j]);counter += 1
    for corner in range(b):
        constraints[counter,p+n+corner*k:p+n+(corner+1)*k] = 1
        other_rhs.append(model["radius"]);counter += 1
    a = sparse.vstack([a,constraints.tocsr()],format="csr")
    rhs = np.concatenate(rhs+[np.asarray(other_rhs)])
    eq = sparse.lil_matrix((b,size))
    for corner in range(b):eq[corner,corner*k:(corner+1)*k] = 1
    bounds = [(0,1)]*p+[(0,None)]*n+[(0,None)]*p+[(0,None)]
    cost = np.zeros(size);cost[-1] = 1
    first = lp(cost,A_ub=a,b_ub=rhs,A_eq=eq.tocsr(),b_eq=np.ones(b),bounds=bounds)
    assert first.success,first.message
    second_cost = np.zeros(size)
    idx,weights = panels["group_pooled"]
    second_cost[p+idx] = weights
    bounds[-1] = (0,float(first.x[-1])+1e-7)
    second = lp(second_cost,A_ub=a,b_ub=rhs,A_eq=eq.tocsr(),b_eq=np.ones(b),bounds=bounds)
    assert second.success,second.message
    corners = np.maximum(second.x[:p].reshape(b,k),0)
    corners /= corners.sum(axis=1,keepdims=True)
    assert corners.min() >= -1e-8
    np.testing.assert_allclose(corners.sum(axis=1),1,atol=1e-8)
    distances = np.abs(corners-center).sum(axis=1)
    assert distances.max() <= model["radius"]+2e-6
    model.update(corner_weights=corners.tolist(), center_weights=center.tolist(),
                 components=COMPONENTS, corner_l1_distances=distances.tolist())
    pred = predict(model,frame[COMPONENTS].to_numpy(),k18,re,alpha,
                   frame.mean8_CD.to_numpy(),np.ones(len(frame),bool))*1e4
    np.testing.assert_allclose(pred,x@second.x[:p],atol=1e-9,rtol=1e-12)
    error = np.abs(pred-y)
    scores=[]
    for name,baseline,denominator in panel_info:
        idx,weights=panels[name]
        scores.append({"panel":name,"baseline":baseline,"actual_ratio":float(weights@error[idx]/denominator)})
    actual=max(s["actual_ratio"] for s in scores)
    violation=float(np.max(a@second.x-rhs))
    assert actual <= first.x[-1]+1e-7+2e-6 and actual >= first.x[-1]-2e-6
    assert violation < 2e-6
    model.update(first_optimal_ratio=float(first.x[-1]),actual_worst_training_ratio=actual,
                 maximum_lp_constraint_violation=violation,training_panels=scores,
                 seconds=time.monotonic()-start,solver_iterations=[int(first.nit),int(second.nit)])
    return model
