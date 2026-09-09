"""Independent saved-policy replay. No fitting, producer imports, or source writes.

Run only after results/complete.json exists. Writes only review/audit_results.json.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
CAP = PROJECT / 'model_development_20260907_frontier/capacity/results'
sys.path.insert(0, str(PROJECT / 'model_development_20260907_transition'))
import shape_inputs

CORE = 'hist62_regularized__1'
VARIANTS = {'risk_transfer': (True, 1.), 'unpenalized_transfer': (True, 0.), 'risk_group': (False, 1.)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def features(b, c, a):
    return np.column_stack([np.std(a/b[:, None], axis=1), np.abs(c/b-1)])


def replay(model, b, c, a, gate):
    ep = np.asarray(model['endpoints'])
    theta = np.asarray(model['corners'])
    assert ep.shape == (2, 2) and theta.shape == (4,)
    assert np.isfinite(ep).all() and np.isfinite(theta).all()
    assert np.all(ep[1] >= ep[0]) and np.all((theta >= 0) & (theta <= 1))
    span = ep[1]-ep[0]
    z = np.clip((features(b,c,a)-ep[0])/np.where(span > 0, span, 1), 0, 1)
    z[:,span == 0] = 0
    u,v = z.T
    phi = np.stack([(1-u)*(1-v),(1-u)*v,u*(1-v),u*v], axis=1)
    np.testing.assert_allclose(phi.sum(axis=1), 1., atol=1e-15, rtol=0)
    assert (phi >= 0).all()
    strength = np.where(gate, phi @ theta, 0.)
    p = np.where(gate, (1-strength)*b+strength*c, b)
    np.testing.assert_array_equal(p[~gate], b[~gate])
    assert np.all(p >= np.minimum(b,c)-1e-15) and np.all(p <= np.maximum(b,c)+1e-15)
    return p, strength


def balanced(group, source):
    counts = {}
    memberships = {}
    for g,s in zip(group,source):
        counts[s,g] = counts.get((s,g),0)+1
        memberships.setdefault(s,set()).add(g)
    w = np.array([1/(counts[s,g]*len(memberships[s])) for g,s in zip(group,source)])
    w /= w.mean()
    return (1+w)/2


def audit_metrics():
    """Independently construct panel masks; do not import assessment arithmetic."""
    target = ROOT/'assessment'
    if not (target/'report.json').exists():
        return {'status':'assessment pending'}
    frames = [pd.read_csv(p) for p in sorted((ROOT/'results').glob('predictions_*.csv'))]
    for name in ['SG_exposed','W_new_challenge']:
        f = pd.read_csv(ROOT/'exposed_results'/f'{name}_predictions.csv')
        f['split'] = name
        assert f.inference_gate.dtype == bool
        frames.append(f)
    d = pd.concat(frames,ignore_index=True)
    assert len(d) == 29856
    d['half_strength'] = d['hist62_regularized__0.5']
    d['full_strength'] = d[CORE]
    prior = pd.read_csv(PROJECT/'model_development_20260907_positive/historical_results/all_row_predictions.csv',low_memory=False)
    for split in d.split.unique():
        mask = d.split == split
        old = prior[prior.split == split]
        if split.startswith(('group_','strict_source_')):
            assert not old.nf2_row_id.duplicated().any()
            old = old.set_index('nf2_row_id').loc[d.loc[mask,'nf2_row_id']].reset_index()
        assert len(old) == mask.sum()
        for field in ['alpha','Re','measured_CD','mean8_CD','xlarge_CD']:
            np.testing.assert_allclose(old[field],d.loc[mask,field],rtol=0,atol=1e-13)
        d.loc[mask,'previous_global'] = old.primary_both.to_numpy()
    panels = {}
    for seed in [20260906,20260908]:
        mask = d.split.str.startswith(f'group_{seed}_')
        assert mask.sum() == 8371 and d.loc[mask,'nf2_row_id'].nunique() == 8371
        panels[f'history_{seed}_pooled'] = mask
        for s in sorted(d.loc[mask,'source'].unique()):
            panels[f'history_{seed}_{s}'] = mask & (d.source == s)
    for split in sorted(s for s in d.split.unique() if s.startswith('strict_source_')):
        panels[split] = d.split == split
    for cohort,field,n,eligible in [('SG_exposed','airfoil',242,234),('W_new_challenge','configuration',255,238)]:
        mask = d.split == cohort
        gate = d.inference_gate.eq(True)
        assert mask.sum() == n and (mask & gate).sum() == eligible
        panels[cohort+'_pooled'] = mask
        panels[f'eligible_only/{cohort}/pooled'] = mask & gate
        for value in sorted(d.loc[mask,field].unique()):
            panels[cohort+'_'+value] = mask & (d[field] == value)
            panels[f'eligible_only/{cohort}/{value}'] = mask & gate & (d[field] == value)
    assert len(panels) == 31
    table = pd.read_csv(target/'panel_metrics.csv').set_index(['candidate','panel'])
    harms = pd.read_csv(target/'harm_metrics.csv').set_index(['candidate','comparator','panel'])
    checked = 0
    labels = list(VARIANTS)+['half_strength','full_strength','previous_global']
    for label in labels:
        for panel,mask in panels.items():
            f = d.loc[mask]; y = f.measured_CD.to_numpy(); e = np.abs(f[label].to_numpy()-y)
            row = table.loc[label,panel]
            assert row['rows'] == len(f)
            np.testing.assert_allclose(row.mae_CD,e.mean(),atol=1e-14,rtol=0)
            for base in ['xlarge_CD','mean8_CD']:
                be = np.abs(f[base].to_numpy()-y)
                np.testing.assert_allclose(row[base+'_improvement_percent'],100*(1-e.sum()/be.sum()),atol=1e-9,rtol=0)
            for base in ['half_strength','xlarge_CD','mean8_CD']:
                delta = e-np.abs(f[base].to_numpy()-y); h = harms.loc[label,base,panel]
                assert h.worse_rows == (delta > 1e-12).sum()
                assert h.better_rows == (delta < -1e-12).sum()
                np.testing.assert_allclose(h.mean_positive_excess_absolute_error_CD,np.maximum(delta,0).mean(),atol=1e-14,rtol=0)
            checked += 1
    boot = pd.read_csv(target/'bootstrap.csv').set_index(['candidate','assignment'])
    decisions = pd.read_csv(target/'decisions.csv').set_index('candidate')
    guards = []
    for seed in [20260906,20260908]:
        f = d[d.split.str.startswith(f'group_{seed}_')]
        names,inv = np.unique(f.group,return_inverse=True)
        assert len(names) == 93
        counts = np.random.default_rng(2026090721).multinomial(93,np.full(93,1/93),size=20000)
        y = f.measured_CD.to_numpy()
        ref = np.bincount(inv,weights=abs(f.half_strength.to_numpy()-y))
        count_rows = np.bincount(inv)
        xl = np.bincount(inv,weights=abs(f.xlarge_CD.to_numpy()-y))
        half_relative = 100*(1-ref/xl)
        half_raw = (ref-xl)/count_rows
        for label in labels:
            err = np.bincount(inv,weights=abs(f[label].to_numpy()-y))
            draws = 100*(1-(counts@err)/(counts@ref))
            interval = np.quantile(draws,[.025,.975])
            row = boot.loc[label,seed]
            np.testing.assert_allclose([row.conditional_95pct_lower,row.conditional_95pct_upper],interval,atol=1e-9,rtol=0)
            if label not in VARIANTS:
                continue
            rel = 100*(1-err/xl); raw = (err-xl)/count_rows
            relative_pass = bool((rel < -1e-6).sum() <= (half_relative < -1e-6).sum() and max(0.,-rel.min()) <= max(0.,-half_relative.min())+1e-6)
            raw_pass = bool((raw > 1e-12).sum() <= (half_raw > 1e-12).sum() and max(0.,raw.max()) <= max(0.,half_raw.max())+1e-12)
            assert bool(decisions.loc[label,f'{seed}_identity_guard_pass']) == relative_pass
            if f'{seed}_raw_CD_identity_guard_pass' in decisions:
                assert bool(decisions.loc[label,f'{seed}_raw_CD_identity_guard_pass']) == raw_pass
            guards.append({'variant':label,'assignment':seed,'relative_guard':relative_pass,'raw_CD_guard':raw_pass})
    return {'status':'PASS','candidate_panel_rows':checked,'paired_bootstrap_intervals':12,'identity_guards':guards,'note':'Three policies and all three controls independently checked.'}


def main():
    out = ROOT/'results'
    assert (out/'complete.json').is_file(), 'Do not audit exposed files before completion'
    d = shape_inputs.load_historical()
    ids = np.arange(len(d['BASE_CD']))
    cases = []
    for seed in [20260906,20260908]:
        for k,test in enumerate(shape_inputs.transition.v2.old.group_folds(d['group'],5,seed)):
            cases.append((f'group_{seed}_fold_{k}',ids[~test],ids[test]))
    for source in sorted(set(d['source']))+['all_uiuc_volumes']:
        test = d['source'] != 'stec8' if source == 'all_uiuc_volumes' else d['source'] == source
        train = ~test & ~np.isin(d['group'],d['group'][test])
        cases.append(('strict_source_'+source,ids[train],ids[test]))
    cases.append(('final',ids,np.array([],dtype=int)))
    report = {'policies': [], 'metrics': [], 'hash_checks': 0}
    for name in ['freeze.json','complete.json']:
        doc = json.loads((out/name).read_text())
        for section in ['source_input_sha256','artifact_sha256']:
            for path,digest in doc[section].items():
                assert sha(path) == digest, path
                report['hash_checks'] += 1
    for split,tr,te in cases:
        assert not set(d['group'][tr]) & set(d['group'][te])
        with np.load(CAP/f'{split}_inner_group.npz') as z:
            np.testing.assert_array_equal(z['indices'],tr)
            np.testing.assert_array_equal(z['identity'],d['BASE_CD'][tr])
            gc = z[CORE].copy()
        blocks = [(tr,gc)]
        transfer = []
        for source in sorted(set(d['source'][tr])):
            test = d['source'][tr] == source
            train = ~test & ~np.isin(d['group'][tr],d['group'][tr[test]])
            path = CAP/f'{split}_inner_transfer_{source}.npz'
            if len(set(d['group'][tr[train]])) < 6 or train.sum() < 300:
                assert not path.exists()
                continue
            with np.load(path) as z:
                np.testing.assert_array_equal(z['train_indices'],tr[train])
                np.testing.assert_array_equal(z['test_indices'],tr[test])
                np.testing.assert_array_equal(z['identity'],d['BASE_CD'][tr[test]])
                assert not set(d['group'][tr[train]]) & set(d['group'][tr[test]])
                transfer.append((tr[test],z[CORE].copy()))
        if transfer:
            ti = np.concatenate([i for i,c in transfer])
            assert len(np.unique(ti)) == len(ti) and set(ti) <= set(tr)
            blocks.append((ti,np.concatenate([c for i,c in transfer])))
        ep = np.quantile(features(d['BASE_CD'][tr],gc,d['all_model_CD'][tr]), [.05,.95],axis=0)
        frame = pd.read_csv(out/f'predictions_{split}.csv') if len(te) else None
        if frame is not None:
            np.testing.assert_array_equal(frame.nf2_row_id,d['nf2_row_id'][te])
            np.testing.assert_allclose(frame.measured_CD,d['MEAS_CD'][te],atol=1e-13,rtol=0)
        for label,(aug,lam) in VARIANTS.items():
            m = json.loads((out/f'policy_{split}_{label}.json').read_text())
            np.testing.assert_array_equal(m['training']['training_indices'],tr)
            np.testing.assert_array_equal(m['training']['training_nf2_row_ids'],d['nf2_row_id'][tr])
            np.testing.assert_array_equal(m['endpoints'],ep)
            active = blocks if aug else blocks[:1]
            ix = np.concatenate([i for i,c in active]); c = np.concatenate([c for i,c in active])
            ws = [balanced(d['group'][i],d['source'][i]) for i,c in active]
            w = np.concatenate([a/a.sum()/len(ws) for a in ws])
            b,y = d['BASE_CD'][ix],d['MEAS_CD'][ix]
            p,_ = replay(m,b,c,d['all_model_CD'][ix],np.ones(len(ix),bool))
            err = np.abs(p-y)*1e4; anchor = np.abs((b+c)/2-y)*1e4
            loss = float(w @ (err+lam*np.maximum(0,err-anchor)))
            diag = m['diagnostics']
            assert abs(loss-diag['actual_objective_counts']) < 1e-9
            assert abs(loss-diag['primary_optimum_counts']) <= 1.11e-8
            assert diag['solver_status'] == [0,0]
            assert abs(np.abs(np.array(m['corners'])-.5).sum()-diag['secondary_corner_distance']) < 1e-12
            rec = {'split':split,'variant':label,'actual_loss_counts':loss,'objective_difference_counts':loss-diag['primary_optimum_counts']}
            if frame is not None:
                p,s = replay(m,d['BASE_CD'][te],frame[CORE].to_numpy(),d['all_model_CD'][te],np.ones(len(te),bool))
                np.testing.assert_allclose(p,frame[label],rtol=0,atol=1e-14)
                np.testing.assert_allclose(s,frame[label+'__strength'],rtol=0,atol=1e-14)
                rec['prediction_max_abs_CD'] = float(np.max(np.abs(p-frame[label])))
            report['policies'].append(rec)
    assert len(report['policies']) == 48
    # Native saved inference replay includes the complete external populations.
    for name,path in [('historical',out/'historical_inference.npz'),('SG_exposed',ROOT/'exposed_results/SG_exposed_inference.npz'),('W_new_challenge',ROOT/'exposed_results/W_new_challenge_inference.npz')]:
        with np.load(path) as z:
            for label in VARIANTS:
                m = json.loads((out/f'policy_final_{label}.json').read_text())
                p,_ = replay(m,z['BASE_CD'],z['CORE_CD'],z['all_model_CD'],z['gate'])
                np.testing.assert_array_equal(p,z[label])
    report['metrics'] = audit_metrics()
    report['status'] = 'PASS independent replay; no fits'
    (ROOT/'review/audit_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],len(report['policies']))


if __name__ == '__main__':
    main()
