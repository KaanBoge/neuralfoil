"""Independent restricted-domain checker. No producer oracle/engine imports.

Caller must supply the existing authenticated, validated numeric-only stages
and unchanged authenticated outward enclosure. This module never loads models.
"""
from pathlib import Path
from fractions import Fraction
import math,sys,time,hashlib,importlib.util
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def _module(path,pin,name):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('independent dependency hash')
    import types
    m=types.ModuleType(name);exec(compile(raw,str(path),'exec'),m.__dict__);return m
coverage=_module(ROOT/'tree_range_refinement/pilot_checker.py','bf4c1c19b5d93d93801b4a03a386ae473f39315faf0e8933b2d763e422f67089','independent_product_coverage')
oracle=_module(ROOT/'tree_range_refinement/feature_relation_oracle_review/oracle.py','e9c94a3105ab4305c430ec8e3c14bfbc880eebe1df2cbef9ba15a5ac0dcf0a11','independent_relation_oracle')
DOMAIN={'id':'FINITE_X62_ABS_MINMAX_NUMERIC_V1','dimensions':62,'relations':['X16=abs(X0)','X18=min(X12,X13)','X19=max(X12,X13)'],'equality':'numeric_signed_zero_equal','finite_binary64':True,'guard_source_sha256':'1f175bdfe40e0e13451963bb4752e2d5903592f0f92c07246038c96e1b8c0127'}
TOP={'format','domain','frontier','trace','lower','upper','splits','product_boxes','r_nonempty_boxes','r_empty_boxes'}
ROW={'id','box','lower','upper','cuts','status','witness'}
def rational(x):
    if type(x) is not str:raise ValueError('rational string required')
    try:q=Fraction(x)
    except (ValueError,ZeroDivisionError):raise ValueError('invalid rational')
    if str(q)!=x:raise ValueError('canonical rational required')
    return q
def schema(checkpoint,dimensions):
    if sys.float_info.radix!=2 or sys.float_info.mant_dig!=53 or sys.float_info.max_exp!=1024:raise RuntimeError('binary64 required')
    if type(dimensions) is not int or dimensions!=62:raise ValueError('62 dimensions')
    if type(checkpoint) is not dict or set(checkpoint)!=TOP:raise ValueError('checkpoint schema')
    if checkpoint['format']!='RELATION_RANGE_CHECKPOINT_V1':raise ValueError('format')
    d=checkpoint['domain']
    if type(d) is not dict or set(d)!=set(DOMAIN) or d!=DOMAIN or type(d['dimensions']) is not int or type(d['finite_binary64']) is not bool:raise ValueError('fixed domain')
    if type(d['relations']) is not list:raise ValueError('relation list')
    if type(checkpoint['frontier']) not in (list,tuple) or type(checkpoint['trace']) not in (list,tuple):raise ValueError('container schema')
    for key in ['product_boxes','r_nonempty_boxes','r_empty_boxes','splits']:
        if type(checkpoint[key]) is not int or checkpoint[key]<0:raise ValueError('count schema')
    active=0;projected=[]
    for row in checkpoint['frontier']:
        if type(row) is not dict or set(row)!=ROW:raise ValueError('row schema')
        cuts=row['cuts']
        if type(cuts) not in (tuple,list):raise ValueError('cuts schema')
        normalized=[]
        for cut in cuts:
            if type(cut) not in (tuple,list) or len(cut)!=2 or type(cut[0]) is not int or not 0<=cut[0]<62 or type(cut[1]) is not float or not math.isfinite(cut[1]):raise ValueError('cut schema')
            normalized.append(tuple(cut))
        if normalized!=sorted(set(normalized)):raise ValueError('cuts not unique sorted')
        if row['status']=='R_EMPTY':
            if row['witness'] is not None or row['lower'] is not None or row['upper'] is not None or cuts:raise ValueError('empty fields')
        elif row['status']=='R_NONEMPTY':
            active+=1
            if rational(row['lower'])>rational(row['upper']):raise ValueError('range reversed')
            if not oracle.valid_witness(row['box'],row['witness']):raise ValueError('invalid witness')
        else:raise ValueError('row status')
        # Numeric placeholders are checker-created coverage scaffolding only.
        projected.append({'id':row['id'],'box':row['box'],'lower':'0','upper':'0','cuts':()})
    if active==0 or checkpoint['product_boxes']!=len(projected) or checkpoint['r_nonempty_boxes']!=active or checkpoint['r_empty_boxes']!=len(projected)-active:raise ValueError('domain counts')
    if rational(checkpoint['lower'])>rational(checkpoint['upper']):raise ValueError('global range reversed')
    projection={'frontier':projected,'trace':checkpoint['trace'],'lower':'0','upper':'0','splits':checkpoint['splits']}
    return coverage.full_cover(projection,dimensions)
def replay(checkpoint,stages,initial,enclosure,dimensions=62,deadline=None):
    boxes=schema(checkpoint,dimensions);visits=0;calls=0;bounds=[]
    if type(initial) is not float or not math.isfinite(initial):raise ValueError('finite initial')
    for row in checkpoint['frontier']:
        box=boxes[row['id']]
        if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('checker deadline')
        decision=oracle.feasible(box);calls+=1
        if decision['feasible']!=(row['status']=='R_NONEMPTY'):raise ValueError('forged domain status')
        if not decision['feasible']:continue
        values=[]
        for tree in stages:
            leaves=[];todo=[(0,{},{})]
            while todo:
                if deadline is not None and time.monotonic()>=deadline:raise TimeoutError('checker deadline')
                j,lower,upper=todo.pop();visits+=1
                path=list(box);impossible=False
                for feature in lower.keys()|upper.keys():
                    lo=max(box[feature][0],lower.get(feature,-math.inf));hi=min(box[feature][1],upper.get(feature,math.inf))
                    if lo>hi:impossible=True;break
                    path[feature]=(lo,hi)
                if impossible:continue
                calls+=1
                if not oracle.feasible(path)['feasible']:continue
                node=tree[j]
                if node['is_leaf']:leaves.append(float(node['value']));continue
                feature,t=int(node['feature_idx']),float(node['num_threshold'])
                u=dict(upper);u[feature]=min(u.get(feature,math.inf),t)
                l=dict(lower);l[feature]=max(l.get(feature,-math.inf),math.nextafter(t,math.inf))
                todo.append((int(node['right']),l,dict(upper)));todo.append((int(node['left']),dict(lower),u))
            if not leaves:raise ValueError('nonempty box has no retained leaf')
            values.append(leaves)
        result=enclosure(initial,values);lo,hi=Fraction(result['lower']),Fraction(result['upper'])
        if lo!=rational(row['lower']) or hi!=rational(row['upper']):raise ValueError('restricted local range mismatch')
        bounds.append((lo,hi))
    lo,hi=min(x[0] for x in bounds),max(x[1] for x in bounds)
    if lo!=rational(checkpoint['lower']) or hi!=rational(checkpoint['upper']):raise ValueError('global range mismatch')
    return {'status':'PASS_RESTRICTED_DOMAIN_REPLAY','domain':dict(DOMAIN),'lower':str(lo),'upper':str(hi),'boxes':len(boxes),'r_nonempty_boxes':len(bounds),'r_empty_boxes':len(boxes)-len(bounds),'splits':checkpoint['splits'],'replay_node_visits':visits,'replay_oracle_calls':calls}
