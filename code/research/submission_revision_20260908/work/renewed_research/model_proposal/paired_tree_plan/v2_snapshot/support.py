"""Authenticated source intake and fail-exclusive receipts; no model I/O on import."""
from pathlib import Path
from fractions import Fraction
import hashlib, json, math, os, sys, time, types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PINS = {
 'paired': ('feature_relation_certification/paired_enclosure.py','8749d464278c4fd064821b7fe62d9fa517e360241ed70f3d8b8e8f7d5208b00c'),
 'oracle': ('feature_relation_certification/exact_oracle.py','35fa867b21c5beed6521f5238560561e18eb0e55a20f443ab4a8c60d91374712'),
 'numeric': ('model_proposal/range_bound_feasibility/qualified_numerics.py','76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a'),
 'evaluator': ('model_proposal/range_bound_feasibility/stage1_v2/evaluator.py','562279b3b636910098bf6f5e1bf2af790998a085d4233fa90975fdbdfcbf4705'),
}
MODEL = 'independent_environment/bounds_extraction/arrays/tree_31_capped.npz'
MODEL_SHA = 'ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
MANIFEST = 'independent_environment/bounds_extraction/manifest.json'
MANIFEST_SHA = '210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea'
STAGE0 = 'model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json'
STAGE0_SHA = '8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782'
MEMBERS = ('initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets')

def digest(raw): return hashlib.sha256(raw).hexdigest()

def safe_path(path):
    p = Path(os.path.abspath(path))
    if any(ord(c)<32 or ord(c)==127 for c in str(p)): raise ValueError('control character path')
    for part in (p,*p.parents):
        if part.is_symlink(): raise ValueError('symlink path or ancestor')
    return p

def read_pinned(path, expected, ledger, kind='bytes'):
    p=safe_path(path)
    if p.stat().st_size > 64*2**20: raise ValueError('input byte cap')
    raw=p.read_bytes()
    if digest(raw)!=expected: raise ValueError('input hash mismatch: '+str(p))
    ledger.append({'kind':kind,'path':str(p),'sha256':expected,'bytes':len(raw)})
    return raw

def dependencies(ledger):
    result={}
    for name,(rel,pin) in PINS.items():
        raw=read_pinned(ROOT/rel,pin,ledger,'source_execute')
        m=types.ModuleType('paired_'+name);m.__file__=str(ROOT/rel)
        exec(compile(raw,m.__file__,'exec'),m.__dict__);result[name]=m
    return result

def fraction(x):
    x=Fraction(x)
    return {'encoding':'signed_hex_fraction_v1','numerator':hex(x.numerator),'denominator':hex(x.denominator)}

def unfraction(x):
    if type(x)!=dict or set(x)!={'encoding','numerator','denominator'} or x['encoding']!='signed_hex_fraction_v1': raise ValueError('fraction schema')
    n,d=x['numerator'],x['denominator']
    if type(n)!=str or type(d)!=str: raise ValueError('fraction strings')
    try: a,b=int(n,16),int(d,16)
    except ValueError: raise ValueError('fraction hex')
    if hex(a)!=n or hex(b)!=d or b<=0: raise ValueError('noncanonical hex')
    q=Fraction(a,b)
    if q.numerator!=a or q.denominator!=b: raise ValueError('noncanonical fraction')
    return q

def encoded(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def exclusive(path,obj):
    raw=encoded(obj)
    if len(raw)>64*2**20: raise ValueError('output payload cap')
    p=safe_path(path)
    with p.open('xb') as f:
        f.write(raw);f.flush();os.fsync(f.fileno())
    return digest(raw)

def runtime():
    i=sys.float_info
    if (i.radix,i.mant_dig,i.min_exp,i.max_exp)!=(2,53,-1021,1024): raise RuntimeError('binary64 format')
    u=2.**-53
    if 1.+u!=1. or (1.+2*u)+u!=1.+4*u: raise RuntimeError('rounding probe')
    tiny=math.ldexp(1.,-1074)
    normal=math.ldexp(1.,-1022)
    if tiny==0 or tiny+tiny!=math.ldexp(1.,-1073) or normal*.5==0 or (normal+tiny)-normal!=tiny: raise RuntimeError('gradual underflow probe')

class Budget:
    """Algorithm-owned conservative accounting, NOT process RSS."""
    def __init__(self,seconds=900):
        self.start=time.monotonic();self.seconds=seconds;self.pairs=0;self.peak=0
    def check(self,owned=0):
        self.peak=max(self.peak,owned)
        if owned>128*2**20: raise MemoryError('estimated algorithm-owned cap')
        if time.monotonic()-self.start>=self.seconds: raise TimeoutError('phase deadline')

