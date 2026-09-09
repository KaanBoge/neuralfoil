"""Predeclared reflection and cross-fitted gating candidates; no I/O on import."""
from pathlib import Path
import sys
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'model_development_20260906_v2'))
import develop_v2 as v2

FAMILIES = ['invariant_balanced', 'invariant_mixed', 'reflection_averaged', 'gate_benefit', 'gate_shrink']
ODD = [0, 4, 9, 15, 20]
EVEN = [1, 2, 3, 5, 6, 7, 8, 10, 11, 14, 16, 17, 18, 19, 21, 22, 23]


def reflect(x):
    out = x.copy()
    out[:, ODD] *= -1
    out[:, 12], out[:, 13] = x[:, 13], x[:, 12]
    return out


def invariant(x):
    odd = x[:, ODD]
    return np.column_stack([x[:, EVEN]] + [odd[:, i]*odd[:, j] for i in range(5) for j in range(i, 5)])


def hist(loss='absolute_error', gate=False, augmented=False):
    return HistGradientBoostingRegressor(loss=loss, max_iter=100 if gate else 200,
        max_leaf_nodes=7 if gate else 15, min_samples_leaf=160 if (gate or augmented) else 80,
        learning_rate=.05, l2_regularization=1, early_stopping=False, categorical_features=None, random_state=824)


def weights(d, idx, mixed=True):
    w = v2.old.balanced_weights(d['group'][idx], d['source'][idx])
    return (1+w)/2 if mixed else w


def gate_x(x, base, pred):
    return np.column_stack([x, (pred-base)/base, np.abs(pred-base)*1e4])


def fit(family, d, idx):
    idx = np.asarray(idx)
    x, base, y = d['X24'][idx], d['BASE_CD'][idx], d['MEAS_CD'][idx]
    w = weights(d, idx, family != 'invariant_balanced')
    if family.startswith('gate_'):
        oof = np.full(len(idx), np.nan)
        for te in v2.old.group_folds(d['group'][idx], 3, 20260910):
            tr, test = idx[~te], idx[te]
            assert not set(d['group'][tr]) & set(d['group'][test])
            inner = v2.fit('hist24_relative_mixed', d, tr)
            oof[te] = v2.correct('relative', inner.predict(d['X24'][test]), d['BASE_CD'][test], 1)
        assert np.isfinite(oof).all()
        gx = gate_x(x, base, oof)
        if family == 'gate_benefit':
            target = (np.abs(y-base)-np.abs(y-oof))*1e4
            gate = hist('squared_error', gate=True).fit(gx, target, sample_weight=w/w.mean())
        else:
            delta = oof-base
            nz = np.abs(delta) > 1e-12
            target = np.clip((y[nz]-base[nz])/delta[nz], 0, 1)
            gw = w[nz]*np.abs(delta[nz])
            gate = hist(gate=True).fit(gx[nz], target, sample_weight=gw/gw.mean())
        base_model = v2.fit('hist24_relative_mixed', d, idx)
        return {'family': family, 'base_model': base_model, 'gate': gate, 'training_rows': len(idx)}
    target = np.clip((y-base)/base, -.5, 1)
    w = w*base
    w /= w.mean()
    if family == 'reflection_averaged':
        # Half weights preserve total training mass; min leaf doubles to retain effective support.
        fx = np.concatenate([x, reflect(x)])
        model = hist(augmented=True).fit(fx, np.tile(target, 2), sample_weight=np.tile(w/2, 2))
    else:
        model = hist().fit(invariant(x), target, sample_weight=w)
    return {'family': family, 'model': model, 'training_rows': len(idx)}


def predict(model, d, idx):
    x, base = d['X24'][idx], d['BASE_CD'][idx]
    family = model['family']
    if family.startswith('gate_'):
        correction = v2.correct('relative', model['base_model'].predict(x), base, 1)
        val = model['gate'].predict(gate_x(x, base, correction))
        strength = (val > 0).astype(float) if family == 'gate_benefit' else np.clip(val, 0, 1)
        pred = base + strength*(correction-base)
    elif family == 'reflection_averaged':
        raw = (model['model'].predict(x)+model['model'].predict(reflect(x)))/2
        pred = v2.correct('relative', raw, base, 1)
    else:
        pred = v2.correct('relative', model['model'].predict(invariant(x)), base, 1)
    assert np.isfinite(pred).all()
    return np.clip(pred, .5*base, 2*base)
