"""Independent adjacent-pair checker. No producer traversal/arithmetic imports.

Only callers may supply model arrays; import performs no model/data access.
"""
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import types
import numpy as np

MODEL_SHA='ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
ORACLE_SHA='e9c94a3105ab4305c430ec8e3c14bfbc880eebe1df2cbef9ba15a5ac0dcf0a11'
MAX=sys.float_info.max
SIX=(0,12,13,16,18,19)
MEMBERS={'initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets'}

def runtime():
    if (sys.float_info.radix,sys.float_info.mant_dig,sys.float_info.min_exp,sys.float_info.max_exp)!=(2,53,-1021,1024):raise ValueError('binary64 required')
    u=2.**-53
    normal=sys.float_info.min;half=.5;smallest=math.nextafter(0.,1.)
    sub=normal*half;twice=smallest+smallest
    if (1.+u!=1. or (1.+2*u)+u!=1.+4*u or smallest!=2.**-1074
        or sub!=2.**-1023 or twice!=2.**-1073):raise ValueError('rounding/underflow contract')

def oracle():
    path=Path(__file__).resolve().parents[2]/'tree_range_refinement/feature_relation_oracle_review/oracle.py'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ORACLE_SHA:raise ValueError('independent oracle changed')
    m=types.ModuleType('paired_independent_oracle');exec(compile(raw,str(path),'exec'),m.__dict__)
    return m

def tick(deadline):
    if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('independent checker deadline')

def keys(x,expected):
    if type(x) is not dict or set(x)!=set(expected):raise ValueError('exact fields required')

def hx(value):
    if type(value) is not str:raise ValueError('hex float string')
    try:x=float.fromhex(value)
    except (ValueError,OverflowError) as e:raise ValueError('hex float') from e
    if not math.isfinite(x) or x.hex()!=value:raise ValueError('canonical finite hex float')
    return x

def integer(x):
    if type(x) is not int:raise ValueError('strict integer')
    return x

def rational(x):
    keys(x,('encoding','numerator','denominator'))
    if x['encoding']!='signed_hex_fraction_v1':raise ValueError('rational codec')
    def read(s):
        if type(s) is not str:raise ValueError('integer hex')
        try:n=int(s,16)
        except ValueError as e:raise ValueError('integer hex') from e
        if hex(n)!=s:raise ValueError('noncanonical integer')
        return n
    n,d=read(x['numerator']),read(x['denominator'])
    if d<=0:raise ValueError('denominator')
    z=F(n,d)
    if z.numerator!=n or z.denominator!=d:raise ValueError('unreduced rational')
    return z

def encode(x):
    x=F(x);return {'encoding':'signed_hex_fraction_v1','numerator':hex(x.numerator),'denominator':hex(x.denominator)}

def directed(x,up):
    try:y=float(x)
    except OverflowError as e:raise ValueError('outward overflow') from e
    if not math.isfinite(y):raise ValueError('outward overflow')
    if (F(y)<x if up else F(y)>x):y=math.nextafter(y,math.inf if up else -math.inf)
    if not math.isfinite(y) or (F(y)<x if up else F(y)>x):raise ValueError('outward enclosure')
    return F(y)

def propagate(lo,hi,sequences):
    if not sequences:raise ValueError('no feasible pair')
    lows=[];highs=[]
    for seq in sequences:
        a,b=lo,hi
        for v in seq:a,b=directed(a+F(v),False),directed(b+F(v),True)
        lows.append(a);highs.append(b)
    return min(lows),max(highs)

def structural(lo,hi):
    def clip(x):return max(F(-1,2),min(F(1),x))
    u=F(1,2**53);e=4*u+2*u*u
    return max(abs(clip(clip(lo)-e)),abs(clip(clip(hi)+e)))/2+3*u/2

def restrict(box,f,t,branch):
    if box is None:return None
    lo,hi=box[f]
    if branch=='L':hi=min(hi,t)
    elif branch=='R':lo=max(lo,math.nextafter(t,math.inf))
    else:raise ValueError('branch')
    if lo>hi or not math.isfinite(lo) or not math.isfinite(hi):return None
    out=list(box);out[f]=(lo,hi);return tuple(out)

def intersect(a,b):
    if a is None or b is None:return None
    c=tuple((max(x[0],y[0]),min(x[1],y[1])) for x,y in zip(a,b))
    return None if any(lo>hi for lo,hi in c) else c

