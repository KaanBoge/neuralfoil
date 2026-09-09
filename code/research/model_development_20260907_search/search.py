"""Nested Cycle 3 comparison. All outputs confined to this experiment."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
import platform
import sys
import time
import numpy as np
import pandas as pd
import sklearn

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT/'smooth'), str(ROOT/'ensemble'), str(ROOT.parent/'model_development_20260906_v2')]
import develop_v2 as v2
import robust_models as robust
import smooth_models as smooth
import ensemble_models as ensemble

FAMILIES = ['cycle1_fixed', 'cycle2_fixed'] + list(robust.FAMILIES) + list(smooth.FAMILIES) + list(ensemble.FAMILIES)
LABELS = ['identity', 'xlarge_fixed'] + [f'{f}__{s:g}' for f in FAMILIES for s in [.5, 1.0]]


def fit(family, d, idx):
    if family.startswith('cycle'):
        return v2.fit('prior9_log' if family == 'cycle1_fixed' else 'hist24_relative_mixed', d, idx)
    return next(m for m in [robust, smooth, ensemble] if family in m.FAMILIES).fit(family, d, idx)


def predict(family, model, d, idx):
    if family.startswith('cycle'):
        oldfamily = 'prior9_log' if family == 'cycle1_fixed' else 'hist24_relative_mixed'
        return v2.correct(v2.target_kind(oldfamily), model.predict(d[v2.feature_key(oldfamily)][idx]), d['BASE_CD'][idx], 1)
    return next(m for m in [robust, smooth, ensemble] if family in m.FAMILIES).predict(model, d, idx)


def all_predictions(d, tr, te):
    assert len(tr) and len(te)
    assert not set(d['group'][tr]) & set(d['group'][te])
    preds = {'identity': d['BASE_CD'][te].copy(), 'xlarge_fixed': d['XLARGE_CD'][te].copy()}
    durations = {}
    for family in FAMILIES:
        start = time.monotonic()
        model = fit(family, d, tr)
        pred = predict(family, model, d, te)
        assert pred.shape == (len(te),) and np.isfinite(pred).all() and (pred>0).all(), family
        for strength in [.5, 1.0]:
            preds[f'{family}__{strength:g}'] = d['BASE_CD'][te]+strength*(pred-d['BASE_CD'][te])
        durations[family] = time.monotonic()-start
    return preds, durations


def select(d, idx, output_prefix):
    oof = {name: np.full(len(idx), np.nan) for name in LABELS}
    group_logs, transfer_logs = [], []
    for i, te in enumerate(v2.old.group_folds(d['group'][idx], 3, 20260907)):
        pr, duration = all_predictions(d, idx[~te], idx[te])
        for name in LABELS: oof[name][te] = pr[name]
        group_logs.append({'fold': i, 'train_rows': int((~te).sum()), 'test_rows': int(te.sum()), 'overlap_groups': 0, 'seconds': duration})
    assert all(np.isfinite(p).all() for p in oof.values())
    np.savez_compressed(str(output_prefix)+'_inner_group.npz', indices=idx, **oof)
    transfer = {name: {} for name in LABELS}
    for source in sorted(set(d['source'][idx])):
        test = d['source'][idx] == source
        tr = ~test & ~np.isin(d['group'][idx], d['group'][idx[test]])
        if len(set(d['group'][idx[tr]])) < 6 or tr.sum() < 300:
            transfer_logs.append({'source': source, 'status': 'insufficient_remaining_training_support', 'train_rows': int(tr.sum())})
            continue
        pr, duration = all_predictions(d, idx[tr], idx[test])
        denom = np.abs(d['BASE_CD'][idx[test]]-d['MEAS_CD'][idx[test]]).sum()
        for name in LABELS:
            transfer[name][source] = float(np.abs(pr[name]-d['MEAS_CD'][idx[test]]).sum()/denom)
        np.savez_compressed(str(output_prefix)+f'_inner_transfer_{source}.npz', train_indices=idx[tr], test_indices=idx[test], **pr)
        transfer_logs.append({'source': source, 'status': 'scored', 'train_rows': int(tr.sum()), 'test_rows': int(test.sum()), 'overlap_groups': 0, 'seconds': duration})
    logs = []
    chosen = {'guarded_pooled': 'identity', 'minimax': 'identity', 'transfer_minimax': 'identity'}
    best = {name: 1.0 for name in chosen}
    ntransfer = sum(r['status']=='scored' for r in transfer_logs)
    for name in LABELS:
        worst, ratios = v2.old.score_candidate(oof[name], d, idx)
        guard = all(r < 1 for key, r in ratios.items() if key != 'overall')
        transfer_score = max([worst]+list(transfer[name].values())) if ntransfer >= 2 else worst
        logs.append({'candidate': name, 'group_ratios': ratios, 'group_worst_ratio': worst, 'guard_pass': guard,
                     'purged_source_ratios': transfer[name], 'transfer_objective': transfer_score})
        scores = {'guarded_pooled': ratios['overall'] if guard else float('inf'), 'minimax': worst, 'transfer_minimax': transfer_score}
        for rule, score in scores.items():
            if score < best[rule]-1e-12: chosen[rule], best[rule] = name, score
    return chosen, {'candidates': logs, 'group_folds': group_logs, 'source_folds': transfer_logs,
                    'transfer_fallback_to_group_minimax': ntransfer < 2}


def evaluate(task):
    name, d, tr, te, out = task
    start = time.monotonic()
    choice, selection = select(d, tr, out/name)
    preds, durations = all_predictions(d, tr, te)
    for rule, selected in choice.items(): preds[rule] = preds[selected]
    frame = pd.DataFrame({'split': name, 'nf2_row_id': d['nf2_row_id'][te], 'group': d['group'][te], 'source': d['source'][te],
        'entry': d['entry'][te], 'Re': d['Re'][te], 'alpha': d['alpha'][te], 'measured_CD': d['MEAS_CD'][te],
        'mean8_CD': d['BASE_CD'][te], 'xlarge_CD': d['XLARGE_CD'][te], **preds})
    prior = pd.read_csv(v2.ROOT/'results'/f'predictions_{name}.csv')
    frame = frame.merge(prior[['nf2_row_id', 'guarded_pooled', 'cycle1_nested']].rename(columns={'guarded_pooled': 'cycle2_nested'}),
        on='nf2_row_id', how='left', validate='one_to_one')
    assert frame.cycle2_nested.notna().all() and frame.cycle1_nested.notna().all()
    frame.to_csv(out/f'predictions_{name}.csv', index=False)
    log = {'split': name, 'train_rows': len(tr), 'test_rows': len(te), 'train_groups': len(set(d['group'][tr])),
           'test_groups': len(set(d['group'][te])), 'overlap_groups': 0, 'selected': choice, 'selection': selection,
           'outer_seconds': durations, 'total_seconds': time.monotonic()-start}
    v2.old.dump(out/f'log_{name}.json', log)
    return log


def summarize(out):
    frames = [pd.read_csv(p) for p in sorted(out.glob('predictions_*.csv'))]
    allpred = pd.concat(frames, ignore_index=True)
    labels = ['group_20260906', 'group_20260908'] + [f'strict_source_{s}' for s in ['stec8','vol1','vol2','vol3','all_uiuc_volumes']]
    summaries = []
    for name in labels:
        frame = allpred[allpred.split.str.startswith(name)]
        if not len(frame): continue
        assert not frame.nf2_row_id.duplicated().any()
        for candidate in LABELS+['guarded_pooled', 'minimax', 'transfer_minimax', 'cycle1_nested', 'cycle2_nested']:
            for baseline in ['xlarge_CD', 'mean8_CD']:
                metric = v2.old.metrics(frame.measured_CD.to_numpy(), frame[candidate].to_numpy(), frame[baseline].to_numpy(),
                    frame.group.to_numpy(), bootstrap=candidate in ['guarded_pooled', 'minimax', 'transfer_minimax'])
                summaries.append({'evaluation': name, 'candidate': candidate, 'baseline': baseline, **metric})
    v2.old.dump(out/'metrics.json', summaries)
    pd.DataFrame([{k:v for k,v in row.items() if not isinstance(v,dict)} for row in summaries]).to_csv(out/'metric_summary.csv',index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--summarize-only', action='store_true')
    args = ap.parse_args()
    out = ROOT/'results'
    out.mkdir(exist_ok=True)
    if args.summarize_only:
        summarize(out)
        return
    assert not (out/'run_manifest.json').exists(), 'Completed or started runs are immutable; use an explicitly separate run directory.'
    d = v2.load_data()
    paths = [Path(__file__), ROOT/'PROTOCOL.md', Path(robust.__file__), Path(smooth.__file__), Path(ensemble.__file__),
             ROOT/'smooth/PROTOCOL.md', ROOT/'ensemble/PROTOCOL.md', Path(v2.__file__), Path(v2.old.__file__),
             v2.OLD/'reproduction/dataset_occurrence.npz', v2.OLD/'methods_audit/entry_group_map.csv', v2.OLD/'methods_audit/ambiguous_nf2_row_ids.csv']
    manifest = {'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), 'python':platform.python_version(),
        'numpy': np.__version__, 'sklearn':sklearn.__version__, 'hashes':{str(p):v2.old.digest(p) for p in paths},
        'families': FAMILIES, 'candidate_labels': LABELS, 'rows':len(d['BASE_CD']), 'groups':len(set(d['group'])),
        'external_status':'SG and W already exposed; no external training, no unscored outcomes accessed'}
    v2.old.dump(out/'run_manifest.json',manifest)
    ids = np.arange(len(d['BASE_CD']))
    tasks = []
    for seed in [20260906,20260908]:
        for i,te in enumerate(v2.old.group_folds(d['group'],5,seed)):
            tasks.append((f'group_{seed}_fold_{i}',d,ids[~te],ids[te],out))
    for source in sorted(set(d['source']))+['all_uiuc_volumes']:
        te = d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        tr = ~te & ~np.isin(d['group'],d['group'][te])
        tasks.append((f'strict_source_{source}',d,ids[tr],ids[te],out))
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(evaluate,t) for t in tasks]
        for job in as_completed(jobs):
            log = job.result()
            print(json.dumps({'finished':log['split'],'selected':log['selected'],'seconds':round(log['total_seconds'],1)}),flush=True)
    summarize(out)
    selected, selection = select(d, ids, out/'final')
    # Explicit pickle experimental artifacts are local-only and never loaded from an untrusted source.
    import pickle
    fitted = {}
    predictions = {}
    for label in sorted(set(selected.values())):
        if label in ['identity','xlarge_fixed']:
            predictions[label] = d['BASE_CD'] if label=='identity' else d['XLARGE_CD']
            fitted[label] = None
        else:
            family,strength = label.rsplit('__',1)
            model = fit(family,d,ids)
            fitted[label] = model
            full = predict(family,model,d,ids)
            predictions[label] = d['BASE_CD']+float(strength)*(full-d['BASE_CD'])
    for label,model in fitted.items():
        with (out/f'candidate_{label}.pkl').open('wb') as f: pickle.dump(model,f,protocol=5)
    np.savez_compressed(out/'final_training_references.npz',**predictions)
    for path,expected in manifest['hashes'].items(): assert v2.old.digest(path)==expected,path
    v2.old.dump(out/'freeze.json',{'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':selected,
        'selection':selection, 'artifact_hashes':{p.name:v2.old.digest(p) for p in out.glob('candidate_*.pkl')},
        'status':'experimental_not_deployed','historical_only_fit':True,'portable_export_verified':False})
    print(json.dumps({'done':True,'selected':selected}),flush=True)


if __name__=='__main__': main()
