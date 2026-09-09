#!/usr/bin/env python3
"""Read-only input reconstruction of recovered lsat_doubleclean.py.

All outputs are written beside this file, never into the recovered payload.
Public API: build_context(project) -> context; build_dataset(context, clean_mask)
-> dict of NumPy arrays; save_datasets(project) -> (context, exact, occurrence).
Masks are Boolean arrays in the full lsat-nf2.csv row order (0-based IDs).
Geometry and model equations reproduce the recovered code; configuration
matching additionally provides the audited occurrence-aware alternative.
Run with --dataset-only for fast feature export, otherwise refit exact protocol.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path
import platform
import sys
import zipfile
import numpy as np

HERE = Path(__file__).resolve().parent
PAYLOAD_REL = Path('validation_extension/export_intake_20260906/payload_n805d74v/NeuralFoil-export-starter-2026-09-06')
SIZES = ['xxsmall', 'xsmall', 'small', 'medium', 'large', 'xlarge', 'xxlarge', 'xxxlarge']
F9 = ['alpha','lre','t2','c2','lcd8','cl8','lsp','topxtr','botxtr']
F16 = ['alpha','lre','t2','tx2','c2','cx2','leR','teA','lcd8','cl8','lsp','conf','topxtr','botxtr','dsize','cm8']
GEOM_NAMES = ['t', 'tx', 'c', 'cx', 'leR', 'teA']

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_csv(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))

def condkey(row):
    return (row['source'], row['airfoil'], round(float(row['Re'])), round(float(row['alpha']), 2))

def observation_key(row, inference=False):
    return (row['source'], row['airfoil'], round(float(row['Re']), 3),
            round(float(row['alpha']), 4),
            round(float(row['CL_meas' if inference else 'CL']), 5),
            round(float(row['CD_meas' if inference else 'CD']), 6))

def load_pts(text):
    out = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2:
            try:
                x, y = float(fields[0]), float(fields[1])
            except ValueError:
                continue
            if -0.5 <= x <= 1.5 and -0.6 <= y <= 0.6:
                out.append([x, y])
    a = np.array(out)
    a[:, 0] -= a[:, 0].min()
    return a / a[:, 0].max()

def foil_stats2(points):
    """Literal numerical operations from recovered geometry descriptor code."""
    le = int(np.argmin([p[0] for p in points]))
    up, lo = points[:le + 1], points[le:]
    def interp(seg, x):
        for k in range(len(seg) - 1):
            a, b = seg[k], seg[k + 1]
            if (x-a[0])*(x-b[0]) <= 0 and abs(b[0]-a[0]) > 1e-9:
                return a[1] + (b[1]-a[1])*(x-a[0])/(b[0]-a[0])
        return 0.0
    t = tx = c = cx = 0.0
    for k in range(1, 100):
        x = 0.5*(1-np.cos(np.pi*k/100))
        yu, yl = interp(up, x), interp(lo, x)
        th, cm = yu-yl, (yu+yl)/2
        if th > t:
            t, tx = th, x
        if abs(cm) > abs(c):
            c, cx = cm, x
    A = points[max(0, le-1)]
    B = points[le]
    Cp = points[min(len(points)-1, le+1)]
    a2 = np.hypot(B[0]-Cp[0], B[1]-Cp[1])
    b3 = np.hypot(A[0]-Cp[0], A[1]-Cp[1])
    c3 = np.hypot(A[0]-B[0], A[1]-B[1])
    s2 = (a2+b3+c3)/2
    tri = np.sqrt(max(1e-18, s2*(s2-a2)*(s2-b3)*(s2-c3)))
    leR = a2*b3*c3/(4*tri)
    v1 = [points[1][0]-points[0][0], points[1][1]-points[0][1]]
    v2 = [points[-2][0]-points[-1][0], points[-2][1]-points[-1][1]]
    den = np.hypot(*v1)*np.hypot(*v2) or 1e-9
    teA = np.degrees(np.arccos(np.clip((v1[0]*v2[0]+v1[1]*v2[1])/den, -1, 1)))
    return dict(t=t, tx=tx, c=c, cx=cx, leR=min(leR, 0.2), teA=teA)

def build_context(project):
    project = Path(project).resolve()
    payload = project / PAYLOAD_REL
    base = payload / 'scratchpad/lsat'
    raw = read_csv(base / 'lsat-corpus.csv')
    rows = read_csv(base / 'lsat-nf2.csv')
    cfg = {condkey(row): row['config'] for row in raw}
    raw_queues = defaultdict(deque)
    key_configs = defaultdict(set)
    for i, row in enumerate(raw):
        raw_queues[observation_key(row)].append(i)
        key_configs[observation_key(row)].add(row['config'])
    raw_ids = []
    for row in rows:
        queue = raw_queues[observation_key(row, True)]
        assert queue, f'Unmatched inference observation: {observation_key(row, True)}'
        raw_ids.append(queue.popleft())
    assert len(set(raw_ids)) == len(rows)
    exact_mask = np.array([r['config'] == 'clean' and cfg.get(condkey(r)) == 'clean' for r in rows])
    occurrence_mask = np.array([r['config'] == 'clean' and raw[i]['config'] == 'clean' for r, i in zip(rows, raw_ids)])
    ambiguous_config = np.array([len(key_configs[observation_key(r, True)]) > 1 for r in rows])
    geom_map = json.loads((base / 'lsat-geometry.json').read_text())
    stats, paths, hashes, geom_errors = {}, {}, {}, {}
    with zipfile.ZipFile(base / 'coord_seligFmt.zip') as zc, zipfile.ZipFile(base / 'Stec8.zip') as zs:
        for key, geom in geom_map.items():
            path = geom['path']
            try:
                if (base / path).exists():
                    data = (base / path).read_bytes()
                    text = (base / path).read_text(errors='replace')
                elif path.startswith('coords/'):
                    data = zc.read(path[len('coords/'):])
                    text = data.decode('latin-1')
                elif path.startswith('stec8/'):
                    data = zs.read(path[len('stec8/'):])
                    text = data.decode('latin-1')
                else:
                    raise FileNotFoundError(path)
                stats[key] = foil_stats2([list(p) for p in load_pts(text)])
                paths[key], hashes[key] = path, hashlib.sha256(data).hexdigest()
            except Exception as exc:
                geom_errors[key] = repr(exc)
    filenames = ['lsat_doubleclean.py','lsat-corpus.csv','lsat-nf2.csv','lsat-geometry.json',
                 'coord_seligFmt.zip','Stec8.zip','dc-oof.csv','dc-report.txt','lsat-xfoil.csv']
    input_hashes = {str((base / name).relative_to(project)): digest(base / name) for name in filenames}
    return dict(project=project, base=base, raw=raw, rows=rows,
                raw_ids=np.array(raw_ids, dtype=np.int64), exact_mask=exact_mask,
                occurrence_mask=occurrence_mask, ambiguous_config=ambiguous_config,
                stats=stats, geometry_paths=paths,
                geometry_hashes=hashes, geometry_errors=geom_errors, input_hashes=input_hashes)

def build_dataset(context, clean_mask):
    """Return feature-eligible rows selected by an arbitrary full-inference mask.

    Uses recovered feature-based thickness t2, not rounded nf2.csv tc.
    raw_row_id is zero-based lsat-corpus.csv data-row index (CSV line = ID+2).
    Geometry hashes identify coordinate bytes, not shape-equivalence classes.
    """
    mask = np.asarray(clean_mask, dtype=bool)
    assert mask.shape == (len(context['rows']),)
    values = defaultdict(list)
    for i, row in enumerate(context['rows']):
        if not mask[i]:
            continue
        key = row['source'] + '|' + row['airfoil']
        geom = context['stats'].get(key)
        if geom is None:
            continue
        a, Re = float(row['alpha']), float(row['Re'])
        if not (Re <= 6e5 and abs(a) <= 12 and 0.05 <= geom['t'] <= 0.20):
            continue
        cds = np.array([float(row['CD_' + s]) for s in SIZES])
        cls = np.array([float(row['CL_' + s]) for s in SIZES])
        cd8, cl8 = cds.mean(), cls.mean()
        meas, clm = float(row['CD_meas']), float(row['CL_meas'])
        if meas <= 0 or cd8 <= 0:
            continue
        spread = max(np.percentile(cds, 90)-np.percentile(cds, 10), 1e-6)
        lre, lcd, lsp = np.log10(Re), np.log(cd8), np.log(spread)
        top, bot = float(row['topxtr']), float(row['botxtr'])
        values['X9'].append([a,lre,geom['t'],geom['c'],lcd,cl8,lsp,top,bot])
        values['X16'].append([a,lre,geom['t'],geom['tx'],geom['c'],geom['cx'],geom['leR'],geom['teA'],
                              lcd,cl8,lsp,float(row['conf_xlarge']),top,bot,
                              np.log(cds[0])-np.log(cds[7]),float(row['cm8'])])
        fields = dict(yCD=np.clip(np.log(meas/cd8),-1.5,1.5), yCL=np.clip(clm-cl8,-0.5,0.5),
                      BASE_CD=cd8, BASE_CL=cl8, MEAS_CD=meas, MEAS_CL=clm,
                      XLARGE_CD=float(row['CD_xlarge']), XLARGE_CL=float(row['CL_xlarge']),
                      af=row['airfoil'], source=row['source'], entry=key, Re=Re, alpha=a,
                      raw_row_id=context['raw_ids'][i], nf2_row_id=i,
                      raw_config=context['raw'][context['raw_ids'][i]]['config'],
                      exact_clean=context['exact_mask'][i], occurrence_clean=context['occurrence_mask'][i],
                      ambiguous_raw_config=context['ambiguous_config'][i],
                      geometry_path=context['geometry_paths'][key], geometry_hash=context['geometry_hashes'][key])
        for name, value in fields.items():
            values[name].append(value)
        values['geometry_stats'].append([geom[k] for k in GEOM_NAMES])
        values['all_model_CD'].append(cds)
        values['all_model_CL'].append(cls)
    out = {name: np.array(value) for name, value in values.items()}
    out.update(feature_names9=np.array(F9), feature_names16=np.array(F16), geometry_names=np.array(GEOM_NAMES))
    out['src'] = out['source'].copy()
    rng = np.random.default_rng(824)
    foils = sorted(set(out['af']))
    rng.shuffle(foils)
    out['fold'] = np.full(len(out['af']), -1, dtype=np.int64)
    for fold in range(5):
        out['fold'][np.isin(out['af'], foils[fold::5])] = fold
    assert np.all(out['fold'] >= 0)
    for name in ['X9','X16','yCD','yCL','BASE_CD','BASE_CL','MEAS_CD','MEAS_CL']:
        assert np.isfinite(out[name]).all(), name
    assert len(set(out['raw_row_id'])) == len(out['raw_row_id'])
    return out

def save_datasets(project):
    context = build_context(project)
    exact = build_dataset(context, context['exact_mask'])
    occurrence = build_dataset(context, context['occurrence_mask'])
    np.savez_compressed(HERE / 'dataset.npz', **exact)
    np.savez_compressed(HERE / 'dataset_occurrence.npz', **occurrence)
    diagnostics = dict(raw_rows=len(context['raw']), inference_rows=len(context['rows']),
        all_inference_rows_match_raw_once=True,
        exact_clean_rows=int(context['exact_mask'].sum()), occurrence_clean_rows=int(context['occurrence_mask'].sum()),
        label_disagreements=int(np.sum(context['exact_mask'] != context['occurrence_mask'])),
        exact_training_rows=len(exact['af']), occurrence_training_rows=len(occurrence['af']),
        ambiguous_full_measurement_keys_rows=int(context['ambiguous_config'].sum()),
        occurrence_clean_rows_with_ambiguous_config=int(np.sum(context['ambiguous_config'] & context['occurrence_mask'])),
        geometry_entries=len(context['stats']), geometry_errors=context['geometry_errors'],
        input_sha256=context['input_hashes'],
        array_interfaces={name: {'shape': list(value.shape), 'dtype': str(value.dtype)} for name,value in exact.items()},
        raw_row_id_definition='0-based CSV data-row index in recovered lsat-corpus.csv; physical CSV line is ID + 2',
        training_filter='Re <= 600000, |alpha| <= 12, computed t2 in [0.05, 0.20], measured and mean8 CD > 0, geometry available',
        split='sorted nominal airfoil names shuffled with numpy default_rng(824), then strided 5-fold groups',
        geometry_hash_definition='SHA256 of coordinate file bytes from archive member or existing identical on-disk path')
    (HERE / 'dataset_manifest.json').write_text(json.dumps(diagnostics, indent=2) + '\n')
    with (HERE / 'configuration_disagreements.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['nf2_row_id','raw_row_id','source','airfoil','Re','alpha','nf_config','raw_config','exact_clean','occurrence_clean'])
        for i in np.flatnonzero(context['exact_mask'] != context['occurrence_mask']):
            row = context['rows'][i]
            raw_id = context['raw_ids'][i]
            writer.writerow([i,raw_id,row['source'],row['airfoil'],row['Re'],row['alpha'],row['config'],
                             context['raw'][raw_id]['config'],context['exact_mask'][i],context['occurrence_mask'][i]])
    print(json.dumps({key:diagnostics[key] for key in ['raw_rows','inference_rows','exact_clean_rows','occurrence_clean_rows','exact_training_rows','occurrence_training_rows','label_disagreements']}, indent=2), flush=True)
    return context, exact, occurrence

def model(kind):
    from sklearn.ensemble import GradientBoostingRegressor
    return GradientBoostingRegressor(n_estimators=150 if kind=='CD' else 300,
        learning_rate=0.06,max_depth=2 if kind=='CD' else 3,
        min_samples_leaf=80 if kind=='CD' else 40,subsample=0.7,random_state=824)

def corrected(kind, base, pred):
    return base*np.exp(np.clip(pred,np.log(0.5),np.log(2))) if kind=='CD' else base+np.clip(pred,-0.5,0.5)

def metric_summary(meas, base, pred, kind):
    scale = 1e4 if kind=='CD' else 1
    a, b = np.abs(base-meas)*scale, np.abs(pred-meas)*scale
    return dict(rows=len(a), baseline_mae=float(a.mean()), corrected_mae=float(b.mean()),
        baseline_median=float(np.median(a)), corrected_median=float(np.median(b)),
        baseline_iqr=np.percentile(a,[25,75]).tolist(), corrected_iqr=np.percentile(b,[25,75]).tolist(),
        relative_mae_reduction_percent=float(100*(1-b.sum()/a.sum())),
        worse_rows=int(np.sum(b>a)), units='drag counts' if kind=='CD' else 'lift coefficient')

def head_to_head(context, data, oofs):
    """Reproduce original row-based common-XFOIL head-to-head and key fallback."""
    xf = {(r['entry'],round(float(r['Re'])),round(float(r['alpha']),2)):
          (float(r['CL_xf']),float(r['CD_xf'])) for r in read_csv(context['base']/'lsat-xfoil.csv')}
    oofmap = {(data['source'][i],data['af'][i],round(data['Re'][i]),round(data['alpha'][i],2)):
              (oofs['oofCD'][i],oofs['oofCL'][i]) for i in range(len(data['af']))}
    records = []
    conditions = []
    for i,row in enumerate(context['rows']):
        if not context['exact_mask'][i]:
            continue
        key = condkey(row)
        common_key = (row['source']+'|'+row['airfoil'],key[2],key[3])
        conditions.append(common_key)
        if common_key not in xf:
            continue
        cd8 = np.mean([float(row['CD_'+s]) for s in SIZES])
        cl8 = np.mean([float(row['CL_'+s]) for s in SIZES])
        z,dcl = oofmap.get(key,(0.0,0.0))
        records.append(dict(key=common_key,cdm=float(row['CD_meas']),clm=float(row['CL_meas']),
            cd8=cd8,cl8=cl8,cdx=float(row['CD_xlarge']),clx=float(row['CL_xlarge']),
            cdc=float(corrected('CD',cd8,z)),clc=float(corrected('CL',cl8,dcl)),
            cdxf=xf[common_key][1],clxf=xf[common_key][0],fallback=key not in oofmap))
    result = dict(clean_rows=len(conditions),unique_clean_conditions=len(set(conditions)),
                  common_rows=len(records),unique_common_conditions=len(set(r['key'] for r in records)),
                  uncorrected_fallback_rows=sum(r['fallback'] for r in records),metrics={})
    for kind,prefix in [('CD','cd'),('CL','cl')]:
        meas = np.array([r[prefix+'m'] for r in records])
        base = np.array([r[prefix+'x'] for r in records])
        result['metrics'][kind] = {name:metric_summary(meas,base,np.array([r[prefix+suffix] for r in records]),kind)
            for name,suffix in [('xlarge','x'),('mean8','8'),('corrected','c'),('XFOIL','xf')]}
    return result

def reproduce(context, data):
    import sklearn
    import scipy
    import pandas
    report = {'runtime':dict(python=platform.python_version(),numpy=np.__version__,pandas=pandas.__version__,
                            sklearn=sklearn.__version__,scipy=scipy.__version__),
              'export_recorded_runtime':dict(python='3.14.4',numpy='2.5.2',pandas='3.0.5',sklearn='1.9.0',scipy='1.18.1'),
              'runtime_matches_export':False, 'training_rows':len(data['af']),
              'input_sha256':context['input_hashes'], 'results':{}}
    oofs = {}
    export = read_csv(context['base'] / 'dc-oof.csv')
    assert len(export) == len(data['af'])
    for i,row in enumerate(export):
        assert (row['entry'],round(float(row['Re'])),round(float(row['alpha']),2)) == (data['entry'][i],round(data['Re'][i]),round(data['alpha'][i],2))
    for kind in ['CD','CL']:
        X = data['X9' if kind=='CD' else 'X16']
        y, base, meas = data['y'+kind],data['BASE_'+kind],data['MEAS_'+kind]
        oof = np.zeros(len(y))
        folds, sources = [], []
        for fold in range(5):
            test = data['fold'] == fold
            assert not set(data['af'][test]) & set(data['af'][~test])
            fit = model(kind).fit(X[~test], y[~test])
            oof[test] = fit.predict(X[test])
            folds.append({'fold':fold, **metric_summary(meas[test],base[test],corrected(kind,base[test],oof[test]),kind)})
            print(kind,'fold',fold,folds[-1]['baseline_mae'],folds[-1]['corrected_mae'],flush=True)
        for name in ['stec8','vols']:
            test = data['source']=='stec8' if name=='stec8' else data['source']!='stec8'
            fit = model(kind).fit(X[~test], y[~test])
            pred = corrected(kind,base[test],fit.predict(X[test]))
            shared = set(data['af'][test]) & set(data['af'][~test])
            sources.append({'test_source':name,'train_rows':int((~test).sum()),
                            'shared_nominal_airfoil_names':sorted(shared),
                            'test_rows_with_shared_nominal_airfoil':int(np.isin(data['af'][test],list(shared)).sum()),
                            **metric_summary(meas[test],base[test],pred,kind)})
            print(kind,'transfer',name,sources[-1]['baseline_mae'],sources[-1]['corrected_mae'],flush=True)
        corrected_oof = corrected(kind,base,oof)
        old = np.array([float(r['zCD_oof' if kind=='CD' else 'dCL_oof']) for r in export])
        delta = np.abs(oof-old)
        fold_base = float(np.mean([f['baseline_mae'] for f in folds]))
        fold_corrected = float(np.mean([f['corrected_mae'] for f in folds]))
        report['results'][kind] = dict(model_params=model(kind).get_params(),folds=folds,
            unweighted_fold_mean=dict(baseline_mae=fold_base,corrected_mae=fold_corrected,
                                     relative_mae_reduction_percent=100*(1-fold_corrected/fold_base)),
            pooled_oof=metric_summary(meas,base,corrected_oof,kind),source_transfer=sources,
            passes_original_ship_gate=bool(fold_corrected<fold_base and all(s['corrected_mae']<s['baseline_mae'] for s in sources)),
            exported_rounded_oof_comparison=dict(keys_and_order_identical=True,
                max_absolute_residual_difference=float(delta.max()),mean_absolute_residual_difference=float(delta.mean()),
                rows_different_after_five_decimal_format=sum(f'{v:.5f}'!=r['zCD_oof' if kind=='CD' else 'dCL_oof'] for v,r in zip(oof,export)),
                rows_within_export_rounding_half_unit=int(np.sum(delta<=5.000001e-6)),
                exported_rounded_metrics=metric_summary(meas,base,corrected(kind,base,old),kind)))
        oofs['oof'+kind] = oof
        oofs['PRED_'+kind] = corrected_oof
    np.savez_compressed(HERE / 'reproduced_oof.npz', **oofs, raw_row_id=data['raw_row_id'], nf2_row_id=data['nf2_row_id'],fold=data['fold'])
    report['historical_row_based_head_to_head'] = head_to_head(context,data,oofs)
    report['input_hashes_unchanged_after_training'] = all(digest(context['project']/path)==value for path,value in context['input_hashes'].items())
    assert report['input_hashes_unchanged_after_training']
    (HERE / 'reproduction_results.json').write_text(json.dumps(report,indent=2) + '\n')
    write_report(report)
    return report

def write_report(report):
    lines = ['# Independent double-clean reproduction','',
        'Assessment: share with explicit caveats. This reproduces a historical internal protocol; it is not a new external validation.', '',
        'The recovered program was inspected but never executed in its source directory. Its geometry calculations, feature order, target clipping, prediction clipping, random seed 824, nominal-airfoil fold allocation, and gradient-boosting parameters are reproduced in this standalone module. Outputs remain in this reproduction directory.','',
        '## Cohorts and runtime','',
        'The exact last-write configuration lookup selects 8,634 rows and 8,370 training rows. A separate occurrence-aware raw-observation lookup pairs every inference row to one distinct raw row and is exported as dataset_occurrence.npz. Its size and all configuration disagreements are recorded in dataset_manifest.json and configuration_disagreements.csv. No last-write cohort is silently treated as the occurrence-aware cohort. Matching by occurrence resolves row multiplicity but cannot establish configuration identity where identical complete measurement keys carry conflicting labels; these records are flagged in ambiguous_raw_config and are not silently excluded. New model development must address this ambiguity separately.','',
        f"Local runtime: {report['runtime']}. Export recorded runtime: {report['export_recorded_runtime']}. Library/platform mismatch prevents a claim of identical environment reproduction; rounded prediction comparisons below measure the actual difference.", '',
        '## Fixed protocol results','',
        '| Output | Pooled baseline MAE | Pooled corrected MAE | Reduction | Original shipment gate |',
        '|---|---:|---:|---:|---|']
    for kind, r in report['results'].items():
        v=r['pooled_oof']
        lines.append(f"| {kind} | {v['baseline_mae']:.8f} | {v['corrected_mae']:.8f} | {v['relative_mae_reduction_percent']:.4f}% | {r['passes_original_ship_gate']} |")
    lines += ['', 'CD errors are in drag counts (one count = 0.0001 in CD); CL errors are dimensionless lift-coefficient errors. Pooled metrics weight every observation equally. The recovered printed MEAN instead averages five fold MAEs without weighting fold size; both estimands are recorded in reproduction_results.json.', '']
    for kind,r in report['results'].items():
        q=r['exported_rounded_oof_comparison']
        lines += [f"### {kind}",'',
          f"All exported row keys and their order match. {q['rows_different_after_five_decimal_format']:,} predictions differ at the exported five-decimal precision; maximum absolute residual difference is {q['max_absolute_residual_difference']:.9g}. {q['rows_within_export_rounding_half_unit']:,} lie within the export rounding half-unit.",'',
          '| Transfer test population | Training rows | Test rows | Baseline MAE | Corrected MAE | Relative reduction | Shared airfoil names |',
          '|---|---:|---:|---:|---:|---:|---:|']
        for s in r['source_transfer']:
            lines.append(f"| {s['test_source']} | {s['train_rows']} | {s['rows']} | {s['baseline_mae']:.8f} | {s['corrected_mae']:.8f} | {s['relative_mae_reduction_percent']:.4f}% | {len(s['shared_nominal_airfoil_names'])} |")
        lines += ['']
    if 'historical_row_based_head_to_head' in report:
        head = report['historical_row_based_head_to_head']
        lines += ['## Historical common-XFOIL head-to-head','',
            f"The original algorithm uses {head['common_rows']:,} matching rows ({head['unique_common_conditions']:,} unique condition keys) from {head['clean_rows']:,} rows ({head['unique_clean_conditions']:,} unique keys). {head['uncorrected_fallback_rows']} common rows use the unchanged mean8 fallback. This reproduction retains its row-based averaging and last-write correction lookup; it is distinct from an occurrence-aware or unique-condition audit.",'',
            '| Output | Predictor | MAE | Median absolute error | Reduction vs xlarge |',
            '|---|---|---:|---:|---:|']
        for kind,models in head['metrics'].items():
            for name,v in models.items():
                lines.append(f"| {kind} | {name} | {v['corrected_mae']:.8f} | {v['corrected_median']:.8f} | {v['relative_mae_reduction_percent']:.4f}% |")
        lines += ['']
    lines += ['## Required caveats and reproduction','',
        'The two source transfers train on stec8 versus pooled volumes, but do not remove seven shared nominal airfoils. They are source-disjoint, not geometry-disjoint. The five-fold protocol is nominal-airfoil-disjoint, but 15 identical-coordinate-file groups with multiple nominal names cross those folds, affecting 2,137 rows in the exact historical training cohort. Consequently the historical grouped result must not be described as a strict unseen-geometry validation. Geometry byte hashes detect identical files, but do not establish equivalence or inequivalence of differently formatted coordinates.','',
        'The historical shipment gate requires improvement in the unweighted mean fold MAE and both source-transfer directions. It does not require 9% improvement, does not evaluate uncertainty, and is not a deployment authorization. The original corrected head-to-head calculation includes predictions even when that shipment gate fails.','',
        'Raw-row IDs are zero-based data-row indices in the recovered lsat-corpus.csv (physical CSV line = ID + 2). Dataset arrays use plain numeric or Unicode dtypes and load with numpy.load(..., allow_pickle=False). build_context(project) supplies exact_mask and occurrence_mask; build_dataset(context, arbitrary_mask) accepts a Boolean mask in full inference-row order and applies the declared feature-domain filter.','',
        'Reproduce with the project .venv Python: python reproduce_doubleclean.py --project /path/to/NeuralFoil_Research_Paper. Add --dataset-only to skip training. Input hashes are verified unchanged after fitting; no source data, original predictions, or manuscript outputs are overwritten.','',
        '## Independent QA','',
        'Run validate_reproduction.py to reconstruct the original pure geometry and feature calculations from inspected, isolated source statements. The original source program is never executed as a whole. QA verifies bit-for-bit X9, X16, both targets, baseline and measured arrays, row ordering, unchanged input hashes, independently recomputed pooled metrics, and weighted-fold reconciliation. reproduction_qa.json records the checks and the cross-fold coordinate-file alias groups.','']
    (HERE / 'REPORT.md').write_text('\n'.join(lines))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=HERE.parents[1])
    parser.add_argument('--dataset-only', action='store_true')
    args=parser.parse_args()
    context,exact,_=save_datasets(args.project)
    if not args.dataset_only:
        reproduce(context,exact)

if __name__=='__main__':
    main()
