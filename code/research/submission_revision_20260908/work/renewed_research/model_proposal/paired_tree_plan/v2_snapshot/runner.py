"""Explicitly approved, one-shot model-only producer. Import performs no I/O."""
import argparse, datetime, io, json, os, platform, signal, time, zipfile
from pathlib import Path
from fractions import Fraction
import numpy as np
import support as s
import producer

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def large_exclusive(path,obj):
    """Serialize to preserved exclusive partial, then create final hardlink exclusively."""
    p=s.safe_path(path);partial=s.safe_path(str(p)+'.partial')
    if p.exists():raise FileExistsError(str(p))
    total=0
    with partial.open('xb') as f:
        for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(obj):
            raw=chunk.encode();total+=len(raw)
            if total>64*2**20:raise ValueError('certificate byte cap')
            f.write(raw)
        f.flush();os.fsync(f.fileno())
    os.link(partial,p)  # atomic no-overwrite final visibility; partial deliberately retained
    import hashlib
    h=hashlib.sha256()
    with p.open('rb') as f:
        for raw in iter(lambda:f.read(1024*1024),b''):h.update(raw)
    return h.hexdigest(),total

def load_arrays(raw,ledger):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())!=7 or set(z.namelist())!={k+'.npy' for k in s.MEMBERS}:raise ValueError('NPZ inventory')
        if sum(i.file_size for i in z.infolist())>8*2**20:raise ValueError('expanded model cap')
    result={}
    with np.load(io.BytesIO(raw),allow_pickle=False) as a:
        for key in s.MEMBERS:
            value=a[key]
            if value.dtype.hasobject:raise ValueError('object array')
            value.setflags(write=False);result[key]=value
            ledger.append({'kind':'npz_materialize','archive_sha256':s.digest(raw),'member':key,'dtype':str(value.dtype),'shape':list(value.shape),'bytes':value.nbytes})
    return result

def check_approval(approval,registry_sha):
    required={'phase','registry_sha256','model_sha256','domains','seconds','workers','real_execution_authorized'}
    if not required.issubset(approval):raise ValueError('approval fields')
    if (approval['phase']!='paired_tree_producer' or approval['registry_sha256']!=registry_sha or approval['model_sha256']!=s.MODEL_SHA or approval['domains']!=['D','R'] or type(approval['seconds']) is not int or approval['seconds']!=900 or type(approval['workers']) is not int or approval['workers']!=1 or approval['real_execution_authorized'] is not True):raise ValueError('approval scope')

def authenticate(registry,ledger):
    for name,pin in registry['sources'].items():s.read_pinned(s.HERE/name,pin,ledger,'local_source_auth')
    for rel,pin in registry['dependencies'].items():s.read_pinned(s.ROOT/rel,pin,ledger,'dependency_auth')

def named_manifest(manifest):
    name='arrays/tree_31_capped.npz'
    if manifest['files'].get(name)!=s.MODEL_SHA:raise ValueError('named manifest model pin')
    records=[r for r in manifest['trees'] if r.get('context')=='final' and r.get('branch')=='proper']
    expected={'context':'final','branch':'proper','capped':name,'upper_free':'arrays/tree_31_upper_free.npz'}
    if records!=[expected]:raise ValueError('sole final/proper named record')

def same_stage0(cert,old):
    records=[r for r in old['records'] if r['context']=='final']
    if len(records)!=1:raise ValueError('one final Stage0 record')
    r=records[0]
    def legacy(q):return Fraction(int(q['numerator']),int(q['denominator']))
    for key in ('lower','upper'):
        if s.unfraction(cert['stage0'][key])!=legacy(r['range'][key]):raise ValueError('Stage0 range identity')
    if s.unfraction(cert['stage0']['B'])!=legacy(r['B_structural']):raise ValueError('Stage0 B identity')
    if old['accessed_tree_sha256']['arrays/tree_31_capped.npz']!=s.MODEL_SHA:raise ValueError('Stage0 model identity')

