"""Parent-dependent fixed KL replay. Requires separate authenticated approval."""
from pathlib import Path
import argparse,json,io,time,signal,os,sys,datetime,hashlib
import numpy as np
import pandas as pd
import integrity,shared
def bind_local(addon):
    result={}
    for name in ['replay.py','shared.py','integrity.py']:
        raw=Path(__file__).with_name(name).read_bytes()
        if raw!=addon['code/'+name]:raise ValueError('executing source differs from authenticated code: '+name)
        result[name]=hashlib.sha256(raw).hexdigest()
    return result
def write(path,value):
    raw=json.dumps(value,indent=2,allow_nan=False).encode()+b'\n'
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def authenticate(args):
    approval_raw=Path(args.approval).read_bytes()
    if integrity.sha(approval_raw)!=args.approval_sha256:raise ValueError('approval hash')
    approval=json.loads(approval_raw)
    if approval.get('archive_sha256')!=args.archive_sha256 or 'replay' not in approval.get('authorized_phases',[]):raise ValueError('replay approval')
    parent,_=integrity.verified_members(args.parent,shared.PARENT_SHA,shared.PARENT_MANIFEST)
    addon,_=integrity.verified_members(args.archive,args.archive_sha256,args.manifest_sha256)
    sources=bind_local(addon)
    return parent,addon,sources
def main(args):
    out=integrity.new_target(args.output);out.mkdir();start=time.monotonic();ledger=[]
    record={'started_UTC':now(),'approval_sha256':args.approval_sha256,'archive_sha256':args.archive_sha256,
        'manifest_sha256':args.manifest_sha256,'parent_archive_sha256':shared.PARENT_SHA,'parent_manifest_sha256':shared.PARENT_MANIFEST,
        'local_start_source_sha256':{n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in ['replay.py','shared.py','integrity.py']}}
    write(out/'ATTEMPT.json',record)
    try:run(args,out,start,ledger,record)
    except BaseException as exc:
        import traceback
        record.update(exception=repr(exc),traceback=traceback.format_exc(),finished_UTC=now(),seconds=time.monotonic()-start,reads=ledger)
        write(out/'FAILURE.json',record);raise
