"""Finite allowlisted reads and scoped exact-buffer module execution."""
from pathlib import Path,PurePosixPath
from contextlib import contextmanager
import hashlib,io,json,sys,types,zipfile,stat
import numpy as np
def sha(b):return hashlib.sha256(b).hexdigest()
def safe_name(n):
    p=PurePosixPath(n)
    if not n or p.is_absolute() or str(p)!=n or '..' in p.parts or '\\' in n or ':' in n or any(ord(c)<32 for c in n):raise ValueError('unsafe path')
def path_bytes(p):
    p=Path(p)
    if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('symlink path')
    return p.read_bytes()
class Access:
    def __init__(self,root,spec):self.root=Path(root);self.spec=spec;self.events=[];self.cache={};self.consumed={}
    def file(self,n):
        safe_name(n)
        if n not in self.spec['files']:raise ValueError('file not allowlisted')
        b=path_bytes(self.root/n);h=sha(b)
        if h!=self.spec['files'][n]:raise ValueError('file identity '+n)
        self.events.append({'operation':'file read','file':n,'sha256':h});self.consumed[n]=h
        return b
    def member(self,archive,n):
        safe_name(n)
        if archive not in self.spec['archives'] or n not in self.spec['archives'][archive]['members']:raise ValueError('member not allowlisted')
        s=self.spec['archives'][archive]
        if archive not in self.cache:
            b=path_bytes(self.root/archive)
            if sha(b)!=s['sha256']:raise ValueError('archive identity')
            self.events.append({'operation':'archive read','file':archive,'sha256':sha(b)});self.consumed[archive]=sha(b)
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                names=z.namelist()
                if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('duplicate name')
                for i in z.infolist():
                    safe_name(i.filename)
                    if i.is_dir() or stat.S_IFMT(i.external_attr>>16) not in (0,stat.S_IFREG) or i.flag_bits&1:raise ValueError('member kind')
                m=z.read('manifest.json')
                if sha(m)!=s['manifest_sha256']:raise ValueError('manifest identity')
                self.events.append({'operation':'JSON parse','file':archive+'!manifest.json','sha256':sha(m)})
                manifest=json.loads(m)
                if any(manifest['files'][k]!=v for k,v in s['members'].items()):raise ValueError('member pin identity')
            self.cache[archive]=b
        with zipfile.ZipFile(io.BytesIO(self.cache[archive])) as z:b=z.read(n)
        if {'sha256':sha(b),'bytes':len(b)}!=s['members'][n]:raise ValueError('member identity')
        self.events.append({'operation':'archive member read','file':archive+'!'+n,'sha256':sha(b)})
        return b
    def json(self,b,identity):
        self.events.append({'operation':'JSON parse','file':identity,'sha256':sha(b)})
        return json.loads(b)
    def arrays(self,b,identity,keys):
        allowed=self.spec['arrays'].get(identity)
        if allowed is None or not set(keys)<=set(allowed):raise ValueError('array not allowlisted')
        with np.load(io.BytesIO(b),allow_pickle=False) as z:
            out={}
            for k in keys:
                v=z[k]
                if v.dtype.hasobject:raise ValueError('object array')
                out[k]=v
                self.events.append({'operation':'NPZ member materialization','file':identity,'sha256':sha(b),'member':k,'shape':list(v.shape),'dtype':str(v.dtype)})
        return out
    def finish(self):
        for n,h in self.consumed.items():
            b=path_bytes(self.root/n)
            if sha(b)!=h:raise ValueError('consumed input changed '+n)
            self.events.append({'operation':'finish authentication','file':n,'sha256':h})
        return self.events
@contextmanager
def modules(access):
    restored={}
    def execute(name,b,identity):
        if name not in restored:restored[name]=sys.modules.get(name)
        m=types.ModuleType(name);m.__file__=identity;sys.modules[name]=m
        access.events.append({'operation':'source execution','file':identity,'sha256':sha(b)})
        exec(compile(b,identity,'exec'),m.__dict__)
        return m
    try:yield execute
    finally:
        for n,old in restored.items():
            if old is None:sys.modules.pop(n,None)
            else:sys.modules[n]=old
