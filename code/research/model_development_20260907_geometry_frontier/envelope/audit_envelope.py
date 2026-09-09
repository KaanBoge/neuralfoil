"""Exact independent-row convex-envelope relaxation, not a fitted predictor.

Standalone process required: the historical loader adjusts a solver binding in
its own imported module; this script never calls that solver or writes outside
its own directory. --verify replays the exact certificate from frozen inputs.
"""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal, localcontext
import hashlib
import json
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
FRONTIER = PROJECT/'model_development_20260907_frontier'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rational(q):
    if q is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 45
        display = str(Decimal(q.numerator)/Decimal(q.denominator))
    return {'numerator':str(q.numerator),'denominator':str(q.denominator),'decimal':display}


def panel_masks(d):
    panels = {}
    for seed in [20260906,20260908]:
        mask = d.split.str.startswith(f'group_{seed}_')
        assert mask.sum() == 8371 and d.loc[mask,'nf2_row_id'].nunique() == 8371
        panels[f'history_{seed}_pooled'] = np.flatnonzero(mask)
        for s in sorted(d.loc[mask,'source'].unique()):
            panels[f'history_{seed}_{s}'] = np.flatnonzero(mask & (d.source == s))
    for name in sorted(s for s in d.split.unique() if s.startswith('strict_source_')):
        panels[name] = np.flatnonzero(d.split == name)
    for cohort,field,n,eligible in [('SG_exposed','airfoil',242,234),('W_new_challenge','configuration',255,238)]:
        mask = d.split == cohort
        gate = d.inference_gate.map(lambda x:x is True or str(x).lower() == 'true' or x == 1)
        assert mask.sum() == n and (mask & gate).sum() == eligible
        panels[cohort+'_pooled'] = np.flatnonzero(mask)
        panels[f'eligible_only/{cohort}/pooled'] = np.flatnonzero(mask & gate)
        for value in sorted(d.loc[mask,field].unique()):
            panels[cohort+'_'+value] = np.flatnonzero(mask & (d[field] == value))
            panels[f'eligible_only/{cohort}/{value}'] = np.flatnonzero(mask & gate & (d[field] == value))
    assert len(panels) == 31
    return panels


def exact(y, p, baselines, panels):
    # Extrema selection is exact for finite binary floats. Arithmetic starts
    # only after conversion to rationals; no rounded float residual is used.
    lower,upper = p.min(axis=1),p.max(axis=1)
    qy = [F.from_float(float(v)) for v in y]
    ql = [F.from_float(float(v)) for v in lower]
    qu = [F.from_float(float(v)) for v in upper]
    oracle = [min(max(v,l),u) for v,l,u in zip(qy,ql,qu)]
    e = [abs(a-b) for a,b in zip(oracle,qy)]
    be = [[abs(F.from_float(float(b))-v) for b,v in zip(baselines[:,j],qy)] for j in range(2)]
    failures = [[a > F(91,100)*b for a,b in zip(e,err)] for err in be]
    rows = []
    ratios = []
    for name,ix in panels.items():
        esum = sum((e[i] for i in ix),F(0))
        record = {'panel':name,'rows':len(ix),'oracle_error_sum_CD':rational(esum),
                  'oracle_MAE_CD':rational(esum/len(ix)),
                  'outside_envelope_rows':sum(e[i] > 0 for i in ix),
                  'zero_oracle_error_rows':sum(e[i] == 0 for i in ix),
                  'fails_9pct_either_baseline_rows':sum(failures[0][i] or failures[1][i] for i in ix),
                  'baselines':{}}
        for j,base in enumerate(['xlarge_CD','mean8_CD']):
            total = sum((be[j][i] for i in ix),F(0))
            improvement = 1-esum/total if total else None
            entry = {'baseline_error_sum_CD':rational(total),
                     'maximum_improvement_fraction':rational(improvement),
                     'zero_baseline_error_rows':sum(be[j][i] == 0 for i in ix),
                     'fails_9pct_rows':sum(failures[j][i] for i in ix),
                     'fails_9pct_with_zero_baseline_rows':sum(failures[j][i] and be[j][i] == 0 for i in ix),
                     'relative_percentage_defined':bool(total)}
            record['baselines'][base] = entry
            if improvement is not None:
                ratios.append((improvement,name,base))
        rows.append(record)
    minimum,name,base = min(ratios)
    return {'panels':rows,'common_improvement_fraction_upper_bound':rational(minimum),
            'limiting_panel':name,'limiting_baseline':base,
            'all_panel_baseline_denominators_positive':len(ratios) == 62},(lower,upper,oracle,e,failures,be)


