"""Fixed proper-only magnitude scale and whole-bundle interval projection.

No I/O or fitting on import. Calibration assumes the caller has isolated all
calibration identities from both the core and scale fitting procedures.
"""
import math
from fractions import Fraction
import numpy as np

SCHEMA = 'whole_group_adaptive_scale_projection_v1'
PARAMETERS = dict(loss='absolute_error', max_iter=200, max_leaf_nodes=7,
    min_samples_leaf=120, learning_rate=.05, l2_regularization=5,
    random_state=829, early_stopping=False, categorical_features=None)
TARGET_FLOOR = 1e-6


def vector(value, name, positive=False):
    raw = np.asarray(value)
    if raw.ndim != 1 or raw.dtype.kind not in 'fiu':
        raise ValueError(name + ' must be a numeric vector')
    out = raw.astype(float)
    if not np.isfinite(out).all() or (positive and np.any(out <= 0)):
        raise ValueError(name + ' must be finite' + (' and positive' if positive else ''))
    return out


def features(value):
    raw = np.asarray(value)
    if raw.ndim != 2 or raw.shape[1] != 62 or raw.dtype.kind not in 'fiu':
        raise ValueError('X62 must be a numeric matrix with 62 columns')
    out = raw.astype(float)
    if not np.isfinite(out).all():
        raise ValueError('X62 must be finite')
    return out


def ids(value, shape, name):
    g = np.asarray(value)
    if g.shape != shape or g.dtype.kind not in 'US':
        raise ValueError(name + ' must be aligned nonempty string IDs')
    g = g.astype(str)
    if np.any(g == ''):
        raise ValueError(name + ' must be aligned nonempty string IDs')
    return g


def balanced_weights(groups, sources):
    counts, members = {}, {}
    pairs = list(zip(sources.tolist(), groups.tolist()))
    for s, g in pairs:
        counts[s, g] = counts.get((s, g), 0) + 1
        members.setdefault(s, set()).add(g)
    w = np.array([1 / (counts[p] * len(members[p[0]])) for p in pairs])
    return w / w.mean()


def training_arrays(y, inner_core, mean8, groups, sources):
    y, c, b = vector(y, 'y', True), vector(inner_core, 'inner_core', True), vector(mean8, 'mean8', True)
    if not len(y) or y.shape != c.shape or y.shape != b.shape:
        raise ValueError('Nonempty aligned training vectors required')
    g, src = ids(groups, y.shape, 'groups'), ids(sources, y.shape, 'sources')
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        try:
            target = np.log(np.maximum(np.abs(y - c) / b, TARGET_FLOOR))
            weights = (1 + balanced_weights(g, src)) / 2
            weights /= weights.mean()
        except FloatingPointError as exc:
            raise ValueError('Nonfinite scale training arithmetic') from exc
    if not np.isfinite(target).all() or not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError('Invalid scale training target or weights')
    return target, weights


def fit(X62, y, inner_core, mean8, groups, sources):
    from sklearn.ensemble import HistGradientBoostingRegressor
    x = features(X62)
    t, w = training_arrays(y, inner_core, mean8, groups, sources)
    if len(x) != len(t):
        raise ValueError('Aligned scale features and targets required')
    estimator = HistGradientBoostingRegressor(**PARAMETERS)
    estimator.fit(x, t, sample_weight=w)
    return {'schema': SCHEMA, 'feature_key': 'X62', 'model': estimator,
            'scale_semantics': 'dimensionless_exp_log_residual_magnitude', 'target_floor': TARGET_FLOOR}


def positive_exp(raw):
    r = vector(raw, 'raw scale')
    with np.errstate(over='raise', invalid='raise', under='ignore'):
        try:
            s = np.exp(r)
        except FloatingPointError as exc:
            raise ValueError('Scale exponential overflow') from exc
    if not np.isfinite(s).all() or np.any(s <= 0):
        raise ValueError('Scale must be finite and positive; no numerical clipping')
    return s


def predict(model, X62):
    if not isinstance(model, dict) or model.get('schema') != SCHEMA or model.get('feature_key') != 'X62':
        raise ValueError('Unknown scale model')
    x = features(X62)
    return positive_exp(model['model'].predict(x)) if len(x) else np.empty(0)