def inventory(arrays,required_stages=400,deadline=None):
    """Independent validation and left-first DFS, including impossible paths."""
    runtime()
    if type(arrays) is not dict or set(arrays)!=MEMBERS:raise ValueError('exact seven members')
    if any(not isinstance(v,np.ndarray) or v.dtype.hasobject for v in arrays.values()):raise ValueError('safe arrays')
    a=arrays;init=a['initial'];off=a['nodes_offsets'];nodes=a['nodes']
    if init.dtype!=np.dtype('float64') or init.size!=1 or not np.isfinite(init).all():raise ValueError('initial')
    if off.dtype.kind not in 'iu' or off.shape!=(required_stages+1,) or int(off[0])!=0 or int(off[-1])!=len(nodes):raise ValueError('offsets')
    oo=[int(x) for x in off]
    if any(not 1<=b-c<=29 for c,b in zip(oo,oo[1:])) or nodes.ndim!=1:raise ValueError('node count')
    fields=('value','is_leaf','feature_idx','num_threshold','left','right','missing_go_to_left','is_categorical')
    if not set(fields)<=set(nodes.dtype.names or ()):raise ValueError('fields')
    if any(nodes.dtype.fields[k][0].kind not in 'iu' for k in fields if k not in ('value','num_threshold')):raise ValueError('integer fields')
    if any(nodes.dtype.fields[k][0]!=np.dtype('float64') for k in ('value','num_threshold')):raise ValueError('float fields')
    for name in ('raw_left_cat_bitsets','binned_left_cat_bitsets'):
        o=a[name+'_offsets']
        if a[name].size or a[name].dtype.kind not in 'iu' or o.dtype.kind not in 'iu' or o.shape!=(required_stages+1,) or np.any(o!=0):raise ValueError('categorical payload')
    result=[]
    for stage,(start,end) in enumerate(zip(oo,oo[1:])):
        tick(deadline);tree=nodes[start:end];seen=set();paths=[]
        if not np.isfinite(tree['value']).all() or not np.isfinite(tree['num_threshold']).all():raise ValueError('nonfinite nodes')
        for flag in ('is_leaf','missing_go_to_left','is_categorical'):
            if any(int(x) not in (0,1) for x in tree[flag]):raise ValueError('flags')
        if np.any(tree['is_categorical']):raise ValueError('categorical tree')
        stack=[(0,[],((-MAX,MAX),)*62)]
        while stack:
            node,edges,box=stack.pop()
            if not 0<=node<len(tree) or node in seen:raise ValueError('topology')
            seen.add(node);v=tree[node]
            if len(edges)>14:raise ValueError('depth')
            if int(v['is_leaf']):
                paths.append(({'stage':stage,'leaf':node,'value':float(v['value']).hex(),'edges':edges,'empty':box is None},box));continue
            f=int(v['feature_idx']);t=float(v['num_threshold'])
            if not 0<=f<62:raise ValueError('feature')
            for branch,child in (('R',int(v['right'])),('L',int(v['left']))):
                edge={'node':node,'feature':f,'threshold':t.hex(),'branch':branch}
                stack.append((child,edges+[edge],restrict(box,f,t,branch)))
        if len(seen)!=len(tree) or not 1<=len(paths)<=15:raise ValueError('unreachable/leaf count')
        result.append(paths)
    return float(init.ravel()[0]),result

def exact_object(actual,expected):
    # JSON spelling differentiates bool/int and int/float; ordering of dict keys
    # is irrelevant but list ordering, signed-zero hex strings and fields are not.
    if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):raise ValueError('exact inventory/schema mismatch')

def bounds(value,expected):
    if type(value) is not list or len(value)!=2:raise ValueError('bounds pair')
    if tuple(map(rational,value))!=tuple(expected):raise ValueError('arithmetic endpoint mismatch')

