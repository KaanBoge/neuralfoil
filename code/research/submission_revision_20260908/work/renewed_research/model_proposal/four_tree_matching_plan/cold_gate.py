"""Source-only fixed cold gate driver. Requires root approval; NOT run at import.

Each scientific component runs once in a fresh child process. No real NPZ ever
opened: both children build the one prescribed synthetic400x15 tree mapping.
"""
import argparse,hashlib,json,os,selectors,signal,subprocess,sys,time,types
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
FIXTURE_SHA=hashlib.sha256(b'fixed-four-tree400x15-allpairs-v1').hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def context(regsha):
    ledger=[]
    def raw(path,pin):
        path=Path(path)
        if any(p.is_symlink() for p in (path,*path.parents)) or path.stat().st_size>2**20:raise ValueError('source/metadata path cap')
        b=path.read_bytes()
        if hashlib.sha256(b).hexdigest()!=pin:raise ValueError('source/metadata pin')
        ledger.append({'operation':'source_or_metadata_bytes','path':str(path),'sha256':pin,'bytes':len(b)});return b
    regraw=raw(HERE/'REGISTRY_SOURCE_V1.json',regsha);reg=json.loads(regraw)
    sources={n:raw(HERE/n,pin) for n,pin in reg['sources'].items()}
    if sources['cold_gate.py']!=Path(__file__).read_bytes():raise ValueError('executing gate source')
    external={n:raw(ROOT/e['path'],e['sha256']) for n,e in reg['checker_sources'].items()}
    def mod(name,b,path):
        m=types.ModuleType(name);m.__file__=str(path);exec(compile(b,str(path),'exec'),m.__dict__);return m
    s=mod('cold_authenticated_io',sources['io_support.py'],HERE/'io_support.py')
    return reg,sources,external,s,ledger,mod
def approval(a,regsha,checksha):
    expected={'phase':'four_tree_fixed_cold_gate','registry_sha256':regsha,'checker_registry_sha256':checksha,'fixture_sha256':FIXTURE_SHA,'producer_seconds':120,'checker_seconds':120,'workers':1,'producer_owned_cap':128*2**20,'checker_owned_cap':256*2**20,'aggregate_output_cap':64*2**20,'synthetic_execution_authorized':True,'actual_model_execution_authorized':False}
    if type(a)!=dict or set(a)!=set(expected) or any(type(a[k]) is not type(v) or a[k]!=v for k,v in expected.items()):raise ValueError('exact cold root approval')
def checker_registry(args,reg,s,ledger):
    path=ROOT/'uncertainty_review/range_bound_feasibility/four_tree_matching/CHECKER_SOURCE_REGISTRY_V1.json'
    r=s.parse(s.pinned(path,args.checker_registry_sha256,ledger),ledger,'checker registry')
    if set(r)!={'schema','model_sha256','sources','producer_registry_sha256'} or r['schema']!='FOUR_TREE_CHECKER_SOURCE_REGISTRY_V1' or r['model_sha256']!=reg['model_sha256'] or r['producer_registry_sha256']!=args.registry_sha256 or r['sources']!=reg['checker_sources']:raise ValueError('exact dual registry chain')
    return r
def hash_only(path,pin,ledger):
    path=Path(path)
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('hash-only safe path')
    h=hashlib.sha256();n=0
    with path.open('rb') as f:
        while b:=f.read(65536):h.update(b);n+=len(b)
    if h.hexdigest()!=pin:raise ValueError('accepted output changed')
    ledger.append({'operation':'streaming hash only','path':str(path),'sha256':pin,'bytes':n})
def verify_child(root,phase,pin,s,ledger):
    r=s.parse(s.pinned(root/phase/'COMPLETE.json',pin,ledger),ledger,phase+' accepted COMPLETE')
    if r['status']!='COMPLETE' or (root/phase/'FAILURE.json').exists():raise ValueError('child not complete')
    for n,h in r['outputs'].items():
        if Path(n).name!=n:raise ValueError('flat child output')
        hash_only(root/phase/n,h,ledger)
    return r
