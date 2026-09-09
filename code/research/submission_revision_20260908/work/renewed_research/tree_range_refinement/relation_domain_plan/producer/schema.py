"""Producer envelope validation; independent checker separately proves coverage."""
from fractions import Fraction
import json
import math
from domain import stamp,in_domain

TOP={'format','domain','frontier','trace','lower','upper','splits','product_boxes','r_nonempty_boxes','r_empty_boxes'}
ROW={'id','box','lower','upper','cuts','status','witness'}


def rational(x):
    if type(x) is not str:raise ValueError('rational string required')
    value=Fraction(x)
    if str(value)!=x:raise ValueError('canonical rational required')
    return value


def validate(value):
    if type(value) is not dict or set(value)!=TOP or value['format']!='RELATION_RANGE_CHECKPOINT_V1':raise ValueError('checkpoint schema')
    if json.dumps(value['domain'],sort_keys=True,allow_nan=False)!=json.dumps(stamp(),sort_keys=True):raise ValueError('domain stamp')
    for key in ('splits','product_boxes','r_nonempty_boxes','r_empty_boxes'):
        if type(value[key]) is not int or value[key]<0:raise ValueError('integer counts')
    if type(value['frontier']) not in (list,tuple) or type(value['trace']) not in (list,tuple):raise ValueError('checkpoint containers')
    if value['splits']>128 or value['splits']!=len(value['trace']) or value['product_boxes']!=value['splits']+1:raise ValueError('split count')
    for event in value['trace']:
        if type(event) is not dict or set(event)!={'parent','feature','threshold','children'}:raise ValueError('event schema')
        if type(event['parent']) is not int or type(event['feature']) is not int or not 0<=event['feature']<62:raise ValueError('event indices')
        if type(event['threshold']) is not float or not math.isfinite(event['threshold']):raise ValueError('event threshold')
        if type(event['children']) not in (tuple,list) or len(event['children'])!=2 or any(type(c) is not int for c in event['children']):raise ValueError('event children')
    seen=set();active=[];empty=0
    for row in value['frontier']:
        if type(row) is not dict or set(row)!=ROW:raise ValueError('row schema')
        if type(row['id']) is not int or row['id']<0 or row['id'] in seen:raise ValueError('row identity')
        seen.add(row['id']);box=row['box']
        if type(box) not in (tuple,list) or len(box)!=62:raise ValueError('box shape')
        for pair in box:
            if type(pair) not in (tuple,list) or len(pair)!=2 or any(type(x) is not float or not math.isfinite(x) for x in pair) or pair[0]>pair[1]:raise ValueError('box intervals')
        cuts=row['cuts']
        if type(cuts) not in (tuple,list):raise ValueError('cut list')
        for cut in cuts:
            if type(cut) not in (tuple,list) or len(cut)!=2 or type(cut[0]) is not int or not 0<=cut[0]<62 or type(cut[1]) is not float or not math.isfinite(cut[1]):raise ValueError('cut schema')
        if [tuple(c) for c in cuts]!=sorted(set(tuple(c) for c in cuts)):raise ValueError('cut ordering')
        if row['status']=='R_EMPTY':
            if row['witness'] is not None or row['lower'] is not None or row['upper'] is not None or len(cuts):raise ValueError('empty row')
            empty+=1
        elif row['status']=='R_NONEMPTY':
            witness=row['witness']
            if not in_domain(witness) or not all(lo<=x<=hi for x,(lo,hi) in zip(witness,box)):raise ValueError('row witness')
            lo,hi=rational(row['lower']),rational(row['upper'])
            if lo>hi:raise ValueError('reversed bound')
            active.append((lo,hi))
        else:raise ValueError('row status')
    if not active or value['product_boxes']!=len(seen) or value['r_nonempty_boxes']!=len(active) or value['r_empty_boxes']!=empty:raise ValueError('frontier counts')
    if rational(value['lower'])!=min(x[0] for x in active) or rational(value['upper'])!=max(x[1] for x in active):raise ValueError('global bound')
    return value
