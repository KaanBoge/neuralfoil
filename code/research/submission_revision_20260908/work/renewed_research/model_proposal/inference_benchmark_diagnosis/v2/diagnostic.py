"""Inert SG-only diagnostic helpers: no data/model access at import."""
import contextlib,hashlib,io,json,os,sys,types,zipfile
from pathlib import Path
import numpy as np

KEYS=('X62','BASE_CD','all_model_CD','gate','CORE_CD','unpenalized_transfer')
OUT_NAMES={'ATTEMPT.json','ACCESS.json','DIAGNOSTICS.json','COMPLETE.json','FAILURE.json'}
CAP=8*2**20
def sha(raw):return hashlib.sha256(raw).hexdigest()
def safe(path):
    p=Path(os.path.abspath(path))
    if any(ord(c)<32 or ord(c)==127 for c in str(p)) or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('unsafe path')
    return p
def read(path,pin,ledger):
    p=safe(path)
    if p.stat().st_size>64*2**20:raise ValueError('input byte cap')
    raw=p.read_bytes()
    if sha(raw)!=pin:raise ValueError('input/source hash mismatch '+str(p))
    ledger.append({'operation':'authenticated bytes','path':str(p),'sha256':pin,'bytes':len(raw)});return raw
def parse(raw,name,ledger):
    value=json.loads(raw);ledger.append({'operation':'JSON parse','identity':name,'sha256':sha(raw)});return value
