"""Context metadata/provenance adapter. Imports never load models or outcomes."""
import contextlib,datetime,hashlib,io,json,os,shutil,signal,subprocess,sys,time,types
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOLE=HERE.parent
ROOT=SOLE.parents[1]
SOLE_REGISTRY_SHA='7c53d7c0385d9df5222e901ec9a7b971b72c96ea72301a3d5e398089600061a2'
MANIFEST='independent_environment/bounds_extraction/manifest.json'
MANIFEST_SHA='210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea'
STAGE0='model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json'
STAGE0_SHA='8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782'
FINAL_PRODUCER_SHA='dce7280d67453cf120001a412d05ba6cbde4c33c05c4a0b65284ae359ddc433c'
FINAL_CERT_SHA='72c4caa8013f61b2943bafb7096d0b69d0ae9f10169e5a055e921ad39e584106'
FINAL_REPLAY_SHA='02b122ad8fb24243815bd8b016c41d91cf83f45c3f1c72f32c80a18d7102079a'
CONTEXTS=[f'group_{seed}_fold_{fold}' for seed in [20260906,20260908] for fold in range(5)]+['strict_source_'+s for s in ['stec8','vol1','vol2','vol3','all_uiuc_volumes']]+['final']
LOGICAL_CAP=9*2**28 # 2.25 GiB; every retained path counts, including hardlinks
REGISTRY_NAME='REGISTRY_v3.json'
PHASE_DIRS=('certificates_produce','certificates_replay','preflight','calibrate','score','assess')
CHILD_CAPS={'certificates_produce':132*2**20,'certificates_replay':4*2**20}
RECEIPT_RESERVE=2**20

def sha(raw):return hashlib.sha256(raw).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def safe(path):
    p=Path(os.path.abspath(path))
    if any(ord(c)<32 or ord(c)==127 for c in str(p)):raise ValueError('control character path')
    if any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('symlink path/ancestor')
    return p
def read(path,pin,ledger,kind='bytes'):
    p=safe(path)
    if p.stat().st_size>128*2**20:raise ValueError('individual source/input byte cap')
    raw=p.read_bytes()
    if sha(raw)!=pin:raise ValueError('hash mismatch '+str(p))
    ledger.append({'path':str(p),'sha256':pin,'bytes':len(raw),'operation':kind});return raw
def parse(raw,ledger,identity):
    obj=json.loads(raw);ledger.append({'identity':identity,'sha256':sha(raw),'operation':'JSON parse'});return obj
def json_read(path,pin,ledger):return parse(read(path,pin,ledger),ledger,str(path))
def save(path,obj):
    raw=json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    p=safe(path)
    if p.is_relative_to(HERE) and p.relative_to(HERE).parts[0] in PHASE_DIRS:
        if extension_usage()+len(raw)>LOGICAL_CAP:raise OSError('full extension pre-write JSON cap')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return sha(raw)

@contextlib.contextmanager
def modules(specs,ledger):
    """Execute exact source buffers and restore every selected module binding."""
    old={name:sys.modules.get(name) for name in specs};result={}
    try:
        for name,(path,pin) in specs.items():
            raw=read(path,pin,ledger,'source execution');m=types.ModuleType(name);m.__file__=str(path)
            sys.modules[name]=m;exec(compile(raw,str(path),'exec'),m.__dict__);result[name]=m
        yield result
    finally:
        for name,m in old.items():
            if m is None:sys.modules.pop(name,None)
            else:sys.modules[name]=m

@contextlib.contextmanager
def sole_modules(ledger):
    reg=json_read(SOLE/'REGISTRY_v3.json',SOLE_REGISTRY_SHA,ledger)
    for name,pin in reg['sources'].items():read(SOLE/name,pin,ledger,'sole source authentication')
    for name,pin in reg['dependencies'].items():read(ROOT/name,pin,ledger,'sole dependency authentication')
    specs={name:(SOLE/(name+'.py'),reg['sources'][name+'.py']) for name in ['support','producer','runner','replay_wrapper']}
    with modules(specs,ledger) as ms:yield ms,reg

def verify_contexts(table,manifest):
    if type(table)!=list or [r.get('context') for r in table]!=CONTEXTS:raise ValueError('sixteen fixed ordered contexts')
    for i,row in enumerate(table):
        expected={'context':CONTEXTS[i],'branch':'proper','capped':f'arrays/tree_{2*i+1:02d}_capped.npz','upper_free':f'arrays/tree_{2*i+1:02d}_upper_free.npz'}
        records=[r for r in manifest['trees'] if r.get('context')==row['context'] and r.get('branch')=='proper']
        if records!=[expected] or row['member']!=expected['capped'] or row['sha256']!=manifest['files'][row['member']]:raise ValueError('named context/model binding')

