"""Stage-0 design: exact rational arithmetic and synthetic-use primitives.

No I/O, fitting, calibration dataset loading, or call into frozen study helpers.
Binary64 round-to-nearest/ties-to-even is an explicit execution assumption.
"""
from fractions import Fraction as F
import math
import numpy as np

U = F(1, 2**53)
CORE_ERROR = 4*U + 2*U*U
GENERIC_BOUND = F(1, 2) + F(3, 2)*U
DOMAIN_MIN, DOMAIN_MAX = 2.**-500, 2.**500
TAU, BETA = F(1, 100), F(1, 20)


def rat(x):
    x = float(x)
    if not math.isfinite(x):
        raise ValueError('finite binary64 required')
    return F.from_float(x)


def directed(x, upward):
    """Enclose a rational by the adjacent binary64 in the chosen direction."""
    x = F(x)
    try:
        f = float(x)
    except OverflowError as exc:
        raise ValueError('nonfinite enclosure') from exc
    if not math.isfinite(f):
        raise ValueError('nonfinite enclosure')
    if (upward and rat(f) < x) or (not upward and rat(f) > x):
        f = math.nextafter(f, math.inf if upward else -math.inf)
    if not math.isfinite(f) or (upward and rat(f) < x) or (not upward and rat(f) > x):
        raise ValueError('invalid directed enclosure')
    return f


def clipq(q):
    return min(F(1), max(F(-1, 2), F(q)))


def structural_bound(lower, upper):
    lower, upper = F(lower), F(upper)
    if lower > upper:
        raise ValueError('reversed range')
    ql, qu = clipq(lower), clipq(upper)
    return max(abs(clipq(ql-CORE_ERROR)), abs(clipq(qu+CORE_ERROR)))/2 + F(3, 2)*U


def sequential_range(initial, stages):
    """Outward enclosure of sequential binary64 initial += one leaf/stage."""
    lo = hi = rat(initial)
    real_lo = real_hi = lo
    count = 0
    for leaves in stages:
        vals = [rat(v) for v in leaves]
        if not vals:
            raise ValueError('empty leaf set')
        mn, mx = min(vals), max(vals)
        real_lo += mn
        real_hi += mx
        lo = rat(directed(lo+mn, False))
        hi = rat(directed(hi+mx, True))
        count += 1
    return {'lower': lo, 'upper': hi, 'real_lower': real_lo,
            'real_upper': real_hi, 'stages': count}


def guarded_core(base, raw, physical_gate):
    """New numerical guard; legacy physical gate and old code are unchanged."""
    b, r, g = np.asarray(base, float), np.asarray(raw, float), np.asarray(physical_gate)
    if b.ndim != 1 or r.shape != b.shape or g.shape != b.shape or g.dtype != bool:
        raise ValueError('aligned vectors and boolean gate required')
    if not np.isfinite(b).all() or (b <= 0).any() or not np.isfinite(r).all():
        raise ValueError('positive finite baseline and finite raw prediction required')
    active = g & (b >= DOMAIN_MIN) & (b <= DOMAIN_MAX)
    c, h = b.copy(), b.copy()
    bb = b[active]
    # Separate operations, no fused multiply-add. Unselected b values never enter arithmetic.
    q = np.clip(r[active], -.5, 1.)
    c[active] = np.clip(bb*(1.+q), .5*bb, 2.*bb)
    h[active] = bb + .5*(c[active]-bb)
    return c, h, active


def exact_endpoint_loss(base, core, anchor, target):
    """True real loss of supplied machine predictions, not rounded cancellation."""
    b, c, h, y = map(rat, (base, core, anchor, target))
    if b <= 0:
        raise ValueError('positive baseline required')
    return max(abs(c-y)-abs(h-y), F(0))/b


def exact_group_means(losses, identities, bound):
    """Synthetic-use Stage0 primitive; does not read any real role/outcome arrays."""
    losses, identities, bound = list(losses), list(identities), F(bound)
    if len(losses) != len(identities) or bound < 0:
        raise ValueError('invalid groups or bound')
    groups = {}
    for loss, identity in zip(losses, identities):
        loss = F(loss)
        if not isinstance(identity, str) or not identity or not 0 <= loss <= bound:
            raise ValueError('invalid identity or bound violation')
        groups.setdefault(identity, []).append(loss)
    return {k: sum(v, F(0))/len(v) for k, v in sorted(groups.items())}


def log_series_enclosure(z, terms=128):
    """log((1+z)/(1-z)); positive series with a rational geometric tail."""
    z = F(z)
    if not 0 < z < 1 or terms != 128:
        raise ValueError('fixed 128-term positive-series domain')
    partial = 2*sum((z**(2*k+1)/F(2*k+1) for k in range(terms)), F(0))
    tail = 2*z**(2*terms+1)/(F(2*terms+1)*(1-z*z))
    return partial, partial+tail


def log20_enclosure():
    a, b = log_series_enclosure(F(1, 9))  # log(5/4)
    c, d = log_series_enclosure(F(1, 3))  # log(2)
    return a+4*c, b+4*d


def sqrt_upper(x):
    """Smallest enclosing multiple of 2^-256, checked using integers."""
    x = F(x)
    if x < 0:
        raise ValueError('negative radicand')
    scale = 2**256
    k = math.isqrt((x.numerator*scale*scale)//x.denominator)
    if F(k*k, scale*scale) < x:
        k += 1
    out = F(k, scale)
    if out*out < x or (k and F((k-1)**2, scale*scale) >= x):
        raise ValueError('sqrt enclosure verification failed')
    return out


def synthetic_confidence(group_means, bound):
    """Design arithmetic only. Stage0 caller must supply synthetic values only."""
    v, bound = [F(x) for x in group_means], F(bound)
    if bound < 0 or any(not 0 <= x <= bound for x in v):
        raise ValueError('bound violation')
    if bound == 0:
        return {'upper': F(0), 't': 1., 'groups': len(v)}
    upper = bound if not v else min(bound, sum(v, F(0))/len(v) +
                                    bound*sqrt_upper(log20_enclosure()[1]/(2*len(v))))
    t = directed(min(F(1), TAU/upper), False)
    if not 0 <= rat(t) <= 1 or rat(t)*upper > TAU:
        raise ValueError('downward strength verification failed')
    return {'upper': upper, 't': t, 'groups': len(v)}


def inward_predict(anchor, core, strength):
    """Round exact affine target inward; verify exact effective fraction ≤ t."""
    h, c, t = rat(anchor), rat(core), rat(strength)
    if not 0 <= t <= 1:
        raise ValueError('strength outside unit interval')
    if c == h:
        return float(h)
    ideal = h+t*(c-h)
    p = directed(ideal, c < h)
    fraction = (rat(p)-h)/(c-h)
    if not 0 <= fraction <= t:
        raise ValueError('inward interpolation invariant failed')
    return p