def scale_cd(mean8, scale):
    b, s = vector(mean8, 'mean8', True), vector(scale, 'scale', True)
    if b.shape != s.shape:
        raise ValueError('Aligned mean8 and scale required')
    with np.errstate(over='raise', invalid='raise', under='ignore'):
        try:
            u = b * s
        except FloatingPointError as exc:
            raise ValueError('CD scale overflow') from exc
    if not np.isfinite(u).all() or np.any(u <= 0):
        raise ValueError('CD scale must be finite and positive')
    return u


def rank(m, alpha=.10):
    if isinstance(m, bool) or not isinstance(m, (int, np.integer)) or m < 0:
        raise ValueError('m must be a nonnegative integer')
    if isinstance(alpha, (str, bool)) or not np.isscalar(alpha):
        raise ValueError('alpha must be a numeric scalar')
    a = float(alpha)
    if not math.isfinite(a) or not 0 < a < 1:
        raise ValueError('alpha must be in (0,1)')
    return math.ceil((int(m) + 1) * (1 - Fraction(str(a))))


def calibrate(core, mean8, scale, y, groups, alpha=.10):
    c, y, u = vector(core, 'core', True), vector(y, 'y'), scale_cd(mean8, scale)
    if not len(c) or c.shape != y.shape or c.shape != u.shape:
        raise ValueError('Nonempty aligned calibration vectors required')
    g = ids(groups, c.shape, 'groups')
    names, inverse = np.unique(g, return_inverse=True)
    with np.errstate(over='raise', invalid='raise', divide='raise', under='ignore'):
        try:
            score = np.abs(y - c) / u
        except FloatingPointError as exc:
            raise ValueError('Nonfinite calibration score') from exc
    if not np.isfinite(score).all():
        raise ValueError('Nonfinite calibration score')
    maxima = np.zeros(len(names))
    np.maximum.at(maxima, inverse, score)
    k = rank(len(names), alpha)
    q = None if k > len(names) else float(np.sort(maxima)[k - 1])
    return {'schema': SCHEMA, 'alpha': float(alpha), 'calibration_groups': len(names),
        'calibration_rows': len(c), 'rank': k, 'q': q, 'unbounded': q is None,
        'score': 'group_max_abs_residual_over_scale_CD', 'scale_CD': 'mean8_CD * dimensionless_scale',
        'group_ids': names.tolist(), 'group_scores': maxima.tolist()}


def _q(model):
    if not isinstance(model, dict) or model.get('schema') != SCHEMA or model.get('scale_CD') != 'mean8_CD * dimensionless_scale':
        raise ValueError('Unknown adaptive calibration schema or scale semantics')
    m = model.get('calibration_groups')
    k = rank(m, model.get('alpha'))
    if m < 1 or model.get('rank') != k or type(model.get('unbounded')) is not bool:
        raise ValueError('Invalid calibration metadata')
    q = model.get('q')
    if k > m:
        if q is not None or model['unbounded'] is not True:
            raise ValueError('Insufficient groups require unbounded interval')
        return None
    if q is None or isinstance(q, (bool, str)) or not np.isscalar(q):
        raise ValueError('Finite nonnegative q required')
    q = float(q)
    if not math.isfinite(q) or q < 0 or model['unbounded']:
        raise ValueError('Invalid q')
    return q


def project(model, core, mean8, scale, baseline, gate):
    q = _q(model)
    c, a, u = vector(core, 'core', True), vector(baseline, 'baseline', True), scale_cd(mean8, scale)
    g = np.asarray(gate)
    if c.shape != a.shape or c.shape != u.shape or g.shape != c.shape or g.dtype != bool:
        raise ValueError('Aligned vectors and strictly boolean gate required')
    lower, upper = np.full(len(c), -np.inf), np.full(len(c), np.inf)
    p = a.copy()
    if q is not None and g.any():
        with np.errstate(over='raise', invalid='raise', under='ignore'):
            try:
                width = q * u[g]
                lower[g], upper[g] = c[g] - width, c[g] + width
            except FloatingPointError as exc:
                raise ValueError('Interval arithmetic overflow') from exc
        p[g] = np.clip(a[g], lower[g], upper[g])
    if not np.isfinite(p).all() or np.any(p <= 0):
        raise ValueError('Invalid projected prediction')
    return {'prediction': p, 'lower': lower, 'upper': upper,
            'intervened': p != a, 'applicable': g.copy(), 'scale_CD': u}
