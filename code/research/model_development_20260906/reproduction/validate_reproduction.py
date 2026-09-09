#!/usr/bin/env python3
"""Independent array and provenance checks against read-only source fragments.

Only the original pure geometry functions and feature-construction statements
are compiled, after inspection; the source program's I/O/training/export blocks
are never run. All artifacts and any bytecode stay in this reproduction folder.
"""
import ast
from collections import defaultdict
import json
from pathlib import Path
import zipfile
import numpy as np
import reproduce_doubleclean as reproduction

HERE = Path(__file__).resolve().parent

def main():
    project = HERE.parents[1]
    ctx = reproduction.build_context(project)
    exact = dict(np.load(HERE/'dataset.npz',allow_pickle=False))
    occurrence = dict(np.load(HERE/'dataset_occurrence.npz',allow_pickle=False))
    source = ctx['base']/'lsat_doubleclean.py'
    tree = ast.parse(source.read_text())
    funcs = [node for node in tree.body if isinstance(node,ast.FunctionDef)
             and node.name in ['key_of','load_pts','foil_stats2']]
    assert {node.name for node in funcs} == {'key_of','load_pts','foil_stats2'}
    with zipfile.ZipFile(ctx['base']/'coord_seligFmt.zip') as coords, zipfile.ZipFile(ctx['base']/'Stec8.zip') as stec:
        def read_geom_text(path):
            full = ctx['base']/path
            if full.exists():
                return full.read_text(errors='replace')
            if path.startswith('coords/'):
                return coords.read(path[len('coords/'):]).decode('latin-1')
            if path.startswith('stec8/'):
                return stec.read(path[len('stec8/'):]).decode('latin-1')
            raise FileNotFoundError(path)
        ns = dict(np=np, read_geom_text=read_geom_text)
        exec(compile(ast.Module(body=funcs,type_ignores=[]),str(source),'exec'),ns)
        original_stats = {}
        for key,path in ctx['geometry_paths'].items():
            original_stats[key] = ns['foil_stats2']([list(p) for p in ns['load_pts'](path)])
        assert original_stats == ctx['stats']
    feature_nodes = []
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Tuple):
            names = [x.id for x in node.targets[0].elts if isinstance(x,ast.Name)]
            if names == ['X16','X9','yCD','yCL','af_l','src_l','meta']:
                feature_nodes.append(node)
        if (isinstance(node,ast.For) and isinstance(node.iter,ast.Name) and node.iter.id=='R2'
                and any(isinstance(item,ast.Name) and item.id=='X9' for item in ast.walk(node))):
            # Select only the feature-construction R2 loop, not core-summary pts.
            feature_nodes.append(node)
    assert len(feature_nodes)==2
    ns.update(R2=[row for i,row in enumerate(ctx['rows']) if ctx['exact_mask'][i]],
              S2=original_stats,SIZES=reproduction.SIZES)
    exec(compile(ast.Module(body=feature_nodes,type_ignores=[]),str(source),'exec'),ns)
    array_checks = {}
    for key in ['X9','X16','yCD','yCL']:
        array_checks[key] = bool(np.array_equal(np.array(ns[key]),exact[key]))
        assert array_checks[key],key
    assert np.array_equal(exact['af'],ns['af_l'])
    assert np.array_equal(exact['source'],ns['src_l'])
    for col,key in [(1,'MEAS_CD'),(2,'BASE_CD'),(3,'MEAS_CL'),(4,'BASE_CL')]:
        assert np.array_equal(exact[key],np.array([m[col] for m in ns['meta']]))
    direct = reproduction.build_dataset(ctx,ctx['exact_mask'])
    direct_occurrence = reproduction.build_dataset(ctx,ctx['occurrence_mask'])
    assert all(np.array_equal(exact[k],direct[k]) for k in exact)
    assert all(np.array_equal(occurrence[k],direct_occurrence[k]) for k in occurrence)
    aliases = defaultdict(lambda:dict(names=set(),folds=set(),rows=0))
    for name,hash_,fold in zip(exact['af'],exact['geometry_hash'],exact['fold']):
        aliases[hash_]['names'].add(str(name))
        aliases[hash_]['folds'].add(int(fold))
        aliases[hash_]['rows']+=1
    duplicated = [dict(geometry_hash=k,names=sorted(v['names']),folds=sorted(v['folds']),rows=v['rows'])
                  for k,v in aliases.items() if len(v['names'])>1]
    cross_fold = [v for v in duplicated if len(v['folds'])>1]
    report = json.loads((HERE/'reproduction_results.json').read_text())
    oofs = dict(np.load(HERE/'reproduced_oof.npz',allow_pickle=False))
    for kind in ['CD','CL']:
        base,meas = exact['BASE_'+kind],exact['MEAS_'+kind]
        pred = reproduction.corrected(kind,base,oofs['oof'+kind])
        assert np.array_equal(pred,oofs['PRED_'+kind])
        recomputed = reproduction.metric_summary(meas,base,pred,kind)
        assert recomputed == report['results'][kind]['pooled_oof']
        n = sum(f['rows'] for f in report['results'][kind]['folds'])
        assert n==len(base)
        weighted = sum(f['rows']*f['corrected_mae'] for f in report['results'][kind]['folds'])/n
        assert abs(weighted-recomputed['corrected_mae'])<1e-12
    hashes_ok = all(reproduction.digest(project/key)==value for key,value in ctx['input_hashes'].items())
    assert hashes_ok
    qa = dict(status='PASS with scientific caveats',
              original_source_pure_geometry_functions_match=True,
              original_source_feature_arrays_match_bit_for_bit=array_checks,
              source_feature_row_order_and_baselines_match=True,
              repeated_dataset_build_arrays_identical=True,
              prediction_transforms_and_pooled_aggregates_recalculate=True,
              weighted_fold_aggregates_match_pooled=True,
              immutable_input_hashes_unchanged=hashes_ok,
              exact_rows=len(exact['af']),occurrence_rows=len(occurrence['af']),
              occurrence_selected_rows_with_ambiguous_config=int(occurrence['ambiguous_raw_config'].sum()),
              multi_name_geometry_hash_groups=duplicated,
              multi_name_geometry_hash_groups_crossing_folds=len(cross_fold),
              rows_in_cross_fold_alias_groups=sum(v['rows'] for v in cross_fold),
              scientific_caveats=['Version-mismatched refit does not reproduce every stored rounded prediction.',
                'Occurrence mapping alone cannot resolve identical full-measurement keys with conflicting configuration labels.',
                'Historical folds separate nominal names but demonstrably reuse identical coordinate files across folds.',
                'Source transfers share seven nominal names and are not geometry-disjoint.',
                'Historical head-to-head counts rows, including one repeated condition key; correction used even when drag shipment gate fails.'])
    (HERE/'reproduction_qa.json').write_text(json.dumps(qa,indent=2)+'\n')
    print(json.dumps({k:v for k,v in qa.items() if k!='multi_name_geometry_hash_groups'},indent=2))

if __name__=='__main__':
    main()