def stage0_equal(cert,old,row,decode):
    from fractions import Fraction
    records=[r for r in old['records'] if r['context']==row['context']]
    if len(records)!=1 or old['accessed_tree_sha256'][row['member']]!=row['sha256']:raise ValueError('context Stage0 identity')
    r=records[0]
    def legacy(x):return Fraction(int(x['numerator']),int(x['denominator']))
    for key in ['lower','upper']:
        if decode(cert['stage0'][key])!=legacy(r['range'][key]):raise ValueError('context Stage0 range')
    if decode(cert['stage0']['B'])!=legacy(r['B_structural']):raise ValueError('context Stage0 B')

def authenticate(reg,pin,approval,ap_sha,phase,ledger):
    if sha(read(HERE/REGISTRY_NAME,pin,ledger))!=pin:raise ValueError('registry')
    for name,h in reg['sources'].items():read(HERE/name,h,ledger,'local source authentication')
    for name,h in reg['external_sources'].items():read(ROOT/name,h,ledger,'external source authentication')
    ap=json_read(approval,ap_sha,ledger)
    expected={'registry_sha256':pin,'phase':phase,'seconds':900,'workers':1,'actual_execution_authorized':True}
    if any(type(ap.get(k)) is not type(v) or ap[k]!=v for k,v in expected.items()):raise ValueError('strict phase approval')
    if ap.get('contexts')!=CONTEXTS:raise ValueError('approved context inventory')
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise ValueError('one thread required')
    return ap

def disk_preflight(path):
    p=safe(path);free=shutil.disk_usage(p).free
    if free<LOGICAL_CAP:raise OSError('less than2.25GiB free allocation')
    return {'free_bytes':free,'reserved_logical_bytes':LOGICAL_CAP,'measure':'filesystem free space, not guaranteed future availability'}
def logical_usage(path):
    total=0
    for p in safe(path).rglob('*'):
        if p.is_symlink():raise ValueError('symlink output')
        if p.is_file():total+=p.stat().st_size
    if total>LOGICAL_CAP:raise OSError('logical output cap')
    return total

def extension_usage():
    total=sum(logical_usage(HERE/name) for name in PHASE_DIRS if (HERE/name).exists())
    if total>LOGICAL_CAP:raise OSError('cumulative full extension logical cap')
    return total

def reserve_child(phase,context):
    if phase not in CHILD_CAPS or context not in CONTEXTS[:-1]:raise ValueError('fixed child reservation')
    destination=safe(HERE/phase/context)
    if destination.exists():raise FileExistsError(str(destination))
    used=extension_usage();reserve=CHILD_CAPS[phase]+2*RECEIPT_RESERVE
    if used+reserve>LOGICAL_CAP:raise OSError('pre-write cumulative child reservation exceeds extension cap')
    if shutil.disk_usage(HERE).free<reserve:raise OSError('insufficient actual free bytes for next child')
    return {'used_extension_bytes':used,'child_cap_bytes':CHILD_CAPS[phase],
            'receipt_reserve_bytes':2*RECEIPT_RESERVE,'reserved_bytes':reserve,'destination':str(destination)}

@contextlib.contextmanager
def storage_guard(destination,cap):
    """One-worker scoped pre-write accounting, including retained hardlinks.

    Restricts every Path.open write and os.link used by frozen producers. Initial
    count includes ALL extension phase trees; each byte/link is charged before
    the original I/O. A separate receipt allowance remains for failure handling.
    """
    destination=safe(destination);total=extension_usage();local=logical_usage(destination) if destination.exists() else 0
    original_open=Path.open;original_link=os.link
    def location(path):
        p=safe(path)
        if p.parent!=destination:raise ValueError('write outside approved child destination')
        return p
    def charge(n):
        nonlocal total,local
        if local+n>cap-RECEIPT_RESERVE or total+n>LOGICAL_CAP-RECEIPT_RESERVE:raise OSError('pre-write storage cap')
        local+=n;total+=n
    class Writer:
        def __init__(self,f):self.f=f
        def __enter__(self):return self
        def __exit__(self,*args):return self.f.__exit__(*args)
        def __getattr__(self,name):return getattr(self.f,name)
        def write(self,raw):
            if not isinstance(raw,bytes):raise TypeError('binary-only controlled output')
            charge(len(raw));return self.f.write(raw)
        def writelines(self,lines):
            for raw in lines:self.write(raw)
    def opened(path,mode='r',*args,**kwargs):
        if any(c in mode for c in 'wax+'):
            location(path)
            if mode!='xb':raise ValueError('exclusive binary output only')
            return Writer(original_open(path,mode,*args,**kwargs))
        return original_open(path,mode,*args,**kwargs)
    def linked(src,dst,*args,**kwargs):
        if args or kwargs:raise ValueError('plain link only')
        p=location(src);location(dst);charge(p.stat().st_size)
        return original_link(src,dst)
    Path.open=opened;os.link=linked
    try:yield
    finally:Path.open=original_open;os.link=original_link

def authenticate_outputs(root,record,ledger):
    root=safe(root)
    for name,pin in record['outputs'].items():
        if Path(name).name!=name or name in ('.','..'):raise ValueError('noncanonical receipt output')
        read(root/name,pin,ledger,'receipt output authentication')

