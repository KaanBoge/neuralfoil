"""Fixed bounded incremental-harm calibration; NumPy only, no file I/O."""
import numpy as np

EPSILON = .01
DELTA = .05
BOUND = .5
LABEL = 'calibrated_incremental_harm_001'
SCHEMA = 'incremental_harm_group_hoeffding_v1'


def inputs(base, core, gate):
    b, c, g = np.asarray(base, float), np.asarray(core, float), np.asarray(gate)
    if b.ndim != 1 or c.shape != b.shape or g.shape != b.shape or g.dtype != bool:
        raise ValueError('Expected aligned vectors and strict boolean gate')
    if not np.isfinite(b).all() or not np.isfinite(c).all() or np.any(b <= 0) or np.any(c <= 0):
        raise ValueError('Positive finite base/core required')
    # Never widen the proof bound to accommodate numeric or upstream violations.
    if np.any(c < .5*b) or np.any(c > 2*b):
        raise ValueError('Capped core violates its exact proof domain')
    c = np.where(g, c, b)
    h = b + .5*(c-b)
    return b, c, h, g


def group_losses(base, core, target, groups, gate):
    b, c, h, g = inputs(base, core, gate)
    y, ids = np.asarray(target, float), np.asarray(groups)
    if y.shape != b.shape or ids.shape != b.shape or not np.isfinite(y).all():
        raise ValueError('Aligned finite target and identity vectors required')
    if ids.dtype.kind not in 'US':
        raise ValueError('Identity strings required')
    ids = ids.astype(str)
    if np.any(ids == ''):
        raise ValueError('Empty identity')
    # Direct difference retained, no target clipping and no positive-loss tolerance.
    loss = np.maximum(abs(c-y)-abs(h-y), 0)/b
    if not np.isfinite(loss).all() or np.any(loss > BOUND) or np.any(loss < 0):
        raise ValueError('Endpoint loss violates fixed proof bound')
    np.testing.assert_array_equal(loss[~g], np.zeros((~g).sum()))
    names = np.unique(ids)
    values = np.array([loss[ids == name].mean() for name in names])
    counts = np.array([(ids == name).sum() for name in names], int)
    return names, values, counts, loss


def calibrate(base, core, target, groups, gate):
    names, values, counts, losses = group_losses(base, core, target, groups, gate)
    m = len(names)
    mean = float(values.mean()) if m else None
    penalty = BOUND*np.sqrt(np.log(1/DELTA)/(2*m)) if m else None
    upper = min(BOUND, mean+penalty) if m else BOUND
    t = min(1., EPSILON/upper)
    model = {'schema': SCHEMA, 'epsilon': EPSILON, 'delta': DELTA, 'B': BOUND,
             'groups': m, 'rows': len(losses), 'endpoint_mean': mean,
             'hoeffding_penalty': float(penalty) if m else None, 'upper_bound': float(upper),
             't': float(t), 'inside_gate_strength': float(.5+.5*t),
             'status': 'conditional_iid_bound_exploratory' if m else 'deterministic_bound_only',
             'group_names': names.tolist(), 'group_endpoint_losses': values.tolist(),
             'group_rows': counts.tolist()}
    validate_model(model)
    return model


def validate_model(model):
    if not isinstance(model, dict) or model.get('schema') != SCHEMA:
        raise ValueError('Unknown calibration schema')
    if any(model.get(k) != v for k,v in [('epsilon',EPSILON),('delta',DELTA),('B',BOUND)]):
        raise ValueError('Constants do not match approved protocol')
    u, t = model.get('upper_bound'), model.get('t')
    if not np.isscalar(u) or not np.isscalar(t) or not np.isfinite([u,t]).all():
        raise ValueError('Finite scalar bound/strength required')
    if not (0 < u <= BOUND and 0 <= t <= 1) or t != min(1., EPSILON/u):
        raise ValueError('Invalid calibration bound/strength')
    return float(t)


def predict(model, base, core, gate):
    t = validate_model(model)
    b, c, h, g = inputs(base, core, gate)
    p = np.where(g, h+t*(c-h), b)
    if not np.isfinite(p).all() or np.any(p <= 0):
        raise ValueError('Invalid prediction')
    return {'prediction': p, 'anchor': h, 'endpoint': c,
            'applied_strength': np.where(g, .5+.5*t, 0.),
            'intervened_vs_anchor': abs(p-h)>1e-12,
            'intervened_vs_mean8': abs(p-b)>1e-12}
