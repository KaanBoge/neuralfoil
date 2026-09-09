"""Standalone approved private archive replay; zero fits, no project imports."""
import argparse,io,json,signal,sys,time,types
from pathlib import Path
import numpy as np
import pandas as pd
import integrity

def load_module(name,raw):
    m=types.ModuleType(name);sys.modules[name]=m;exec(compile(raw,name+'.py','exec'),m.__dict__);return m
def arrays(raw):
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def compare(name,table,expected):
    a=pd.read_csv(io.StringIO(table.to_csv(index=False)),low_memory=False)
    b=pd.read_csv(io.BytesIO(expected),low_memory=False)
    if list(a.columns)!=list(b.columns) or len(a)!=len(b):raise ValueError('table schema/rows '+name)
    cells=[]
    for column in a:
        if pd.api.types.is_numeric_dtype(a[column]) and a[column].dtype!=bool:
            x,y=a[column].to_numpy(),b[column].to_numpy()
            np.testing.assert_array_equal(pd.isna(x),pd.isna(y))
            unequal=(x!=y)&~pd.isna(x)
            if pd.api.types.is_integer_dtype(a[column]):np.testing.assert_array_equal(x,y)
            for row in np.flatnonzero(unequal):
                cells.append({'table':name,'column':column,'row':int(row),'actual':float(x[row]),
                    'expected':float(y[row]),'difference':float(x[row]-y[row])})
        else:pd.testing.assert_series_equal(a[column],b[column],check_names=False)
    return cells

