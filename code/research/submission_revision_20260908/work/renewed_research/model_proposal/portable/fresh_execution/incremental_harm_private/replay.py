"""Standalone private replay. Authenticate bytes before parsing executable code."""
import argparse,hashlib,io,json,sys,time,types,unittest
from pathlib import Path,PurePosixPath
import numpy as np
import pandas as pd


def digest(data):return hashlib.sha256(data).hexdigest()


def authenticate(root,expected):
    root=Path(root).resolve()
    raw=(root/'manifest.json').read_bytes()
    if not isinstance(expected,str) or len(expected)!=64 or digest(raw)!=expected:
        raise ValueError('Explicit pinned manifest SHA256 mismatch')
    manifest=json.loads(raw)
    if manifest.get('schema')!='private_incremental_replay_v1':raise ValueError('Unknown package schema')
    buffers={}
    for name,h in manifest['members'].items():
        p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or p.as_posix()!=name:
            raise ValueError('Unsafe member name')
        path=root/name
        if any(q.is_symlink() for q in [path,*path.parents] if q!=root.parent):
            raise ValueError('Symlink member not allowed')
        if not path.is_file() or root not in path.resolve().parents:raise ValueError('Missing/outside member')
        value=path.read_bytes()
        if digest(value)!=h:raise ValueError('Changed member: '+name)
        buffers[name]=value
    return manifest,buffers


def load_module(name,data):
    module=types.ModuleType(name);module.__file__=name+'.py';sys.modules[name]=module
    exec(compile(data,name+'.py','exec'),module.__dict__)
    return module


def reserve_output(path,root):
    p=Path(path).resolve();root=Path(root).resolve()
    if p==root or root in p.parents:raise ValueError('Output must be outside immutable package')
    p.mkdir(parents=True,exist_ok=False)
    return p


def npz(data):
    with np.load(io.BytesIO(data),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def frame(data):return pd.read_csv(io.BytesIO(data),low_memory=False)


def compare(name,value,expected):
    actual=pd.read_csv(io.StringIO(value.to_csv(index=False)),low_memory=False)
    assert list(actual.columns)==list(expected.columns),(name,'columns')
    assert len(actual)==len(expected),(name,'rows')
    diffs={};counts={}
    for field in actual:
        a,b=actual[field],expected[field]
        if pd.api.types.is_numeric_dtype(a) and a.dtype!=bool:
            x,y=a.to_numpy(),b.to_numpy()
            np.testing.assert_array_equal(np.isnan(x),np.isnan(y))
            d=abs(x-y);diffs[field]=float(np.nanmax(d,initial=0));counts[field]=int(((x!=y)&~np.isnan(x)).sum())
            if pd.api.types.is_integer_dtype(a):np.testing.assert_array_equal(x,y)
        else:pd.testing.assert_series_equal(a,b,check_names=False)
    return {'table':name,'rows':len(actual),'max_abs_difference':diffs,'unequal_count':counts,
            'exact_after_CSV_roundtrip':not any(counts.values())}


def main(root,expected,output):
    started=time.monotonic();root=Path(root).resolve()
    manifest,buf=authenticate(root,expected)
    out=reserve_output(output,root)
    policy=load_module('incremental_harm',buf['incremental_harm.py'])
    metrics=load_module('metrics',buf['metrics.py'])
    tests=load_module('test_incremental_harm',buf['test_incremental_harm.py'])
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    (out/'synthetic_tests.txt').write_text(stream.getvalue())
    assert result.wasSuccessful() and result.testsRun==15
    scalars=[];native=[]
    for context in manifest['contexts']:
        z=npz(buf[f'calibration/{context}.npz']);member=json.loads(buf[f'roles/{context}.json'])
        for a,b in [('proper_groups','calibration_groups'),('proper_groups','test_groups'),('calibration_groups','test_groups')]:
            assert not set(member[a])&set(member[b])
        np.testing.assert_array_equal(z['indices'],member['calibration_indices'])
        np.testing.assert_array_equal(z['nf2_row_id'],member['calibration_nf2_row_ids'])
        actual=policy.calibrate(z['BASE_CD'],z['CORE_CD_capped'],z['MEAS_CD'],z['group'],z['gate'])
        saved=json.loads(buf[f'calibrators/{context}.json'])
        for key,value in actual.items():assert value==saved[key],(context,key)
        scalars.append({'context':context,'t':saved['t'],'groups':saved['groups'],'exact':True})
    for context in manifest['native_contexts']:
        n=npz(buf[f'native/{context}.npz'])
        model=json.loads(buf[f'calibrators/{"final" if context in metrics.EXTERNAL else context}.json'])
        p=policy.predict(model,n['BASE_CD'],n['CORE_CD'],n['gate'])
        for key,value in p.items():np.testing.assert_array_equal(value,n[key])
        native.append({'context':context,'rows':len(n['BASE_CD']),'exact':True})
    z=npz(buf['scoring_inputs.npz']);schema=json.loads(buf['scoring_schema.json']);columns={}
    for name in schema['columns']:
        v=z[name]
        if name in schema['object_columns']:
            v=v.astype(object);v[z[name+'__null']]=np.nan
        columns[name]=v
    f=pd.DataFrame(columns)
    panels=metrics.make_panels(f)
    tables={'panel_metrics':metrics.panel_metrics(f,panels),'bootstrap':metrics.bootstrap(f),'group_metrics':metrics.group_metrics(f)}
    tables['decisions']=metrics.decisions(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
    tables['candidate_summary']=metrics.summary(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
    tables['harm_metrics']=metrics.harms(f,panels)
    risk,bundles,interventions=metrics.extra_metrics(f,panels)
    tables.update(expected_harm_metrics=risk,bundle_harm_metrics=bundles,intervention_metrics=interventions)
    cal=[]
    for context in manifest['contexts']:
        v=json.loads(buf[f'calibrators/{context}.json'])
        cal.append({k:v[k] for k in ['context','groups','rows','endpoint_mean','hoeffding_penalty','upper_bound','t','inside_gate_strength','status']})
    tables['calibration_summary']=pd.DataFrame(cal)
    comparisons=[]
    for name,value in tables.items():
        comparisons.append(compare(name,value,frame(buf[f'expected/{name}.csv'])))
        value.to_csv(out/f'{name}.csv',index=False)
    # Expected controls and baseline inputs are included, not refitted or selected.
    assert len(f)==29856 and len(panels)==31
    assert not tables['decisions'].performance_advance.any() and not tables['decisions'].robustness_advance.any()
    # A second output attempt must fail without altering the completed directory.
    try:reserve_output(out,root)
    except FileExistsError:pass
    else:raise AssertionError('Overwrite was not refused')
    report={'status':'REPLAY_COMPLETE_WITH_EXPLICIT_FLOAT_DIFFERENCES' if not all(c['exact_after_CSV_roundtrip'] for c in comparisons) else 'PASS_EXACT',
        'manifest_sha256':expected,'synthetic_tests_passed':15,'scalar_calibrators':scalars,'native_inference':native,
        'tables':comparisons,'panels':31,'split_row_instances':len(f),'bootstrap_draws':20000,
        'no_new_core_fits':True,'no_numeric_equality_tolerance_introduced':True,'overwrite_refused':True,
        'seconds':time.monotonic()-started,'runtime':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
        'scope':'Private retained-label replay, not fresh experimental validation, risk certification, or public rights clearance.'}
    (out/'REPORT.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':report['status'],'seconds':report['seconds'],'native_rows':sum(v['rows'] for v in native)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();main(Path(__file__).resolve().parent,args.manifest_sha256,args.output)