def generate():
    assert not (HERE/'certificate.json').exists(), 'Preserve completed audit'
    witness = FRONTIER/'union_calibration/complete_report.json'
    doc = json.loads(witness.read_text())
    before = {str(witness):sha(witness)}
    for path,digest in doc['input_sha256'].items():
        assert sha(path) == digest,path
        before[path] = digest
    sys.path.insert(0,str(FRONTIER))
    import union_calibration as union
    d,columns,aliases,hashes = union.get_data()
    assert columns == doc['components'] and len(columns) == 30
    for path,digest in hashes.items():
        assert path in before and before[path] == digest,path
    for p in [Path(__file__),HERE/'PROTOCOL.md',Path(union.__file__),Path(union.assessment.__file__),Path(union.old.__file__),Path(union.assessment.reconcile.__file__)]:
        before[str(p)] = sha(p)
    y = d.measured_CD.to_numpy(float)
    p = d[columns].to_numpy(float)
    b = d[['xlarge_CD','mean8_CD']].to_numpy(float)
    assert len(d) == 29856 and np.isfinite(p).all() and np.isfinite(y).all() and np.isfinite(b).all()
    gate = d.inference_gate.map(lambda x:x is True or str(x).lower() == 'true' or x == 1).to_numpy(bool)
    inactive = d.split.isin(['SG_exposed','W_new_challenge']).to_numpy() & ~gate
    assert inactive.sum() == 25
    np.testing.assert_array_equal(p[inactive],np.repeat(b[inactive,1,None],30,axis=1))
    panels = panel_masks(d)
    cert,details = exact(y,p,b,panels)
    lower,upper,oracle,error,failures,be = details
    metadata = d[[c for c in ['split','nf2_row_id','group','source','entry','airfoil','configuration','alpha','Re','inference_gate'] if c in d]].copy()
    metadata.insert(0,'context_row_index',np.arange(len(d)))
    metadata['measured_CD'] = y
    metadata['lower_CD'] = lower
    metadata['upper_CD'] = upper
    metadata['oracle_CD_display'] = [float(v) for v in oracle]
    metadata['oracle_error_CD_display'] = [float(v) for v in error]
    metadata['fails_9pct_xlarge'] = failures[0]
    metadata['fails_9pct_mean8'] = failures[1]
    metadata['fails_9pct_either'] = np.logical_or(*failures)
    metadata['zero_error_xlarge'] = [v == 0 for v in be[0]]
    metadata['zero_error_mean8'] = [v == 0 for v in be[1]]
    metadata['forced_mean8_fallback'] = inactive
    metadata.to_csv(HERE/'row_envelope.csv',index=False)
    np.savez_compressed(HERE/'parsed_inputs.npz',y=y,predictions=p,baselines=b,**{'panel_'+str(i):ix for i,ix in enumerate(panels.values())})
    cert.update({'status':'EXACT_LABEL_KNOWING_ROW_RELAXATION_NOT_A_TRAINED_MODEL',
                 'rows_with_repeated_contexts':len(d),'columns':columns,'component_aliases':aliases,
                 'forced_mean8_rows':int(inactive.sum()),'source_sha256':before,
                 'snapshot_sha256':sha(HERE/'parsed_inputs.npz'),'row_table_sha256':sha(HERE/'row_envelope.csv'),
                 'arithmetic':'Fractions of parsed IEEE binary floats; all differences/sums/ratios exact',
                 'scope':'Independent row choices relax shared-feature/router constraints; no bound on new/refitted component families.'})
    for path,digest in before.items():
        assert sha(path) == digest,path
    (HERE/'certificate.json').write_text(json.dumps(cert,indent=2)+'\n')
    summary = []
    for r in cert['panels']:
        row = {k:v for k,v in r.items() if k not in ['baselines','oracle_error_sum_CD','oracle_MAE_CD']}
        row['oracle_MAE_counts'] = float(r['oracle_MAE_CD']['decimal'])*1e4
        for base,v in r['baselines'].items():
            row[base+'_maximum_improvement_percent'] = float(v['maximum_improvement_fraction']['decimal'])*100 if v['relative_percentage_defined'] else None
            row[base+'_fails_9pct_rows'] = v['fails_9pct_rows']
            row[base+'_zero_baseline_rows'] = v['zero_baseline_error_rows']
        summary.append(row)
    pd.DataFrame(summary).to_csv(HERE/'panel_summary.csv',index=False)
    print('Exact certificate generated',cert['limiting_panel'],cert['common_improvement_fraction_upper_bound']['decimal'])


def verify():
    cert = json.loads((HERE/'certificate.json').read_text())
    assert sha(HERE/'parsed_inputs.npz') == cert['snapshot_sha256']
    assert sha(HERE/'row_envelope.csv') == cert['row_table_sha256']
    for path,digest in cert['source_sha256'].items():
        assert sha(path) == digest,path
    with np.load(HERE/'parsed_inputs.npz') as z:
        panels = {r['panel']:z['panel_'+str(i)] for i,r in enumerate(cert['panels'])}
        again,_ = exact(z['y'],z['predictions'],z['baselines'],panels)
        # A distinct arithmetic expression: distance equals max(L-y, y-U, 0).
        lo,hi = z['predictions'].min(axis=1),z['predictions'].max(axis=1)
        distance = [max(F(float(l))-F(float(y)),F(float(y))-F(float(h)),F(0)) for l,h,y in zip(lo,hi,z['y'])]
        for r,ix in zip(again['panels'],panels.values()):
            assert rational(sum((distance[i] for i in ix),F(0))) == r['oracle_error_sum_CD']
    for k,v in again.items():
        assert cert[k] == v,k
    result = {'status':'PASS','panels':31,'baseline_comparisons':62,'exact_replay':True,
              'independent_distance_identity':True,'certificate_sha256':sha(HERE/'certificate.json')}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result)


if __name__ == '__main__':
    verify() if '--verify' in sys.argv else generate()
