"""Scoped, exclusive, budgeted streaming publication. No scientific imports."""
from pathlib import Path
import hashlib,json,os,time
CAP=64*2**20;RESERVE=2**20
def digest(raw):return hashlib.sha256(raw).hexdigest()
def safe(path):
    p=Path(os.path.abspath(path))
    if any(ord(c)<32 or ord(c)==127 for c in str(p)):raise ValueError('control path')
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('symlink path')
    return p
def pinned(path,pin,ledger,limit=2**20):
    p=safe(path)
    if type(pin)!=str or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):raise ValueError('SHA256')
    if p.stat().st_size>limit:raise ValueError('input byte cap')
    with p.open('rb') as f:raw=f.read(limit+1)
    if len(raw)>limit or digest(raw)!=pin:raise ValueError('authenticated exact input bytes')
    ledger.append({'operation':'authenticated_bytes','path':str(p),'sha256':pin,'bytes':len(raw)});return raw
def parse(raw,ledger,identity):
    def pairs(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('duplicate JSON field')
            d[k]=v
        return d
    result=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
    ledger.append({'operation':'JSON parse','identity':identity,'sha256':digest(raw),'bytes':len(raw)});return result
class Store:
    def __init__(self,root,deadline,cap=CAP,reserve=RESERVE,budget_root=None):
        self.root=safe(root);self.deadline=deadline;self.cap=cap;self.reserve=reserve;self.outputs={};self.highwater=0
        self.budget_root=safe(budget_root) if budget_root is not None else self.root
        if self.root!=self.budget_root and self.budget_root not in self.root.parents:raise ValueError('budget root must contain output')
        self.root.mkdir(exist_ok=False)
    def used(self):
        total=0
        for p in self.budget_root.rglob('*'):
            safe(p)
            if p.is_dir():continue
            if not p.is_file():raise ValueError('unexpected output entry')
            total+=p.stat().st_size
        self.highwater=max(self.highwater,total);return total
    def check(self,extra=0,emergency=False):
        if self.used()+extra>self.cap-(0 if emergency else self.reserve):raise OSError('64MiB aggregate logical output cap')
        if not emergency and time.monotonic()>=self.deadline:raise TimeoutError('publication deadline')
    def write_json(self,name,obj,emergency=False):
        if type(name)!=str or Path(name).name!=name or not name.endswith('.json'):raise ValueError('local JSON name')
        final=safe(self.root/name);partial=safe(self.root/(name+'.partial'))
        if final.exists() or partial.exists():raise FileExistsError('preserve all existing outputs')
        self.check(emergency=emergency);hasher=hashlib.sha256();size=0
        flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
        with os.fdopen(os.open(partial,flags,0o600),'wb',buffering=0) as f:
            buf=[];pending=0
            def emit():
                nonlocal size,pending,buf
                if not buf:return
                raw=b''.join(buf);self.check(len(raw),emergency);n=f.write(raw)
                if n!=len(raw):raise OSError('short output write')
                hasher.update(raw);size+=n;buf=[];pending=0
            for token in json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False).iterencode(obj):
                raw=token.encode('utf-8')
                if len(raw)>2**20:raise ValueError('streaming token cap')
                if pending+len(raw)>16384:emit()
                buf.append(raw);pending+=len(raw)
            emit();f.flush();os.fsync(f.fileno())
        self.check(size,emergency);self.outputs[partial.name]=hasher.hexdigest()
        # No fallible deadline check after this publication point. Partial and
        # final are both retained and charged as logical files, even hardlinked.
        os.link(partial,final)
        directory=os.open(self.root,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
        self.outputs[name]=hasher.hexdigest();return hasher.hexdigest(),size
    def verify_outputs(self,ledger):
        self.check()
        for n,pin in self.outputs.items():
            p=safe(self.root/n);hasher=hashlib.sha256();size=0
            with p.open('rb') as f:
                while True:
                    chunk=f.read(65536)
                    if not chunk:break
                    size+=len(chunk);hasher.update(chunk);self.check()
            if hasher.hexdigest()!=pin:raise ValueError('accepted output changed')
            ledger.append({'operation':'streamed output authentication','path':str(p),'sha256':pin,'bytes':size})
        self.check()
