"""Synthetic-only numeric-tree box refinement. No imports of project artifacts."""
from dataclasses import dataclass
from fractions import Fraction
import math
import sys

MAX=sys.float_info.max

@dataclass(frozen=True)
class Leaf:
    value: float

@dataclass(frozen=True)
class Split:
    feature: int
    threshold: float
    left: object
    right: object

class VisitBudget(Exception):
    pass

def validate(trees,dimensions):
    if type(dimensions) is not int or dimensions<1:raise ValueError('positive dimensions')
    if not trees:raise ValueError('nonempty ensemble')
    for tree in trees:
        seen=set();stack=[tree]
        while stack:
            node=stack.pop()
            if id(node) in seen:raise ValueError('cycle or shared child')
            seen.add(id(node))
            if isinstance(node,Leaf):
                if type(node.value) is not float or not math.isfinite(node.value):raise ValueError('finite binary64 leaf')
            elif isinstance(node,Split):
                if type(node.feature) is not int or not 0<=node.feature<dimensions:raise ValueError('feature index')
                if type(node.threshold) is not float or not math.isfinite(node.threshold):raise ValueError('finite binary64 threshold')
                stack.extend([node.left,node.right])
            else:raise ValueError('unsupported node')

def full_box(dimensions):
    return tuple((-MAX,MAX) for _ in range(dimensions))

def split_box(box,feature,threshold):
    lo,hi=box[feature]
    def child(a,b):
        if a>b or not math.isfinite(a) or not math.isfinite(b):return None
        out=list(box);out[feature]=(a,b);return tuple(out)
    return child(lo,min(hi,threshold)),child(max(lo,math.nextafter(threshold,math.inf)),hi)

def reachable(tree,box,visits=None):
    values=[];cuts=set();stack=[(tree,box)]
    while stack:
        node,current=stack.pop()
        if visits is not None:
            visits['count']+=1
            if visits['count']>visits['limit']:raise VisitBudget('node-visit limit')
        if isinstance(node,Leaf):
            values.append(node.value);continue
        left,right=split_box(current,node.feature,node.threshold)
        if left is not None and right is not None:cuts.add((node.feature,node.threshold))
        if right is not None:stack.append((node.right,right))
        if left is not None:stack.append((node.left,left))
    if not values:raise ValueError('nonempty box must reach a leaf')
    return values,cuts

def box_bound(trees,box,initial,enclose,visits=None):
    stages=[];cuts=set()
    for tree in trees:
        values,more=reachable(tree,box,visits);stages.append(values);cuts.update(more)
    raw=enclose(initial,stages)
    lo,hi=Fraction(raw['lower']),Fraction(raw['upper'])
    if lo>hi:raise ValueError('reversed enclosure')
    return {'box':box,'lower':lo,'upper':hi,'cuts':tuple(sorted(cuts))}

def refine(trees,dimensions,initial,enclose,max_splits=16,max_visits=200000):
    """Return the last sound full frontier; failed child cannot remove parent."""
    trees=tuple(trees);validate(trees,dimensions)
    if type(initial) is not float or not math.isfinite(initial):raise ValueError('finite initial')
    if type(max_splits) is not int or max_splits<0:raise ValueError('split budget')
    if type(max_visits) is not int or max_visits<1:raise ValueError('visit budget')
    visits={'count':0,'limit':max_visits}
    first=box_bound(trees,full_box(dimensions),initial,enclose,visits)
    first['id']=0;frontier={0:first};trace=[];next_id=1;failure=None
    history=[(first['lower'],first['upper'])]
    stop='split_budget'
    for _ in range(max_splits):
        available=[v for v in frontier.values() if v['cuts']]
        if not available:stop='routing_resolved';break
        parent=min(available,key=lambda v:(-(v['upper']-v['lower']),v['id']))
        feature,threshold=parent['cuts'][0]
        left,right=split_box(parent['box'],feature,threshold)
        if left is None or right is None:raise ValueError('nonpartitioning split')
        try:
            children=[box_bound(trees,b,initial,enclose,visits) for b in [left,right]]
            for c in children:
                if not parent['lower']<=c['lower']<=c['upper']<=parent['upper']:
                    raise ValueError('child enclosure is not nested')
        except (VisitBudget,ValueError,RuntimeError) as exc:
            stop='incomplete_expansion_preserved_parent';failure=type(exc).__name__+': '+str(exc);break
        for c in children:c['id']=next_id;next_id+=1
        del frontier[parent['id']]
        for c in children:frontier[c['id']]=c
        trace.append({'parent':parent['id'],'feature':feature,'threshold':threshold,'children':[c['id'] for c in children]})
        history.append((min(v['lower'] for v in frontier.values()),max(v['upper'] for v in frontier.values())))
    if not any(v['cuts'] for v in frontier.values()):stop='routing_resolved'
    return {'lower':history[-1][0],'upper':history[-1][1],'frontier':tuple(frontier.values()),
            'trace':trace,'history':history,'node_visits':visits['count'],'stop':stop,'failure':failure,
            'scope':'synthetic full finite binary64 domain; outward bounds not necessarily attained'}

def predict(trees,initial,x):
    if any(type(v) is not float or not math.isfinite(v) for v in x):raise ValueError('finite float input')
    out=initial
    for tree in trees:
        node=tree
        while isinstance(node,Split):node=node.left if x[node.feature]<=node.threshold else node.right
        out=out+node.value
        if not math.isfinite(out):raise ValueError('sequential overflow')
    return out
