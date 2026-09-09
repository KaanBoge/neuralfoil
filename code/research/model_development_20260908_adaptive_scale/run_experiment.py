"""64 fixed Stage B fits. Requires an explicitly pinned completed Stage A freeze.

No work on import. Do not launch without main-agent clearance. Existing outputs
are never overwritten. Stage A comparative outcomes are never used for selection.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import pickle
import sys
import time
import traceback
import warnings
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
A = PROJECT/'model_development_20260907_cap_ablation'
SELECTIVE = PROJECT/'model_development_20260907_selective'
TRANSITION = PROJECT/'model_development_20260907_transition'
CAPACITY = PROJECT/'model_development_20260907_frontier/capacity'
OUT, EXPOSED = HERE/'results', HERE/'exposed_results'
INNER_SEED = 2026090731
LABELS = ['adaptive_project_mean8', 'adaptive_project_xlarge',
          'proper_upper_free_full', 'proper_upper_free_half']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_bytes(path, expected):
    data = Path(path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected, f'Changed artifact: {path}'
    return data


def dump(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def save_npz(path, **arrays):
    with Path(path).open('xb') as f:
        np.savez_compressed(f, **arrays)


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authenticate(expected_freeze):
    """Verify all A frozen bytes but do not inspect its comparative outcomes."""
    path = A/'results/freeze.json'
    frozen = json.loads(checked_bytes(path, expected_freeze))
    assert frozen['core_count'] == 96 and frozen['calibrator_count'] == 48
    assert len(frozen['artifact_sha256']) == 192 and len(frozen['contexts']) == 16
    assert frozen['external_outcomes_opened'] is False
    witnessed = {str(path): expected_freeze}
    for name, digest in {**frozen['source_input_sha256'], **frozen['artifact_sha256']}.items():
        checked_bytes(name, digest)
        witnessed[name] = digest
    for path in [HERE/'PROTOCOL.md', HERE/'adaptive_scale.py', HERE/'test_adaptive_scale.py', Path(__file__)]:
        witnessed[str(path)] = sha(path)
    for required in [A/'cap_models.py', SELECTIVE/'run_experiment.py', TRANSITION/'shape_inputs.py',
                     TRANSITION/'transition_inputs.py', SELECTIVE/'results/complete.json']:
        assert str(required) in witnessed, f'Missing inherited witness: {required}'
    return frozen, witnessed


def rows_for_fit(d, idx):
    return {k: d[k][idx].copy() for k in ['X62', 'BASE_CD', 'MEAS_CD', 'group', 'source']}


def infer(scale_lib, cal, core, b, s, xl, gate, cap):
    p = scale_lib.project(cal, core, b, s, b, gate)
    x = scale_lib.project(cal, core, b, s, xl, gate)
    np.testing.assert_array_equal(p['lower'], x['lower'])
    np.testing.assert_array_equal(p['upper'], x['upper'])
    np.testing.assert_array_equal(p['prediction'][~gate], b[~gate])
    np.testing.assert_array_equal(x['prediction'][~gate], xl[~gate])
    return {'adaptive_project_mean8': p['prediction'], 'adaptive_project_xlarge': x['prediction'],
        'proper_upper_free_full': np.where(gate, core, b),
        'proper_upper_free_half': np.where(gate, cap.half(core, b), b),
        'adaptive_project_mean8__intervened': p['intervened'],
        'adaptive_project_xlarge__intervened': x['intervened'],
        'interval_lower': p['lower'], 'interval_upper': p['upper'],
        'interval_applicable': p['applicable'], 'dimensionless_scale': s,
        'scale_CD': p['scale_CD']}


def save_reference(path, d, idx, core, gate, values):
    save_npz(path, indices=idx, X62=d['X62'][idx], BASE_CD=d['BASE_CD'][idx],
        XLARGE_CD=d['XLARGE_CD'][idx], CORE_CD=core,
        all_model_CD=d['all_model_CD'][idx], gate=gate, **values)


def main(expected_a_freeze):
    assert not OUT.exists() and not EXPOSED.exists(), 'Preserve previous attempts; use a successor directory'
    frozen, hashes = authenticate(expected_a_freeze)
    old = load_module('selective_producer_stage_b_readonly', SELECTIVE/'run_experiment.py')
    cap = load_module('cap_models_stage_b_readonly', A/'cap_models.py')
    sys.path.insert(0, str(TRANSITION))
    import shape_inputs as inputs
    import adaptive_scale as scale_lib
    import scipy
    import sklearn
    OUT.mkdir()
    dump(OUT/'run_manifest.json', {'started_utc': now(), 'source_input_sha256': hashes,
        'a_freeze_sha256': expected_a_freeze, 'core_family': 'upper_free', 'inner_seed': INNER_SEED,
        'scale_parameters': scale_lib.PARAMETERS, 'target_floor': scale_lib.TARGET_FLOOR,
        'alpha': .10, 'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
        'sklearn': sklearn.__version__, 'external_outcomes_opened': False,
        'selection_used_a_comparative_outcomes': False})
    d = inputs.load_historical()
    assert d['X62'].shape == (8371, 62) and len(set(d['group'])) == 93
    tasks = list(old.splits(d, inputs.transition.v2.old))
    assert [t[0] for t in tasks] == frozen['contexts'] and len(tasks) == 16
    artifacts, logs = {}, []
    final_core = final_scale = final_calibrator = None
    for context, train, test in tasks:
        tick = time.monotonic()
        mem_path = A/'results'/f'membership_{context}.json'
        member = json.loads(checked_bytes(mem_path, frozen['artifact_sha256'][str(mem_path)]))
        proper, cal = np.array(member['proper_indices'], int), np.array(member['calibration_indices'], int)
        pp, cc, recomputed = old.membership(d, train, test, context)
        np.testing.assert_array_equal(proper, pp); np.testing.assert_array_equal(cal, cc)
        for key, value in recomputed.items():
            assert member[key] == value, (context, key)
        core_path = A/'results'/f'core_{context}_proper_upper_free.pkl'
        # Locally created trusted model, deserialized from the exact authenticated bytes.
        core_model = pickle.loads(checked_bytes(core_path, frozen['artifact_sha256'][str(core_path)]))
        assert core_model['family'] == 'upper_free' and core_model['feature_key'] == 'X62'
        fit_data = rows_for_fit(d, proper)
        changed = {**d, 'MEAS_CD': d['MEAS_CD'].copy()}
        changed['MEAS_CD'][np.setdiff1d(np.arange(len(d['BASE_CD'])), proper)] = np.nan
        for key, value in fit_data.items():
            np.testing.assert_array_equal(value, rows_for_fit(changed, proper)[key])
        inner_oof = np.full(len(proper), np.nan)
        fold_id = np.full(len(proper), -1, dtype=int)
        seen = np.zeros(len(proper), int)
        inner_memberships, fitlogs = [], []
        folds = list(inputs.transition.v2.old.group_folds(fit_data['group'], 3, INNER_SEED))
        assert len(folds) == 3 and len(set(fit_data['group'])) >= 3
        for fold, held in enumerate(folds):
            held = np.asarray(held)
            assert held.shape == (len(proper),) and held.dtype == bool and held.any() and (~held).any()
            local_train, local_test = np.flatnonzero(~held), np.flatnonzero(held)
            inner_train, inner_test = proper[local_train], proper[local_test]
            assert not set(d['group'][inner_train]) & set(d['group'][inner_test])
            assert not set(d['group'][inner_train]) & set(d['group'][np.r_[cal, test]])
            inner_data = rows_for_fit(d, inner_train)
            t = time.monotonic()
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                inner_model = cap.fit('upper_free', inner_data, np.arange(len(inner_train)))
            # Prediction receives a proper-only dictionary; outer/cal labels never cross this boundary.
            inner_oof[local_test] = cap.predict(inner_model, fit_data, local_test)
            seen[local_test] += 1; fold_id[local_test] = fold
            path = OUT/f'inner_core_{context}_fold_{fold}.pkl'
            with path.open('xb') as f: pickle.dump(inner_model, f, protocol=pickle.HIGHEST_PROTOCOL)
            artifacts[str(path)] = sha(path)
            inner_memberships.append({'fold': fold, 'train_indices': inner_train.tolist(),
                'test_indices': inner_test.tolist(), 'train_groups': sorted(set(d['group'][inner_train])),
                'test_groups': sorted(set(d['group'][inner_test])),
                'train_nf2_row_ids': d['nf2_row_id'][inner_train].tolist(),
                'test_nf2_row_ids': d['nf2_row_id'][inner_test].tolist()})
            fitlogs.append({'kind': 'inner_core', 'fold': fold, 'rows': len(inner_train),
                'iterations': int(inner_model['model'].n_iter_), 'seconds': time.monotonic()-t,
                'warnings': [str(w.message) for w in caught]})
        assert np.all(seen == 1) and np.isfinite(inner_oof).all() and np.all(inner_oof > 0)
        target, weight = scale_lib.training_arrays(fit_data['MEAS_CD'], inner_oof,
            fit_data['BASE_CD'], fit_data['group'], fit_data['source'])
        t = time.monotonic()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            scale_model = scale_lib.fit(fit_data['X62'], fit_data['MEAS_CD'], inner_oof,
                fit_data['BASE_CD'], fit_data['group'], fit_data['source'])
        fitlogs.append({'kind': 'scale', 'rows': len(proper), 'iterations': int(scale_model['model'].n_iter_),
            'seconds': time.monotonic()-t, 'warnings': [str(w.message) for w in caught],
            'target_min': float(target.min()), 'target_max': float(target.max()),
            'weight_min': float(weight.min()), 'weight_max': float(weight.max())})
        scale_path = OUT/f'scale_{context}.pkl'
        with scale_path.open('xb') as f: pickle.dump(scale_model, f, protocol=pickle.HIGHEST_PROTOCOL)
        cal_core = cap.predict(core_model, d, cal)
        # Read ONLY matching upper_free calibration core; no comparative scores or family selection.
        old_cp = A/'results'/f'calibration_{context}.npz'
        import io
        with np.load(io.BytesIO(checked_bytes(old_cp, frozen['artifact_sha256'][str(old_cp)])), allow_pickle=False) as z:
            np.testing.assert_array_equal(z['indices'], cal)
            np.testing.assert_array_equal(z['CORE_CD_upper_free'], cal_core)
        cal_scale = scale_lib.predict(scale_model, d['X62'][cal])
        calibrator = scale_lib.calibrate(cal_core, d['BASE_CD'][cal], cal_scale,
            d['MEAS_CD'][cal], d['group'][cal], alpha=.10)
        q = np.inf if calibrator['q'] is None else calibrator['q']
        dump(OUT/f'calibrator_{context}.json', calibrator)
        record = dict(recomputed)
        record.update({'a_proper_core_path': str(core_path), 'a_proper_core_sha256': hashes[str(core_path)],
            'inner_seed': INNER_SEED, 'inner_folds': inner_memberships,
            'proper_input_excluded_label_mutation_identical': True, 'post_calibration_refit': False})
        dump(OUT/f'membership_{context}.json', record)
        save_npz(OUT/f'scale_training_{context}.npz', indices=proper, nf2_row_id=d['nf2_row_id'][proper],
            X62=fit_data['X62'], BASE_CD=fit_data['BASE_CD'], MEAS_CD=fit_data['MEAS_CD'],
            group=fit_data['group'].astype(str), source=fit_data['source'].astype(str),
            inner_fold=fold_id, INNER_OOF_CORE_CD=inner_oof, scale_target=target, scale_weight=weight,
            dimensionless_scale=scale_lib.predict(scale_model, fit_data['X62']))
        save_npz(OUT/f'calibration_{context}.npz', indices=cal, nf2_row_id=d['nf2_row_id'][cal],
            X62=d['X62'][cal], BASE_CD=d['BASE_CD'][cal], MEAS_CD=d['MEAS_CD'][cal],
            CORE_CD=cal_core, dimensionless_scale=cal_scale,
            scale_CD=scale_lib.scale_cd(d['BASE_CD'][cal], cal_scale), group=d['group'][cal].astype(str))
        idx = test if context != 'final' else np.arange(len(d['BASE_CD']))
        core = cap.predict(core_model, d, idx)
        s = scale_lib.predict(scale_model, d['X62'][idx]); gate = np.ones(len(idx), bool)
        values = infer(scale_lib, calibrator, core, d['BASE_CD'][idx], s, d['XLARGE_CD'][idx], gate, cap)
        save_reference(OUT/f'inference_{context}.npz', d, idx, core, gate, values)
        if context != 'final':
            frame = old.historical_frame(d, idx, context)
            for key, value in values.items(): frame[key] = value
            frame['calibration_q'] = q
            frame.to_csv(OUT/f'predictions_{context}.csv', index=False, mode='x')
        for path in [scale_path, OUT/f'calibrator_{context}.json', OUT/f'membership_{context}.json',
                     OUT/f'scale_training_{context}.npz', OUT/f'calibration_{context}.npz', OUT/f'inference_{context}.npz']:
            artifacts[str(path)] = sha(path)
        log = {'context': context, 'new_fits': fitlogs, 'proper_rows': len(proper), 'calibration_rows': len(cal),
            'outer_rows': len(test), 'calibration_groups': calibrator['calibration_groups'],
            'q': calibrator['q'], 'seconds': time.monotonic()-tick}
        logs.append(log)
        print(json.dumps({'context': context, 'completed_new_fits': len(logs)*4,
                          'seconds': log['seconds']}), flush=True)
        if context == 'final': final_core, final_scale, final_calibrator = core_model, scale_model, calibrator
    assert len(artifacts) == 144 and sum(len(x['new_fits']) for x in logs) == 64
    for path, digest in {**hashes, **artifacts}.items(): assert sha(path) == digest, path
    dump(OUT/'freeze.json', {'frozen_utc': now(), 'new_fit_count': 64, 'inner_core_count': 48,
        'scale_count': 16, 'calibrator_count': 16, 'a_proper_core_count': 16,
        'a_freeze_sha256': expected_a_freeze, 'artifact_sha256': artifacts, 'source_input_sha256': hashes,
        'contexts': [t[0] for t in tasks], 'external_outcomes_opened': False})
    print('All64 new fits and16 calibrators frozen; beginning previously exposed diagnostics.', flush=True)
    # This is the first external feature/condition/outcome loading boundary for B.
    prior_path = SELECTIVE/'results/complete.json'
    prior = json.loads(checked_bytes(prior_path, hashes[str(prior_path)]))
    external_hashes = prior['external_input_sha256'].copy()
    for path, digest in external_hashes.items(): checked_bytes(path, digest)
    EXPOSED.mkdir()
    for name, count in [('SG_exposed', 242), ('W_new_challenge', 255)]:
        ex = inputs.load_exposed(name)
        csv_path = CAPACITY/'exposed_results'/f'{name}_predictions.csv'
        assert str(csv_path) in external_hashes
        import io
        frame = pd.read_csv(io.BytesIO(checked_bytes(csv_path, external_hashes[str(csv_path)])))
        assert len(frame) == count and frame.inference_gate.dtype == bool
        np.testing.assert_array_equal(frame.alpha, ex['alpha']); np.testing.assert_array_equal(frame.Re, ex['Re'])
        np.testing.assert_allclose(frame.mean8_CD, ex['BASE_CD'], atol=1e-13, rtol=0)
        np.testing.assert_allclose(frame.xlarge_CD, ex['XLARGE_CD'], atol=1e-13, rtol=0)
        idx=np.arange(count);gate=frame.inference_gate.to_numpy()
        core=cap.predict(final_core, ex, idx);s=scale_lib.predict(final_scale, ex['X62'])
        values=infer(scale_lib, final_calibrator, core, ex['BASE_CD'], s, ex['XLARGE_CD'], gate, cap)
        for key,value in values.items():frame[key]=value
        frame['calibration_q']=np.inf if final_calibrator['q'] is None else final_calibrator['q']
        frame.to_csv(EXPOSED/f'{name}_predictions.csv', index=False, mode='x')
        save_reference(EXPOSED/f'{name}_inference.npz', ex, idx, core, gate, values)
    outputs={str(p):sha(p) for p in sorted(OUT.glob('predictions_*.csv'))}
    outputs.update({str(p):sha(p) for p in sorted(EXPOSED.iterdir())})
    for path,digest in {**hashes,**artifacts,**external_hashes}.items():assert sha(path)==digest,path
    dump(OUT/'complete.json', {'completed_utc':now(), 'new_fit_count':64, 'inner_core_count':48,
        'scale_count':16, 'calibrator_count':16, 'splits':logs, 'labels':LABELS,
        'artifact_sha256':artifacts, 'source_input_sha256':hashes, 'external_input_sha256':external_hashes,
        'output_sha256':outputs, 'freeze_sha256':sha(OUT/'freeze.json'),
        'status':'fixed exploratory adaptive-scale experiment; not independent validation; not deployed'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--a-freeze-sha256',required=True,help='Root-approved pinned Stage A freeze hash')
    args=parser.parse_args()
    try:main(args.a_freeze_sha256)
    except BaseException:
        if OUT.exists() and not (OUT/'failure.json').exists():
            dump(OUT/'failure.json',{'failed_utc':now(),'traceback':traceback.format_exc()})
        raise
