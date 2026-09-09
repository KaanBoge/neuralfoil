"""Three fixed risk policies; matching historical OOF fits precede external scoring."""
from pathlib import Path
import hashlib
import json
import pickle
import sys
import time
import numpy as np
import pandas as pd
import scipy
import sklearn
import risk_policy

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
FRONTIER = PROJECT / 'model_development_20260907_frontier'
CAPACITY = FRONTIER / 'capacity'
sys.path[:0] = [str(PROJECT / 'model_development_20260907_transition'), str(CAPACITY)]
import shape_inputs as inputs
import capacity_models

OUT = HERE / 'results'
CORE = 'hist62_regularized__1'
HALF = 'hist62_regularized__0.5'
VARIANTS = {'risk_transfer': (True, 1.), 'unpenalized_transfer': (True, 0.), 'risk_group': (False, 1.)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def splits(d):
    ids = np.arange(len(d['BASE_CD']))
    for seed in [20260906, 20260908]:
        for fold, test in enumerate(inputs.transition.v2.old.group_folds(d['group'], 5, seed)):
            yield f'group_{seed}_fold_{fold}', ids[~test], ids[test]
    for source in sorted(set(d['source'])) + ['all_uiuc_volumes']:
        test = d['source'] != 'stec8' if source == 'all_uiuc_volumes' else d['source'] == source
        train = ~test & ~np.isin(d['group'], d['group'][test])
        yield f'strict_source_{source}', ids[train], ids[test]


def load_context(d, idx, split):
    """No access to labels outside idx; archive witnesses precede archive loading."""
    witness = FRONTIER / 'union_historical/results' / f'weights_{split}.json'
    hashes = {str(witness): sha(witness)}
    expected = json.loads(witness.read_text())['input_sha256']

    def archive(path):
        assert str(path) in expected, f'Missing prior archive witness: {path}'
        digest = sha(path)
        assert digest == expected[str(path)], f'Archive changed: {path}'
        hashes[str(path)] = digest
        with np.load(path, allow_pickle=False) as z:
            return {k: z[k].copy() for k in z.files}

    group = archive(CAPACITY / 'results' / f'{split}_inner_group.npz')
    np.testing.assert_array_equal(group['indices'], idx)
    np.testing.assert_array_equal(group['identity'], d['BASE_CD'][idx])
    np.testing.assert_array_equal(group['xlarge_fixed'], d['XLARGE_CD'][idx])
    np.testing.assert_allclose(group[HALF], d['BASE_CD'][idx] + .5*(group[CORE]-d['BASE_CD'][idx]), rtol=0, atol=1e-15)
    inner_logs = []
    for fold, test in enumerate(inputs.transition.v2.old.group_folds(d['group'][idx], 3, 20260907)):
        assert not set(d['group'][idx[~test]]) & set(d['group'][idx[test]])
        inner_logs.append({'fold': fold, 'train_rows': int((~test).sum()), 'test_rows': int(test.sum()), 'group_overlap': 0})
    transfer_ids, transfer_core, transfers = [], [], []
    for source in sorted(set(d['source'][idx])):
        test = d['source'][idx] == source
        train = ~test & ~np.isin(d['group'][idx], d['group'][idx[test]])
        path = CAPACITY / 'results' / f'{split}_inner_transfer_{source}.npz'
        if len(set(d['group'][idx[train]])) < 6 or train.sum() < 300:
            assert not path.exists(), 'Unexpected unsupported transfer archive'
            transfers.append({'source': source, 'status': 'insufficient_training_support', 'train_rows': int(train.sum())})
            continue
        z = archive(path)
        np.testing.assert_array_equal(z['train_indices'], idx[train])
        np.testing.assert_array_equal(z['test_indices'], idx[test])
        np.testing.assert_array_equal(z['identity'], d['BASE_CD'][idx[test]])
        assert not set(d['group'][idx[train]]) & set(d['group'][idx[test]])
        assert not set(d['source'][idx[train]]) & {source}
        transfer_ids.append(idx[test])
        transfer_core.append(z[CORE])
        transfers.append({'source': source, 'status': 'used', 'train_rows': int(train.sum()), 'test_rows': int(test.sum()), 'group_overlap': 0})
    ti = np.concatenate(transfer_ids) if transfer_ids else np.array([], dtype=int)
    tc = np.concatenate(transfer_core) if transfer_core else np.array([], dtype=float)
    assert len(np.unique(ti)) == len(ti) and set(ti) <= set(idx)
    return {'group_indices': idx.copy(), 'group_core': group[CORE], 'transfer_indices': ti, 'transfer_core': tc,
            'input_sha256': hashes, 'inner_group_log': inner_logs, 'transfer_log': transfers}


def build_fit_inputs(d, context, use_transfer):
    gi, gc = context['group_indices'], context['group_core']
    ti, tc = context['transfer_indices'], context['transfer_core']
    do_transfer = use_transfer and len(ti) > 0
    blocks = [(gi, gc)] + ([(ti, tc)] if do_transfer else [])
    weights = []
    for idx, _ in blocks:
        w = (1. + capacity_models.balanced_weights(d['group'][idx], d['source'][idx])) / 2.
        weights.append(w/w.sum()/len(blocks))
    idx = np.concatenate([v[0] for v in blocks])
    core = np.concatenate([v[1] for v in blocks])
    return {'base': d['BASE_CD'][idx], 'core': core, 'y': d['MEAS_CD'][idx],
            'all_model_CD': d['all_model_CD'][idx], 'weights': np.concatenate(weights),
            'feature_reference': (d['BASE_CD'][gi], gc, d['all_model_CD'][gi])}, idx, bool(do_transfer)


def fit_split(d, tr, te, split):
    assert not set(d['group'][tr]) & set(d['group'][te])
    context = load_context(d, tr, split)
    models = {}
    for label, (augmented, penalty) in VARIANTS.items():
        args, fit_idx, augmented_used = build_fit_inputs(d, context, augmented)
        assert set(fit_idx) <= set(tr) and not set(fit_idx) & set(te)
        model = risk_policy.fit(**args, penalty=penalty)
        # Deliberately corrupt every excluded outcome; fit arrays must not change.
        mutated = {**d, 'MEAS_CD': d['MEAS_CD'].copy()}
        mutated['MEAS_CD'][np.setdiff1d(np.arange(len(d['BASE_CD'])), tr)] = np.nan
        check, _, _ = build_fit_inputs(mutated, context, augmented)
        for key in ['base', 'core', 'y', 'all_model_CD', 'weights']:
            np.testing.assert_array_equal(args[key], check[key])
        for aa, bb in zip(args['feature_reference'], check['feature_reference']):
            np.testing.assert_array_equal(aa, bb)
        model['training'] = {'split': split, 'variant': label, 'training_indices': tr.tolist(),
            'training_nf2_row_ids': d['nf2_row_id'][tr].tolist(), 'training_groups': sorted(set(d['group'][tr])),
            'outer_test_rows': len(te), 'group_overlap': 0, 'transfer_augmentation_requested': augmented,
            'transfer_augmentation_used': augmented_used, 'group_context_rows': len(tr),
            'transfer_context_rows': len(context['transfer_indices']) if augmented_used else 0,
            'input_sha256': context['input_sha256'], 'inner_group_log': context['inner_group_log'],
            'transfer_log': context['transfer_log'], 'excluded_label_mutation_inputs_identical': True}
        path = OUT / f'policy_{split}_{label}.json'
        dump(path, model)
        models[label] = json.loads(path.read_text())
    return models, context['input_sha256']


def score_models(frame, d, idx, models, core, gate):
    np.testing.assert_allclose(frame.mean8_CD.to_numpy(), d['BASE_CD'][idx], atol=1e-13, rtol=0)
    assert gate.dtype == bool and gate.shape == (len(frame),)
    for label, model in models.items():
        pred, strength = risk_policy.predict(model, d['BASE_CD'][idx], core, d['all_model_CD'][idx], gate)
        assert np.all(strength >= 0) and np.all(strength <= 1 + 1e-15)
        np.testing.assert_array_equal(pred[~gate], d['BASE_CD'][idx][~gate])
        frame[label], frame[label+'__strength'] = pred, strength
    return frame


def verify_existing_sources():
    # Preserve producer metadata and validate historically relevant dependency hashes.
    path = CAPACITY / 'results/run_manifest.json'
    manifest = json.loads(path.read_text())
    verified = {str(path): sha(path)}
    for filename, expected in manifest['hashes'].items():
        if 'SG_exposed' in filename or 'W_new_challenge' in filename:
            continue  # Do not read external outcomes/features before policy freeze.
        assert sha(filename) == expected, filename
        verified[filename] = expected
    return verified


def main():
    OUT.mkdir(exist_ok=False)
    hashes = verify_existing_sources()
    for path in [Path(__file__), HERE/'risk_policy.py', HERE/'PROTOCOL.md', HERE/'test_risk_policy.py',
                 Path(inputs.__file__), Path(capacity_models.__file__),
                 FRONTIER/'assessment_final/report.json', CAPACITY/'portable/manifest.json', CAPACITY/'results/freeze.json']:
        hashes[str(path)] = sha(path)
    core_path = CAPACITY/'results/fit_hist62_regularized.pkl'
    core_expected = json.loads((CAPACITY/'results/freeze.json').read_text())['artifacts']['hist62_regularized']['sha256']
    assert sha(core_path) == core_expected
    hashes[str(core_path)] = core_expected
    dump(OUT/'run_manifest.json', {'started_utc': now(), 'source_input_sha256': hashes,
         'variants': VARIANTS, 'python': sys.version, 'numpy': np.__version__, 'scipy': scipy.__version__,
         'sklearn': sklearn.__version__, 'external_outcomes_opened': False})
    d = inputs.load_historical()
    assert d['X62'].shape == (8371,62) and len(set(d['group'])) == 93
    logs = []
    for split, tr, te in splits(d):
        start = time.monotonic()
        models, used = fit_split(d, tr, te, split)
        hashes.update(used)
        source = CAPACITY/'results'/f'predictions_{split}.csv'
        # Prior completed assessment witnessed these outer files.
        witness = json.loads((FRONTIER/'assessment_final/report.json').read_text())['input_sha256']
        assert sha(source) == witness[str(source)]
        hashes[str(source)] = sha(source)
        frame = pd.read_csv(source)
        np.testing.assert_array_equal(frame.nf2_row_id.to_numpy(), d['nf2_row_id'][te])
        np.testing.assert_allclose(frame.measured_CD.to_numpy(), d['MEAS_CD'][te], rtol=0, atol=1e-13)
        frame = score_models(frame, d, te, models, frame[CORE].to_numpy(), np.ones(len(te), dtype=bool))
        frame.to_csv(OUT/f'predictions_{split}.csv', index=False)
        log = {'split': split, 'seconds': time.monotonic()-start, 'rows': len(te)}
        logs.append(log)
        print(json.dumps(log), flush=True)
    ids = np.arange(len(d['BASE_CD']))
    final, used = fit_split(d, ids, np.array([], dtype=int), 'final')
    hashes.update(used)
    assert len(list(OUT.glob('policy_*.json'))) == 48
    for filename, expected in hashes.items():
        assert sha(filename) == expected, filename
    artifact_hashes = {str(p): sha(p) for p in sorted(OUT.glob('policy_*.json'))}
    dump(OUT/'freeze.json', {'frozen_utc': now(), 'artifact_sha256': artifact_hashes,
         'source_input_sha256': hashes, 'policy_count': 48, 'external_outcomes_opened': False,
         'status': 'historical_only_fixed_procedures; no selector; experimental_not_deployed'})
    print('All 48 policies frozen. Beginning previously exposed SG/W diagnostics.', flush=True)
    # Verify the local, previously produced sklearn model before deserialization.
    assert sha(core_path) == core_expected
    for filename, expected in json.loads((CAPACITY/'results/run_manifest.json').read_text())['hashes'].items():
        if 'SG_exposed' in filename or 'W_new_challenge' in filename:
            assert sha(filename) == expected, filename
            hashes[filename] = expected
    with core_path.open('rb') as f:
        core_model = pickle.load(f)
    exposed_dir = HERE/'exposed_results'
    exposed_dir.mkdir(exist_ok=False)
    for name, count in [('SG_exposed', 242), ('W_new_challenge',255)]:
        ex = inputs.load_exposed(name)
        source = CAPACITY/'exposed_results'/f'{name}_predictions.csv'
        expected = json.loads((CAPACITY/'portable/manifest.json').read_text())['hashes'][str(source)]
        assert sha(source) == expected
        hashes[str(source)] = expected
        frame = pd.read_csv(source)
        assert len(frame) == count and frame.inference_gate.dtype == bool
        np.testing.assert_array_equal(frame.alpha.to_numpy(), ex['alpha'])
        np.testing.assert_array_equal(frame.Re.to_numpy(), ex['Re'])
        ix = np.arange(count)
        core = capacity_models.predict(core_model, ex, ix)
        gate = frame.inference_gate.to_numpy()
        np.testing.assert_allclose(np.where(gate,core,ex['BASE_CD']), frame[CORE].to_numpy(), rtol=0,atol=1e-13)
        frame = score_models(frame, ex, ix, final, core, gate)
        frame.to_csv(exposed_dir/f'{name}_predictions.csv', index=False)
        # Label-free replay references; these contain no experimental outcomes.
        np.savez_compressed(exposed_dir/f'{name}_inference.npz', BASE_CD=ex['BASE_CD'], CORE_CD=core,
            all_model_CD=ex['all_model_CD'], X62=ex['X62'], gate=gate,
            **{label: frame[label].to_numpy() for label in VARIANTS})
    full_core = capacity_models.predict(core_model, d, ids)
    predictions = {label: risk_policy.predict(model,d['BASE_CD'],full_core,d['all_model_CD'],np.ones(len(ids),bool))[0]
                   for label, model in final.items()}
    np.savez_compressed(OUT/'historical_inference.npz', BASE_CD=d['BASE_CD'], CORE_CD=full_core,
        all_model_CD=d['all_model_CD'], X62=d['X62'], gate=np.ones(len(ids),bool), **predictions)
    for filename, expected in {**hashes, **artifact_hashes}.items():
        assert sha(filename) == expected, filename
    dump(OUT/'complete.json', {'completed_utc':now(), 'splits':logs, 'source_input_sha256':hashes,
         'artifact_sha256':artifact_hashes, 'freeze_sha256':sha(OUT/'freeze.json'), 'rows':{'historical':8371,'SG':242,'W':255},
         'status':'completed_fixed_adaptive_procedures; not independent validation; not deployed'})
    print('Completed all historical and exposed predictions.', flush=True)


if __name__ == '__main__':
    main()
