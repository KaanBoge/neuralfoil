"""Source/synthetic successor only: identical numeric routing, cached accounting."""
from fractions import Fraction
import sys
import time
from pilot_engine_v2 import Budget,owned_size,partition,MAX
from cache_v3 import Sealed,Prefix,thaw


class Limits:
    def __init__(self,stages,seconds=120,visits=4000000,memory=128*1024*1024,audit=None):
        self.deadline=time.monotonic()+seconds;self.visits=0;self.max_visits=visits
        self.memory=memory;self.stages=tuple(stages)
        if any(t.flags.writeable for t in self.stages):raise ValueError('read-only stages')
        self.static_owned_size=owned_size(self.stages)+sys.getsizeof((None,None,None))
        self.current=None;self.children=();self.has_children=False;self.completed_splits=0;self.initialized=False
        self.peak_estimate=0;self.audit=audit

    def install(self,current,children=None):
        if current is not None and not isinstance(current,Sealed):raise TypeError('sealed current')
        if children is not None and any(not isinstance(c,Sealed) for c in children):raise TypeError('sealed children')
        self.current=current;self.has_children=children is not None;self.children=tuple(children or ())

    def check(self,active=(),prefix=None,extra=(),sealed_extra=(),visit=False):
        if visit:
            if self.visits>=self.max_visits:raise Budget('node visit budget')
            self.visits+=1
        if time.monotonic()>=self.deadline:raise Budget('search time budget')
        # Charge immutable components separately; overlap is deliberately charged
        # again. Every mutable active component still receives full recursion.
        persistent=(self.current.charge if self.current else 0)+sum(c.charge for c in self.children)
        if any(not isinstance(c,Sealed) for c in sealed_extra):raise TypeError('sealed extra')
        persistent+=sum(c.charge for c in sealed_extra)
        bookkeeping=(sys.getsizeof(self)+owned_size(tuple(self.__dict__.keys()))+
                     sys.getsizeof(self.__dict__)+sys.getsizeof(self.children)+
                     sys.getsizeof([None for _ in self.children])+1024)
        prefix_charge=prefix.charge() if prefix is not None else 0
        estimate=3*(self.static_owned_size+persistent+prefix_charge+
                    owned_size((active,extra))+bookkeeping)+8*1024*1024
        self.peak_estimate=max(self.peak_estimate,estimate)
        if self.audit is not None:
            # Debug comparison against unchanged V2 whole-graph recursion.
            # Debug allocations are testing instrumentation, not enabled in runs.
            current=thaw(self.current.value) if self.current else ()
            children=[thaw(c.value) for c in self.children]
            persistent_ref=(current,children) if self.has_children else current
            transient=(prefix.reference(),*active) if prefix is not None else active
            original=3*(self.static_owned_size+owned_size((persistent_ref,transient,extra)))+8*1024*1024
            self.audit(estimate,original,visit,(persistent_ref,transient))
        if estimate>self.memory:raise Budget('algorithm-owned allocation estimate budget')


def bound(stages,initial,box,enclosure,limits):
    values=Prefix();cuts=set()
    for tree in stages:
        leaves=[];stack=[(0,box)]
        while stack:
            limits.check((cuts,leaves,stack),prefix=values,visit=True)
            index,path=stack.pop();node=tree[index]
            if node['is_leaf']:
                leaves.append(float(node['value']));continue
            feature,threshold=int(node['feature_idx']),float(node['num_threshold'])
            left,right=partition(path,feature,threshold)
            if left is not None and right is not None:cuts.add((feature,threshold))
            if right is not None:stack.append((int(node['right']),right))
            if left is not None:stack.append((int(node['left']),left))
        if not leaves:raise ValueError('nonempty box without reachable leaf')
        values.append(leaves)
    limits.check((cuts,),prefix=values)
    result=enclosure(initial,values)
    return {'box':box,'lower':str(result['lower']),'upper':str(result['upper']),'cuts':tuple(sorted(cuts))}


def make_snapshot(frontier,trace):
    return Sealed.make({'frontier':tuple(frontier),'trace':tuple(trace),
                       'lower':str(min(Fraction(x['lower']) for x in frontier)),
                       'upper':str(max(Fraction(x['upper']) for x in frontier)),
                       'splits':len(trace)})


def publish_copy(current,limits,publish):
    value=thaw(current.value)
    limits.check(extra=value)
    publish(value)  # No mutable object in this copy aliases the sealed snapshot.


def refine(stages,initial,enclosure,limits,publish,splits=128,dimensions=62):
    first=bound(stages,initial,((-MAX,MAX),)*dimensions,enclosure,limits);first['id']=0
    current=make_snapshot((first,),());limits.install(current);limits.initialized=True
    publish_copy(current,limits,publish)
    for _ in range(splits):
        choices=[x for x in current['frontier'] if x['cuts']]
        if not choices:return thaw(current.value),'routing_resolved'
        parent=min(choices,key=lambda x:(-(Fraction(x['upper'])-Fraction(x['lower'])),x['id']))
        feature,threshold=parent['cuts'][0];boxes=partition(parent['box'],feature,threshold)
        if any(b is None for b in boxes):raise ValueError('nonpartitioning frontier split')
        children=[]
        for b in boxes:
            limits.install(current,children)
            child=bound(stages,initial,b,enclosure,limits)
            if not Fraction(parent['lower'])<=Fraction(child['lower'])<=Fraction(child['upper'])<=Fraction(parent['upper']):raise ValueError('nonmonotone enclosure')
            child['id']=2*len(current['trace'])+1+len(children)
            children.append(Sealed.make(child))
        trace=current['trace']+({'parent':parent['id'],'feature':feature,'threshold':threshold,'children':[c['id'] for c in children]},)
        frontier=tuple(x for x in current['frontier'] if x['id']!=parent['id'])+tuple(c.value for c in children)
        candidate=make_snapshot(frontier,trace)
        limits.install(current,children)
        limits.check(extra=(thaw(candidate.value),tuple(thaw(c.value) for c in children)),sealed_extra=(candidate,))
        current=candidate;limits.completed_splits=current['splits'];limits.install(current)
        if current['splits'] in (1,4,16,64,128):publish_copy(current,limits,publish)
    return thaw(current.value),('routing_resolved' if not any(x['cuts'] for x in current['frontier']) else 'split_budget')