def deep_owned(v,seen=None):
    """Retained reachable graph diagnostic, NOT transient peak or RSS."""
    from fractions import Fraction
    import numpy as np
    if seen is None:seen=set()
    if id(v) in seen:return 0
    seen.add(id(v));n=sys.getsizeof(v)
    if isinstance(v,dict):n+=sum(deep_owned(k,seen)+deep_owned(x,seen) for k,x in v.items())
    elif isinstance(v,(tuple,list)):n+=sum(deep_owned(x,seen) for x in v)
    elif isinstance(v,Fraction):n+=deep_owned(v.numerator,seen)+deep_owned(v.denominator,seen)
    elif isinstance(v,np.ndarray) and v.base is not None:n+=deep_owned(v.base,seen)
    return n
def execute_child(args):
    started=time.monotonic();reg,sources,external,s,ledger,mod=context(args.registry_sha256)
    checker_registry(args,reg,s,ledger)
    a=s.parse(s.pinned(HERE/'ROOT_COLD_GATE_APPROVAL.json',args.approval_sha256,ledger),ledger,'cold approval');approval(a,args.registry_sha256,args.checker_registry_sha256)
    if any(os.environ.get(k)!='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')):raise ValueError('single thread child')
    root=HERE/'cold_attempt_1';token=s.parse(s.pinned(root/'TOKEN.json',args.token_sha256,ledger),ledger,'parent token')
    if token!={'registry_sha256':args.registry_sha256,'checker_registry_sha256':args.checker_registry_sha256,'approval_sha256':args.approval_sha256,'parent_pid':os.getppid(),'fixture_sha256':FIXTURE_SHA}:raise ValueError('owned fresh child token')
    store=s.Store(root/args.child,started+120,budget_root=root)
    meta={'phase':args.child,'start_utc':utc(),'registry_sha256':args.registry_sha256,'checker_registry_sha256':args.checker_registry_sha256,'approval_sha256':args.approval_sha256,'fixture_sha256':FIXTURE_SHA,'pid':os.getpid(),'parent_pid':os.getppid()}
    try:
        store.write_json('ATTEMPT.json',meta)
        fixtures=mod('cold_fixed_fixtures',sources['fixtures.py'],HERE/'fixtures.py');arrays=fixtures.performance_arrays()
        if args.child=='producer':
            p=mod('cold_fixed_producer',sources['producer.py'],HERE/'producer.py');b=p.Budget(120);b.started=started
            cert=p.construct(arrays,b,model_sha=FIXTURE_SHA,source_bytes=sum(map(len,sources.values())),input_bytes=0)
            if cert['counts']['pair_classifications']!=135000 or cert['counts']['feasible_pairs']!=135000:raise ValueError('full allfeasible fixed synthetic support')
            retained=deep_owned({'arrays':arrays,'certificate':cert,'sources':sources,'external_sources':external})
            if retained>b.peak:raise MemoryError('retained-owned diagnostic exceeds conservative estimate')
            store.write_json('certificate.json',cert)
            summary={'counts':cert['counts'],'owned_estimate':b.peak,'deep_owned_retained_bytes':retained,'deep_owned_scope':'retained reachable graph only; not peak/RSS','certificate_sha256':store.outputs['certificate.json']}
        else:
            pc=s.parse(s.pinned(root/'producer/COMPLETE.json',args.producer_complete_sha256,ledger),ledger,'producer complete')
            if pc['status']!='COMPLETE' or pc['registry_sha256']!=args.registry_sha256 or pc['approval_sha256']!=args.approval_sha256 or (root/'producer/FAILURE.json').exists():raise ValueError('fixed producer predecessor')
            for n,pin in pc['outputs'].items():
                if Path(n).name!=n:raise ValueError('producer output name')
                # Certificate buffers must be read once below, no hidden copies.
                if n not in ['certificate.json','certificate.json.partial']:s.pinned(root/'producer'/n,pin,ledger,64*2**20)
            cr=s.pinned(root/'producer/certificate.json',pc['outputs']['certificate.json'],ledger,64*2**20)
            checker=mod('cold_independent_checker',external['checker'],ROOT/reg['checker_sources']['checker']['path'])
            sourcebytes=sum(map(len,sources.values()))+sum(map(len,external.values()))
            cert,allocation=checker.parse_certificate(cr,array_bytes=sum(v.nbytes for v in arrays.values()),source_bytes=sourcebytes)
            ledger.append({'operation':'bounded synthetic certificate JSON parse','bytes':len(cr),'allocation':allocation})
            estimate=checker.owned_estimate(sum(v.nbytes for v in arrays.values()),sourcebytes,len(cr),allocation)
            verified=checker.check(cert,arrays,deadline=started+120,expected_model_sha=FIXTURE_SHA,source_bytes=sourcebytes,input_bytes=len(cr),parsed_bytes=allocation)
            if verified['counts']['pair_classifications']!=135000 or verified['counts']['feasible_pairs']!=135000:raise ValueError('complete135k replay')
            retained=deep_owned({'arrays':arrays,'certificate':cert,'certificate_bytes':cr,'sources':sources,'external_sources':external,'verified':verified})
            if retained>estimate:raise MemoryError('checker retained-owned diagnostic exceeds estimate')
            store.write_json('REPLAY.json',verified)
            summary={'counts':verified['counts'],'owned_estimate':estimate,'deep_owned_retained_bytes':retained,'deep_owned_scope':'retained reachable graph only; not peak/RSS','certificate_sha256':pc['outputs']['certificate.json'],'producer_complete_sha256':args.producer_complete_sha256}
        # Recheck source/approval buffers, then all accepted child outputs.
        context(args.registry_sha256);checker_registry(args,reg,s,ledger);s.pinned(HERE/'ROOT_COLD_GATE_APPROVAL.json',args.approval_sha256,ledger);store.verify_outputs(ledger)
        if args.child=='checker':verify_child(root,'producer',args.producer_complete_sha256,s,ledger)
        store.write_json('ACCESS.json',ledger)
        seconds=time.monotonic()-started
        if seconds>=120:raise TimeoutError('complete cold phase deadline')
        store.write_json('COMPLETE.json',dict(meta,status='COMPLETE',finish_utc=utc(),seconds=seconds,outputs=dict(store.outputs),summary=summary))
    except BaseException as exc:
        store.write_json('FAILURE.json',dict(meta,status='FAIL_FIXED_COLD_GATE',error=repr(exc)[:4096],seconds=time.monotonic()-started,accepted_outputs=dict(store.outputs)),emergency=True);raise