def main(args):
    started=time.monotonic()
    buffers,manifest=integrity.verified_members(args.archive,args.archive_sha256,args.manifest_sha256)
    out=integrity.new_target(args.output);out.mkdir()
    try:
        q=load_module('qualified_numerics',buffers['code/qualified_numerics.py'])
        codec=load_module('codec',buffers['code/codec.py']);policy=load_module('policy',buffers['code/policy.py'])
        metrics=load_module('metrics',buffers['code/metrics.py']);fc=load_module('frame_codec',buffers['code/frame_codec.py'])
        info=json.loads(buffers['inventory.json']);labels=info['labels'];scalars=[];native=[];feature_results=[]
        saved={}
        for context in info['contexts']:
            z=arrays(buffers[f'calibration/{context}.npz']);role=json.loads(buffers[f'roles/{context}.json'])
            for a,b in [('proper_groups','calibration_groups'),('proper_groups','test_groups'),('calibration_groups','test_groups')]:
                if set(role[a])&set(role[b]):raise ValueError('role overlap')
            np.testing.assert_array_equal(z['indices'],role['calibration_indices']);np.testing.assert_array_equal(z['nf2_row_id'],role['calibration_nf2_row_ids'])
            for label in labels:
                record=json.loads(buffers[f'scalars/{label}_{context}.json']);saved[label,context]=record
                actual=policy.fit_scalar(z['BASE_CD'],z['core'],z['anchor'],z['MEAS_CD'],z['group'].astype(str),codec.fraction(record['bound']))
                for key in ['upper','bound','exact_mean']:
                    if actual[key]!=codec.fraction(record[key]):raise ValueError('exact scalar rational mismatch')
                if actual['t']!=record['t'] or actual['rows']!=record['rows'] or actual['groups']!=record['groups']:raise ValueError('scalar metadata/t mismatch')
                if actual['group_means']!={k:codec.fraction(v) for k,v in record['group_means'].items()}:raise ValueError('group means mismatch')
                scalars.append({'context':context,'candidate':label,'exact':True})
        for context in info['native_contexts']:
            z=arrays(buffers[f'native/{context}.npz']);core_context='final' if context in metrics.EXTERNAL else context
            for label in labels:
                record=saved[label,core_context]
                p,e=policy.predictions(record,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
                np.testing.assert_array_equal(p,z[label]);np.testing.assert_array_equal(e,z[label+'__effective_fraction'])
                np.testing.assert_array_equal(np.where(z['gate'],.5+.5*record['t'],0.),z[label+'__strength'])
                np.testing.assert_array_equal(p[~z['gate']],z['BASE_CD'][~z['gate']])
            native.append({'context':context,'rows':len(z['BASE_CD']),'both_procedures_exact':True})
        # Topology/range certificate replay is label-free and independent of optional X62 evaluation.
        ev=load_module('evaluator',buffers['code/evaluator.py']);cert=json.loads(buffers['certificates/STAGE0_CERTIFICATE.json'])
        models={}
        for row in cert['records']:
            context=row['context'];m=ev.SequentialHist(arrays(buffers[f'trees/{context}.npz']));models[context]=m
            bounds=q.sequential_range(m.initial,(t['value'][t['is_leaf'].astype(bool)] for t in m.stages))
            for key in ['lower','upper','real_lower','real_upper']:
                if bounds[key]!=codec.fraction(row['range'][key]):raise ValueError('range mismatch')
            if q.structural_bound(bounds['lower'],bounds['upper'])!=codec.fraction(row['B_structural']):raise ValueError('B mismatch')
        if args.verify_feature_parity:
            if not info['features_included']:raise ValueError('optional features not included')
            master=arrays(buffers['features/X62.npz']);X=master['X62'];maps=json.loads(buffers['features/maps.json'])
            for role,contexts in [('calibration',info['contexts']),('native',info['native_contexts'])]:
                for context in contexts:
                    z=arrays(buffers[f'{role}/{context}.npz']);key='final' if context in metrics.EXTERNAL else context
                    ix=np.array(maps[role+'/'+context],int)
                    if len(ix)!=len(z['BASE_CD']) or (ix<0).any() or (ix>=8868).any():raise ValueError('feature map')
                    np.testing.assert_array_equal(master['BASE_CD'][ix],z['BASE_CD'])
                    c,h,g=q.guarded_core(z['BASE_CD'],models[key].predict_raw(X[ix]),z['gate'])
                    np.testing.assert_array_equal(c,z['core']);np.testing.assert_array_equal(h,z['anchor']);np.testing.assert_array_equal(g,z['gate'])
                    feature_results.append({'role':role,'context':context,'exact':True})
        frame=fc.unpack(arrays(buffers['scoring/frame.npz']),json.loads(buffers['scoring/schema.json']))
        panels={k:np.array(v,int) for k,v in json.loads(buffers['scoring/panels.json']).items()}
        if len(frame)!=29856 or len(panels)!=31:raise ValueError('assessment denominator')
        tables={'panel_metrics':metrics.panel_metrics(frame,panels),'bootstrap':metrics.bootstrap(frame),'group_metrics':metrics.group_metrics(frame)}
        tables['decisions']=metrics.decisions(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
        tables['candidate_summary']=metrics.summary(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
        tables['harm_metrics']=metrics.harms(frame,panels)
        risk,bundles,interventions=metrics.extras(frame,panels)
        tables.update(expected_harm_metrics=risk,bundle_harm_metrics=bundles,intervention_metrics=interventions)
        rows=[]
        for context in info['contexts']:
            for label in labels:
                z=saved[label,context]
                rows.append({'context':context,'candidate':label,'groups':z['groups'],'rows':z['rows'],
                    'B':float(codec.fraction(z['bound'])),'upper':float(codec.fraction(z['upper'])),
                    'endpoint_mean':float(codec.fraction(z['exact_mean'])) if z['exact_mean'] else None,'t':z['t']})
        tables['calibration_summary']=pd.DataFrame(rows);tables['all_row_predictions']=frame
        differences=[]
        for name,table in tables.items():
            differences.extend(compare(name,table,buffers['expected/'+name+'.csv']))
            with (out/(name+'.csv')).open('x') as f:table.to_csv(f,index=False)
        if tables['decisions'].performance_advance.any() or tables['decisions'].robustness_advance.any():raise ValueError('advancement changed')
        codec.write_json(out/'FLOAT_DIFFERENCES.json',differences)
        codec.write_json(out/'REPORT.json',{'status':'COMPLETE_WITH_EXPLICIT_FLOAT_DIFFERENCES' if differences else 'EXACT_REPLAY_PASS',
            'scalar_checks':scalars,'native_checks':native,'tree_certificates':len(models),'optional_feature_checks':feature_results,
            'numeric_difference_cells':len(differences),'no_new_numeric_tolerance':True,'all_decisions_unchanged':True,
            'near_zero_sign_statistics_preserved_not_overridden':True,'seconds':time.monotonic()-started,
            'runtime':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
            'scope':'Private retained-data replay, not fitting or independent experimental validation'})
    except BaseException as exc:
        import traceback
        with (out/'FAILURE.json').open('x') as f:json.dump({'exception':repr(exc),'traceback':traceback.format_exc()},f,indent=2)
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--archive-sha256',required=True)
    p.add_argument('--manifest-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--verify-feature-parity',action='store_true')
    a=p.parse_args()
    if __import__('os').environ.get('OMP_NUM_THREADS')!='1' or __import__('os').environ.get('OPENBLAS_NUM_THREADS')!='1':raise ValueError('single thread required')
    def timeout(*unused):raise TimeoutError('900-second replay guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900);main(a)
