"""New metadata/resource adapter; scientific implementations remain immutable."""
import hashlib,json,os,time,types,shutil
from pathlib import Path
from fractions import Fraction as F
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
CONTEXTS=[f'group_{s}_fold_{i}' for s in (20260906,20260908) for i in range(5)]+['strict_source_'+s for s in ('stec8','vol1','vol2','vol3','all_uiuc_volumes')]+['final']
CAP=9*2**28;CHILD_CAP=64*2**20;RESERVE=2**20
DEADLINE=None
def tick():
    if DEADLINE is not None and time.monotonic()>=DEADLINE:raise TimeoutError('phase authentication deadline')
def sha(b):return hashlib.sha256(b).hexdigest()
def safe(p):
    p=Path(os.path.abspath(p))
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('symlink path')
    return p
def read(p,h,ledger,limit=2**20):
    tick()
    p=safe(p)
    if p.stat().st_size>limit:raise ValueError('bounded input')
    b=p.read_bytes();tick()
    if len(b)>limit or sha(b)!=h:raise ValueError('exact input hash')
    ledger.append({'operation':'authenticated_bytes','path':str(p),'sha256':h,'bytes':len(b)});return b
def stream(p,h,ledger):
    tick()
    p=safe(p);digest=hashlib.sha256();n=0
    with p.open('rb') as f:
        while b:=f.read(65536):tick();digest.update(b);n+=len(b)
    tick()
    if digest.hexdigest()!=h:raise ValueError('streamed pin')
    ledger.append({'operation':'hash_only','path':str(p),'sha256':h,'bytes':n})
def parse(b):
    def unique(rows):
        d={}
        for k,v in rows:
            if k in d:raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    return json.loads(b,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def module(b,name,path):
    m=types.ModuleType(name);m.__file__=str(path);exec(compile(b,str(path),'exec'),m.__dict__);return m
def validate_contexts(rows,manifest):
    if type(rows)!=list or [x.get('context') for x in rows]!=CONTEXTS:raise ValueError('fixed sixteen ordered contexts')
    for i,r in enumerate(rows):
        member=f'arrays/tree_{2*i+1:02d}_capped.npz'
        expected={'context':CONTEXTS[i],'branch':'proper','capped':member,'upper_free':member.replace('_capped','_upper_free')}
        if [x for x in manifest['trees'] if x.get('context')==CONTEXTS[i] and x.get('branch')=='proper']!=[expected] or r['member']!=member or r['model_sha256']!=manifest['files'][member]:raise ValueError('proper capped context identity')
def authenticate(reg,pin,ledger):
    read(HERE/'REGISTRY_v3.json',pin,ledger)
    for n,h in reg['sources'].items():
        if Path(n).name!=n:raise ValueError('local source path')
        read(HERE/n,h,ledger)
    for e in reg['external_sources'].values():read(ROOT/e['path'],e['sha256'],ledger)
    for e in reg['metadata'].values():stream(ROOT/e['path'],e['sha256'],ledger)
def strict_approval(a,regsha,phase):
    base={'phase':phase,'registry_sha256':regsha,'contexts':CONTEXTS,'domain':'FINITE_X62_V1','workers':1,'seconds':900,'child_seconds':900,'producer_owned_cap':128*2**20,'checker_owned_cap':256*2**20,'child_output_cap':CHILD_CAP,'combined_output_cap':CAP,'actual_execution_authorized':True}
    extras={'producer_complete_sha256'} if phase=='certificates_replay' else set()
    if phase not in ('certificates_produce','certificates_replay') or set(a)!=set(base)|extras or any(type(a[k]) is not type(v) or a[k]!=v for k,v in base.items()):raise ValueError('strict separate phase approval')
    for k in extras:
        if type(a[k])!=str or len(a[k])!=64 or any(c not in '0123456789abcdef' for c in a[k]):raise ValueError('predecessor SHA')
def usage():
    n=0
    for name in ('certificates_produce','certificates_replay'):
        p=HERE/name
        if p.exists():
            for x in p.rglob('*'):
                safe(x)
                if x.is_file():n+=x.stat().st_size
                elif not x.is_dir():raise ValueError('output type')
    return n
def reserve():
    if usage()+CHILD_CAP+2*RESERVE>CAP or shutil.disk_usage(HERE).free<CHILD_CAP+2*RESERVE:raise OSError('aggregate child preallocation')
def store_type(io):
    class Store(io.Store):
        def check(self,extra=0,emergency=False):
            super().check(extra,emergency)
            if usage()+extra>CAP-(0 if emergency else RESERVE):raise OSError('combined logical output precharge')
    return Store
def verify_outputs(path,r,ledger):
    if (path/'FAILURE.json').exists():raise ValueError('predecessor failed')
    for n,h in r['outputs'].items():
        if Path(n).name!=n:raise ValueError('output flat name')
        stream(path/n,h,ledger)
def compare(result,row,stage0):
    def dec(v):return F(int(v['numerator'],16),int(v['denominator'],16))
    records=[v for v in stage0['records'] if v['context']==row['context']]
    if len(records)!=1 or stage0['accessed_tree_sha256'][row['member']]!=row['model_sha256']:raise ValueError('stage0 role')
    old=records[0]
    for k in ('lower','upper'):
        v=old['range'][k]
        if dec(result['stage0'][k])!=F(int(v['numerator']),int(v['denominator'])):raise ValueError('stage0 range')
    v=old['B_structural']
    if dec(result['stage0']['B'])!=F(int(v['numerator']),int(v['denominator'])):raise ValueError('stage0 B')
    for k in ('lower','upper','B'):
        if dec(result['original_adjacent'][k])!=dec(row['old_D'][k]):raise ValueError('original context adjacent exact equality')
def inherited(reg,ledger):
    entries=reg['final'];p=parse(read(ROOT/entries['producer']['path'],entries['producer']['sha256'],ledger));r=parse(read(ROOT/entries['replay']['path'],entries['replay']['sha256'],ledger))
    verify_outputs((ROOT/entries['producer']['path']).parent,p,ledger);verify_outputs((ROOT/entries['replay']['path']).parent,r,ledger)
    if r['producer_complete_sha256']!=entries['producer']['sha256'] or r['certificate_sha256']!=p['outputs']['certificate.json'] or r['summary']['final']!=p['summary']['final']:raise ValueError('final inherited exact chain')
    return {'context':'final','status':'INHERITED_AUTHENTICATED','producer_complete_sha256':entries['producer']['sha256'],'replay_complete_sha256':entries['replay']['sha256'],'certificate_sha256':r['certificate_sha256'],'model_sha256':r['model_sha256'],'summary':{k:r['summary'][k] for k in ('counts','stage0','original_adjacent','final')}}
