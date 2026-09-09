"""Literal request measurement with exact post-checks and input isolation."""
import time
import numpy as np
from serving import ROUTES,COHORTS,QUALIFIED,exact
from timing import schedule
from loader_v2 import same
def snapshot(serv):return {c:{k:v.copy() for k,v in w.items() if isinstance(v,np.ndarray)} for c,w in serv.workload.items()}
def unchanged(serv,before):
    for c,w in before.items():
        for k,v in w.items():same(serv.workload[c][k],v,'input mutation '+c+'/'+k)
def valid(serv,result):
    for c in COHORTS:
        keys=[k for k in result if k.startswith(c+'/')]
        if not keys:raise ValueError('missing cohort output')
        n=len(serv.workload[c]['alpha'])
        for key in keys:
            a=np.asarray(result[key])
            if a.ndim<1 or len(a)!=n or a.dtype.kind not in 'fbiu' or not np.isfinite(a).all():raise ValueError('output shape/dtype/finite')
            field=key.split('/',1)[1]
            if field in ['CD','raw_CD','quantized_CD','BASE_CD','XLARGE_CD','all_model_CD','core','anchor'] and (a<=0).any():raise ValueError('nonpositive CD')
            if field in ['gate','intervened'] and a.dtype!=bool:raise ValueError('nonboolean output')
def measured(serv,route,expected,clock=time.perf_counter):
    before=snapshot(serv)
    start=clock();value=serv.request(route);elapsed=clock()-start
    unchanged(serv,before);valid(serv,value);exact(value,expected)
    return elapsed
def preflight(serv,refs):
    result={}
    for route in ROUTES:
        before=snapshot(serv);d=serv.request(route,diagnostics=True)
        unchanged(serv,before);valid(serv,d)
        for c in COHORTS:
            r=refs[c]
            if route in ROUTES[:2]:same(d[c+'/quantized_CD'],r['features']['XLARGE_CD' if route==ROUTES[0] else 'BASE_CD'],'baseline')
            else:
                for k,v in r['features'].items():
                    if k not in ['alpha','Re','airfoil']:same(d[c+'/'+k],v,k)
                if route==ROUTES[2]:same(d[c+'/CD'],r['original'],'original native CD')
                else:
                    z=r['kl'] if '_kl_' in route else r['native']
                    for field,suffix in [('CD',''),('strength','__strength'),('effective_fraction','__effective_fraction'),('intervened','__intervened')]:same(d[c+'/'+field],z[route+suffix],field)
                    for k in ['core','anchor','gate']:same(d[c+'/'+k],r['native'][k],k)
                gate=serv.workload[c]['gate'];same(d[c+'/CD'][~gate],r['features']['BASE_CD'][~gate],'fallback')
        before=snapshot(serv);value=serv.request(route)
        unchanged(serv,before);valid(serv,value)
        # The timed normal return must match its already archived-checked fields.
        exact(value,{key:d[key] for key in value})
        result[route]=value
    return result
def warm(serv,refs,emit):
    counts={'untimed_fidelity_requests':0,'untimed_warmup_requests':0,'timed_requests':0}
    for _ in range(3):
        for route in ROUTES:
            before=snapshot(serv);value=serv.request(route);unchanged(serv,before);valid(serv,value);exact(value,refs[route])
            counts['untimed_fidelity_requests' if _==0 else 'untimed_warmup_requests']+=1
    for repeat,route in schedule():
        emit({'repeat':repeat,'route':route,'seconds':measured(serv,route,refs[route]),'output_rows':497})
        counts['timed_requests']+=1
    if counts!={'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49}:raise ValueError('warm schedule counts')
    return counts
