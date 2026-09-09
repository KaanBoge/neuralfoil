"""Fixed D-only four-tree matching relaxation. No file/model access on import.

This is a producer, not the independent checker. No real execution authorization.
"""
from fractions import Fraction as F
import math,sys,time
import numpy as np

MODEL_SHA='ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
MEMBERS=('initial','nodes','nodes_offsets','raw_left_cat_bitsets','raw_left_cat_bitsets_offsets','binned_left_cat_bitsets','binned_left_cat_bitsets_offsets')
PAIRS=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
MATCHINGS=((0,5),(1,4),(2,3))
MAX=sys.float_info.max
FULL=tuple((-MAX,MAX) for _ in range(62))
U=F(1,2**53);HALF_ETA=F(1,2**1075)
OWNED_CAP=128*2**20

def runtime():
    f=sys.float_info
    if (f.radix,f.mant_dig,f.min_exp,f.max_exp)!=(2,53,-1021,1024):raise ValueError('binary64 format required')
    u=float(U);normal=f.min;half=.5;eta=math.nextafter(0.,1.)
    if 1.+u!=1. or (1.+2*u)+u!=1.+4*u or eta!=math.ldexp(1.,-1074):raise ValueError('nearest-even assumption/probe')
    if normal*half!=math.ldexp(1.,-1023) or eta+eta!=math.ldexp(1.,-1073) or (normal+eta)-normal!=eta:raise ValueError('gradual underflow assumption/probe')

def rational(v):
    v=F(v)
    if max(v.numerator.bit_length(),v.denominator.bit_length())>4096:raise ValueError('exact integer limb cap')
    return v

def encode(v):
    v=rational(v);return {'encoding':'signed_hex_fraction_v1','numerator':hex(v.numerator),'denominator':hex(v.denominator)}

def pair_encode(v):return [encode(v[0]),encode(v[1])]

def directed(v,up):
    v=rational(v)
    try:f=float(v)
    except OverflowError as e:raise ValueError('outward overflow') from e
    if not math.isfinite(f):raise ValueError('outward overflow')
    if F(f)<v if up else F(f)>v:f=math.nextafter(f,math.inf if up else -math.inf)
    if not math.isfinite(f) or (F(f)<v if up else F(f)>v):raise ValueError('finite outward endpoint required')
    return F(f)

def structural(interval):
    clip=lambda v:max(F(-1,2),min(F(1),v))
    lo,hi=interval;e=4*U+2*U*U
    return max(abs(clip(clip(lo)-e)),abs(clip(clip(hi)+e)))/2+3*U/2

def summary(interval):return {'lower':encode(interval[0]),'upper':encode(interval[1]),'B':encode(structural(interval))}

def memory_plan(array_bytes=0,input_bytes=0,source_bytes=0):
    for x in (array_bytes,input_bytes,source_bytes):
        if type(x)!=int or x<0:raise ValueError('nonnegative byte counts')
    # All structural maxima are reserved before inventory allocation. Streaming
    # JSON emits one small token at a time; no full JSON text/bytes buffer exists.
    estimate=(16*2**20+4*source_bytes+2*input_bytes+6*array_bytes+
              1024*6000+512*84000+262144*100+4*135000+4*2**20)
    return {'measure':'conservative_algorithm_owned_not_RSS','estimated_owned_bytes':estimate,
            'source_bytes':source_bytes,'input_bytes':input_bytes,'array_bytes':array_bytes,
            'path_limit':6000,'edge_limit':84000,'block_limit':100,'classification_limit':135000}

class Budget:
    def __init__(self,seconds=900):
        self.started=time.monotonic();self.seconds=seconds;self.pairs=0;self.peak=0
    def check(self,owned=0):
        self.peak=max(self.peak,owned)
        if owned>OWNED_CAP:raise MemoryError('128MiB owned estimate cap')
        if time.monotonic()-self.started>=self.seconds:raise TimeoutError('producer deadline')

def restrict(box,feature,threshold,branch):
    if box is None:return None
    lo,hi=box[feature]
    if branch==0:hi=min(hi,threshold)
    elif branch==1:lo=max(lo,math.nextafter(threshold,math.inf))
    else:raise ValueError('branch code')
    if lo>hi or not math.isfinite(lo) or not math.isfinite(hi):return None
    v=list(box);v[feature]=(lo,hi);return tuple(v)

def path_box(edges):
    box=FULL
    for _,f,t,branch in edges:box=restrict(box,f,float.fromhex(t),branch)
    return box

def intersection(a,b):
    if a is None or b is None:return None
    box=tuple((max(x[0],y[0]),min(x[1],y[1])) for x,y in zip(a,b))
    return None if any(lo>hi for lo,hi in box) else box

