"""Route-specific preparation; native cold calls touch no correction archives."""
from pathlib import Path
import importlib.util,importlib.metadata,platform
import numpy as np
from serving import Serving,COHORTS,QUALIFIED,ROUTES
from provenance_v2 import Access,modules,sha,safe_name,path_bytes
FEATURE='submission_revision_20260908/work/feature_reproduction/addon/'
ORIGINAL='model_development_20260907_risk_policy/portable/'
PREPARED='model_development_20260907_geometry_frontier/engineering/fast_inference/prepared.py'
PARENT='submission_revision_20260908/work/renewed_research/model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
ADDON='submission_revision_20260908/work/renewed_research/model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip'
def same(a,b,name):
    a=np.asarray(a);b=np.asarray(b)
    if a.shape!=b.shape or a.dtype!=b.dtype or not np.array_equal(a,b):raise ValueError('exact shape/dtype/value mismatch '+name)
def runtime(access):
    identity=FEATURE+'expected_runtime.json';expected=access.json(access.file(identity),identity)
    witness={}
    # Read only the finite archived runtime source/weight inventory, before import.
    roots={name:Path(importlib.util.find_spec(name).origin).parent for name in ['aerosandbox','neuralfoil']}
    for name,h in expected['source_sha256'].items():
        package,relative=name.split('/',1);safe_name(relative);p=roots[package]/relative
        b=path_bytes(p)
        if sha(b)!=h:raise ValueError('forward source/weight identity '+name)
        witness[str(p)]=h;access.events.append({'operation':'runtime source/weight authentication','file':str(p),'sha256':h})
    observed={'python':platform.python_version(),'versions':{k:importlib.metadata.version(k) for k in ['numpy','aerosandbox','neuralfoil','casadi']},'source_sha256':expected['source_sha256']}
    if observed!=expected:raise ValueError('runtime version mismatch')
    import aerosandbox as asb,neuralfoil
    for package,m in [('aerosandbox',asb),('neuralfoil',neuralfoil)]:
        if Path(m.__file__).parent.resolve()!=roots[package].resolve():raise ValueError('runtime imported origin')
    return asb,observed,witness
def load(root,registry,route=None,with_references=False,access=None):
    scope='all' if route is None else route
    access=access or Access(root,registry['scopes'][scope]);asb,observed,runtime_pins=runtime(access)
    original=qualified=policy=q=None;scalars={};references={};work={}
    native=route in ROUTES[:2]
    want_original=route is None or route==ROUTES[2]
    want_qualified=route is None or route in QUALIFIED
    with modules(access) as execute:
        f=execute('bench_feature_math_v2',access.file(FEATURE+'feature_math.py'),FEATURE+'feature_math.py')
        if want_original:
            prep=execute('bench_prepared_v2',access.file(PREPARED),PREPARED)
            identity=ORIGINAL+'experimental_policies.json'
            original=prep.prepare(access.json(access.file(identity),identity))
        if want_qualified:
            def code(name):return access.member(PARENT,'code/'+name+'.py')
            q=execute('qualified_numerics',code('qualified_numerics'),PARENT+'!code/qualified_numerics.py')
            policy=execute('bench_policy_v2',code('policy'),PARENT+'!code/policy.py')
            ev=execute('bench_evaluator_v2',code('evaluator'),PARENT+'!code/evaluator.py')
            identity=PARENT+'!trees/final.npz';keys=access.spec['arrays'][identity]
            qualified=ev.SequentialHist(access.arrays(access.member(PARENT,'trees/final.npz'),identity,keys))
            for label in QUALIFIED if route is None else [route]:
                archive=ADDON if '_kl_' in label else PARENT;member=f'scalars/{label}_final.json'
                s=access.json(access.member(archive,member),archive+'!'+member);t=s['t']
                if type(t) not in (float,int) or not np.isfinite(t) or not 0<=t<=1:raise ValueError('scalar')
                scalars[label]={'t':t}
        identity=FEATURE+'manifest.json';fm=access.json(access.file(identity),identity)
        for c in COHORTS:
            identity=FEATURE+f'data/{c}.npz';keys=['alpha','Re','airfoil']
            if with_references:keys=access.spec['arrays'][identity]
            ref=access.arrays(access.file(identity),identity,keys)
            n=registry['workload_rows'][c]
            if ref['alpha'].dtype!=np.dtype('float64') or ref['Re'].dtype!=np.dtype('float64') or ref['alpha'].shape!=(n,) or ref['Re'].shape!=(n,) or not np.isfinite(ref['alpha']).all() or not np.isfinite(ref['Re']).all() or (ref['Re']<=0).any():raise ValueError('conditions')
            old=z=kl=None;gate=np.ones(n,dtype=bool)
            if want_original:
                identity=ORIGINAL+'inference_references.npz';keys=[c+'_gate']
                if with_references:keys += [c+'_'+k for k in ['unpenalized_transfer','BASE_CD','X62','all_model_CD']]
                old=access.arrays(access.file(identity),identity,keys);gate=old[c+'_gate']
            if want_qualified:
                identity=PARENT+f'!native/{c}.npz';keys=['gate']
                if with_references:keys=access.spec['arrays'][identity]
                z=access.arrays(access.member(PARENT,f'native/{c}.npz'),identity,keys)
                if want_original:same(gate,z['gate'],'physical gate bridge')
                gate=z['gate']
                if with_references:
                    identity=ADDON+f'!predictions/{c}.npz'
                    kl=access.arrays(access.member(ADDON,f'predictions/{c}.npz'),identity,access.spec['arrays'][identity])
                    same(z['indices'],kl['indices'],'index bridge');same(z['BASE_CD'],ref['BASE_CD'],'qualified baseline')
            if gate.dtype!=bool or gate.shape!=(n,):raise ValueError('gate')
            if with_references:
                for k in ['BASE_CD','X62','all_model_CD']:same(ref[k],old[c+'_'+k],'original '+k)
                references[c]={'features':ref,'original':old[c+'_unpenalized_transfer'],'native':z,'kl':kl}
            coords={name:access.file(FEATURE+d['path']).decode(errors='replace') for name,d in fm['coordinates'][c].items()}
            if set(ref['airfoil'])!=set(coords):raise ValueError('coordinate membership')
            work[c]={'alpha':ref['alpha'],'Re':ref['Re'],'airfoil':ref['airfoil'],'gate':gate,'coordinates':coords}
    return Serving(f,asb,original,qualified,policy,q,scalars,work),references,observed,access,runtime_pins
def finish(access,runtime_pins):
    access.finish()
    for p,h in runtime_pins.items():
        if sha(path_bytes(p))!=h:raise ValueError('runtime source/weight changed')
        access.events.append({'operation':'runtime finish authentication','file':p,'sha256':h})