def run_child(command,root,name,seconds=120):
    """Only the directly owned process group; no arbitrary process matching."""
    logs=(root/(name+'.stdout.txt'),root/(name+'.stderr.txt'))
    started=time.monotonic()
    with logs[0].open('xb') as out,logs[1].open('xb') as err:
        child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
        selector=selectors.DefaultSelector()
        selector.register(child.stdout,selectors.EVENT_READ,out);selector.register(child.stderr,selectors.EVENT_READ,err)
        try:
            while selector.get_map() or child.poll() is None:
                if time.monotonic()-started>=seconds:raise TimeoutError('cold child wall limit')
                for key,_ in selector.select(.05):
                    chunk=os.read(key.fd,16384)
                    if not chunk:selector.unregister(key.fileobj);key.fileobj.close();continue
                    used=sum(x.stat().st_size for x in root.rglob('*') if x.is_file())
                    if used+len(chunk)>64*2**20-2**20:raise OSError('cold log prewrite output guard')
                    key.data.write(chunk);key.data.flush()
                used=sum(x.stat().st_size for x in root.rglob('*') if x.is_file())
                if used>64*2**20-2**20:raise OSError('cold aggregate output guard')
            code=child.wait()
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGKILL);child.wait()
            raise
        finally:
            selector.close()
            for stream in (child.stdout,child.stderr):stream.close()
            out.flush();err.flush();os.fsync(out.fileno());os.fsync(err.fileno())
    if time.monotonic()-started>seconds:raise TimeoutError('cold post-exit wall limit')
    if code!=0:raise RuntimeError('cold child failure: '+name)
    return time.monotonic()-started
