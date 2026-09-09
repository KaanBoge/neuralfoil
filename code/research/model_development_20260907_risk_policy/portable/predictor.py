"""Standalone NumPy-only feature inference for three experimental risk policies.

Tree traversal adapted from search/portable/portable_models.py; policy arithmetic
from frozen ../risk_policy.py. Source hashes are retained by the export manifest.
No fitting, filesystem access, or external imports occur on import.
"""
import numpy as np

LABELS = ('risk_transfer', 'unpenalized_transfer', 'risk_group')


def numeric(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
        raise ValueError(name + ' must be finite numeric data')
    return a.astype(float)


def validate(artifact):
    if artifact.get('schema') != 'experimental-risk-policy-package-v1':
        raise ValueError('Unknown package schema')
    core = artifact['core']
    if (core.get('schema') != 'neuralfoil-feature-correction-v1' or
        core.get('engine') != 'relative_hist' or core.get('feature_key') != 'X62' or
        type(core.get('strength')) not in (int,float) or core['strength'] != 1):
        raise ValueError('Expected full-strength X62 relative histogram core')
    hist = core['hist']
    if hist['features'] != 62 or numeric(hist['baseline'],'baseline').ndim != 0:
        raise ValueError('Invalid histogram shape')
    if not isinstance(hist['trees'],list) or not hist['trees']:
        raise ValueError('Missing trees')
    for t in hist['trees']:
        leaf=np.asarray(t['leaf'])
        if leaf.dtype != bool or leaf.ndim != 1 or not len(leaf):
            raise ValueError('Invalid tree leaves')
        n=len(leaf)
        for key in ['feature','left','right']:
            a=np.asarray(t[key])
            if a.dtype.kind not in 'iu' or a.shape != (n,):
                raise ValueError('Invalid tree integer array')
        for key in ['threshold','value']:
            if numeric(t[key],key).shape != (n,):
                raise ValueError('Invalid tree numerical array')
        active=~leaf
        f=np.asarray(t['feature']); l=np.asarray(t['left']); r=np.asarray(t['right'])
        if np.any((f[active]<0)|(f[active]>=62)) or np.any((l<0)|(l>=n)|(r<0)|(r>=n)):
            raise ValueError('Tree index out of bounds')
        # Validate termination for every reachable path before any inference.
        visiting=set(); finished=set()
        def visit(i):
            if i in visiting: raise ValueError('Cyclic tree')
            if i in finished: return
            visiting.add(i)
            if not leaf[i]: visit(int(l[i])); visit(int(r[i]))
            visiting.remove(i); finished.add(i)
        visit(0)
    if set(artifact['policies']) != set(LABELS):
        raise ValueError('Expected exactly three policies')
    for p in artifact['policies'].values():
        if p.get('schema') != 'bilinear_half_anchor_harm_v1':
            raise ValueError('Unknown policy schema')
        e=numeric(p['endpoints'],'endpoints'); c=numeric(p['corners'],'corners')
        if e.shape != (2,2) or np.any(e<0) or np.any(e[1]<e[0]):
            raise ValueError('Invalid endpoints')
        if c.shape != (4,) or np.any((c<0)|(c>1)):
            raise ValueError('Invalid corners')
    return artifact


def predict(artifact, X62, BASE_CD, all_model_CD, gate, label='risk_transfer'):
    """Return (CD, applied strength); gate is mandatory and must be boolean.

    Inputs are the unchanged historical X62 convention, not raw coordinates.
    Policy label is an explicit algorithm choice, never an airfoil identity.
    """
    validate(artifact)
    if label not in LABELS: raise ValueError('Unknown policy label')
    b=numeric(BASE_CD,'BASE_CD'); x=numeric(X62,'X62'); a=numeric(all_model_CD,'all_model_CD')
    g=np.asarray(gate)
    if b.ndim != 1 or x.shape != (len(b),62) or a.shape != (len(b),8):
        raise ValueError('Expected (n,), (n,62), (n,8) inputs')
    if np.any(b<=0) or np.any(a<=0) or g.dtype != bool or g.shape != b.shape:
        raise ValueError('Positive CD and aligned boolean gate required')
    hist=artifact['core']['hist']; raw=np.full(len(b),hist['baseline'],dtype=float)
    for t in hist['trees']:
        f=np.asarray(t['feature']); threshold=np.asarray(t['threshold'])
        left=np.asarray(t['left']); right=np.asarray(t['right']); leaf=np.asarray(t['leaf'])
        nodes=np.zeros(len(b),dtype=int)
        for _ in range(len(leaf)):
            active=np.flatnonzero(~leaf[nodes])
            if not len(active): break
            current=nodes[active]
            nodes[active]=np.where(x[active,f[current]]<=threshold[current],left[current],right[current])
        else: raise ValueError('Tree failed to terminate')
        raw+=np.asarray(t['value'])[nodes]
    # Match original helper's bounded relative correction and strength=1 arithmetic.
    c=np.clip(b*(1+np.clip(raw,-.5,1)),.5*b,2*b)
    c=b+1.*(c-b)
    f=np.column_stack((np.std(a/b[:,None],axis=1),np.abs(c/b-1)))
    if not np.isfinite(f).all(): raise ValueError('Nonfinite features')
    p=artifact['policies'][label]; e=np.asarray(p['endpoints']); span=e[1]-e[0]
    z=np.clip((f-e[0])/np.where(span>0,span,1),0,1); z[:,span==0]=0
    u,v=z.T
    phi=np.column_stack(((1-u)*(1-v),(1-u)*v,u*(1-v),u*v))
    strength=np.where(g,phi@np.asarray(p['corners']),0.)
    pred=np.where(g,(1-strength)*b+strength*c,b)
    if not np.isfinite(pred).all() or np.any(pred<=0): raise ValueError('Invalid output')
    return pred,strength
