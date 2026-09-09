"""Parent-dependent fixed KL replay. Requires separate authenticated approval."""
from pathlib import Path
import argparse,json,io,time,signal,os,sys
import numpy as np
import pandas as pd
import integrity,shared
def main(args):
    approval_raw=Path(args.approval).read_bytes()
    if integrity.sha(approval_raw)!=args.approval_sha256:raise ValueError('approval hash')
    approval=json.loads(approval_raw)
    if approval.get('archive_sha256')!=args.archive_sha256 or 'replay' not in approval.get('authorized_phases',[]):raise ValueError('replay approval')
    parent,_=integrity.verified_members(args.parent,shared.PARENT_SHA,shared.PARENT_MANIFEST)
    addon,_=integrity.verified_members(args.archive,args.archive_sha256,args.manifest_sha256)
    dependency=json.loads(addon['PARENT_REQUIREMENTS.json'])
    if dependency['archive_sha256']!=shared.PARENT_SHA or dependency['manifest_sha256']!=shared.PARENT_MANIFEST:raise ValueError('parent identity')
    for n,h in dependency['required_members'].items():
        if integrity.sha(parent[n])!=h:raise ValueError('parent member')
    out=integrity.new_target(args.output);out.mkdir();start=time.monotonic();ledger=[]
    try:
        q,codec,n,c,fc,overlay,m=shared.engines(parent,addon)
        saved={};checks=[]
        for ctx in dependency['contexts']:
            z=shared.arrays(parent[f'calibration/{ctx}.npz'],ledger,'parent/calibration/'+ctx)
            role=json.loads(parent[f'roles/{ctx}.json'])
            for a,b in [('proper_groups','calibration_groups'),('proper_groups','test_groups'),('calibration_groups','test_groups')]:
                if set(role[a])&set(role[b]):raise ValueError('role overlap')
            np.testing.assert_array_equal(z['indices'],role['calibration_indices']);np.testing.assert_array_equal(z['nf2_row_id'],role['calibration_nf2_row_ids'])
            for label,oldlabel in zip(shared.LABELS,shared.OLD):
                record=json.loads(addon[f'scalars/{label}_{ctx}.json']);B=codec.fraction(record['bound'])
                old=json.loads(parent[f'scalars/{oldlabel}_{ctx}.json'])
                args0=(z['BASE_CD'],z['core'],z['anchor'],z['MEAS_CD'],z['group'].astype(str),B)
                h=n.fit_scalar(*args0)
                for k in ['upper','bound','exact_mean']:
                    if h[k]!=codec.fraction(old[k]):raise ValueError('matched scalar')
                if h['t']!=old['t']:raise ValueError('matched t')
                if h['rows']!=old['rows'] or h['groups']!=old['groups'] or h['group_means']!={k:codec.fraction(v) for k,v in old['group_means'].items()}:raise ValueError('matched group witness')
                actual=c.fit_kl_scalar(*args0);actual.update(candidate=label,context=ctx)
                canonical=json.loads(json.dumps(actual,default=codec.encode))
                if canonical!=record:raise ValueError('complete KL scalar witness mismatch')
                saved[label,ctx]=record;checks.append({'context':ctx,'candidate':label,'exact':True})
        native=[]
        for ctx in dependency['native_contexts']:
            z=shared.arrays(parent[f'native/{ctx}.npz'],ledger,'parent/native/'+ctx,['indices','BASE_CD','core','anchor','gate'])
            expected=shared.arrays(addon[f'predictions/{ctx}.npz'],ledger,'addon/native/'+ctx)
            np.testing.assert_array_equal(expected['indices'],z['indices'])
            for label in shared.LABELS:
                model=saved[label,'final' if ctx in shared.EXT else ctx];p,e=n.predictions(model,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
                values={label:p,label+'__effective_fraction':e,label+'__strength':np.where(z['gate'],.5+.5*model['t'],0.),label+'__intervened':abs(p-z['anchor'])>1e-12}
                for k,v in values.items():np.testing.assert_array_equal(v,expected[k])
                np.testing.assert_array_equal(p[~z['gate']],z['BASE_CD'][~z['gate']])
                for v,h,core,g in zip(p,z['anchor'],z['core'],z['gate']):
                    if g and core!=h and not 0<=(q.rat(v)-q.rat(h))/(q.rat(core)-q.rat(h))<=q.rat(model['t']):raise ValueError('fraction')
            native.append({'context':ctx,'exact':True})
        ev=shared.module('evaluator',parent['code/evaluator.py']);cert=json.loads(parent['certificates/STAGE0_CERTIFICATE.json'])
        for row in cert['records']:
            tree=ev.SequentialHist(shared.arrays(parent['trees/'+row['context']+'.npz'],ledger,'parent/tree/'+row['context']))
            bounds=q.sequential_range(tree.initial,(t['value'][t['is_leaf'].astype(bool)] for t in tree.stages))
            for k in ['lower','upper','real_lower','real_upper']:
                if bounds[k]!=codec.fraction(row['range'][k]):raise ValueError('certificate')
            if q.structural_bound(bounds['lower'],bounds['upper'])!=codec.fraction(row['B_structural']):raise ValueError('B certificate')
        frame=fc.unpack(shared.arrays(parent['scoring/frame.npz'],ledger,'parent/scoring/frame'),json.loads(parent['scoring/schema.json']))
        frames={ctx:pd.read_csv(io.BytesIO(addon[f'prediction_csv/{ctx}.csv']),low_memory=False) for ctx in dependency['native_contexts'] if ctx!='final'}
        frame=overlay.overlay(frame,frames);panels={k:np.array(v,int) for k,v in json.loads(parent['scoring/panels.json']).items()}
        tables={'panel_metrics':m.panel_metrics(frame,panels),'bootstrap':m.bootstrap(frame),'group_metrics':m.group_metrics(frame)}
        tables['decisions']=m.decisions(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics']);tables['candidate_summary']=m.summary(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics']);tables['harm_metrics']=m.harms(frame,panels)
        risk,bundles,interventions=m.extras(frame,panels);tables.update(expected_harm_metrics=risk,bundle_harm_metrics=bundles,intervention_metrics=interventions,all_row_predictions=frame)
        differences=[]
        for name,table in tables.items():
            differences+=shared.compare_tables(name,table,addon['expected/'+name+'.csv']);table.to_csv(out/(name+'.csv'),index=False,mode='x')
        codec.write_json(out/'FLOAT_DIFFERENCES.json',differences)
        if tables['decisions'].performance_advance.any() or tables['decisions'].robustness_advance.any():raise ValueError('advance changed')
        unresolved=[x for x in differences if not x['within_inherited_audit_tolerance'] and not x['known_zero_sign_diagnostic']]
        codec.write_json(out/'REPORT.json',{'status':'DIFFERENCES_REQUIRE_REVIEW' if differences else 'EXACT_REPLAY_PASS','unresolved_outside_contract':len(unresolved),
            'scalar_checks':checks,'native_checks':native,'certificates':16,'counts':shared.COUNTS,'differences':len(differences),
            'seconds':time.monotonic()-start,'runtime':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},'materializations':ledger,
            'scope':'Private retained-data replay, no fits, no independent experimental validation'})
        if unresolved:raise ValueError('unresolved numerical discrepancies')
    except BaseException as exc:
        import traceback
        raw=json.dumps({'exception':repr(exc),'traceback':traceback.format_exc(),'seconds':time.monotonic()-start,'materializations':ledger},indent=2)
        with (out/'FAILURE.json').open('x') as f:f.write(raw)
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['parent','archive','archive-sha256','manifest-sha256','output','approval','approval-sha256']:p.add_argument('--'+n,required=True)
    args=p.parse_args()
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise ValueError('one thread')
    def timeout(*unused):raise TimeoutError('900-second replay guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900);main(args)
