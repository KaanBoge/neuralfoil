"""Finite authenticated loader; no I/O or model loading at import."""
from pathlib import Path,PurePosixPath
import hashlib,io,json,sys,types,zipfile,stat,platform,importlib.metadata
import numpy as np
from serving import Serving,COHORTS,QUALIFIED
FEATURE='submission_revision_20260908/work/feature_reproduction/addon/'
ORIGINAL='model_development_20260907_risk_policy/portable/'
PREPARED='model_development_20260907_geometry_frontier/engineering/fast_inference/prepared.py'
sha=lambda b:hashlib.sha256(b).hexdigest()
def safe_name(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or str(p)!=name or '..' in p.parts or '\\' in name or ':' in name:raise ValueError('unsafe path')
def module(name,raw):
    m=types.ModuleType(name);sys.modules[name]=m;exec(compile(raw,name,'exec'),m.__dict__);return m
def arrays(raw,keys):
    # Only explicitly named array members may be materialized.
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        if not set(keys)<=set(z.files):raise ValueError('missing allowed arrays')
        out={k:z[k] for k in keys}
    if any(a.dtype.hasobject for a in out.values()):raise ValueError('object array')
    return out
def authenticate(root,registry):
    root=Path(root);buffers={}
    # Complete finite input authentication before any scientific parser.
    for name,h in registry['files'].items():
        safe_name(name);p=root/name
        if any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('symlink')
        b=p.read_bytes()
        if sha(b)!=h:raise ValueError('input identity '+name)
        buffers[name]=b
    archived={}
    for name,spec in registry['archives'].items():
        safe_name(name);p=root/name
        if any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('symlink')
        b=p.read_bytes()
        if sha(b)!=spec['sha256']:raise ValueError('archive identity')
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            names=z.namelist()
            if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('duplicate archive name')
            for i in z.infolist():
                safe_name(i.filename)
                if i.is_dir() or stat.S_IFMT(i.external_attr>>16) not in (0,stat.S_IFREG) or i.flag_bits&1:raise ValueError('archive file kind')
            m=z.read('manifest.json')
            if sha(m)!=spec['manifest_sha256']:raise ValueError('archive manifest')
            manifest=json.loads(m)
            for member,expected in spec['members'].items():
                if manifest['files'][member]!=expected:raise ValueError('allowlist manifest mismatch')
                v=z.read(member)
                if sha(v)!=expected['sha256'] or len(v)!=expected['bytes']:raise ValueError('allowed member identity')
                archived[('addon/' if 'kl_harm' in name else 'parent/')+member]=v
    return buffers,archived
def load(root,registry):
    b,a=authenticate(root,registry)
    import aerosandbox as asb,neuralfoil
    observed={'python':platform.python_version(),'versions':{k:importlib.metadata.version(k) for k in ['numpy','aerosandbox','neuralfoil','casadi']},'source_sha256':{}}
    for mod in [asb,neuralfoil]:
        folder=Path(mod.__file__).parent
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.suffix in ['.py','.npz']:observed['source_sha256'][mod.__name__+'/'+str(p.relative_to(folder))]=sha(p.read_bytes())
    if observed!=json.loads(b[FEATURE+'expected_runtime.json']):raise ValueError('runtime/source/weight mismatch')
    f=module('bench_feature_math',b[FEATURE+'feature_math.py'])
    prep=module('bench_prepared',b[PREPARED]);original=prep.prepare(json.loads(b[ORIGINAL+'experimental_policies.json']))
    q=module('qualified_numerics',a['parent/code/qualified_numerics.py']);policy=module('bench_policy',a['parent/code/policy.py']);ev=module('bench_evaluator',a['parent/code/evaluator.py'])
    tree_keys=['initial','nodes_offsets','nodes','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets']
    qualified=ev.SequentialHist(arrays(a['parent/trees/final.npz'],tree_keys))
    scalars={}
    for label in QUALIFIED:
        origin='addon' if '_kl_' in label else 'parent'
        s=json.loads(a[f'{origin}/scalars/{label}_final.json'])
        t=s['t']
        if type(t) not in (float,int) or not np.isfinite(t) or not 0<=t<=1:raise ValueError('invalid saved scalar')
        scalars[label]={'t':t} # discard calibration summaries; never recalibrate
    fm=json.loads(b[FEATURE+'manifest.json']);work={};references={}
    feature_keys=['alpha','Re','airfoil','X9','X16','X24','X44','X62','K18','BASE_CD','XLARGE_CD','all_model_CD','all_model_CL']+['ncrit_'+k for k in f.FIELDS]
    for c in COHORTS:
        ref=arrays(b[FEATURE+f'data/{c}.npz'],feature_keys)
        if len(ref['alpha'])!=registry['workload_rows'][c]:raise ValueError('workload count')
        old=arrays(b[ORIGINAL+'inference_references.npz'],[c+'_'+k for k in ['gate','unpenalized_transfer','BASE_CD','X62','all_model_CD']])
        gate=old[c+'_gate'];native=arrays(a[f'parent/native/{c}.npz'],['indices','BASE_CD','core','anchor','gate']+[k+s for k in QUALIFIED[:2] for s in ['', '__strength','__effective_fraction','__intervened']])
        kl=arrays(a[f'addon/predictions/{c}.npz'],['indices']+[k+s for k in QUALIFIED[2:] for s in ['', '__strength','__effective_fraction','__intervened']])
        if gate.dtype!=bool or gate.shape!=ref['alpha'].shape:raise ValueError('physical gate shape')
        for key in ['BASE_CD','X62','all_model_CD']:
            if not np.array_equal(ref[key],old[c+'_'+key]):raise ValueError('original feature bridge')
        if not np.array_equal(native['BASE_CD'],ref['BASE_CD']) or not np.array_equal(native['gate'],gate):raise ValueError('qualified bridge')
        if not np.array_equal(native['indices'],kl['indices']):raise ValueError('index bridge')
        coords={n:b[FEATURE+d['path']].decode(errors='replace') for n,d in fm['coordinates'][c].items()}
        if set(ref['airfoil'])!=set(coords):raise ValueError('coordinate membership')
        work[c]={'alpha':ref['alpha'],'Re':ref['Re'],'airfoil':ref['airfoil'],'gate':gate,'coordinates':coords}
        references[c]={'features':ref,'original':old[c+'_unpenalized_transfer'],'native':native,'kl':kl}
    return Serving(f,asb,original,qualified,policy,q,scalars,work),references,observed