def protected_attempt(out,metadata,work,seconds=900):
    """No retry; durable attempted/failure outputs, including SIGALRM timeout."""
    out=s.safe_path(out);out.mkdir(exist_ok=False)
    start=time.monotonic();ledger=[];outputs={};started=utc()
    outputs['ATTEMPT.json']=s.exclusive(out/'ATTEMPT.json',dict(metadata,start_utc=started,python=platform.python_version(),pid=os.getpid()))
    previous=signal.getsignal(signal.SIGALRM)
    def alarm(*_):raise TimeoutError('hard phase guard')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        summary=work(out,ledger,outputs)
        outputs['ACCESS.json']=s.exclusive(out/'ACCESS.json',ledger)
        receipt=dict(metadata,status='COMPLETE',start_utc=started,finish_utc=utc(),elapsed_seconds=time.monotonic()-start,outputs=outputs,summary=summary)
        s.exclusive(out/'COMPLETE.json',receipt)
        return receipt
    except BaseException as exc:
        # Preserve scientific intermediates and every partial before propagating.
        s.exclusive(out/'FAILURE.json',dict(metadata,status='NO_NEW_CERTIFICATE',start_utc=started,finish_utc=utc(),elapsed_seconds=time.monotonic()-start,error=repr(exc),outputs=outputs,access=ledger))
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)

def execute(args):
    regpath=s.HERE/'REGISTRY_v2.json';approvalpath=s.safe_path(args.approval)
    early=[]
    # Approval/schema errors occur before any model access; retain them in attempt wrapper.
    metadata={'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256,'model_sha256':s.MODEL_SHA,'phase':'paired_tree_producer'}
    def work(out,ledger,outputs):
        regraw=s.read_pinned(regpath,args.registry_sha256,ledger,'registry_json');reg=json.loads(regraw)
        apraw=s.read_pinned(approvalpath,args.approval_sha256,ledger,'approval_json');approval=json.loads(apraw)
        check_approval(approval,args.registry_sha256);authenticate(reg,ledger)
        if os.environ.get('OMP_NUM_THREADS')!='1' or os.environ.get('OPENBLAS_NUM_THREADS')!='1':raise ValueError('single-thread environment required')
        deps=s.dependencies(ledger)
        manifest=json.loads(s.read_pinned(s.ROOT/s.MANIFEST,s.MANIFEST_SHA,ledger,'manifest_json'))
        named_manifest(manifest)
        old=json.loads(s.read_pinned(s.ROOT/s.STAGE0,s.STAGE0_SHA,ledger,'Stage0_json'))
        raw=s.read_pinned(s.ROOT/s.MODEL,s.MODEL_SHA,ledger,'model_npz_bytes')
        arrays=load_arrays(raw,ledger);budget=s.Budget(900)
        def checkpoint(domain,n,obj):
            name=f'checkpoint_{domain}_{n:03d}.json';outputs[name]=s.exclusive(out/name,obj)
        cert=producer.construct(arrays,deps,budget,checkpoint)
        same_stage0(cert,old)
        sha,size=large_exclusive(out/'certificate.json',cert);outputs['certificate.json']=sha
        outputs['certificate.json.partial']=sha
        authenticate(reg,ledger)
        s.read_pinned(regpath,args.registry_sha256,ledger,'end_registry_auth')
        s.read_pinned(approvalpath,args.approval_sha256,ledger,'end_approval_auth')
        s.read_pinned(s.ROOT/s.MODEL,s.MODEL_SHA,ledger,'end_model_auth')
        return {'counts':cert['counts'],'estimated_owned_peak_bytes':budget.peak,'memory_measure':'conservative algorithm-owned estimate, NOT RSS','certificate_bytes':size,'model_materializations':1,'fits':0,'features_targets_loaded':0}
    return protected_attempt(args.output,metadata,work)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry-sha256',required=True);p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True);p.add_argument('--output',required=True)
    print(json.dumps(execute(p.parse_args()),sort_keys=True))
