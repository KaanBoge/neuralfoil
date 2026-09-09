"""Experimental whole-group split calibration and baseline projection.

Pure NumPy inference; no data access or model fitting on import. The caller
must supply scores from a predictor that never trained on calibration groups.
Coverage requires exchangeability of complete finite group bundles. It is not
a guarantee of selected-case coverage or universal accuracy improvement.
"""
import math
from fractions import Fraction

import numpy as np

SCHEMA = "whole_group_interval_projection_v1"


def _vector(value, name, positive=False):
    raw = np.asarray(value)
    if raw.dtype.kind not in "fiu" or raw.ndim != 1:
        raise ValueError(name + " must be a numeric vector")
    out = raw.astype(float)
    if not np.isfinite(out).all() or (positive and np.any(out <= 0)):
        raise ValueError(name + " must be finite" + (" and positive" if positive else ""))
    return out


def _alpha(value):
    if isinstance(value, (bool, str)) or not np.isscalar(value):
        raise ValueError("alpha must be a numeric scalar in (0,1)")
    value = float(value)
    if not math.isfinite(value) or not 0 < value < 1:
        raise ValueError("alpha must be in (0,1)")
    return value


def rank(m, alpha):
    """Exact decimal-alpha rank, avoiding floating-ceil boundary surprises."""
    a = _alpha(alpha)
    if isinstance(m, bool) or not isinstance(m, (int, np.integer)) or m < 0:
        raise ValueError("m must be a nonnegative integer")
    return math.ceil((int(m) + 1) * (1 - Fraction(str(a))))


def calibrate(core, mean8, y, groups, alpha=.10):
    """Compute unweighted maxima per calibration identity and a kth statistic.

    No automatic removal of extremes or repeated within-group observations.
    Empty calibration sets are rejected; small sets yield an unbounded model.
    Group strings are required so missing/ambiguous IDs cannot silently pool.
    """
    c = _vector(core, "core", True)
    b = _vector(mean8, "mean8", True)
    target = _vector(y, "y")
    g = np.asarray(groups)
    if b.shape != c.shape or target.shape != c.shape or not len(c):
        raise ValueError("Nonempty aligned calibration vectors required")
    if g.shape != c.shape or g.dtype.kind not in "US" or np.any(g == ""):
        raise ValueError("groups must be nonempty string IDs aligned to observations")
    alpha = _alpha(alpha)
    ids, inverse = np.unique(g.astype(str), return_inverse=True)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        try:
            score = np.abs(target - c) / b
        except FloatingPointError as exc:
            raise ValueError("Nonfinite calibration residual") from exc
    if not np.isfinite(score).all():
        raise ValueError("Nonfinite calibration score")
    maxima = np.zeros(len(ids))
    np.maximum.at(maxima, inverse, score)
    k = rank(len(ids), alpha)
    q = None if k > len(ids) else float(np.sort(maxima)[k - 1])
    return {"schema": SCHEMA, "alpha": alpha, "calibration_groups": len(ids),
            "calibration_rows": len(c), "rank": k, "q": q,
            "unbounded": q is None, "score": "group_max_abs_residual_over_mean8",
            "group_ids": ids.tolist(), "group_scores": maxima.tolist()}


def _model(model):
    if not isinstance(model, dict) or model.get("schema") != SCHEMA:
        raise ValueError("Unknown calibration schema")
    alpha = _alpha(model.get("alpha"))
    m = model.get("calibration_groups")
    k = rank(m, alpha)
    if m < 1 or model.get("rank") != k or type(model.get("unbounded")) is not bool:
        raise ValueError("Invalid calibration count/rank/flag")
    q = model.get("q")
    if k > m:
        if q is not None or model["unbounded"] is not True:
            raise ValueError("Insufficient group count requires unbounded interval")
        return None
    if isinstance(q, (bool, str)) or not np.isscalar(q) or q is None:
        raise ValueError("Finite nonnegative q required")
    q = float(q)
    if not math.isfinite(q) or q < 0 or model["unbounded"]:
        raise ValueError("Invalid finite q")
    return q


def project(model, core, mean8, baseline, gate):
    """Return baseline projected into a calibrated interval, plus diagnostics.

    Non-applicable rows have unbounded intervals and exact supplied-baseline
    fallback, even if that supplied baseline is not mean-eight. Infinite-q
    rows are applicable inside the gate but uninformative, not invalid.
    """
    q = _model(model)
    c = _vector(core, "core", True)
    b = _vector(mean8, "mean8", True)
    a = _vector(baseline, "baseline", True)
    g = np.asarray(gate)
    if c.shape != b.shape or c.shape != a.shape or g.shape != c.shape or g.dtype != bool:
        raise ValueError("Aligned vectors and a strictly boolean gate required")
    lower, upper = np.full(len(c), -np.inf), np.full(len(c), np.inf)
    prediction = a.copy()
    if q is not None and g.any():
        with np.errstate(over="raise", invalid="raise"):
            try:
                width = q * b[g]
                lower[g], upper[g] = c[g] - width, c[g] + width
            except FloatingPointError as exc:
                raise ValueError("Finite interval arithmetic overflow") from exc
        prediction[g] = np.clip(a[g], lower[g], upper[g])
    if not np.isfinite(prediction).all() or np.any(prediction <= 0):
        raise ValueError("Invalid projected prediction")
    return {"prediction": prediction, "lower": lower, "upper": upper,
            "intervened": prediction != a, "applicable": g.copy()}
