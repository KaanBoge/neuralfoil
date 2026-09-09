"""Standalone exact numeric endpoint oracle. No file, NumPy or project imports."""
import math
import sys

MAX=sys.float_info.max


def interval(a,b):
    lo=max(a[0],b[0]);hi=min(a[1],b[1])
    return (lo,hi) if lo<=hi else None


def absolute_witness(a,r):
    r=interval(r,(0.0,MAX))
    if r is None:return None
    positive=interval(a,r)
    negative=interval(a,(-r[1],-r[0]))
    chosen=positive if positive is not None else negative
    if chosen is None:return None
    value=chosen[0]
    return value,abs(value)


def order_witness(small,large):
    if small is None or large is None or small[0]>large[1]:return None
    first=small[0];second=max(large[0],first)
    return first,second


def transition_witness(top,bottom,minimum,maximum):
    pair=order_witness(interval(top,minimum),interval(bottom,maximum))
    if pair is not None:
        t,b=pair
    else:
        pair=order_witness(interval(bottom,minimum),interval(top,maximum))
        if pair is None:return None
        b,t=pair
    return t,b,min(t,b),max(t,b)


def validate(box):
    if sys.float_info.radix!=2 or sys.float_info.mant_dig!=53 or sys.float_info.max_exp!=1024:
        raise RuntimeError('binary64 Python float required')
    if type(box) not in (list,tuple) or len(box)!=62:raise ValueError('62 endpoint pairs required')
    for pair in box:
        if type(pair) not in (list,tuple) or len(pair)!=2:raise ValueError('endpoint pair')
        if any(type(x) is not float or not math.isfinite(x) for x in pair):raise ValueError('finite binary64 endpoints')
        if pair[0]>pair[1]:raise ValueError('reversed interval')


def feasible(box):
    validate(box)
    a=absolute_witness(box[0],box[16])
    if a is None:return {'feasible':False,'witness':None,'reason':'absolute_block'}
    t=transition_witness(box[12],box[13],box[18],box[19])
    if t is None:return {'feasible':False,'witness':None,'reason':'transition_block'}
    witness=[pair[0] for pair in box]
    witness[0],witness[16]=a
    witness[12],witness[13],witness[18],witness[19]=t
    return {'feasible':True,'witness':witness,'reason':'explicit_binary64_witness'}


def valid_witness(box,x):
    """Direct guard/membership evaluation, independent of construction cases."""
    validate(box)
    return (type(x) in (list,tuple) and len(x)==62 and
            all(type(v) is float and math.isfinite(v) and lo<=v<=hi for v,(lo,hi) in zip(x,box)) and
            x[16]==abs(x[0]) and x[18]==min(x[12],x[13]) and x[19]==max(x[12],x[13]))
