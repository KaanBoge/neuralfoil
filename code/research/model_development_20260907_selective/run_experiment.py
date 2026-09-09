"""Frozen identity-separated calibration producer; no work on import."""
from pathlib import Path
import hashlib
import json
import math
import pickle
import sys
import time
import traceback
from fractions import Fraction

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
OUT = HERE / 'results'
EXPOSED = HERE / 'exposed_results'
CAPACITY = PROJECT / 'model_development_20260907_frontier/capacity'
TRANSITION = PROJECT / 'model_development_20260907_transition'
RISK = PROJECT / 'model_development_20260907_risk_policy'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    with Path(path).open('x') as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write('\n')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def authenticate():
    """Authenticate historical dependencies before importing or loading them."""
    witnessed = {}
    manifests = [(RISK/'results/freeze.json', 'source_input_sha256'),
                 (PROJECT/'model_development_20260907_search/results/run_manifest.json', 'hashes'),
                 (TRANSITION/'results/run_manifest.json', 'hashes')]
    allowed = {
        CAPACITY/'capacity_models.py', TRANSITION/'shape_inputs.py', TRANSITION/'transition_inputs.py',
        TRANSITION/'inputs/historical.npz', TRANSITION/'shape_inputs/historical.npz',
        PROJECT/'model_development_20260906_v2/develop_v2.py',
        PROJECT/'model_development_20260906/develop_drag.py',
        PROJECT/'model_development_20260906/reproduction/dataset_occurrence.npz',
        PROJECT/'model_development_20260906/methods_audit/entry_group_map.csv',
        PROJECT/'model_development_20260906/methods_audit/ambiguous_nf2_row_ids.csv',
        CAPACITY/'portable/manifest.json',
    }
    for path, key in manifests:
        witnessed[str(path)] = sha(path)
        for name, expected in json.loads(path.read_text())[key].items():
            if Path(name) in allowed:
                assert sha(name) == expected, f'Changed dependency: {name}'
                witnessed[name] = expected
    assert allowed <= {Path(p) for p in witnessed}, 'Missing previous dependency witness'
    for path in [Path(__file__), HERE/'selective.py', HERE/'PROTOCOL.md', HERE/'test_selective.py']:
        witnessed[str(path)] = sha(path)
    return witnessed


def splits(d, old):
    ids = np.arange(len(d['BASE_CD']))
    for seed in [20260906, 20260908]:
        for fold, test in enumerate(old.group_folds(d['group'], 5, seed)):
            yield f'group_{seed}_fold_{fold}', ids[~test], ids[test]
    for source in sorted(set(d['source'])) + ['all_uiuc_volumes']:
        test = d['source'] != 'stec8' if source == 'all_uiuc_volumes' else d['source'] == source
        train = ~test & ~np.isin(d['group'], d['group'][test])
        yield f'strict_source_{source}', ids[train], ids[test]
    yield 'final', ids, np.array([], dtype=int)


def membership(d, train, test, name):
    group_names = np.array(sorted(set(d['group'][train])), dtype=str)
    seed = int(hashlib.sha256(('selective_v1:2026090727:' + name).encode('utf-8')).hexdigest()[:8], 16)
    shuffled = group_names.copy()
    np.random.default_rng(seed).shuffle(shuffled)
    cal_groups = shuffled[:math.ceil(len(shuffled)/4)]
    mask = np.isin(d['group'][train], cal_groups)
    proper, cal = train[~mask], train[mask]
    assert len(proper) and len(cal)
    for a, b in [(proper, cal), (proper, test), (cal, test)]:
        assert not set(d['group'][a]) & set(d['group'][b])
    assert np.array_equal(np.sort(np.r_[proper, cal]), np.sort(train))
    record = {'split': name, 'seed': seed, 'calibration_fraction': 'ceil(G/4)',
              'enclosing_groups': group_names.tolist(), 'shuffled_groups': shuffled.tolist(),
              'proper_groups': sorted(set(d['group'][proper])),
              'calibration_groups': sorted(set(d['group'][cal])),
              'test_groups': sorted(set(d['group'][test])), 'group_overlap': 0}
    for label, ids in [('enclosing', train), ('proper', proper), ('calibration', cal), ('test', test)]:
        record[label+'_indices'] = ids.tolist()
        record[label+'_nf2_row_ids'] = d['nf2_row_id'][ids].tolist()
    return proper, cal, record


