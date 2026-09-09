"""Untimed exact fidelity barrier. Caller must authenticate all supplied sources.

No I/O, model construction or inference on import. This module is not a runner
and supplies no approval or bypass around the frozen parent resource guards.
"""
import numpy as np
from feature_adapter import calc_with_foil,predict_base_with_foil
from response_snapshot import ResponseSnapshot
from serving_optimized import ROUTES,COHORTS
import measurement_v5 as frozen_measurement

def same(a,b,path='value'):
    if isinstance(a,dict) and isinstance(b,dict):
        if a.keys()!=b.keys():raise ValueError('key mismatch '+path)
        for k in a:same(a[k],b[k],path+'/'+k)
    elif isinstance(a,(tuple,list)) and type(a) is type(b):
        if len(a)!=len(b):raise ValueError('length mismatch '+path)
        for j,(x,y) in enumerate(zip(a,b)):same(x,y,path+'/'+str(j))
    else:
        x=np.asarray(a);y=np.asarray(b)
        if x.dtype.hasobject or y.dtype.hasobject or x.shape!=y.shape or x.dtype!=y.dtype or x.tobytes(order='C')!=y.tobytes(order='C'):raise ValueError('bit mismatch '+path)

def audit_geometry_block(math,asb,coordinates,alpha,re):
    """Independent original three-fit and complete response comparison, untimed."""
    before=[x.copy() for x in [coordinates,alpha,re]]
    foils=[asb.Airfoil(name=n,coordinates=coordinates).to_kulfan_airfoil() for n in ['shape_sensitivity','transition_sensitivity','external_evaluation']]
    params=[ResponseSnapshot(f.kulfan_parameters) for f in foils]
    same(params[0].copy(),params[1].copy(),'original shape/transition Kulfan')
    same(params[0].copy(),params[2].copy(),'original shape/teacher Kulfan')
    # Separate object for the optimized block, using unchanged shape construction.
    shared=asb.Airfoil(name='shape_sensitivity',coordinates=coordinates).to_kulfan_airfoil()
    shared_params=ResponseSnapshot(shared.kulfan_parameters)
    same(shared_params.copy(),params[0].copy(),'reused Kulfan')
    sensitivity,retained=calc_with_foil(coordinates,alpha,re,shared,math)
    # Reproduce every original call position, not an isolated differently batched call.
    original_sensitivity=None
    for ncrit in math.GRID:
        result=foils[1].get_aero_from_neuralfoil(alpha=alpha,Re=re,mach=0.,n_crit=ncrit,model_size='xlarge',xtr_upper=1.,xtr_lower=1.)
        if ncrit==9:original_sensitivity=ResponseSnapshot(result)
    original_teacher=None
    for size in math.SIZES:
        result=foils[2].get_aero_from_neuralfoil(alpha=np.asarray(alpha),Re=np.asarray(re),mach=0.,n_crit=9,model_size=size)
        if size=='xlarge':original_teacher=ResponseSnapshot(result)
    same(retained.copy(),original_sensitivity.copy(),'full unquantized sensitivity response')
    same(retained.copy(),original_teacher.copy(),'full unquantized teacher response')
    predict_base_with_foil(coordinates,alpha,re,shared,retained,math)
    for foil,param in zip(foils,params):same(foil.kulfan_parameters,param.copy(),'independent foil mutation')
    same(shared.kulfan_parameters,shared_params.copy(),'shared foil mutation')
    for old,value in zip(before,[coordinates,alpha,re]):same(old,value,'block input mutation')
    return {'independent_original_fits':3,'optimized_fit':1,'complete_response_comparisons':2}

def preflight(original,optimized,frozen_v6,original_archive_refs):
    """All seven normal/diagnostic fields must match original and frozen V6.

    Performs the unchanged V6 preflight for archive/current canonical and
    qualified-source checks. Its archive discrepancies remain separate.
    This barrier never adopts optimized references.
    """
    route_labels=ROUTES;cohorts=COHORTS
    if set(frozen_v6)!=set(route_labels):raise ValueError('all frozen V6 routes required')
    for service in [original,optimized]:
        if set(service.workload)!=set(cohorts):raise ValueError('cohort scope')
        if [len(service.workload[c]['alpha']) for c in cohorts]!=[242,255]:raise ValueError('full497-row workload')
        if sum(len(service.workload[c]['coordinates']) for c in cohorts)!=4:raise ValueError('four geometry scope')
        if any(service.workload[c]['gate'].dtype!=np.dtype(bool) for c in cohorts):raise ValueError('boolean gate required')
        if sum(np.count_nonzero(~service.workload[c]['gate']) for c in cohorts)!=25:raise ValueError('supplied gate count')
    for c in cohorts:same(original.workload[c],optimized.workload[c],'identical complete workload '+c)
    original_work=ResponseSnapshot(original.workload)
    optimized_work=ResponseSnapshot(optimized.workload)
    current_original,archive_inventory=frozen_measurement.preflight(original,original_archive_refs)
    for route in route_labels:same(current_original[route],frozen_v6[route],'unchanged original versus frozen V6')
    for c in cohorts:
        same(original.workload[c]['gate'],optimized.workload[c]['gate'],'supplied gate')
        w=optimized.workload[c]
        for name,text in w['coordinates'].items():
            ix=np.flatnonzero(w['airfoil']==name)
            audit_geometry_block(optimized.f,optimized.asb,optimized.f.load_pts(text),w['alpha'][ix],w['Re'][ix])
    for route in route_labels:
        d=original.request(route,diagnostics=True);v=optimized.request(route,diagnostics=True)
        same(d,v,'all diagnostic fields '+route)
        for service in [original,optimized]:
            normal=service.request(route);same(normal,frozen_v6[route],'frozen V6 normal '+route)
            same(normal,{k:d[k] for k in normal},'normal/diagnostic '+route)
            for c in cohorts:
                if not route.startswith('native_'):
                    gate=service.workload[c]['gate'];same(normal[c+'/CD'][~gate],d[c+'/BASE_CD'][~gate],'fallback')
    for service,before in [(original,original_work),(optimized,optimized_work)]:
        same(service.workload,before.copy(),'complete caller workload mutation')
    return {'status':'PASS_FULL_COMPONENT_BIT_FIDELITY','routes':7,'archive_inventory':archive_inventory,'reference_origin':'frozen V6 and independent literal original; never optimized output'}