def certificate_chain(phase,pin,regsha,ledger):
    if phase not in CHILD_CAPS:raise ValueError('certificate phase')
    root=HERE/phase;r=json_read(root/'COMPLETE.json',pin,ledger)
    if r.get('status')!='COMPLETE' or r.get('phase')!=phase or r.get('registry_sha256')!=regsha:raise ValueError('certificate aggregate identity')
    authenticate_outputs(root,r,ledger);entries=r['summary']['contexts']
    if set(entries)!=set(CONTEXTS):raise ValueError('all sixteen certificate barrier')
    prior=None
    if phase=='certificates_replay':
        prior=certificate_chain('certificates_produce',r['summary']['predecessor_sha256'],regsha,ledger)
    for context in CONTEXTS[:-1]:
        e=entries[context];cr=json_read(root/context/'COMPLETE.json',e['complete_sha256'],ledger)
        if cr.get('status')!='COMPLETE' or cr.get('phase')!=phase or cr.get('registry_sha256')!=regsha:raise ValueError('child completion identity')
        if cr['summary']!={k:v for k,v in e.items() if k!='complete_sha256'} or e['context']!=context:raise ValueError('aggregate child summary binding')
        authenticate_outputs(root/context,cr,ledger)
        if phase=='certificates_produce':
            if cr['outputs']['certificate.json']!=e['certificate_sha256']:raise ValueError('producer certificate binding')
        else:
            pe=prior['summary']['contexts'][context]
            if e.get('status')!='PASS_CONTEXT_REPLAY' or any(e[k]!=pe[k] for k in ['certificate_sha256','model_sha256']):raise ValueError('replay producer binding')
            if e['producer_complete_sha256']!=pe['complete_sha256']:raise ValueError('replay child predecessor')
    expected=inherited_final(ledger,phase=='certificates_replay')
    if entries['final']!=expected:raise ValueError('inherited final complete binding')
    return r

def attempt(out,meta,work,seconds=900):
    out=safe(out);out.mkdir(exist_ok=False);start=time.monotonic();ledger=[];outputs={}
    meta=dict(meta,start_utc=now(),pid=os.getpid(),python=sys.version)
    outputs['ATTEMPT.json']=save(out/'ATTEMPT.json',meta)
    old=signal.getsignal(signal.SIGALRM);term=signal.getsignal(signal.SIGTERM)
    def timeout(*_):raise TimeoutError('fixed aggregate/context deadline')
    signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGTERM,timeout);signal.setitimer(signal.ITIMER_REAL,seconds)
    try:
        summary=work(out,ledger,outputs,start+seconds)
        outputs['ACCESS.json']=save(out/'ACCESS.json',ledger)
        result=dict(meta,status='COMPLETE',finish_utc=now(),seconds=time.monotonic()-start,outputs=outputs,summary=summary)
        save(out/'COMPLETE.json',result);return result
    except BaseException as exc:
        if meta.get('phase') in CHILD_CAPS and 'context' not in meta and not (out/'CONTEXT_STATUS.json').exists():
            outputs['CONTEXT_STATUS.json']=save(out/'CONTEXT_STATUS.json',{c:'NOT_RUN' for c in CONTEXTS})
        save(out/'FAILURE.json',dict(meta,status='FAILED_STOP_NO_RETRY',finish_utc=now(),seconds=time.monotonic()-start,error=repr(exc),outputs=outputs,access=ledger));raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old);signal.signal(signal.SIGTERM,term)

def inherited_final(ledger,include_replay):
    p=json_read(SOLE/'actual_producer_attempt_1/COMPLETE.json',FINAL_PRODUCER_SHA,ledger)
    if p['status']!='COMPLETE' or p['outputs']['certificate.json']!=FINAL_CERT_SHA:raise ValueError('inherited producer')
    authenticate_outputs(SOLE/'actual_producer_attempt_1',p,ledger)
    cert=json_read(SOLE/'actual_producer_attempt_1/certificate.json',FINAL_CERT_SHA,ledger)
    if cert['model_sha256']!=p['model_sha256']:raise ValueError('inherited model')
    r=None
    if include_replay:
        r=json_read(SOLE/'actual_replay_attempt_1/COMPLETE.json',FINAL_REPLAY_SHA,ledger)
        if r['summary']['status']!='PASS_AUTHENTICATED_INDEPENDENT_REPLAY' or r['model_sha256']!=p['model_sha256']:raise ValueError('inherited replay')
        authenticate_outputs(SOLE/'actual_replay_attempt_1',r,ledger)
        ap=json_read(SOLE/'ROOT_ACTUAL_REPLAY_APPROVAL.json',r['approval_sha256'],ledger)
        if ap['producer_complete_sha256']!=FINAL_PRODUCER_SHA or ap['certificate_sha256']!=FINAL_CERT_SHA:raise ValueError('inherited replay predecessor pins')
    return {'context':'final','status':'INHERITED_AUTHENTICATED','producer_complete_sha256':FINAL_PRODUCER_SHA,'replay_complete_sha256':FINAL_REPLAY_SHA if include_replay else None,'certificate_sha256':FINAL_CERT_SHA,'model_sha256':p['model_sha256'],'summary':cert['summary']}