def inventory(arrays,budget):
    if type(arrays)!=dict or set(arrays)!=set(MEMBERS):raise ValueError('seven member schema')
    if any(not isinstance(a,np.ndarray) or a.dtype.hasobject for a in arrays.values()):raise ValueError('safe arrays only')
    initial=arrays['initial'];nodes=arrays['nodes'];offsets=arrays['nodes_offsets']
    if initial.dtype!=np.dtype('f8') or initial.size!=1 or not np.isfinite(initial).all():raise ValueError('initial f8')
    if nodes.ndim!=1 or len(nodes)>11600 or offsets.dtype.kind not in 'iu' or offsets.shape!=(401,):raise ValueError('node/offset shape')
    off=[int(x) for x in offsets]
    if off[0]!=0 or off[-1]!=len(nodes) or any(not 1<=b-a<=29 for a,b in zip(off,off[1:])):raise ValueError('offset coverage')
    fields=('value','is_leaf','feature_idx','num_threshold','left','right','missing_go_to_left','is_categorical')
    if not set(fields)<=set(nodes.dtype.names or ()):raise ValueError('node fields')
    for n in fields:
        dt=nodes.dtype.fields[n][0]
        if (dt!=np.dtype('f8') if n in ('value','num_threshold') else dt.kind not in 'iu'):raise ValueError('node field dtype')
    for n in ('raw_left_cat_bitsets','binned_left_cat_bitsets'):
        a,o=arrays[n],arrays[n+'_offsets']
        if a.size or a.dtype.kind not in 'iu' or o.dtype.kind not in 'iu' or o.shape!=(401,) or np.any(o!=0):raise ValueError('categorical member exclusion')
    paths=[];edge_count=0
    for stage,(a,b) in enumerate(zip(off,off[1:])):
        budget.check();tree=nodes[a:b]
        if not np.isfinite(tree['value']).all() or not np.isfinite(tree['num_threshold']).all():raise ValueError('finite node values')
        for name in ('is_leaf','missing_go_to_left','is_categorical'):
            if np.any((tree[name]!=0)&(tree[name]!=1)):raise ValueError('binary flags')
        if np.any(tree['is_categorical']):raise ValueError('numeric-only trees')
        stack=[(0,[])];seen=set();leaves=[]
        while stack:
            j,edges=stack.pop()
            if not 0<=j<len(tree) or j in seen:raise ValueError('local tree topology')
            seen.add(j)
            if len(edges)>14:raise ValueError('path depth')
            node=tree[j]
            if node['is_leaf']:
                edge_count+=len(edges)
                leaves.append({'leaf':j,'value':float(node['value']).hex(),'edges':edges,'empty':path_box(edges) is None})
            else:
                feature=int(node['feature_idx']);threshold=float(node['num_threshold']).hex()
                if not 0<=feature<62:raise ValueError('feature dimension')
                for branch,child in ((1,int(node['right'])),(0,int(node['left']))):stack.append((child,edges+[[j,feature,threshold,branch]]))
        if len(seen)!=len(tree) or not 1<=len(leaves)<=15:raise ValueError('complete leaf topology')
        paths.append({'stage':stage,'leaves':sorted(leaves,key=lambda x:x['leaf'])})
    if edge_count>84000 or sum(len(x['leaves']) for x in paths)>6000:raise ValueError('complete inventory caps')
    return float(initial.ravel()[0]),paths,edge_count

def ordered(interval,sequences):
    low=high=None
    for seq in sequences:
        a,b=interval
        for v in seq:a,b=directed(a+v,False),directed(b+v,True)
        low=a if low is None else min(low,a);high=b if high is None else max(high,b)
    if low is None:raise ValueError('no feasible pair on nonempty D')
    return low,high

def classify(left,right,boxes,budget):
    statuses=bytearray();seqs=[];lower=upper=None
    for a in left:
        for b in right:
            budget.pairs+=1
            if budget.pairs>135000:raise ValueError('classification cap')
            if budget.pairs%64==0:budget.check()
            aa,bb=boxes[0][a['leaf']],boxes[1][b['leaf']]
            code=0 if aa is None or bb is None else 1 if intersection(aa,bb) is None else 2
            statuses.append(code)
            if code==2:
                v,w=F(float.fromhex(a['value'])),F(float.fromhex(b['value']));seqs.append((v,w));s=rational(v+w)
                lower=s if lower is None else min(lower,s);upper=s if upper is None else max(upper,s)
    if lower is None:raise ValueError('empty compatible pair')
    return statuses.hex(),seqs,(lower,upper)

