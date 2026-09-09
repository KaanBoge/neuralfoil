"""Finite phase-scoped safe archive reader. Import reads no data."""
import hashlib,io,json,zipfile
from pathlib import Path
import numpy as np

ZIP_SHA='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
MANIFEST_SHA='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
OLD_LABELS=['qualified_structural_harm_001','qualified_generic_harm_001']
NEW_LABELS=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
EXTERNAL=['SG_exposed','W_new_challenge']
def sha(raw):return hashlib.sha256(raw).hexdigest()

class Inputs:
    def __init__(self,path,phase):
        if phase not in ['preflight','calibrate','score','assess']:raise ValueError('phase')
        self.phase=phase;self.events=[];raw=Path(path).read_bytes()
        if sha(raw)!=ZIP_SHA:raise ValueError('archive authentication')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=z.namelist()
            if len(names)!=141 or len(set(names))!=len(names):raise ValueError('archive inventory')
            manifest=z.read('manifest.json')
            if sha(manifest)!=MANIFEST_SHA:raise ValueError('manifest authentication')
            self.manifest=json.loads(manifest);self.buffers={}
            if set(names)!=set(self.manifest['files'])|{'manifest.json'}:raise ValueError('payload inventory')
            for name,record in self.manifest['files'].items():
                value=z.read(name)
                if sha(value)!=record['sha256'] or len(value)!=record['bytes']:raise ValueError('payload hash')
                self.buffers[name]=value
        # JSON metadata only, no outcome-dependent scalar records.
        self.info=self.metadata('inventory.json')
        self.contexts=self.info['contexts'];self.native=self.info['native_contexts']
        if len(self.contexts)!=16 or len(set(self.contexts))!=16 or len(self.native)!=18:raise ValueError('contexts')
    def metadata(self,name):
        allowed=name in ['inventory.json','certificates/STAGE0_CERTIFICATE.json'] or name.startswith('roles/')
        allowed|=self.phase=='calibrate' and name.startswith('scalars/')
        allowed|=self.phase=='assess' and name in ['scoring/schema.json','scoring/panels.json']
        if not allowed:raise ValueError('forbidden JSON phase access: '+name)
        self.events.append({'file':name,'sha256':sha(self.buffers[name]),'operation':'JSON parse'})
        return json.loads(self.buffers[name])
    def array(self,name,keys):
        allowed=set()
        if name.startswith('calibration/') and self.phase in ['preflight','calibrate']:
            allowed={'indices','nf2_row_id','group','BASE_CD','core','anchor','gate'}
            if self.phase=='calibrate':allowed.add('MEAS_CD')
        elif name.startswith('native/') and self.phase in ['preflight','score']:
            allowed={'indices','BASE_CD','core','anchor','gate'}
        elif name=='scoring/frame.npz' and self.phase=='assess':
            with np.load(io.BytesIO(self.buffers[name]),allow_pickle=False) as z:allowed=set(z.files)
        if not keys or not set(keys)<=allowed:raise ValueError('forbidden NPZ phase members')
        result={}
        with np.load(io.BytesIO(self.buffers[name]),allow_pickle=False) as z:
            for key in keys:
                v=z[key]
                if v.dtype.hasobject:raise ValueError('object array')
                result[key]=v
                self.events.append({'file':name,'sha256':sha(self.buffers[name]),'operation':'NPZ member',
                    'member':key,'dtype':str(v.dtype),'shape':list(v.shape),'bytes':int(v.nbytes)})
        return result
    def scoring_arrays(self):
        if self.phase!='assess':raise ValueError('assessment only')
        with np.load(io.BytesIO(self.buffers['scoring/frame.npz']),allow_pickle=False) as z:keys=z.files
        return self.array('scoring/frame.npz',keys)
    def code(self,name):
        if name not in ['code/codec.py','code/policy.py','code/qualified_numerics.py','code/metrics.py','code/frame_codec.py']:
            raise ValueError('code allowlist')
        return self.buffers[name]
