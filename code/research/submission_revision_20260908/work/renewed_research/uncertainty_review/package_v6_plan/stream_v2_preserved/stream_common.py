"""Bounded transport/authority only; no scientific parsing or execution."""
import hashlib,json,os,re,signal,stat,time
from contextlib import contextmanager
from pathlib import Path,PurePosixPath

CHUNK=1024*1024
EXPANDED=9*1024**3//4
COMPRESSED=240*1024**2
METADATA=16*1024**2
MAX_FILES=20000
SECONDS=900
SOURCES={'stream_common.py','write_evidence.py','verify_evidence.py','test_stream_evidence.py'}
def digest(b):return hashlib.sha256(b).hexdigest()
def pin(h):
    if type(h) is not str or re.fullmatch('[0-9a-f]{64}',h) is None:raise ValueError('SHA256 required')
def parse(raw):
    if len(raw)>METADATA:raise ValueError('metadata cap')
    def unique(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('duplicate JSON')
            d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def encode(d):
    b=(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    if len(b)>METADATA:raise ValueError('metadata serialization cap')
    return b
def safe(s):
    if type(s) is not str or not s:raise ValueError('path string')
    p=PurePosixPath(s)
    if p.is_absolute() or str(p)!=s or '..' in p.parts or '\\' in s or ':' in s or any(ord(c)<32 or 127<=ord(c)<=159 for c in s):raise ValueError('unsafe path')
    return p
def allowed(s):
    p=safe(s)
    if any(x in s.lower() for x in ['eight_tree','eight-tree','eighttree','volume4','volume_4','sealed']):raise ValueError('excluded study/data')
    if any(x.lower().startswith(('venv','conda')) or x in {'.venv','.git','__pycache__','site-packages','pkgs','envs','.cache','cache'} for x in p.parts[:-1]):raise ValueError('environment tree')
def path(root,name):
    p=Path(root)/safe(name)
    if any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('symlink ancestor')
    return p
class Clock:
    def __init__(self):self.start=time.monotonic();self.end=self.start+SECONDS
    def check(self):
        if time.monotonic()>=self.end:raise TimeoutError('whole-entry deadline')
@contextmanager
def deadline():
    """Main-thread POSIX wall alarm starts before authority and input work."""
    old=signal.getsignal(signal.SIGALRM)
    if signal.getitimer(signal.ITIMER_REAL)!=(0.0,0.0):raise ValueError('existing timer')
    def alarm(*_):raise TimeoutError('whole-entry 900 second wall alarm')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,SECONDS)
    clock=Clock()
    try:yield clock
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
class Reader:
    def __init__(self,root,clock):self.root=Path(root).absolute();self.clock=clock;self.pins={}
    def check(self,name,h,metadata=False):
        self.clock.check();pin(h);p=path(self.root,name)
        if not stat.S_ISREG(p.stat().st_mode):raise ValueError('regular source')
        if metadata and p.stat().st_size>METADATA:raise ValueError('metadata pre-read cap')
        result=[];hasher=hashlib.sha256();count=0
        with p.open('rb') as f:
            while b:=f.read(CHUNK):
                self.clock.check();count+=len(b)
                if metadata and count>METADATA:raise ValueError('metadata cumulative read cap')
                hasher.update(b)
                if metadata:result.append(b)
        if hasher.hexdigest()!=h:raise ValueError('input digest '+name)
        if name in self.pins and self.pins[name]!=h:raise ValueError('conflicting source')
        self.pins[name]=h
        return b''.join(result) if metadata else None
    def end(self):
        for n,h in list(self.pins.items()):self.check(n,h)
def records(selection):
    if set(selection)!={'schema','claim','files','unresolved','closure_review'} or selection['schema']!='v9-evidence-selection-1' or selection['claim']!='SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE' or selection['unresolved']!=[]:raise ValueError('resolved evidence selection')
    rows=selection['files']
    if type(rows) is not list or not 0<len(rows)<=MAX_FILES:raise ValueError('finite file count')
    names=[]
    for r in rows:
        if set(r)!={'source','target','sha256','bytes'}:raise ValueError('strict file record')
        allowed(r['source']);allowed(r['target']);pin(r['sha256'])
        if type(r['bytes']) is not int or not 0<=r['bytes']<=EXPANDED:raise ValueError('typed size')
        names.append(r['target'].casefold())
    if len(names)!=len(set(names)) or 'manifest.json' in names or any(a!=b and b.startswith(a+'/') for a in names for b in names):raise ValueError('target collision')
    if sum(r['bytes'] for r in rows)+METADATA>EXPANDED:raise ValueError('expanded cap with metadata reserve')
    if set(selection['closure_review'])!={'source','sha256'}:raise ValueError('closure review binding')
    safe(selection['closure_review']['source']);pin(selection['closure_review']['sha256'])
    return rows
def authorize(rd,approval,expected,phase,output):
    a=parse(rd.check(approval,expected,True))
    required={'schema','phase','execution_authorized','source_pins','selection','selection_sha256','output','max_seconds','max_expanded_bytes','max_archive_bytes','workers'}
    if phase=='VERIFY_EXTRACT':required|={'archive','archive_sha256','writer_receipt','writer_receipt_sha256','writer_approval','writer_approval_sha256'}
    if set(a)!=required or a['schema']!='v9-evidence-approval-1' or a['phase']!=phase or a['execution_authorized'] is not True or a['output']!=output:raise ValueError('explicit phase authorization')
    for k,v in [('max_seconds',SECONDS),('max_expanded_bytes',EXPANDED),('max_archive_bytes',COMPRESSED),('workers',1)]:
        if type(a[k]) is not int or a[k]!=v:raise ValueError('fixed resource authority')
    actual=Path(__file__).parent
    expected_paths={str((actual/n).relative_to(rd.root)) for n in SOURCES}
    if set(a['source_pins'])!=expected_paths:raise ValueError('executing sources and tests binding')
    for n,h in a['source_pins'].items():rd.check(n,h)
    s=parse(rd.check(a['selection'],a['selection_sha256'],True));rows=records(s)
    rd.check(s['closure_review']['source'],s['closure_review']['sha256'])
    return a,s,rows
def publish(pathname,d,clock):
    clock.check();raw=encode(d)
    with Path(pathname).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    clock.check()
def failure(out,error):
    """Small failure exception receipt; preserve all partials, no retry/cleanup."""
    if out is not None and out.is_dir():
        raw=encode({'status':'FAILED_PRESERVED','error_type':type(error).__name__,'message':str(error)[:2000],'scientific_execution':False})
        with (out/'FAILURE.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
