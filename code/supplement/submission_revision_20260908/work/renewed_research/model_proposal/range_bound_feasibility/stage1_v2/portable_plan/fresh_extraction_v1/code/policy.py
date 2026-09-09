from qualified_numerics import *
import qualified_numerics as q
def group_means_exact(losses, identities, bound):
    """Production exact arithmetic; packaged approved study replay."""
    losses, identities, bound = (list(losses), list(identities), F(bound))
    if len(losses) != len(identities) or bound < 0:
        raise ValueError('invalid groups or bound')
    groups = {}
    for loss, identity in zip(losses, identities):
        loss = F(loss)
        if not isinstance(identity, str) or not identity or (not 0 <= loss <= bound):
            raise ValueError('invalid identity or bound violation')
        groups.setdefault(identity, []).append(loss)
    return {k: sum(v, F(0)) / len(v) for k, v in sorted(groups.items())}

def calibrate_exact_groups(group_means, bound):
    """Production exact arithmetic; packaged approved study replay."""
    v, bound = ([F(x) for x in group_means], F(bound))
    if bound < 0 or any((not 0 <= x <= bound for x in v)):
        raise ValueError('bound violation')
    if bound == 0:
        return {'upper': F(0), 't': 1.0, 'groups': len(v)}
    upper = bound if not v else min(bound, sum(v, F(0)) / len(v) + bound * sqrt_upper(log20_enclosure()[1] / (2 * len(v))))
    t = directed(min(F(1), TAU / upper), False)
    if not 0 <= rat(t) <= 1 or rat(t) * upper > TAU:
        raise ValueError('downward strength verification failed')
    return {'upper': upper, 't': t, 'groups': len(v)}
def fit_scalar(base, core, anchor, targets, identities, bound):
    """No fitting of a core. Strictly bounded exact endpoint-loss scalar calibration."""
    n = len(base)
    if any(len(v) != n for v in [core, anchor, targets, identities]):
        raise ValueError('aligned calibration vectors required')
    losses = [q.exact_endpoint_loss(b,c,h,y) for b,c,h,y in zip(base,core,anchor,targets)]
    means = group_means_exact(losses, identities, bound)
    result = calibrate_exact_groups(means.values(), bound)
    result.update(bound=bound, group_means=means, rows=n,
                  exact_mean=sum(means.values(),q.F(0))/len(means) if means else None)
    return result

def predictions(model, base, core, anchor, gate):
    import numpy as np
    t = model['t']
    if not 0 <= q.rat(t) <= 1:
        raise ValueError('invalid strength')
    p = np.array([q.inward_predict(h,c,t) if g else b
                  for b,c,h,g in zip(base,core,anchor,gate)])
    effective = np.array([float((q.rat(v)-q.rat(h))/(q.rat(c)-q.rat(h)))
                          if g and c != h else 0.
                          for v,h,c,g in zip(p,anchor,core,gate)])
    return p, effective