def core_data(d, idx):
    """Only proper rows and required feature/weight/target fields cross fit boundary."""
    return {key: d[key][idx].copy() for key in ['X62', 'BASE_CD', 'MEAS_CD', 'group', 'source']}


def historical_frame(d, idx, name):
    frame = pd.DataFrame({'split': name, 'nf2_row_id': d['nf2_row_id'][idx],
        'group': d['group'][idx], 'source': d['source'][idx], 'entry': d['entry'][idx],
        'Re': d['Re'][idx], 'alpha': d['alpha'][idx], 'measured_CD': d['MEAS_CD'][idx],
        'mean8_CD': d['BASE_CD'][idx], 'xlarge_CD': d['XLARGE_CD'][idx],
        'inference_gate': np.ones(len(idx), dtype=bool)})
    return frame


def predictions(selective, model, core, base, xlarge, gate):
    mean = selective.project(model, core, base, base, gate)
    xl = selective.project(model, core, base, xlarge, gate)
    np.testing.assert_array_equal(mean['lower'], xl['lower'])
    np.testing.assert_array_equal(mean['upper'], xl['upper'])
    np.testing.assert_array_equal(mean['prediction'][~gate], base[~gate])
    np.testing.assert_array_equal(xl['prediction'][~gate], xlarge[~gate])
    return {'project_mean8': mean['prediction'], 'project_xlarge': xl['prediction'],
        'proper_core': np.where(gate, core, base), 'proper_half': np.where(gate, base+.5*(core-base), base),
        'interval_lower': mean['lower'], 'interval_upper': mean['upper'],
        'project_mean8__intervened': mean['intervened'], 'project_xlarge__intervened': xl['intervened'],
        'interval_applicable': mean['applicable']}


def references(path, d, idx, core, gate, values):
    assert not path.exists()
    np.savez_compressed(path, indices=idx, X62=d['X62'][idx], BASE_CD=d['BASE_CD'][idx],
        XLARGE_CD=d['XLARGE_CD'][idx], CORE_CD=core, all_model_CD=d['all_model_CD'][idx], gate=gate, **values)


