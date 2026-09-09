"""96 fixed cap-ablation fits; all models freeze before external loading."""
from pathlib import Path
import hashlib
import importlib.util
import json
import pickle
import sys
import time
import traceback
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
SELECTIVE = PROJECT/'model_development_20260907_selective'
CAPACITY = PROJECT/'model_development_20260907_frontier/capacity'
RISK = PROJECT/'model_development_20260907_risk_policy'
OUT = HERE/'results'
EXPOSED = HERE/'exposed_results'
FAMILIES = ('capped', 'upper_free', 'positive_log')
LABELS = ([f'{f}_{s}' for f in FAMILIES for s in ['full','half']] +
          [f'proper_{f}_{s}' for f in FAMILIES for s in ['full','half']] +
          [f'project_{b}_{f}' for f in FAMILIES for b in ['mean8','xlarge']])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    with Path(path).open('x') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authenticate():
    prior_path = SELECTIVE/'results/complete.json'
    prior = json.loads(prior_path.read_text())
    hashes = {str(prior_path): sha(prior_path)}
    for name, expected in {**prior['source_input_sha256'], **prior['artifact_sha256']}.items():
        assert sha(name) == expected, name
        hashes[name] = expected
    assert sha(SELECTIVE/'results/freeze.json') == prior['freeze_sha256']
    hashes[str(SELECTIVE/'results/freeze.json')] = prior['freeze_sha256']
    for path in [HERE/'cap_models.py', HERE/'test_cap_models.py', HERE/'PROTOCOL.md', Path(__file__)]:
        hashes[str(path)] = sha(path)
    for path in [PROJECT/'model_development_20260907_frontier/assessment_final/report.json',
                 RISK/'portable/manifest.json']:
        hashes[str(path)] = sha(path)
    return hashes


def save_npz(path, **arrays):
    assert not path.exists()
    np.savez_compressed(path, **arrays)


def evaluate(models, calibrators, d, idx, gate, cap, selective):
    base, xl = d['BASE_CD'][idx], d['XLARGE_CD'][idx]
    values, raw = {}, {}
    for family in FAMILIES:
        for branch, prefix in [('full',''), ('proper','proper_')]:
            pred = cap.predict(models[branch, family], d, idx)
            raw[f'{branch}_core_{family}'] = pred
            values[f'{prefix}{family}_full'] = np.where(gate, pred, base)
            values[f'{prefix}{family}_half'] = np.where(gate, cap.half(pred, base), base)
        core = raw[f'proper_core_{family}']
        for label, baseline in [('mean8',base), ('xlarge',xl)]:
            result = selective.project(calibrators[family], core, base, baseline, gate)
            values[f'project_{label}_{family}'] = result['prediction']
            values[f'project_{label}_{family}__intervened'] = result['intervened']
            np.testing.assert_array_equal(result['prediction'][~gate], baseline[~gate])
        values[f'interval_lower_{family}'] = result['lower']
        values[f'interval_upper_{family}'] = result['upper']
        values[f'interval_applicable_{family}'] = result['applicable']
        values['interval_applicable'] = result['applicable']
        q = calibrators[family]['q']
        values[f'calibration_q_{family}'] = np.full(len(idx), np.inf if q is None else q)
    assert len(LABELS) == 18 and all(label in values for label in LABELS)
    assert np.isfinite(np.column_stack([values[label] for label in LABELS])).all()
    return values, raw


