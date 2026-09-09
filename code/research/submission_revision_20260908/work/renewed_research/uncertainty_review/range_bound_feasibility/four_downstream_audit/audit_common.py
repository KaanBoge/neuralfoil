"""Review-only primitives; no filesystem or numerical array access at import."""
import hashlib,json,time
from pathlib import Path
from fractions import Fraction as F
NEW=('qualified_four_D_harm_001','qualified_four_D_kl_harm_001')
COUNTS={'labels':21,'views':31,'native_cases':18,'calibration_contexts':16,'scored_splits':17,'scalars':32,'panel_rows':651,'bootstrap_rows':420,'old_bootstrap_rows':342,'group_rows':3906,'harm_rows':7812,'decisions':2}
PHASES=('preflight','calibrate','score','assess')
def pin(s):return type(s) is str and len(s)==64 and all(c in '0123456789abcdef' for c in s)
def json_unique(raw):
    def unique(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate key')
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
class Access:
    """Runtime binding must be independently supplied and approved for one phase."""
    def __init__(self,binding):
        required={'phase','root_saved_audit_authorized','complete_sha256','approval_sha256','registry_sha256','predecessor_sha256','seconds','workers'}
        if type(binding)!=dict or set(binding)!=required or binding['phase'] not in PHASES or binding['root_saved_audit_authorized'] is not True or type(binding['seconds']) is not int or binding['seconds']!=900 or type(binding['workers']) is not int or binding['workers']!=1:raise ValueError('explicit single phase root binding')
        if not all(pin(binding[k]) for k in ('complete_sha256','approval_sha256','registry_sha256')):raise ValueError('required phase pins')
        if not pin(binding['predecessor_sha256']):raise ValueError('explicit predecessor required in every phase')
        self.binding=dict(binding);self.deadline=time.monotonic()+900;self.events=[];self.inputs={}
    def tick(self):
        if time.monotonic()>=self.deadline:raise TimeoutError('saved audit deadline')
    def read(self,path,digest,limit=2**20):
        self.tick();p=Path(path)
        if not pin(digest) or any(x.is_symlink() for x in (p,*p.parents)) or p.stat().st_size>limit:raise ValueError('bounded authenticated path')
        raw=p.read_bytes();self.tick()
        if len(raw)>limit or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('exact bytes')
        self.inputs[str(p)]=digest;self.events.append({'operation':'authenticated bytes','path':str(p),'sha256':digest,'bytes':len(raw)});return raw
    def receipt(self,raw):
        r=json_unique(raw);b=self.binding
        if r.get('status')!='COMPLETE' or r.get('phase')!=b['phase'] or r.get('registry_sha256')!=b['registry_sha256'] or r.get('approval_sha256')!=b['approval_sha256']:raise ValueError('completion phase provenance')
        if hashlib.sha256(raw).hexdigest()!=b['complete_sha256']:raise ValueError('selected completion')
        if r['summary']['predecessor_sha256']!=b['predecessor_sha256']:raise ValueError('sequential saved phase')
        return r
    def permit_payload(self,role):
        allow={'preflight':{'metadata','native_without_targets','membership_without_scores'},'calibrate':{'metadata','calibration_only','membership','frozen_scalar'},'score':{'metadata','native_without_targets','frozen_scalar','outcome_free_predictions'},'assess':{'metadata','typed_assessment','frozen_predictions','frozen_tables'}}
        if role not in allow[self.binding['phase']]:raise ValueError('phase-forbidden payload role')
        self.events.append({'operation':'explicit payload permission','role':role})
def decode(v):
    if type(v)!=dict or set(v)!={'encoding','numerator','denominator'}:raise ValueError('exact Fraction fields')
    if v['encoding'] not in ('signed-hex-v1','signed_hex_fraction_v1'):raise ValueError('reviewed codec')
    n,d=int(v['numerator'],16),int(v['denominator'],16)
    if d<=0:raise ValueError('positive denominator')
    return F(n,d)
def group_positive_losses(base,core,anchor,target,identity):
    """Pure exact binary64 endpoint loss, equal row within identity/group mean."""
    if not len(base)==len(core)==len(anchor)==len(target)==len(identity):raise ValueError('aligned roles')
    grouped={};losses=[]
    for b,c,h,y,g in zip(base,core,anchor,target,identity):
        b,c,h,y=map(F,(b,c,h,y))
        if b<=0:raise ValueError('positive normalizer')
        loss=max(F(0),abs(c-y)-abs(h-y))/b;losses.append(loss);grouped.setdefault(g,[]).append(loss)
    means={g:sum(v,F(0))/len(v) for g,v in grouped.items()};mean=sum(means.values(),F(0))/len(means) if means else F(0)
    return losses,means,mean
def sign(x):return (x>0)-(x<0)
def scalar_directions(current,previous):
    u,old=decode(current['upper']),decode(previous['upper']);t,ot=F(current['t']),F(previous['t'])
    return {'U_direction':sign(u-old),'t_direction':sign(t-ot),'tU_direction':sign(t*u-ot*old)}
def exact_keyed_subset(rows,expected,keys,labels,refs=None):
    def index(rs):
        out={}
        for r in rs:
            k=tuple(r[x] for x in keys)
            if k in out:raise ValueError('duplicate table key')
            out[k]=r
        return out
    actual=index([r for r in rows if r['candidate'] in labels and (refs is None or r['reference'] in refs)]);old=index(expected)
    if actual!=old:raise ValueError('old serialized table changed')
    return len(actual)
