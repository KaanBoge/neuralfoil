"""Three frozen cap-ablation families; no I/O on import."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

FAMILIES = ('capped', 'upper_free', 'positive_log')
PARAMETERS = dict(loss='absolute_error', max_iter=400, max_leaf_nodes=15,
    min_samples_leaf=120, learning_rate=.035, l2_regularization=5,
    random_state=824, early_stopping=False, categorical_features=None)


def vector(x, name, positive=False):
    a = np.asarray(x)
    if a.ndim != 1 or a.dtype.kind not in 'fiu':
        raise ValueError(name + ' must be a numerical vector')
    a = a.astype(float)
    if not np.isfinite(a).all() or (positive and np.any(a <= 0)):
        raise ValueError(name + ' must be finite' + (' and positive' if positive else ''))
    return a


def balanced_weights(groups, sources):
    counts, members = {}, {}
    pairs = list(zip(sources.tolist(), groups.tolist()))
    for source, group in pairs:
        counts[source, group] = counts.get((source, group), 0) + 1
        members.setdefault(source, set()).add(group)
    w = np.array([1 / (counts[pair] * len(members[pair[0]])) for pair in pairs])
    return w / w.mean()


def training_arrays(family, base, y, groups, sources):
    if family not in FAMILIES:
        raise ValueError('Unknown family')
    b, target = vector(base, 'base', True), vector(y, 'y', True)
    g, s = np.asarray(groups), np.asarray(sources)
    if not len(b) or any(a.shape != b.shape for a in [target, g, s]):
        raise ValueError('Nonempty aligned training rows required')
    if g.dtype.kind not in 'US' or s.dtype.kind not in 'US' or np.any(g == '') or np.any(s == ''):
        raise ValueError('Nonempty string group/source IDs required for training weights')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        try:
            v = (1 + balanced_weights(g, s)) / 2
            if family == 'positive_log':
                t = np.log(target / b)
                w = v * target
            else:
                t = (target - b) / b
                t = np.clip(t, -.5, 1.) if family == 'capped' else np.maximum(t, -.5)
                w = v * b
            w /= w.mean()
        except FloatingPointError as exc:
            raise ValueError('Nonfinite training transformation') from exc
    if not np.isfinite(t).all() or not np.isfinite(w).all() or np.any(w <= 0):
        raise ValueError('Invalid transformed targets or weights')
    return t, w


def transform(family, raw, base):
    if family not in FAMILIES:
        raise ValueError('Unknown family')
    r, b = vector(raw, 'raw'), vector(base, 'base', True)
    if r.shape != b.shape:
        raise ValueError('Aligned predictions and baselines required')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        try:
            if family == 'capped':
                pred = np.clip(b * (1 + np.clip(r, -.5, 1.)), .5 * b, 2 * b)
            elif family == 'upper_free':
                pred = b * (1 + np.maximum(r, -.5))
            else:
                pred = b * np.exp(r)
        except FloatingPointError as exc:
            raise ValueError('Prediction arithmetic overflow or invalid result') from exc
    if not np.isfinite(pred).all() or np.any(pred <= 0):
        raise ValueError('Prediction must be finite and positive; no numerical clipping permitted')
    return pred


def half(core, base):
    c, b = vector(core, 'core', True), vector(base, 'base', True)
    if c.shape != b.shape:
        raise ValueError('Aligned vectors required')
    with np.errstate(over='raise', invalid='raise'):
        try:
            p = b + .5 * (c - b)
        except FloatingPointError as exc:
            raise ValueError('Half interpolation arithmetic failure') from exc
    if not np.isfinite(p).all() or np.any(p <= 0):
        raise ValueError('Half prediction must be finite and positive')
    return p


def fit(family, d, idx):
    x = np.asarray(d['X62'][idx], dtype=float)
    if x.ndim != 2 or x.shape[1] != 62 or not len(x) or not np.isfinite(x).all():
        raise ValueError('Finite nonempty X62 required')
    target, weights = training_arrays(family, d['BASE_CD'][idx], d['MEAS_CD'][idx],
                                     d['group'][idx], d['source'][idx])
    if len(target) != len(x):
        raise ValueError('Aligned features and targets required')
    estimator = HistGradientBoostingRegressor(**PARAMETERS)
    estimator.fit(x, target, sample_weight=weights)
    return {'family': family, 'feature_key': 'X62', 'model': estimator}


def predict(model, d, idx):
    x = np.asarray(d['X62'][idx], dtype=float)
    b = vector(d['BASE_CD'][idx], 'base', True)
    if x.ndim != 2 or x.shape != (len(b), 62) or not np.isfinite(x).all():
        raise ValueError('Finite aligned X62 required')
    if not len(b):
        return b.copy()
    return transform(model['family'], model['model'].predict(x), b)