def main():
    assert not OUT.exists() and not EXPOSED.exists(), 'Preserve earlier attempt; do not overwrite'
    source_hashes = authenticate()
    sys.path[:0] = [str(CAPACITY), str(TRANSITION)]
    import capacity_models
    import shape_inputs as inputs
    import selective
    import scipy
    import sklearn
    OUT.mkdir()
    dump(OUT/'run_manifest.json', {'started_utc': now(), 'source_input_sha256': source_hashes,
        'numpy': np.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__,
        'python': sys.version, 'alpha': .10, 'external_outcomes_opened': False})
    d = inputs.load_historical()
    assert d['X62'].shape == (8371, 62) and len(set(d['group'])) == 93
    tasks = list(splits(d, inputs.transition.v2.old))
    assert len(tasks) == 16
    artifacts, logs = {}, []
    final_core = final_calibrator = final_q = None
    for name, train, test in tasks:
        start = time.monotonic()
        proper, cal, record = membership(d, train, test, name)
        fit_data = core_data(d, proper)
        mutated = {**d, 'MEAS_CD': d['MEAS_CD'].copy()}
        mutated['MEAS_CD'][np.setdiff1d(np.arange(len(d['BASE_CD'])), proper)] = np.nan
        for key, values in fit_data.items():
            np.testing.assert_array_equal(values, core_data(mutated, proper)[key])
        core_model = capacity_models.fit('hist62_regularized', fit_data, np.arange(len(proper)))
        cal_core = capacity_models.predict(core_model, d, cal)
        cal_args = (cal_core, d['BASE_CD'][cal], d['MEAS_CD'][cal], d['group'][cal])
        calibrator = selective.calibrate(*cal_args, alpha=.10)
        mutated['MEAS_CD'] = d['MEAS_CD'].copy()
        mutated['MEAS_CD'][np.setdiff1d(np.arange(len(d['BASE_CD'])), cal)] = np.nan
        np.testing.assert_array_equal(cal_args[2], mutated['MEAS_CD'][cal])
        scores = np.array([np.max(np.abs(d['MEAS_CD'][cal][d['group'][cal] == g]-cal_core[d['group'][cal] == g]) /
                                    d['BASE_CD'][cal][d['group'][cal] == g]) for g in sorted(set(d['group'][cal]))])
        rank = math.ceil((len(scores)+1)*Fraction(9, 10))
        q = float(np.sort(scores)[rank-1]) if rank <= len(scores) else float('inf')
        assert calibrator['rank'] == rank
        assert calibrator['q'] == (q if np.isfinite(q) else None)
        record.update({'calibration_rank': rank, 'calibration_q': q if np.isfinite(q) else None,
            'unbounded': not np.isfinite(q), 'calibration_group_scores': scores.tolist(),
            'proper_input_excluded_label_mutation_identical': True,
            'calibration_input_excluded_label_mutation_identical': True, 'post_calibration_refit': False})
        core_path, cal_path = OUT/f'core_{name}.pkl', OUT/f'calibrator_{name}.json'
        with core_path.open('xb') as stream:
            pickle.dump(core_model, stream, protocol=pickle.HIGHEST_PROTOCOL)
        dump(cal_path, calibrator)
        dump(OUT/f'membership_{name}.json', record)
        cp = OUT/f'calibration_{name}.npz'
        assert not cp.exists()
        np.savez_compressed(cp, indices=cal, nf2_row_id=d['nf2_row_id'][cal], group=d['group'][cal].astype(str),
            X62=d['X62'][cal], BASE_CD=d['BASE_CD'][cal], CORE_CD=cal_core, MEAS_CD=d['MEAS_CD'][cal])
        idx = test if name != 'final' else np.arange(len(d['BASE_CD']))
        core = capacity_models.predict(core_model, d, idx)
        gate = np.ones(len(idx), dtype=bool)
        values = predictions(selective, calibrator, core, d['BASE_CD'][idx], d['XLARGE_CD'][idx], gate)
        expected_lower = core-q*d['BASE_CD'][idx]
        expected_upper = core+q*d['BASE_CD'][idx]
        np.testing.assert_array_equal(values['interval_lower'], expected_lower)
        np.testing.assert_array_equal(values['interval_upper'], expected_upper)
        references(OUT/f'inference_{name}.npz', d, idx, core, gate, values)
        if name != 'final':
            frame = historical_frame(d, idx, name)
            for key, value in values.items():
                frame[key] = value
            frame['calibration_q'] = q
            frame.to_csv(OUT/f'predictions_{name}.csv', index=False, mode='x')
        for path in [core_path, cal_path, OUT/f'membership_{name}.json', cp, OUT/f'inference_{name}.npz']:
            artifacts[str(path)] = sha(path)
        log = {'split': name, 'proper_rows': len(proper), 'calibration_rows': len(cal), 'outer_rows': len(test),
            'proper_groups': len(set(d['group'][proper])), 'calibration_groups': len(scores),
            'q': q if np.isfinite(q) else None, 'unbounded': not np.isfinite(q), 'seconds': time.monotonic()-start}
        logs.append(log)
        print(json.dumps(log, allow_nan=False), flush=True)
        if name == 'final':
            final_core, final_calibrator, final_q = core_model, calibrator, q
    assert len(artifacts) == 80 and len(logs) == 16
    for filename, expected in {**source_hashes, **artifacts}.items():
        assert sha(filename) == expected, filename
    dump(OUT/'freeze.json', {'frozen_utc': now(), 'core_count': 16, 'calibrator_count': 16,
        'artifact_sha256': artifacts, 'source_input_sha256': source_hashes,
        'external_outcomes_opened': False, 'contexts': [n for n, _, _ in tasks]})
    print('All 16 proper cores and calibrators frozen; beginning exposed diagnostics.', flush=True)
    # External input hashes and outcomes are accessed only beyond the frozen boundary.
    external_hashes = {}
    prior = json.loads((CAPACITY/'results/run_manifest.json').read_text())['hashes']
    csv_witness = json.loads((CAPACITY/'portable/manifest.json').read_text())['hashes']
    transition_witness = json.loads((TRANSITION/'results/run_manifest.json').read_text())['hashes']
    forward_manifest = PROJECT/'model_development_20260907_search/exposed_results/fit_manifest.json'
    forward_witness = json.loads(forward_manifest.read_text())['hashes']
    for path in [CAPACITY/'results/run_manifest.json', CAPACITY/'portable/manifest.json',
                 TRANSITION/'results/run_manifest.json', forward_manifest]:
        external_hashes[str(path)] = sha(path)
    EXPOSED.mkdir()
    for name, count in [('SG_exposed', 242), ('W_new_challenge', 255)]:
        paths = [TRANSITION/'inputs'/f'{name}.npz', TRANSITION/'shape_inputs'/f'{name}.npz',
                 PROJECT/'model_development_20260907_search/exposed_inputs/forward_verified'/f'{name}.npz',
                 CAPACITY/'exposed_results'/f'{name}_predictions.csv']
        for path in paths:
            candidates = [w[str(path)] for w in [prior, csv_witness, transition_witness, forward_witness] if str(path) in w]
            assert candidates and all(sha(path) == expected for expected in candidates), str(path)
            external_hashes[str(path)] = sha(path)
        ex = inputs.load_exposed(name)
        frame = pd.read_csv(paths[-1])
        assert len(frame) == count and frame.inference_gate.dtype == bool
        np.testing.assert_array_equal(frame.alpha.to_numpy(), ex['alpha'])
        np.testing.assert_array_equal(frame.Re.to_numpy(), ex['Re'])
        np.testing.assert_allclose(frame.mean8_CD.to_numpy(), ex['BASE_CD'], rtol=0, atol=1e-13)
        np.testing.assert_allclose(frame.xlarge_CD.to_numpy(), ex['XLARGE_CD'], rtol=0, atol=1e-13)
        idx = np.arange(count)
        core = capacity_models.predict(final_core, ex, idx)
        gate = frame.inference_gate.to_numpy()
        values = predictions(selective, final_calibrator, core, ex['BASE_CD'], ex['XLARGE_CD'], gate)
        for key, value in values.items():
            frame[key] = value
        frame['calibration_q'] = final_q
        frame.to_csv(EXPOSED/f'{name}_predictions.csv', index=False, mode='x')
        references(EXPOSED/f'{name}_inference.npz', ex, idx, core, gate, values)
    outputs = {str(p): sha(p) for p in sorted(OUT.glob('predictions_*.csv'))}
    outputs.update({str(p): sha(p) for p in sorted(EXPOSED.iterdir())})
    for filename, expected in {**source_hashes, **artifacts, **external_hashes}.items():
        assert sha(filename) == expected, filename
    dump(OUT/'complete.json', {'completed_utc': now(), 'splits': logs, 'core_count': 16, 'calibrator_count': 16,
        'artifact_sha256': artifacts, 'output_sha256': outputs, 'source_input_sha256': source_hashes,
        'external_input_sha256': external_hashes, 'freeze_sha256': sha(OUT/'freeze.json'),
        'status': 'fixed adaptive exploratory procedure; not independent validation; not deployed'})
    print('Completed all 16 contexts and exposed diagnostics.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        if OUT.exists() and not (OUT/'failure.json').exists():
            dump(OUT/'failure.json', {'failed_utc': now(), 'traceback': traceback.format_exc()})
        raise