def execute_parent(args):
    started=time.monotonic();reg,sources,external,s,ledger,mod=context(args.registry_sha256)
    checker_registry(args,reg,s,ledger)
    ap=s.parse(s.pinned(HERE/'ROOT_COLD_GATE_APPROVAL.json',args.approval_sha256,ledger),ledger,'root cold approval');approval(ap,args.registry_sha256,args.checker_registry_sha256)
    root=HERE/'cold_attempt_1';store=s.Store(root,started+250)
    meta={'registry_sha256':args.registry_sha256,'checker_registry_sha256':args.checker_registry_sha256,'approval_sha256':args.approval_sha256,'fixture_sha256':FIXTURE_SHA,'start_utc':utc(),'actual_model_access':False}
    try:
        store.write_json('ATTEMPT.json',meta);token={'registry_sha256':args.registry_sha256,'checker_registry_sha256':args.checker_registry_sha256,'approval_sha256':args.approval_sha256,'parent_pid':os.getpid(),'fixture_sha256':FIXTURE_SHA};th,_=store.write_json('TOKEN.json',token)
        summaries={};pc=None
        for phase in ['producer','checker']:
            command=[sys.executable,'-B',str(HERE/'cold_gate.py'),'--registry-sha256',args.registry_sha256,'--checker-registry-sha256',args.checker_registry_sha256,'--approval-sha256',args.approval_sha256,'--child',phase,'--token-sha256',th]
            if phase=='checker':command+=['--producer-complete-sha256',pc]
            elapsed=run_child(command,root,phase)
            raw=(root/phase/'COMPLETE.json').read_bytes();pin=s.digest(raw);receipt=s.parse(raw,ledger,phase+' COMPLETE')
            if receipt['status']!='COMPLETE' or receipt['registry_sha256']!=args.registry_sha256 or receipt['checker_registry_sha256']!=args.checker_registry_sha256 or receipt['approval_sha256']!=args.approval_sha256 or (root/phase/'FAILURE.json').exists():raise ValueError('accepted child completion')
            for suffix in ['stdout.txt','stderr.txt']:
                path=root/(phase+'.'+suffix);store.outputs[path.name]=s.digest(path.read_bytes())
            if phase=='producer':pc=pin
            summaries[phase]={'seconds':elapsed,'owned_estimate':receipt['summary']['owned_estimate'],'deep_owned_retained_bytes':receipt['summary']['deep_owned_retained_bytes'],'complete_sha256':pin,'logical_output_bytes':sum(x.stat().st_size for x in (root/phase).rglob('*') if x.is_file())}
        context(args.registry_sha256);checker_registry(args,reg,s,ledger);s.pinned(HERE/'ROOT_COLD_GATE_APPROVAL.json',args.approval_sha256,ledger);store.check()
        for phase,v in summaries.items():verify_child(root,phase,v['complete_sha256'],s,ledger)
        store.verify_outputs(ledger)
        store.write_json('ACCESS.json',ledger)
        store.write_json('COMPLETE.json',dict(meta,status='PASS_FIXED_135000_GATE',pair_classifications=135000,finish_utc=utc(),**summaries,outputs=dict(store.outputs)))
    except BaseException as exc:
        store.write_json('FAILURE.json',dict(meta,status='FAIL_FIXED_COLD_GATE',error=repr(exc)[:4096],seconds=time.monotonic()-started),emergency=True);raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry-sha256',required=True);p.add_argument('--checker-registry-sha256',required=True);p.add_argument('--approval-sha256',required=True);p.add_argument('--child',choices=['producer','checker']);p.add_argument('--token-sha256');p.add_argument('--producer-complete-sha256');args=p.parse_args()
    (execute_child if args.child else execute_parent)(args)
