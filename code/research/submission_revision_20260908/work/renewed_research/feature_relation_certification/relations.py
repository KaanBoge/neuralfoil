"""Pure, source-derived interval contraction; no I/O or scientific data access.

This defines a RESTRICTED domain, not the original Cartesian feature domain.
Binary64 numeric equality is intended; the signs of numeric zero are irrelevant
to the finite threshold predicates. No rounded arithmetic is used in updates.
"""
import math

DIMENSIONS = 62
MAX_PASSES = 16
RELEVANT = (0, 12, 13, 16, 18, 19)


def relation_guard(values):
    """Check all-finite builtin-float inputs and the three numeric relations."""
    if not isinstance(values, (list, tuple)) or len(values) != DIMENSIONS:
        return False
    if any(type(x) is not float or not math.isfinite(x) for x in values):
        return False
    return (values[16] == abs(values[0])
            and values[18] == min(values[12], values[13])
            and values[19] == max(values[12], values[13]))


def _validated_box(box):
    if not isinstance(box, (list, tuple)) or len(box) != DIMENSIONS:
        raise ValueError("a 62-dimensional interval box is required")
    result = []
    for interval in box:
        if not isinstance(interval, (list, tuple)) or len(interval) != 2:
            raise ValueError("each interval needs two endpoints")
        lo, hi = interval
        if any(type(x) is not float or not math.isfinite(x) for x in (lo, hi)):
            raise ValueError("finite builtin binary64 float endpoints required")
        if lo > hi:
            raise ValueError("input interval is already reversed")
        result.append([lo, hi])
    return result


class _Contradiction(Exception):
    pass


def contract(box, passes=MAX_PASSES):
    """Return a subset containing EVERY relation-feasible point, or None.

    None means a necessary interval condition was contradictory. Reaching the
    iteration cap merely returns the current conservative box. This is not a
    complete feasibility solver, smallest-box algorithm or fixed-point claim.
    Caller inputs are never changed. ``passes=0`` is an identity diagnostic.
    """
    if type(passes) is not int or not 0 <= passes <= MAX_PASSES:
        raise ValueError("passes must be an integer between zero and sixteen")
    b = _validated_box(box)

    def lo(i):
        return b[i][0]

    def hi(i):
        return b[i][1]

    def meet(i, lower, upper):
        lower, upper = max(lo(i), lower), min(hi(i), upper)
        if lower > upper:
            raise _Contradiction()
        b[i] = [lower, upper]

    try:
        for _ in range(passes):
            previous = tuple(tuple(x) for x in b)
            # r=abs(a). A straddling interval retains both signs; no union is
            # approximated by selecting only its positive or negative branch.
            minimum_abs = lo(0) if lo(0) >= 0. else (-hi(0) if hi(0) <= 0. else 0.)
            meet(16, minimum_abs, max(abs(lo(0)), abs(hi(0))))
            meet(0, -hi(16), hi(16))
            if lo(0) >= 0.:
                meet(0, lo(16), hi(16))
            elif hi(0) <= 0.:
                meet(0, -hi(16), -lo(16))

            # c=min(a,b). The strict comparison is essential: equality does
            # not force the other operand to attain the minimum.
            meet(18, min(lo(12), lo(13)), min(hi(12), hi(13)))
            meet(12, lo(18), hi(12))
            meet(13, lo(18), hi(13))
            if lo(12) > hi(18):
                meet(13, lo(13), hi(18))
            if lo(13) > hi(18):
                meet(12, lo(12), hi(18))

            # d=max(a,b), with the symmetric strict implication.
            meet(19, max(lo(12), lo(13)), max(hi(12), hi(13)))
            meet(12, lo(12), hi(19))
            meet(13, lo(13), hi(19))
            if hi(12) < lo(19):
                meet(13, lo(19), hi(13))
            if hi(13) < lo(19):
                meet(12, lo(19), hi(12))
            # min(a,b) <= max(a,b).
            meet(18, lo(18), hi(19))
            meet(19, lo(18), hi(19))
            if tuple(tuple(x) for x in b) == previous:
                break
    except _Contradiction:
        return None
    return tuple(tuple(x) for x in b)