def check(certificate,arrays,deadline=None,*,expected_model_sha=MODEL_SHA):
    """Wrapper must authenticate input bytes against expected_model_sha first.

    The default accepts only the prespecified real-model identity. Synthetic
    callers explicitly pass a distinct declaration hash and still use 400 trees.
    No hash of a NumPy mapping is misrepresented as authentication of NPZ bytes.
    """
    runtime();tick(deadline)
    if type(expected_model_sha) is not str or len(expected_model_sha)!=64 or any(c not in '0123456789abcdef' for c in expected_model_sha):raise ValueError('expected model SHA')
    c=certificate
    keys(c,('schema','model_sha256','initial','paths','domains','stage0','summary','counts'))
    if c['schema']!='PAIRED_TREE_CERTIFICATE_V1' or c['model_sha256']!=expected_model_sha:raise ValueError('certificate/model binding')
    initial,trees=inventory(arrays,400,deadline)
    if c['initial']!=initial.hex():raise ValueError('initial mismatch')
    trees=[sorted(t,key=lambda row:row[0]['leaf']) for t in trees]
    expected_paths=[row[0] for tree in trees for row in tree]
    exact_object(c['paths'],expected_paths)
    old=(F(initial),F(initial))
    for tree in trees:
        vals=[hx(row[0]['value']) for row in tree]
        old=propagate(*old,[(v,) for v in vals])
    cartesian=(F(initial),F(initial))
    for j in range(200):
        tick(deadline)
        cartesian=propagate(*cartesian,[(hx(a[0]['value']),hx(b[0]['value']))
                            for a in trees[2*j] for b in trees[2*j+1]])
    if cartesian!=old:raise ValueError('Cartesian versus independent arithmetic')
    keys(c['stage0'],('lower','upper','B'))
    if tuple(rational(c['stage0'][k]) for k in ('lower','upper','B'))!=(*old,structural(*old)):raise ValueError('Stage0 mismatch')
    keys(c['domains'],('D','R'));keys(c['summary'],('D','R'))
    independent=oracle();results={};attempt_total=0
    for name,identity in (('D','FINITE_X62_V1'),('R','FINITE_X62_ABS_MINMAX_NUMERIC_V1')):
        section=c['domains'][name];keys(section,('id','blocks'))
        if section['id']!=identity or type(section['blocks']) is not list or len(section['blocks'])!=200:raise ValueError('domain/block inventory')
        current=(F(initial),F(initial));attempts=feasible_count=0
        for j,block in enumerate(section['blocks']):
            tick(deadline);keys(block,('block','stages','pairs','incoming','outgoing'))
            exact_object(block['block'],j);exact_object(block['stages'],[2*j,2*j+1])
            bounds(block['incoming'],current)
            pair_ids=[(a,b) for a in trees[2*j] for b in trees[2*j+1]]
            if type(block['pairs']) is not list or len(block['pairs'])!=len(pair_ids):raise ValueError('complete Cartesian pairs required')
            sequences=[]
            for record,(left,right) in zip(block['pairs'],pair_ids):
                if attempts%64==0:tick(deadline)
                keys(record,('leaves','status','witness'))
                exact_object(record['leaves'],[left[0]['leaf'],right[0]['leaf']])
                box=intersect(left[1],right[1])
                if left[1] is None or right[1] is None:status='path_empty'
                elif box is None:status='intersection_empty'
                elif name=='R' and not independent.feasible(box)['feasible']:status='R_infeasible'
                else:status='feasible'
                if record['status']!=status:raise ValueError('independent pair classification mismatch')
                attempts+=1
                if status!='feasible':
                    if record['witness'] is not None:raise ValueError('rejected witness')
                    continue
                if type(record['witness']) is not list or len(record['witness'])!=6:raise ValueError('six-coordinate witness')
                point=[b[0] for b in box]
                for k,v in zip(SIX,record['witness']):point[k]=hx(v)
                if not all(lo<=x<=hi for x,(lo,hi) in zip(point,box)):raise ValueError('witness outside intersection')
                if name=='D' and any(point[k]!=box[k][0] for k in SIX):raise ValueError('D lower-endpoint witness rule')
                if name=='R' and not independent.valid_witness(box,point):raise ValueError('relation witness')
                for row in (left[0],right[0]):
                    for edge in row['edges']:
                        actual=point[edge['feature']]<=hx(edge['threshold'])
                        if actual!=(edge['branch']=='L'):raise ValueError('original branch witness')
                sequences.append((hx(left[0]['value']),hx(right[0]['value'])));feasible_count+=1
            current=propagate(*current,sequences);bounds(block['outgoing'],current)
        summary=c['summary'][name];keys(summary,('lower','upper','B','attempted_pairs','feasible_pairs'))
        if tuple(rational(summary[k]) for k in ('lower','upper','B'))!=(*current,structural(*current)):raise ValueError('summary bounds')
        exact_object(summary['attempted_pairs'],attempts);exact_object(summary['feasible_pairs'],feasible_count)
        results[name]=current;attempt_total+=attempts
    if not old[0]<=results['D'][0]<=results['R'][0]<=results['R'][1]<=results['D'][1]<=old[1]:raise ValueError('domain nesting')
    counts={'stages':400,'blocks_per_domain':200,'paths':len(expected_paths),
            'path_edges':sum(len(row['edges']) for row in expected_paths),'attempted_pairs':attempt_total}
    exact_object(c['counts'],counts)
    tick(deadline)
    return {'status':'PASS_INDEPENDENT_ADJACENT_PAIR_REPLAY','model_sha256':expected_model_sha,
            'counts':counts,'stage0':c['stage0'],'summary':c['summary'],
            'all_cartesian_equals_independent':True,
            'input_byte_authentication_required_from_wrapper':True}
