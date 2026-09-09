"""Four-corner half-anchor harm policy. Import is data-I/O-free; inference is NumPy-only."""
import numpy as np

SCALE = 1e4
TIE_TOL = 1e-9  # Absolute drag-count objective tolerance, not an exact tie.


def _array(value, name):
    raw = np.asarray(value)
    if raw.dtype.kind not in 'fiu':
        raise ValueError(name + ' must be numeric')
    out = raw.astype(float)
    if not np.isfinite(out).all():
        raise ValueError(name + ' must be finite')
    return out


def _inputs(base, core, all_model_CD):
    b, c, a = [_array(v, n) for v, n in zip(
        (base, core, all_model_CD), ('base', 'core', 'all_model_CD'))]
    if b.ndim != 1 or c.shape != b.shape or a.shape != (len(b), 8):
        raise ValueError('Expected base/core (n,) and all_model_CD (n,8)')
    if np.any(b <= 0) or np.any(c <= 0) or np.any(a <= 0):
        raise ValueError('Inference inputs must be positive')
    f = np.column_stack((np.std(a / b[:, None], axis=1), np.abs(c / b - 1)))
    if not np.isfinite(f).all():
        raise ValueError('Nonfinite relative features')
    return b, c, f


def _basis(features, endpoints):
    span = endpoints[1] - endpoints[0]
    z = np.clip((features - endpoints[0]) / np.where(span > 0, span, 1), 0, 1)
    z[:, span == 0] = 0
    u, v = z.T
    return np.column_stack(((1-u)*(1-v), (1-u)*v, u*(1-v), u*v))


def _model(model):
    if model.get('schema') != 'bilinear_half_anchor_harm_v1':
        raise ValueError('Unknown policy schema')
    endpoints = _array(model.get('endpoints'), 'endpoints')
    corners = _array(model.get('corners'), 'corners')
    if endpoints.shape != (2, 2) or np.any(endpoints < 0) or np.any(endpoints[1] < endpoints[0]):
        raise ValueError('Invalid feature endpoints')
    if corners.shape != (4,) or np.any(corners < 0) or np.any(corners > 1):
        raise ValueError('Invalid corner strengths')
    return endpoints, corners


def predict(model, base, core, all_model_CD, gate):
    """Return (CD, applied strength); false gates have exact base and zero strength."""
    endpoints, corners = _model(model)  # Validate even when every gate is false.
    b, c, features = _inputs(base, core, all_model_CD)
    gate = np.asarray(gate)
    if gate.dtype != np.dtype(bool) or gate.shape != b.shape:
        raise ValueError('gate must be a boolean (n,) array')
    strength = np.where(gate, _basis(features, endpoints) @ corners, 0.)
    pred = np.where(gate, (1-strength)*b + strength*c, b)
    if not np.isfinite(pred).all() or np.any(pred <= 0):
        raise ValueError('Invalid prediction')
    return pred, strength


def fit(base, core, y, all_model_CD, weights, penalty, feature_reference=None):
    """Fit only supplied observations; caller owns group/source split isolation.

    feature_reference supplies only the group-OOF feature block when the fitting
    observations also contain transfer contexts. Penalty and architecture are
    prespecified by the caller. Secondary fit permits TIE_TOL objective increase.
    """
    from scipy import sparse
    from scipy.optimize import linprog
    import warnings

    b, c, features = _inputs(base, core, all_model_CD)
    y, w = _array(y, 'y'), _array(weights, 'weights')
    lam = _array(penalty, 'penalty')
    if not len(b) or y.shape != b.shape or w.shape != b.shape or np.any(w <= 0):
        raise ValueError('Nonempty observations and positive aligned weights required')
    if lam.ndim != 0 or lam < 0:
        raise ValueError('penalty must be finite nonnegative scalar')
    lam = float(lam)
    w = w / np.max(w)
    w /= w.sum()
    reference = features if feature_reference is None else _inputs(*feature_reference)[2]
    if not len(reference):
        raise ValueError('Empty feature reference')
    endpoints = np.quantile(reference, [.05, .95], axis=0)
    phi = _basis(features, endpoints)
    n = len(b)
    # Variables: four corners, n absolute errors, n positive excess errors,
    # four absolute corner distances from the half-strength anchor.
    k = 2*n + 8
    d = sparse.csr_matrix((c-b)[:, None] * phi * SCALE)
    eye = sparse.eye(n, format='csr')
    z = sparse.csr_matrix((n, n))
    z4 = sparse.csr_matrix((n, 4))
    r = (y-b)*SCALE
    anchor_error = np.abs(((b+c)*.5-y)*SCALE)
    a = sparse.vstack([
        sparse.hstack([d, -eye, z, z4]),
        sparse.hstack([-d, -eye, z, z4]),
        sparse.hstack([z4, eye, -eye, z4]),
        sparse.hstack([sparse.eye(4), sparse.csr_matrix((4,2*n)), -sparse.eye(4)]),
        sparse.hstack([-sparse.eye(4), sparse.csr_matrix((4,2*n)), -sparse.eye(4)])], format='csr')
    rhs = np.concatenate((r, -r, anchor_error, np.full(4,.5), np.full(4,-.5)))
    cost = np.concatenate((np.zeros(4), w, lam*w, np.zeros(4)))
    bounds = [(0,1)]*4 + [(0,None)]*(k-4)

    def solve(objective, matrix, right):
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Unrecognized options detected.*')
            result = linprog(objective, A_ub=matrix, b_ub=right, bounds=bounds,
                method='highs', options={'threads':1, 'primal_feasibility_tolerance':1e-10,
                                          'dual_feasibility_tolerance':1e-10})
        if not result.success:
            raise RuntimeError('Policy LP failed: '+result.message)
        violation = max(0., float(np.max(matrix @ result.x-right)))
        if violation > 1e-8:
            raise RuntimeError('Policy LP constraint violation')
        return result, violation

    first, v1 = solve(cost, a, rhs)
    second_a = sparse.vstack((a, sparse.csr_matrix(cost[None,:])), format='csr')
    second_rhs = np.r_[rhs, first.fun+TIE_TOL]
    secondary = np.r_[np.zeros(k-4), np.ones(4)]
    second, v2 = solve(secondary, second_a, second_rhs)
    corners = np.clip(second.x[:4], 0, 1)
    pred = b + (phi @ corners)*(c-b)
    error = np.abs((pred-y)*SCALE)
    harm = np.maximum(error-anchor_error, 0)
    actual = float(w @ error + lam*(w @ harm))
    if abs(actual-first.fun) > TIE_TOL+1e-8:
        raise RuntimeError('Actual loss disagrees with LP optimum')
    model = {'schema':'bilinear_half_anchor_harm_v1', 'endpoints':endpoints.tolist(),
             'corners':corners.tolist(), 'penalty':lam,
             'diagnostics': {'rows':n, 'feature_reference_rows':len(reference),
                 'primary_optimum_counts':float(first.fun), 'actual_objective_counts':actual,
                 'mae_counts':float(w @ error), 'positive_excess_counts':float(w @ harm),
                 'anchor_mae_counts':float(w @ anchor_error),
                 'secondary_corner_distance':float(np.abs(corners-.5).sum()),
                 'tie_tolerance_counts':TIE_TOL, 'maximum_constraint_violation':max(v1,v2),
                 'solver_status':[int(first.status),int(second.status)]}}
    _model(model)
    return model
