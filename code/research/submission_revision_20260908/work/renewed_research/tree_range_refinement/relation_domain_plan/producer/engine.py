"""Source-only restricted-domain producer; no array or source loading on import."""
from fractions import Fraction
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'performance_diagnosis'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pilot_engine_v2 import partition,MAX
from engine_v3 import Limits as CachedLimits
from cache_v3 import Sealed,Prefix,thaw
from domain import assert_binary64,in_domain,stamp
from schema import validate


class Limits(CachedLimits):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.oracle_calls=0;self.infeasible_queries=0


def query(box,oracle,limits,active=(),prefix=None,prechecked=False):
    assert_binary64()  # Must occur before even an authenticated root oracle call.
    if not prechecked:limits.check(active,prefix=prefix)
    point=oracle(box)
    limits.oracle_calls+=1
    limits.check(active,prefix=prefix,extra=(box,point))
    if point is None:
        limits.infeasible_queries+=1;return None
    if not in_domain(point) or not all(lo<=x<=hi for x,(lo,hi) in zip(point,box)):
        raise ValueError('invalid producer oracle witness')
    return point


def bound(stages,initial,box,enclosure,limits,oracle):
    witness=query(box,oracle,limits)
    if witness is None:
        return {'box':box,'status':'R_EMPTY','witness':None,'lower':None,'upper':None,'cuts':()}
    values=Prefix();cuts=set()
    for tree in stages:
        leaves=[];stack=[(0,box)]
        while stack:
            limits.check((cuts,leaves,stack,witness),prefix=values,visit=True)
            index,path=stack.pop()
            if query(path,oracle,limits,(cuts,leaves,stack,witness),values,prechecked=True) is None:continue
            node=tree[index]
            if node['is_leaf']:
                leaves.append(float(node['value']));continue
            feature,threshold=int(node['feature_idx']),float(node['num_threshold'])
            left,right=partition(path,feature,threshold)
            if left is not None and right is not None:cuts.add((feature,threshold))
            if right is not None:stack.append((int(node['right']),right))
            if left is not None:stack.append((int(node['left']),left))
        if not leaves:raise ValueError('R-nonempty box lacks a reachable tree leaf')
        values.append(leaves)
    limits.check((cuts,witness),prefix=values)
    result=enclosure(initial,values)
    return {'box':box,'status':'R_NONEMPTY','witness':witness,
            'lower':str(result['lower']),'upper':str(result['upper']),'cuts':tuple(sorted(cuts))}


def make_snapshot(frontier,trace):
    active=[x for x in frontier if x['status']=='R_NONEMPTY']
    if not active:raise ValueError('full root partition cannot be entirely R-empty')
    return Sealed.make({'format':'RELATION_RANGE_CHECKPOINT_V1','domain':stamp(),
        'frontier':tuple(frontier),'trace':tuple(trace),'splits':len(trace),
        'lower':str(min(Fraction(x['lower']) for x in active)),
        'upper':str(max(Fraction(x['upper']) for x in active)),
        'product_boxes':len(frontier),'r_nonempty_boxes':len(active),'r_empty_boxes':len(frontier)-len(active)})


def publish_copy(current,limits,publish):
    value=thaw(current.value);limits.check(extra=value);validate(value);publish(value)


def refine(stages,initial,enclosure,limits,publish,splits=128,dimensions=62,oracle=None):
    assert_binary64()
    if dimensions!=62 or not callable(oracle):raise ValueError('exact62-dimensional oracle required')
    first=bound(stages,initial,((-MAX,MAX),)*dimensions,enclosure,limits,oracle);first['id']=0
    current=make_snapshot((first,),());limits.install(current);limits.initialized=True
    publish_copy(current,limits,publish)
    for _ in range(splits):
        choices=[x for x in current['frontier'] if x['status']=='R_NONEMPTY' and x['cuts']]
        if not choices:return thaw(current.value),'routing_resolved'
        parent=min(choices,key=lambda x:(-(Fraction(x['upper'])-Fraction(x['lower'])),x['id']))
        feature,threshold=parent['cuts'][0];boxes=partition(parent['box'],feature,threshold)
        if any(b is None for b in boxes):raise ValueError('nonpartitioning product split')
        children=[]
        for b in boxes:
            limits.install(current,children)
            child=bound(stages,initial,b,enclosure,limits,oracle)
            if child['status']=='R_NONEMPTY' and not Fraction(parent['lower'])<=Fraction(child['lower'])<=Fraction(child['upper'])<=Fraction(parent['upper']):
                raise ValueError('nonmonotone restricted enclosure')
            child['id']=2*len(current['trace'])+1+len(children);children.append(Sealed.make(child))
        trace=current['trace']+({'parent':parent['id'],'feature':feature,'threshold':threshold,'children':[c['id'] for c in children]},)
        frontier=tuple(x for x in current['frontier'] if x['id']!=parent['id'])+tuple(c.value for c in children)
        candidate=make_snapshot(frontier,trace);limits.install(current,children)
        limits.check(extra=(thaw(candidate.value),tuple(thaw(c.value) for c in children)),sealed_extra=(candidate,))
        current=candidate;limits.completed_splits=current['splits'];limits.install(current)
        if current['splits'] in (1,4,16,64,128):publish_copy(current,limits,publish)
    return thaw(current.value),('routing_resolved' if not any(x['cuts'] for x in current['frontier'] if x['status']=='R_NONEMPTY') else 'split_budget')