def main():
    assert not OUT.exists() and not EXPOSED.exists(), 'Preserve previous attempts'
    hashes = authenticate()
    old = load_module('selective_producer_frozen', SELECTIVE/'run_experiment.py')
    selective = load_module('selective_frozen', SELECTIVE/'selective.py')
    sys.path.insert(0, str(PROJECT/'model_development_20260907_transition'))
    import shape_inputs as inputs
    import cap_models as cap
    import scipy
    import sklearn
    OUT.mkdir()
    dump(OUT/'run_manifest.json', {'started_utc':now(), 'source_input_sha256':hashes,
        'families':FAMILIES, 'labels':LABELS, 'numpy':np.__version__, 'scipy':scipy.__version__,
        'sklearn':sklearn.__version__, 'python':sys.version, 'parameters':cap.PARAMETERS,
        'external_outcomes_opened':False})
    d = inputs.load_historical()
    assert d['X62'].shape == (8371,62) and len(set(d['group'])) == 93
    tasks = list(old.splits(d, inputs.transition.v2.old))
    assert len(tasks) == 16
    csv_witness = json.loads((PROJECT/'model_development_20260907_frontier/assessment_final/report.json').read_text())['input_sha256']
    native_witness = json.loads((RISK/'portable/manifest.json').read_text())['source_label_free_reference_hashes']
    artifacts, logs, parity = {}, [], []
    final_models = final_calibrators = None
    for context, train, test in tasks:
        tick = time.monotonic()
        member_path = SELECTIVE/'results'/f'membership_{context}.json'
        member = json.loads(member_path.read_text())
        proper, cal = np.array(member['proper_indices'],int), np.array(member['calibration_indices'],int)
        pp, cc, recomputed = old.membership(d, train, test, context)
        np.testing.assert_array_equal(proper, pp); np.testing.assert_array_equal(cal, cc)
        np.testing.assert_array_equal(train, member['enclosing_indices'])
        np.testing.assert_array_equal(test, member['test_indices'])
        for k, value in recomputed.items():
            assert member[k] == value, (context,k)
        dump(OUT/f'membership_{context}.json', member)
        models, calibrators, calibration_predictions, fitlogs = {}, {}, {}, []
        for family in FAMILIES:
            for branch, ids in [('full',train),('proper',proper)]:
                t = time.monotonic()
                fitdata = old.core_data(d, ids)
                changed = {**d, 'MEAS_CD':d['MEAS_CD'].copy()}
                changed['MEAS_CD'][np.setdiff1d(np.arange(len(d['BASE_CD'])), ids)] = np.nan
                check = old.core_data(changed, ids)
                for key in fitdata:
                    np.testing.assert_array_equal(fitdata[key],check[key])
                model = cap.fit(family, fitdata, np.arange(len(ids)))
                models[branch,family] = model
                path = OUT/f'core_{context}_{branch}_{family}.pkl'
                with path.open('xb') as stream:
                    pickle.dump(model,stream,protocol=pickle.HIGHEST_PROTOCOL)
                artifacts[str(path)] = sha(path)
                target, weight = cap.training_arrays(family,fitdata['BASE_CD'],fitdata['MEAS_CD'],fitdata['group'],fitdata['source'])
                fitlogs.append({'family':family,'branch':branch,'rows':len(ids),'groups':len(set(d['group'][ids])),
                    'iterations':int(model['model'].n_iter_), 'target_min':float(target.min()),'target_max':float(target.max()),
                    'weight_min':float(weight.min()),'weight_max':float(weight.max()),
                    'excluded_label_mutation_inputs_identical':True,'seconds':time.monotonic()-t})
            cp = cap.predict(models['proper',family], d, cal)
            calibration_predictions[f'CORE_CD_{family}'] = cp
            changed['MEAS_CD'] = d['MEAS_CD'].copy()
            changed['MEAS_CD'][np.setdiff1d(np.arange(len(d['BASE_CD'])),cal)] = np.nan
            np.testing.assert_array_equal(changed['MEAS_CD'][cal],d['MEAS_CD'][cal])
            calibrators[family] = selective.calibrate(cp,d['BASE_CD'][cal],d['MEAS_CD'][cal],d['group'][cal],alpha=.1)
            path = OUT/f'calibrator_{context}_{family}.json'
            dump(path,calibrators[family]); artifacts[str(path)] = sha(path)
        prior_cal = SELECTIVE/'results'/f'calibration_{context}.npz'
        with np.load(prior_cal,allow_pickle=False) as z:
            np.testing.assert_array_equal(calibration_predictions['CORE_CD_capped'],z['CORE_CD'])
        previous_calibrator=json.loads((SELECTIVE/'results'/f'calibrator_{context}.json').read_text())
        assert calibrators['capped'] == previous_calibrator
        idx = test if context != 'final' else np.arange(len(d['BASE_CD']))
        gate = np.ones(len(idx),dtype=bool)
        values,raw = evaluate(models,calibrators,d,idx,gate,cap,selective)
        with np.load(SELECTIVE/'results'/f'inference_{context}.npz',allow_pickle=False) as z:
            np.testing.assert_array_equal(raw['proper_core_capped'],z['CORE_CD'])
        if context != 'final':
            reference=CAPACITY/'results'/f'predictions_{context}.csv'
            assert sha(reference) == csv_witness[str(reference)]
            hashes[str(reference)] = sha(reference)
            prev=pd.read_csv(reference,usecols=['nf2_row_id','hist62_regularized__1'])
            np.testing.assert_array_equal(prev.nf2_row_id,d['nf2_row_id'][idx])
            np.testing.assert_allclose(raw['full_core_capped'],prev['hist62_regularized__1'],rtol=0,atol=1e-13)
            frame=old.historical_frame(d,idx,context)
            for key,value in values.items():frame[key]=value
            frame.to_csv(OUT/f'predictions_{context}.csv',index=False,mode='x')
            full_drift=float(np.max(np.abs(raw['full_core_capped']-prev['hist62_regularized__1'].to_numpy())))
        else:
            reference=RISK/'results/historical_inference.npz'
            assert sha(reference) == native_witness[str(reference)]
            hashes[str(reference)] = sha(reference)
            with np.load(reference,allow_pickle=False) as z:
                np.testing.assert_array_equal(raw['full_core_capped'],z['CORE_CD'])
            full_drift=0.
        parity.append({'context':context,'proper_native_exact':True,'capped_calibrator_exact':True,'full_max_abs_CD':full_drift})
        cal_path=OUT/f'calibration_{context}.npz'
        save_npz(cal_path,indices=cal,nf2_row_id=d['nf2_row_id'][cal],group=d['group'][cal].astype(str),
            X62=d['X62'][cal],BASE_CD=d['BASE_CD'][cal],MEAS_CD=d['MEAS_CD'][cal],**calibration_predictions)
        ref_path=OUT/f'inference_{context}.npz'
        save_npz(ref_path,indices=idx,X62=d['X62'][idx],BASE_CD=d['BASE_CD'][idx],XLARGE_CD=d['XLARGE_CD'][idx],
            all_model_CD=d['all_model_CD'][idx],gate=gate,**raw,**values)
        for path in [OUT/f'membership_{context}.json',cal_path,ref_path]:artifacts[str(path)]=sha(path)
        log={'context':context,'fits':fitlogs,'calibration_groups':len(set(d['group'][cal])),
             'q':{f:calibrators[f]['q'] for f in FAMILIES},'seconds':time.monotonic()-tick}
        logs.append(log)
        print(json.dumps({'context':context,'completed_core_fits':len(logs)*6,'seconds':log['seconds']}),flush=True)
        if context=='final':final_models,final_calibrators=models,calibrators
    assert len(artifacts)==192 and sum(len(x['fits']) for x in logs)==96
    for path,expected in {**hashes,**artifacts}.items():assert sha(path)==expected,path
    dump(OUT/'freeze.json',{'frozen_utc':now(),'core_count':96,'calibrator_count':48,'artifact_sha256':artifacts,
        'source_input_sha256':hashes,'contexts':[x[0] for x in tasks],'external_outcomes_opened':False,'capped_parity':parity})
    print('All 96 cores and 48 calibrators frozen. Beginning exposed diagnostics.',flush=True)
    # Authenticate and load only the previously exposed external conditions/outcomes.
    prior=json.loads((SELECTIVE/'results/complete.json').read_text())
    external_hashes={}
    for path,expected in prior['external_input_sha256'].items():
        assert sha(path)==expected,path
        external_hashes[path]=expected
    EXPOSED.mkdir()
    for name,count in [('SG_exposed',242),('W_new_challenge',255)]:
        ex=inputs.load_exposed(name)
        source=CAPACITY/'exposed_results'/f'{name}_predictions.csv'
        assert str(source) in external_hashes
        frame=pd.read_csv(source)
        assert len(frame)==count and frame.inference_gate.dtype==bool
        np.testing.assert_array_equal(frame.alpha,ex['alpha']);np.testing.assert_array_equal(frame.Re,ex['Re'])
        np.testing.assert_allclose(frame.mean8_CD,ex['BASE_CD'],rtol=0,atol=1e-13)
        np.testing.assert_allclose(frame.xlarge_CD,ex['XLARGE_CD'],rtol=0,atol=1e-13)
        idx=np.arange(count);gate=frame.inference_gate.to_numpy()
        values,raw=evaluate(final_models,final_calibrators,ex,idx,gate,cap,selective)
        np.testing.assert_allclose(values['capped_full'],frame['hist62_regularized__1'],rtol=0,atol=1e-13)
        ref=SELECTIVE/'exposed_results'/f'{name}_inference.npz'
        assert sha(ref)==prior['output_sha256'][str(ref)]
        external_hashes[str(ref)]=sha(ref)
        with np.load(ref,allow_pickle=False) as z:
            np.testing.assert_array_equal(raw['proper_core_capped'],z['CORE_CD'])
            np.testing.assert_array_equal(values['project_mean8_capped'],z['project_mean8'])
            np.testing.assert_array_equal(values['project_xlarge_capped'],z['project_xlarge'])
        for key,value in values.items():frame[key]=value
        frame.to_csv(EXPOSED/f'{name}_predictions.csv',index=False,mode='x')
        save_npz(EXPOSED/f'{name}_inference.npz',indices=idx,X62=ex['X62'],BASE_CD=ex['BASE_CD'],
            XLARGE_CD=ex['XLARGE_CD'],all_model_CD=ex['all_model_CD'],gate=gate,**raw,**values)
    output_hashes={str(p):sha(p) for p in sorted(OUT.glob('predictions_*.csv'))}
    output_hashes.update({str(p):sha(p) for p in sorted(EXPOSED.iterdir())})
    for path,expected in {**hashes,**artifacts,**external_hashes}.items():assert sha(path)==expected,path
    dump(OUT/'complete.json',{'completed_utc':now(),'core_count':96,'calibrator_count':48,'labels':LABELS,
        'splits':logs,'capped_parity':parity,'source_input_sha256':hashes,'artifact_sha256':artifacts,
        'external_input_sha256':external_hashes,'output_sha256':output_hashes,'freeze_sha256':sha(OUT/'freeze.json'),
        'status':'fixed adaptive development; not independent validation; not deployed'})
    print('Completed all frozen cap-ablation outputs.',flush=True)


if __name__=='__main__':
    try:main()
    except BaseException:
        if OUT.exists() and not (OUT/'failure.json').exists():
            dump(OUT/'failure.json',{'failed_utc':now(),'traceback':traceback.format_exc()})
        raise