def construct(arrays,budget,*,model_sha=MODEL_SHA,source_bytes=0,input_bytes=0):
    runtime()
    if type(model_sha)!=str or len(model_sha)!=64 or any(c not in '0123456789abcdef' for c in model_sha):raise ValueError('model identity')
    if type(arrays)!=dict or any(not isinstance(a,np.ndarray) for a in arrays.values()):raise ValueError('arrays mapping')
    accounting=memory_plan(sum(a.nbytes for a in arrays.values()),input_bytes,source_bytes);budget.check(accounting['estimated_owned_bytes'])
    initial,paths,edges=inventory(arrays,budget);new=old=stage0=(F(initial),F(initial));feasible=0;blocks=[]
    for row in paths:
        vals=[F(float.fromhex(p['value'])) for p in row['leaves']]
        stage0=(directed(stage0[0]+min(vals),False),directed(stage0[1]+max(vals),True))
    for j in range(100):
        budget.check(accounting['estimated_owned_bytes']);trees=paths[4*j:4*j+4]
        boxes=[{p['leaf']:path_box(p['edges']) for p in row['leaves']} for row in trees]
        pairs=[];seqs=[];pairranges=[]
        for a,b in PAIRS:
            status,seq,interval=classify(trees[a]['leaves'],trees[b]['leaves'],(boxes[a],boxes[b]),budget)
            feasible+=len(seq);seqs.append(seq);pairranges.append(interval)
            pairs.append({'stages':[4*j+a,4*j+b],'shape':[len(trees[a]['leaves']),len(trees[b]['leaves'])],'status_hex':status,'feasible':len(seq),'real_sum':pair_encode(interval)})
        mranges=[(rational(pairranges[a][0]+pairranges[b][0]),rational(pairranges[a][1]+pairranges[b][1])) for a,b in MATCHINGS]
        matched=(max(x[0] for x in mranges),min(x[1] for x in mranges))
        if matched[0]>matched[1]:raise ValueError('empty matching interval')
        adjacent1=ordered(new,seqs[0]);adjacent2=ordered(adjacent1,seqs[5]);oldout=ordered(ordered(old,seqs[0]),seqs[5])
        cart=new;steps=[];error=F(0)
        for k,row in enumerate(trees):
            values=[F(float.fromhex(p['value'])) for p in row['leaves']];pre=(rational(cart[0]+min(values)),rational(cart[1]+max(values)));mag=max(abs(pre[0]),abs(pre[1]));delta=rational(U*mag+HALF_ETA);after=(directed(pre[0],False),directed(pre[1],True));error=rational(error+delta)
            steps.append({'stage':4*j+k,'incoming':pair_encode(cart),'pre_sum':pair_encode(pre),'magnitude':encode(mag),'delta':encode(delta),'outgoing':pair_encode(after)});cart=after
        branch=(directed(new[0]+matched[0]-error,False),directed(new[1]+matched[1]+error,True));out=(max(adjacent2[0],branch[0]),min(adjacent2[1],branch[1]))
        if out[0]>out[1] or not oldout[0]<=out[0]<=out[1]<=oldout[1]:raise ValueError('machine interval nesting')
        blocks.append({'block':j,'stages':list(range(4*j,4*j+4)),'pairs':pairs,'matchings':[{'pair_indices':list(ids),'real_sum':pair_encode(v)} for ids,v in zip(MATCHINGS,mranges)],'real_sum':pair_encode(matched),'incoming':pair_encode(new),'adjacent_transfer':[pair_encode(adjacent1),pair_encode(adjacent2)],'error_steps':steps,'error_total':encode(error),'rounding_branch':pair_encode(branch),'outgoing':pair_encode(out),'original_incoming':pair_encode(old),'original_outgoing':pair_encode(oldout)})
        new,old=out,oldout
    if not stage0[0]<=old[0]<=new[0]<=new[1]<=old[1]<=stage0[1]:raise ValueError('final nesting')
    if not structural(new)<=structural(old)<=structural(stage0):raise ValueError('B nesting')
    budget.check(accounting['estimated_owned_bytes'])
    return {'schema':'FOUR_TREE_MATCHING_CERTIFICATE_V1','model_sha256':model_sha,'domain':'FINITE_X62_V1','initial':initial.hex(),'paths':paths,'blocks':blocks,'stage0':summary(stage0),'original_adjacent':summary(old),'final':summary(new),'counts':{'stages':400,'blocks':100,'paths':sum(len(x['leaves']) for x in paths),'path_edges':edges,'pair_classifications':budget.pairs,'feasible_pairs':feasible},'accounting':accounting}
