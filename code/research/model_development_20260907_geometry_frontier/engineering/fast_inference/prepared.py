"""Optional immutable prepared risk-policy predictor; NumPy and stdlib only."""
from dataclasses import dataclass
from pathlib import Path
import hashlib,json
import numpy as np

LABELS=('risk_transfer','unpenalized_transfer','risk_group')
MANIFEST_SHA256='706d9604d95b31f5614fc9c768e67bb3c6a84c2b7d8aa1c9f133e03c03397d82'

def numeric(value,name):
    a=np.asarray(value)
    if a.dtype.kind not in 'fiu' or not np.isfinite(a).all():raise ValueError(name+' must be finite numeric data')
    return a.astype(float)

def immutable(a,dtype=None):
    a=np.asarray(a,dtype=dtype)
    return np.frombuffer(a.tobytes(),dtype=a.dtype).reshape(a.shape)

@dataclass(frozen=True,slots=True)
class Tree:
    feature:np.ndarray
    threshold:np.ndarray
    left:np.ndarray
    right:np.ndarray
    leaf:np.ndarray
    value:np.ndarray

@dataclass(frozen=True,slots=True)
class Policy:
    endpoints:np.ndarray
    corners:np.ndarray

@dataclass(frozen=True,slots=True)
class Prepared:
    baseline:float
    trees:tuple
    policies:tuple

    def predict(self,X62,BASE_CD,all_model_CD,gate,label='risk_transfer'):
        if label not in LABELS:raise ValueError('Unknown policy label')
        b=numeric(BASE_CD,'BASE_CD');x=numeric(X62,'X62');a=numeric(all_model_CD,'all_model_CD');g=np.asarray(gate)
        if b.ndim!=1 or x.shape!=(len(b),62) or a.shape!=(len(b),8):raise ValueError('Expected (n,), (n,62), (n,8) inputs')
        if (b<=0).any() or (a<=0).any() or g.dtype!=bool or g.shape!=b.shape:raise ValueError('Positive CD and aligned boolean gate required')
        raw=np.full(len(b),self.baseline,dtype=float)
        for t in self.trees:
            nodes=np.zeros(len(b),dtype=int)
            for _ in range(len(t.leaf)):
                active=np.flatnonzero(~t.leaf[nodes])
                if not len(active):break
                current=nodes[active]
                nodes[active]=np.where(x[active,t.feature[current]]<=t.threshold[current],t.left[current],t.right[current])
            else:raise ValueError('Tree failed to terminate')
            raw+=t.value[nodes]
        c=np.clip(b*(1+np.clip(raw,-.5,1)),.5*b,2*b);c=b+1.*(c-b)
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            f=np.column_stack((np.std(a/b[:,None],axis=1),np.abs(c/b-1)))
        if not np.isfinite(f).all():raise ValueError('Nonfinite features')
        p=self.policies[LABELS.index(label)];e=p.endpoints;span=e[1]-e[0]
        z=np.clip((f-e[0])/np.where(span>0,span,1),0,1);z[:,span==0]=0
        u,v=z.T;phi=np.column_stack(((1-u)*(1-v),(1-u)*v,u*(1-v),u*v))
        strength=np.where(g,phi@p.corners,0.)
        pred=np.where(g,(1-strength)*b+strength*c,b)
        if not np.isfinite(pred).all() or (pred<=0).any():raise ValueError('Invalid output')
        return pred,strength

def prepare(artifact):
    """Validate/copy caller-owned numerical JSON; use load_prepared for authentication."""
    if not isinstance(artifact,dict) or artifact.get('schema')!='experimental-risk-policy-package-v1':raise ValueError('Unknown package schema')
    core=artifact['core']
    if core.get('schema')!='neuralfoil-feature-correction-v1' or core.get('engine')!='relative_hist' or core.get('feature_key')!='X62' or type(core.get('strength')) not in (int,float) or core['strength']!=1:raise ValueError('Expected full-strength X62 histogram')
    hist=core['hist'];baseline=numeric(hist['baseline'],'baseline')
    if hist['features']!=62 or baseline.ndim!=0 or not isinstance(hist['trees'],list) or not hist['trees']:raise ValueError('Invalid histogram')
    trees=[]
    for t in hist['trees']:
        leaf=np.asarray(t['leaf']);n=len(leaf) if leaf.ndim==1 else 0
        if leaf.dtype!=bool or not n:raise ValueError('Invalid tree leaves')
        arrays={}
        for key in ['feature','left','right']:
            a=np.asarray(t[key])
            if a.dtype.kind not in 'iu' or a.shape!=(n,):raise ValueError('Invalid integer array')
            arrays[key]=a
        for key in ['threshold','value']:
            a=numeric(t[key],key)
            if a.shape!=(n,):raise ValueError('Invalid numerical array')
            arrays[key]=a
        f,l,r=[arrays[k] for k in ['feature','left','right']]
        if ((f[~leaf]<0)|(f[~leaf]>=62)).any() or ((l<0)|(l>=n)|(r<0)|(r>=n)).any():raise ValueError('Tree index out of bounds')
        # Iterative tri-color traversal checks all nodes, including unreachable
        # subgraphs, without recursive call-stack limits on untrusted JSON.
        color=np.zeros(n,dtype=np.uint8)
        for root in range(n):
            if color[root]==2:continue
            stack=[(root,False)]
            while stack:
                i,finish=stack.pop()
                if finish:color[i]=2;continue
                if color[i]==1:raise ValueError('Cyclic tree')
                if color[i]==2:continue
                color[i]=1;stack.append((i,True))
                if not leaf[i]:stack.extend([(int(r[i]),False),(int(l[i]),False)])
        trees.append(Tree(immutable(f),immutable(arrays['threshold']),immutable(l),immutable(r),immutable(leaf),immutable(arrays['value'])))
    if set(artifact['policies'])!=set(LABELS):raise ValueError('Expected three policies')
    policies=[]
    for label in LABELS:
        p=artifact['policies'][label]
        if p.get('schema')!='bilinear_half_anchor_harm_v1':raise ValueError('Unknown policy schema')
        e=numeric(p['endpoints'],'endpoints');c=numeric(p['corners'],'corners')
        if e.shape!=(2,2) or (e<0).any() or (e[1]<e[0]).any() or c.shape!=(4,) or ((c<0)|(c>1)).any():raise ValueError('Invalid policy arrays')
        policies.append(Policy(immutable(e),immutable(c)))
    return Prepared(float(baseline),tuple(trees),tuple(policies))

def authenticated_artifact(directory,expected_manifest_sha256=MANIFEST_SHA256):
    directory=Path(directory);raw=(directory/'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_manifest_sha256:raise ValueError('Manifest authentication failed')
    manifest=json.loads(raw)
    for name,expected in manifest['package_hashes'].items():
        if Path(name).name!=name:raise ValueError('Invalid manifest member path')
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:raise ValueError('Package hash mismatch: '+name)
    return json.loads((directory/'experimental_policies.json').read_text()),manifest

def load_prepared(directory,expected_manifest_sha256=MANIFEST_SHA256):
    artifact,_=authenticated_artifact(directory,expected_manifest_sha256)
    return prepare(artifact)
