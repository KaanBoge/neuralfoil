"""Verbatim AST-equivalent frozen mathematical engine; no loader or scientific main."""
import numpy as np

ATOL_CD = 1e-13


RADIUS_TOL_CD = 1e-12


LD = np.longdouble


def arrays(b, c, y, w):
    result = tuple(np.asarray(a, dtype=LD) for a in (b, c, y, w))
    if any(a.ndim != 1 or a.shape != result[0].shape for a in result):
        raise ValueError("aligned, nonempty 1-D arrays required")
    if not len(result[0]) or not all(np.isfinite(a).all() for a in result):
        raise ValueError("finite, nonempty arrays required")
    if any((a < 0).any() for a in result) or not result[3].sum() > 0:
        raise ValueError("nonnegative predictions, labels, weights required")
    return result


def margin(b, c, target, r):
    return (LD(1) - LD(r)) * np.abs(b-target) - np.abs(c-target)


class RowBox:
    def __init__(self, b, c, y, w, r):
        self.b, self.c, self.y, self.w = arrays(b, c, y, w)
        if not 0 <= r <= 1:
            raise ValueError("r must be a fractional target in [0,1]")
        self.r = r
        self.zero = r == 0 and np.array_equal(self.b, self.c)
        self.observed = float(np.sum(self.w * margin(self.b, self.c, self.y, r)))

    def bounds(self, epsilon):
        if not np.isfinite(epsilon) or epsilon < 0:
            raise ValueError("finite nonnegative radius required")
        if epsilon == 0:
            return self.observed, self.observed
        if self.zero:
            return 0., 0.
        lo, hi = np.maximum(0, self.y-LD(epsilon)), self.y+LD(epsilon)
        # Clipped prediction knots are inside the interval; duplicate endpoints are harmless.
        values = np.stack([margin(self.b, self.c, t, self.r) for t in
                           (lo, hi, np.clip(self.b, lo, hi), np.clip(self.c, lo, hi))])
        return (float(np.sum(self.w * values.min(axis=0))),
                float(np.sum(self.w * values.max(axis=0))))

    def minimum_baseline_mae(self, epsilon):
        lo, hi = np.maximum(0, self.y-LD(epsilon)), self.y+LD(epsilon)
        return float(np.sum(self.w * np.maximum(np.maximum(lo-self.b, self.b-hi), 0)))


class ShiftCurve:
    """One shared shift block; preserve its original mass, not normalized block mass."""
    def __init__(self, b, c, y, w, r):
        self.b, self.c, self.y, self.w = arrays(b, c, y, w)
        if not 0 <= r <= 1:
            raise ValueError("r must be in [0,1]")
        self.r = r
        self.zero = r == 0 and np.array_equal(self.b, self.c)
        knots = np.concatenate([-self.y, self.b-self.y, self.c-self.y])
        changes = np.concatenate([LD(r)*self.w, 2*(1-LD(r))*self.w, -2*self.w])
        order = np.argsort(knots, kind="stable")
        sorted_knots, sorted_changes = knots[order], changes[order]
        starts = np.r_[0, np.flatnonzero(np.diff(sorted_knots) != 0)+1]
        self.knots = sorted_knots[starts]
        changes = np.add.reduceat(sorted_changes, starts)
        self.slopes = np.cumsum(changes)
        left = np.sum(self.w * ((1-LD(r))*self.b-self.c))
        self.values = left + np.r_[LD(0), np.cumsum(self.slopes[:-1]*np.diff(self.knots))]

    def direct(self, delta):
        if self.zero:
            return LD(0)
        return np.sum(self.w * margin(self.b, self.c, np.maximum(0, self.y+LD(delta)), self.r))

    def evaluate(self, delta):
        ix = np.searchsorted(self.knots, delta, side="right")-1
        if ix < 0:
            return self.values[0]
        return self.values[ix] + self.slopes[ix]*(LD(delta)-self.knots[ix])

    def bounds(self, epsilon):
        if self.zero:
            return LD(0), LD(0)
        if epsilon == 0:
            v = self.direct(0)
            return v, v
        low = np.searchsorted(self.knots, -LD(epsilon), side="left")
        high = np.searchsorted(self.knots, LD(epsilon), side="right")
        locations = np.r_[-LD(epsilon), self.knots[low:high], LD(epsilon)]
        values = np.r_[self.evaluate(-LD(epsilon)), self.values[low:high], self.evaluate(LD(epsilon))]
        # Re-evaluate extremizers directly, so slope-integration roundoff does not
        # itself create near-root sign crossings. Long double is a stability aid,
        # not an assertion of exact arithmetic or cross-platform bitwise identity.
        return self.direct(locations[np.argmin(values)]), self.direct(locations[np.argmax(values)])


class SharedShifts:
    def __init__(self, b, c, y, w, r, blocks):
        b, c, y, w = arrays(b, c, y, w)
        blocks = np.asarray(blocks)
        if blocks.shape != b.shape:
            raise ValueError("one block label per row required")
        self.curves = [ShiftCurve(b[blocks == k], c[blocks == k], y[blocks == k],
                                  w[blocks == k], r) for k in np.unique(blocks)]
        self.observed = float(np.sum(w*margin(b, c, y, r)))

    def bounds(self, epsilon):
        if not np.isfinite(epsilon) or epsilon < 0:
            raise ValueError("finite nonnegative radius required")
        if epsilon == 0:
            return self.observed, self.observed
        bounds = np.asarray([c.bounds(epsilon) for c in self.curves], dtype=LD)
        return tuple(float(x) for x in bounds.sum(axis=0))


def first_zero(model, r, limit=1., tolerance=RADIUS_TOL_CD):
    observed = model.bounds(0)[0]
    record = dict(observed_margin_CD=observed, radius_status=None,
                  radius_lower_CD=None, radius_upper_CD=None,
                  lower_endpoint_margin_CD=None, upper_endpoint_margin_CD=None,
                  lipschitz_radius_CD=observed/(2-r) if observed > 0 else None,
                  search_limit_CD=limit, absolute_bracket_tolerance_CD=tolerance)
    if observed <= 0:
        record.update(radius_status="observed_negative" if observed < 0 else "observed_zero",
                      radius_lower_CD=0., radius_upper_CD=0.,
                      lower_endpoint_margin_CD=observed, upper_endpoint_margin_CD=observed)
        return record
    lower, upper = 0., min(1e-4, limit)
    while model.bounds(upper)[0] > 0 and upper < limit:
        lower, upper = upper, min(upper*2, limit)
    upper_margin = model.bounds(upper)[0]
    if upper_margin > 0:
        record.update(radius_status="right_censored", radius_lower_CD=limit,
                      lower_endpoint_margin_CD=upper_margin)
        return record
    while upper-lower > tolerance:
        mid = (lower+upper)/2
        if model.bounds(mid)[0] > 0:
            lower = mid
        else:
            upper = mid
    record.update(radius_status="finite_bracket", radius_lower_CD=lower, radius_upper_CD=upper,
                  lower_endpoint_margin_CD=model.bounds(lower)[0],
                  upper_endpoint_margin_CD=model.bounds(upper)[0])
    assert record["lower_endpoint_margin_CD"] > 0
    assert record["upper_endpoint_margin_CD"] <= 0
    assert upper-lower <= tolerance
    assert upper+ATOL_CD >= record["lipschitz_radius_CD"]
    return record