def run(args,out,start,ledger,record):
    parent_raw,addon_raw,sources=authenticate(args);record['executing_source_sha256']=sources
    parent=shared.Reader(parent_raw,ledger,'parent');addon=shared.Reader(addon_raw,ledger,'addon')
    dependency=addon.json('PARENT_REQUIREMENTS.json')
    if dependency['archive_sha256']!=shared.PARENT_SHA or dependency['manifest_sha256']!=shared.PARENT_MANIFEST:raise ValueError('parent identity')
    for n,h in dependency['required_members'].items():
        if integrity.sha(parent_raw[n])!=h:raise ValueError('parent member')
    try:
        q,codec,n,c,fc,overlay,m=shared.engines(parent,addon)
        saved={};checks=[]
        for ctx in dependency['contexts']:
            z=parent.arrays(f'calibration/{ctx}.npz');role=parent.json(f'roles/{ctx}.json');shared.validate_roles(z,role)
            for label,oldlabel in zip(shared.LABELS,shared.OLD):
                scalar_record=addon.json(f'scalars/{label}_{ctx}.json');B=codec.fraction(scalar_record['bound'])
                old=parent.json(f'scalars/{oldlabel}_{ctx}.json')
                args0=(z['BASE_CD'],z['core'],z['anchor'],z['MEAS_CD'],z['group'].astype(str),B)
                h=n.fit_scalar(*args0)
                for k in ['upper','bound','exact_mean']:
                    if h[k]!=codec.fraction(old[k]):raise ValueError('matched scalar')
                if h['t']!=old['t']:raise ValueError('matched t')
                if h['rows']!=old['rows'] or h['groups']!=old['groups'] or h['group_means']!={k:codec.fraction(v) for k,v in old['group_means'].items()}:raise ValueError('matched group witness')
                actual=c.fit_kl_scalar(*args0);actual.update(candidate=label,context=ctx)
                shared.scalar_equal(actual,scalar_record,codec)
                saved[label,ctx]=scalar_record;checks.append({'context':ctx,'candidate':label,'exact':True})
        native=[]
        for ctx in dependency['native_contexts']:
            z=parent.arrays(f'native/{ctx}.npz',['indices','BASE_CD','core','anchor','gate'])
            expected=addon.arrays(f'predictions/{ctx}.npz')
            np.testing.assert_array_equal(expected['indices'],z['indices'])
            for label in shared.LABELS:
                model=saved[label,'final' if ctx in shared.EXT else ctx];p,e=n.predictions(model,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
                values={label:p,label+'__effective_fraction':e,label+'__strength':np.where(z['gate'],.5+.5*model['t'],0.),label+'__intervened':abs(p-z['anchor'])>1e-12}
                shared.native_equal(values,{k:expected[k] for k in values})
                np.testing.assert_array_equal(p[~z['gate']],z['BASE_CD'][~z['gate']])
                for v,h,core,g in zip(p,z['anchor'],z['core'],z['gate']):
                    if g and core!=h and not 0<=(q.rat(v)-q.rat(h))/(q.rat(core)-q.rat(h))<=q.rat(model['t']):raise ValueError('fraction')
            native.append({'context':ctx,'exact':True})
        ev=shared.module('evaluator',parent.code('code/evaluator.py'));cert=parent.json('certificates/STAGE0_CERTIFICATE.json')
        for row in cert['records']:
            tree=ev.SequentialHist(parent.arrays('trees/'+row['context']+'.npz'))
            bounds=q.sequential_range(tree.initial,(t['value'][t['is_leaf'].astype(bool)] for t in tree.stages))
            for k in ['lower','upper','real_lower','real_upper']:
                if bounds[k]!=codec.fraction(row['range'][k]):raise ValueError('certificate')
            if q.structural_bound(bounds['lower'],bounds['upper'])!=codec.fraction(row['B_structural']):raise ValueError('B certificate')
        frame=fc.unpack(parent.arrays('scoring/frame.npz'),parent.json('scoring/schema.json'))
        frames={ctx:addon.csv(f'prediction_csv/{ctx}.csv') for ctx in dependency['native_contexts'] if ctx!='final'}
        frame=overlay.overlay(frame,frames);panels={k:np.array(v,int) for k,v in parent.json('scoring/panels.json').items()}
        tables={'panel_metrics':m.panel_metrics(frame,panels),'bootstrap':m.bootstrap(frame),'group_metrics':m.group_metrics(frame)}
        tables['decisions']=m.decisions(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics']);tables['candidate_summary']=m.summary(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics']);tables['harm_metrics']=m.harms(frame,panels)
        risk,bundles,interventions=m.extras(frame,panels);tables.update(expected_harm_metrics=risk,bundle_harm_metrics=bundles,intervention_metrics=interventions,all_row_predictions=frame)
        differences=[]
        try:
            for name,table in tables.items():
                shared.compare_tables(name,table,addon.raw('expected/'+name+'.csv','pandas.read_csv expected input'),ledger,differences)
                table.to_csv(out/(name+'.csv'),index=False,mode='x')
        finally:codec.write_json(out/'FLOAT_DIFFERENCES.json',differences)
        if tables['decisions'].performance_advance.any() or tables['decisions'].robustness_advance.any():raise ValueError('advance changed')
        unresolved=[x for x in differences if not x['within_inherited_audit_tolerance'] and not x['known_zero_sign_diagnostic']]
        p2,a2,s2=authenticate(args)
        if s2!=sources:raise ValueError('executing sources changed at completion')
        record.update(finished_UTC=now(),status='DIFFERENCES_REQUIRE_REVIEW' if differences else 'EXACT_REPLAY_PASS',unresolved_outside_contract=len(unresolved))
        record.update({'scalar_checks':checks,'native_checks':native,'certificates':16,'counts':shared.COUNTS,'differences':len(differences),
            'seconds':time.monotonic()-start,'runtime':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},'materializations':ledger,
            'scope':'Private retained-data replay, no fits, no independent experimental validation',
            'end_authentication':True,'outputs':{p.name:integrity.sha(p.read_bytes()) for p in out.iterdir() if p.is_file()}})
        if unresolved:raise ValueError('unresolved numerical discrepancies')
        codec.write_json(out/'COMPLETE.json',record)
    except BaseException as exc:
        import traceback
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['parent','archive','archive-sha256','manifest-sha256','output','approval','approval-sha256']:p.add_argument('--'+n,required=True)
    args=p.parse_args()
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise ValueError('one thread')
    def timeout(*unused):raise TimeoutError('900-second replay guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900);main(args)
