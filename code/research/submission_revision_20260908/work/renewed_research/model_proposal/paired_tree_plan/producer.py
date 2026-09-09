"""Complete adjacent leaf-pair certificates; caller supplies authenticated arrays."""
from fractions import Fraction
import itertools, math, sys
import numpy as np
from support import MEMBERS, MODEL_SHA, fraction, runtime

REL=(0,12,13,16,18,19)
FULL=tuple((-sys.float_info.max,sys.float_info.max) for _ in range(62))
SCHEMA='PAIRED_TREE_CERTIFICATE_V1'
DOMAIN_IDS={'D':'FINITE_X62_V1','R':'FINITE_X62_ABS_MINMAX_NUMERIC_V1'}

def path_box(edges):
    box=list(FULL)
    for e in edges:
        f,t=e['feature'],float.fromhex(e['threshold']);lo,hi=box[f]
        if e['branch']=='L': hi=min(hi,t)
        else: lo=max(lo,math.nextafter(t,math.inf))
        if lo>hi: return None
        box[f]=(lo,hi)
    return tuple(box)

def intersect(a,b):
    if a is None or b is None:return None
    out=[]
    for (al,au),(bl,bu) in zip(a,b):
        lo,hi=max(al,bl),min(au,bu)
        if lo>hi:return None
        out.append((lo,hi))
    return tuple(out)

def enumerate_paths(stages,budget):
    paths=[];edges_total=0
    for s,tree in enumerate(stages):
        budget.check()
        if len(tree)>29:raise ValueError('29 nodes per tree cap')
        todo=[(0,[])];local=[]
        while todo:
            j,edges=todo.pop();node=tree[j]
            if len(edges)>14:raise ValueError('path depth cap')
            if node['is_leaf']:
                edges_total+=len(edges)
                local.append({'stage':s,'leaf':j,'value':float(node['value']).hex(),'edges':edges,'empty':path_box(edges) is None})
            else:
                base={'node':j,'feature':int(node['feature_idx']),'threshold':float(node['num_threshold']).hex()}
                todo.append((int(node['right']),edges+[dict(base,branch='R')]))
                todo.append((int(node['left']),edges+[dict(base,branch='L')]))
        if not 1<=len(local)<=15:raise ValueError('leaf cap')
        paths.append(sorted(local,key=lambda p:p['leaf']))
    if sum(map(len,paths))>6000 or edges_total>84000:raise ValueError('inventory cap')
    return paths,edges_total

def estimated_bytes(arrays,paths,edges,pair_count):
    # Arrays/input/decode/evaluator/stage copies; Python path/edge structures;
    # retained pair records including 6 witness strings; block temporaries;
    # exact integers <=~2200 bits and final serialization transient reserve.
    return (16*2**20 + 6*sum(a.nbytes for a in arrays.values()) +
            1024*sum(map(len,paths))+512*edges+768*pair_count+4*2**20)

def propagate(lo,hi,sequences,paired):
    low=[];high=[]
    for seq in sequences:
        a,b=lo,hi
        for v in seq:
            a=paired._directed(a+Fraction.from_float(v),False)
            b=paired._directed(b+Fraction.from_float(v),True)
        low.append(a);high.append(b)
    if not low:raise ValueError('nonempty domain has empty block')
    return min(low),max(high)

def construct(arrays,deps,budget,checkpoint=None,model_sha=MODEL_SHA):
    runtime()
    if set(arrays)!=set(MEMBERS):raise ValueError('exact member set')
    if any(not isinstance(a,np.ndarray) or a.dtype.hasobject for a in arrays.values()):raise ValueError('safe arrays required')
    if len(arrays['nodes'])>11600:raise ValueError('node cap')
    model=deps['evaluator'].SequentialHist(arrays)
    stages=model.stages;paths,edges=enumerate_paths(stages,budget)
    owned=lambda pc:estimated_bytes(arrays,paths,edges,pc)
    budget.check(owned(0))
    initial=model.initial
    leaves=[[float.fromhex(p['value']) for p in ps] for ps in paths]
    stage0=deps['numeric'].sequential_range(initial,leaves)
    cartesian=[list(itertools.product(leaves[2*j],leaves[2*j+1])) for j in range(200)]
    cart=deps['paired'].enclose(initial,cartesian)
    if (cart['lower'],cart['upper'])!=(stage0['lower'],stage0['upper']):raise ValueError('Cartesian/Stage0 mismatch')
    del cartesian
    result={'schema':SCHEMA,'model_sha256':model_sha,'initial':initial.hex(),
            'paths':[p for ps in paths for p in ps],'domains':{},
            'stage0':{'lower':fraction(stage0['lower']),'upper':fraction(stage0['upper']),'B':fraction(deps['numeric'].structural_bound(stage0['lower'],stage0['upper']))},'summary':{},'counts':{}}
    attempted=0;bounds={}
    for domain in ('D','R'):
        lo=hi=Fraction.from_float(initial);blocks=[];feasible_count=0
        for j in range(200):
            budget.check(owned(attempted))
            left,right=paths[2*j],paths[2*j+1]
            boxes={p['stage']*32+p['leaf']:path_box(p['edges']) for p in left+right}
            records=[];seqs=[]
            for a,b in itertools.product(left,right):
                attempted+=1;budget.pairs=attempted
                if attempted>90000:raise ValueError('pair cap')
                if attempted%64==0:budget.check(owned(attempted))
                aa,bb=boxes[a['stage']*32+a['leaf']],boxes[b['stage']*32+b['leaf']]
                box=intersect(aa,bb);w=None
                if aa is None or bb is None: status='path_empty'
                elif box is None:status='intersection_empty'
                else:
                    w=tuple(t[0] for t in box) if domain=='D' else deps['oracle'].feasible_witness(box)
                    status='feasible' if w is not None else 'R_infeasible'
                records.append({'leaves':[a['leaf'],b['leaf']],'status':status,
                                'witness':None if w is None else [w[k].hex() for k in REL]})
                if w is not None:
                    feasible_count+=1;seqs.append((float.fromhex(a['value']),float.fromhex(b['value'])))
            incoming=[fraction(lo),fraction(hi)]
            lo,hi=propagate(lo,hi,seqs,deps['paired'])
            blocks.append({'block':j,'stages':[2*j,2*j+1],'pairs':records,'incoming':incoming,'outgoing':[fraction(lo),fraction(hi)]})
            if checkpoint is not None and (j+1)%20==0:
                checkpoint(domain,j+1,{'completed_blocks':j+1,'lower':fraction(lo),'upper':fraction(hi),'pair_attempts':attempted})
        bounds[domain]=(lo,hi)
        result['domains'][domain]={'id':DOMAIN_IDS[domain],'blocks':blocks}
        result['summary'][domain]={'lower':fraction(lo),'upper':fraction(hi),'B':fraction(deps['numeric'].structural_bound(lo,hi)),
                                   'attempted_pairs':sum(len(b['pairs']) for b in blocks),'feasible_pairs':feasible_count}
    if not stage0['lower']<=bounds['D'][0]<=bounds['R'][0]<=bounds['R'][1]<=bounds['D'][1]<=stage0['upper']:raise ValueError('nesting invariant')
    result['counts']={'stages':400,'blocks_per_domain':200,'paths':sum(map(len,paths)),'path_edges':edges,'attempted_pairs':attempted}
    budget.check(owned(attempted))
    return result
