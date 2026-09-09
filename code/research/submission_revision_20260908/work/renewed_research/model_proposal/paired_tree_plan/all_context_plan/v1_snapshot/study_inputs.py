"""Phase-scoped safe parent/add-on buffers. No outcome access on import."""
import contextlib,io,json,sys,types,zipfile
from pathlib import PurePosixPath
import numpy as np
import pandas as pd
import adapter as a

PARENT='model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
PARENT_SHA='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
PARENT_MANIFEST='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
ADDON='model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip'
ADDON_SHA='45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b'
ADDON_MANIFEST='dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d'
LABELS=['qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001']
OLD_KL=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
OLD_H=['qualified_structural_harm_001','qualified_generic_harm_001']
EXT=['SG_exposed','W_new_challenge']
KEYS=['indices','BASE_CD','core','anchor','gate']
OLD_REFS=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half',OLD_H[1],OLD_H[0],OLD_KL[1]]
REFS=OLD_REFS+[OLD_KL[0],LABELS[0]]

def archive(path,pin,manifest_pin,ledger):
    raw=a.read(path,pin,ledger,'archive bytes including unparsed labels')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist()
        if len(set(names))!=len(names) or sum(i.file_size for i in z.infolist())>256*2**20:raise ValueError('archive size/duplicates')
        for n in names:
            p=PurePosixPath(n)
            if p.is_absolute() or '..' in p.parts or any(ord(c)<32 for c in n):raise ValueError('archive name')
        mr=z.read('manifest.json')
        if a.sha(mr)!=manifest_pin:raise ValueError('inner manifest identity')
        manifest=a.parse(mr,ledger,'archive manifest')
        if set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('manifest inventory')
        result={}
        for n,r in manifest['files'].items():
            b=z.read(n)
            if a.sha(b)!=r['sha256'] or len(b)!=r['bytes']:raise ValueError('payload identity')
            result[n]=b
    ledger.append({'operation':'archive payload byte authentication only','sha256':pin,'payloads':len(result),'no_array_materialization':True})
    return result

class Reader:
    def __init__(self,buffers,phase,origin,ledger):
        if phase not in ['preflight','calibrate','score','assess']:raise ValueError('phase')
        self.buffers=buffers;self.phase=phase;self.origin=origin;self.ledger=ledger;self.pins={n:a.sha(v) for n,v in buffers.items()}
    def raw(self,name,operation):
        b=self.buffers[name]
        if a.sha(b)!=self.pins[name]:raise ValueError('buffer mutation')
        self.ledger.append({'origin':self.origin,'member':name,'sha256':self.pins[name],'operation':operation});return b
    def json(self,name):
        allowed=name in ['inventory.json','PARENT_REQUIREMENTS.json','certificates/STAGE0_CERTIFICATE.json'] or name.startswith('roles/')
        allowed|=self.phase=='calibrate' and name.startswith('scalars/')
        allowed|=self.phase=='assess' and name in ['scoring/schema.json','scoring/panels.json']
        if not allowed:raise ValueError('forbidden JSON phase member')
        return json.loads(self.raw(name,'JSON parse'))
    def csv(self,name):
        if self.phase!='assess' or not name.startswith(('prediction_csv/','expected/')):raise ValueError('CSV only assessment')
        return pd.read_csv(io.BytesIO(self.raw(name,'pandas.read_csv')),low_memory=False)
    def arrays(self,name,keys=None):
        allowed=set()
        if name.startswith('calibration/') and self.phase in ['preflight','calibrate']:
            allowed=set(KEYS+['group','nf2_row_id'])
            if self.phase=='calibrate':allowed.add('MEAS_CD')
        elif name.startswith('native/') and self.phase in ['preflight','score']:allowed=set(KEYS)
        elif name=='scoring/frame.npz' and self.phase=='assess':
            with np.load(io.BytesIO(self.buffers[name]),allow_pickle=False) as z:allowed=set(z.files)
        if keys is None:keys=list(allowed) if name=='scoring/frame.npz' else []
        if not keys or len(set(keys))!=len(keys) or not set(keys)<=allowed:raise ValueError('forbidden NPZ materialization')
        raw=self.raw(name,'NPZ open');result={}
        with np.load(io.BytesIO(raw),allow_pickle=False) as z:
            for key in keys:
                v=z[key]
                if v.dtype.hasobject:raise ValueError('object array')
                result[key]=v;self.ledger.append({'origin':self.origin,'file':name,'operation':'NPZ materialization','member':key,'sha256':a.sha(raw),'shape':list(v.shape),'dtype':str(v.dtype)})
        return result
    def code(self,name):
        if name not in {'code/qualified_numerics.py','code/codec.py','code/policy.py','code/exact_kl.py','code/adapter.py','code/frame_codec.py','code/overlay.py','code/metrics.py'}:raise ValueError('code allowlist')
        return self.raw(name,'source execution')

@contextlib.contextmanager
def engines(reg,parent,addon,ledger):
    folder=a.ROOT/'model_proposal/kl_bound_study/portable_plan'
    specs={n:(folder/(n+'.py'),reg['external_sources']['model_proposal/kl_bound_study/portable_plan/'+n+'.py']) for n in ['integrity','shared']}
    names=['qualified_numerics','codec','parent_policy','exact_kl','kl_adapter','frame_codec','typed_overlay','metrics']
    old={n:sys.modules.get(n) for n in names}
    try:
        with a.modules(specs,ledger) as m:yield (*m['shared'].engines(parent,addon),m['shared'])
    finally:
        for n,v in old.items():
            if v is None:sys.modules.pop(n,None)
            else:sys.modules[n]=v

def schema(z):
    n=len(z['BASE_CD'])
    if any(z[k].shape!=(n,) for k in KEYS) or z['gate'].dtype!=bool or z['indices'].dtype.kind not in 'iu':raise ValueError('native schema')
    if len(set(z['indices']))!=n:raise ValueError('duplicate index')
    for k in ['BASE_CD','core','anchor']:
        if z[k].dtype!=np.float64 or not np.isfinite(z[k]).all() or (z[k]<=0).any():raise ValueError('positive finite float64')
    for k in ['core','anchor']:np.testing.assert_array_equal(z[k][~z['gate']],z['BASE_CD'][~z['gate']])

def verify_roles(role):
    for suffix in ['groups','indices']:
        sets=[]
        for name in ['proper','calibration','test']:
            vals=role[name+'_'+suffix]
            if len(vals)!=len(set(vals)):raise ValueError('duplicate role member')
            sets.append(set(vals))
        if any(sets[i]&sets[j] for i,j in [(0,1),(0,2),(1,2)]):raise ValueError('role overlap')

def typed_overlay(frame,predictions,labels):
    original=frame.copy(deep=True)
    if set(predictions)!=set(frame.split.unique()):raise ValueError('split inventory')
    for split in frame.split.unique():
        f=predictions[split];mask=frame.split.eq(split);old=frame.loc[mask]
        if len(old)!=len(f):raise ValueError('split length')
        if split not in EXT:
            if f.nf2_row_id.duplicated().any() or old.nf2_row_id.duplicated().any() or set(f.nf2_row_id)!=set(old.nf2_row_id):raise ValueError('row identities')
            f=f.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(f['indices'],np.arange(len(f)))
        np.testing.assert_allclose(f.BASE_CD,old.mean8_CD,rtol=0,atol=1e-13)
        for label in labels:
            for key in [label,label+'__effective_fraction',label+'__strength',label+'__intervened']:
                frame.loc[mask,key]=f[key].to_numpy()
    pd.testing.assert_frame_equal(frame[original.columns],original,check_exact=True)
    return frame