def save(out,name,obj):
    if name not in OUT_NAMES:raise ValueError('output allowlist')
    raw=json.dumps(obj,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
    used=sum(p.stat().st_size for p in safe(out).iterdir() if p.is_file())
    # Reserve one MiB for the exclusive failure receipt, not an extra cap.
    allowance=CAP if name=='FAILURE.json' else CAP-2**20
    if used+len(raw)>allowance:raise ValueError('output byte cap')
    with safe(out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return sha(raw)
def arrays(raw,ledger,n=242):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len({i.filename for i in infos})!=len(infos) or sum(i.file_size for i in infos)>64*2**20:raise ValueError('NPZ inventory cap/duplicate')
        if any('/' in i.filename or not i.filename.endswith('.npy') for i in infos):raise ValueError('NPZ member names')
    result={}
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        for key in KEYS:
            member='SG_exposed_'+key;value=z[member]
            ledger.append({'operation':'NPZ member materialization','archive_sha256':sha(raw),'member':member,'shape':list(value.shape),'dtype':str(value.dtype)})
            shape=(n,62) if key=='X62' else (n,8) if key=='all_model_CD' else (n,)
            if value.shape!=shape or value.dtype!=(np.dtype(bool) if key=='gate' else np.dtype('float64')):raise ValueError('SG array shape/dtype')
            if not np.isfinite(value).all():raise ValueError('nonfinite input')
            if key in ['BASE_CD','all_model_CD','CORE_CD','unpenalized_transfer'] and (value<=0).any():raise ValueError('nonpositive CD')
            result[key]=value
    return result
def layout(value):
    x=np.asarray(value)
    return {'shape':list(x.shape),'dtype':str(x.dtype),'strides':list(x.strides),'C':bool(x.flags.c_contiguous),'F':bool(x.flags.f_contiguous),'writeable':bool(x.flags.writeable),'sha256_C_value_bytes':sha(x.tobytes(order='C'))}
def compare(x,y):
    x=np.asarray(x);y=np.asarray(y);out={'actual':layout(x),'expected':layout(y)}
    out['same_shape_dtype']=x.shape==y.shape and x.dtype==y.dtype
    if not out['same_shape_dtype']:return out
    out['numerically_equal']=bool(np.array_equal(x,y));out['bitwise_equal']=x.tobytes(order='C')==y.tobytes(order='C')
    if x.dtype!=np.dtype('float64'):return out
    if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('nonfinite comparison')
    bitsx=x.view(np.uint64);bitsy=y.view(np.uint64);indices=np.argwhere(bitsx!=bitsy);diff=[]
    def ordered(v):
        v=int(v);return (~v)&((1<<64)-1) if v>>63 else v|(1<<63)
    for ix in indices:
        t=tuple(ix);a=float(x[t]);b=float(y[t]);diff.append({'index':ix.tolist(),'actual_hex':a.hex(),'expected_hex':b.hex(),'absolute_difference':abs(a-b),'ULPs':abs(ordered(bitsx[t])-ordered(bitsy[t]))})
    out['different_cells']=diff;out['different_count']=len(diff);out['max_abs']=max((d['absolute_difference'] for d in diff),default=0.);out['max_ULPs']=max((d['ULPs'] for d in diff),default=0)
    return out
@contextlib.contextmanager
def modules(buffers,ledger):
    old={name:sys.modules.get(name) for name in buffers};loaded={}
    try:
        for name,(path,raw) in buffers.items():
            m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
            exec(compile(raw,str(path),'exec'),m.__dict__);loaded[name]=m
            ledger.append({'operation':'source buffer execution','path':str(path),'sha256':sha(raw)})
        yield loaded
    finally:
        for name,m in old.items():
            if m is None:sys.modules.pop(name,None)
            else:sys.modules[name]=m
def capture(call,function):
    old=sys.getprofile();values={};layouts={};code=function.__code__
    def profile(frame,event,arg):
        if frame.f_code is code and event=='return':
            for name,value in frame.f_locals.items():
                if name in ['raw','c','f','z','phi','strength','pred','features'] and isinstance(value,np.ndarray):
                    layouts[name]=layout(value);values[name]=value.copy(order='K')
    sys.setprofile(profile)
    try:return call(),values,layouts
    finally:sys.setprofile(old)
def evaluate(d,artifact,mods):
    prepared=mods['sg_prepared'].prepare(artifact);portable=mods['sg_portable'];native=mods['sg_native']
    x,b,a,g=[d[k] for k in ['X62','BASE_CD','all_model_CD','gate']];label='unpenalized_transfer'
    before={k:v.copy(order='K') for k,v in d.items()}
    (p,ps),pc,pl=capture(lambda:prepared.predict(x,b,a,g,label),prepared.predict)
    (o,os),oc,ol=capture(lambda:portable.predict(artifact,x,b,a,g,label),portable.predict)
    (v,vs),vc,vl=capture(lambda:native.predict(artifact['policies'][label],b,d['CORE_CD'],a,g),native.predict)
    comparisons={'prepared_vs_portable_CD':compare(p,o),'prepared_vs_portable_strength':compare(ps,os),
       'prepared_vs_archived_native_CD':compare(p,d[label]),'portable_vs_archived_native_CD':compare(o,d[label]),
       'native_policy_saved_core_vs_archived_CD':compare(v,d[label]),'prepared_core_vs_saved_core':compare(pc['c'],d['CORE_CD']),
       'prepared_vs_native_policy_strength':compare(ps,vs),'prepared_vs_native_policy_features':compare(pc['f'],vc['features'])}
    for key in ['raw','c','f','z','phi']:comparisons['prepared_vs_portable_'+key]=compare(pc[key],oc[key])
    capped=np.clip(b*(1+np.clip(pc['raw'],-.5,1)),.5*b,2*b)
    comparisons['redundant_full_strength_expression']=compare(pc['c'],capped)
    for key in d:
        if not compare(d[key],before[key])['bitwise_equal']:raise ValueError('input mutated')
    for output in [p,o,v]:
        if not compare(output[~g],b[~g])['bitwise_equal']:raise ValueError('fallback changed')
    return {'status':'DIAGNOSTIC_INVENTORY_NOT_NUMERICAL_PASS','comparisons':comparisons,'inputs':{k:layout(v) for k,v in d.items()},'locals_original_layout':{'prepared':pl,'portable':ol,'native':vl},'input_immutability_exact':True,'false_gate_fallback_exact':True}
