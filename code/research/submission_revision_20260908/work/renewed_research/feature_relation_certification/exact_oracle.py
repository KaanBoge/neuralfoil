"""Exact box feasibility for three relations; pure binary64 endpoint logic.

See EXACT_ORACLE_PLAN.md for the necessary-and-sufficient case proof.
This restricted domain is not the original unrestricted feature product.
"""
import math
import sys

DIMENSIONS = 62


def _box(box):
    if not isinstance(box, (list, tuple)) or len(box) != DIMENSIONS:
        raise ValueError("a 62-dimensional interval box is required")
    result = []
    for item in box:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError("each interval needs two endpoints")
        lo, hi = item
        if any(type(x) is not float or not math.isfinite(x) for x in item):
            raise ValueError("finite builtin binary64 endpoints required")
        if lo > hi:
            raise ValueError("reversed input interval")
        result.append((lo, hi))
    return tuple(result)


def _intersection(first, second):
    lo, hi = max(first[0], second[0]), min(first[1], second[1])
    return None if lo > hi else (lo, hi)


def _absolute_witness(alpha, absolute):
    nonnegative = _intersection(absolute, (0.0, sys.float_info.max))
    if nonnegative is None:
        return None
    lo, hi = nonnegative
    for branch in ((lo, hi), (-hi, -lo)):
        overlap = _intersection(alpha, branch)
        if overlap is not None:
            value = overlap[0]
            return value, abs(value)
    return None


def _ordered_witness(smaller, larger, minimum, maximum):
    low = _intersection(smaller, minimum)
    high = _intersection(larger, maximum)
    if low is None or high is None or low[0] > high[1]:
        return None
    return low[0], max(high[0], low[0])


def feasible_witness(box):
    """Return a feasible 62-tuple, or None iff this valid box is infeasible.

    Coordinates 16,18,19 equal abs(0), min(12,13), max(12,13).
    Numeric signed-zero equality is intended. Invalid inputs raise ValueError;
    there is no search budget, rounding tolerance or unknown result category.
    """
    box = _box(box)
    absolute = _absolute_witness(box[0], box[16])
    if absolute is None:
        return None
    order = _ordered_witness(box[12], box[13], box[18], box[19])
    if order is not None:
        top, bottom = order
    else:
        reverse = _ordered_witness(box[13], box[12], box[18], box[19])
        if reverse is None:
            return None
        bottom, top = reverse
    point = [interval[0] for interval in box]
    point[0], point[16] = absolute
    point[12], point[13] = top, bottom
    point[18], point[19] = min(top, bottom), max(top, bottom)
    return tuple(point)


def feasible(box):
    """Exact Boolean feasibility; malformed boxes still raise ValueError."""
    return feasible_witness(box) is not None
