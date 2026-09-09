"""The existing benchmark eligibility rule, not a learned safety classifier.

This helper does not certify physical validity or reduced prediction error.
It uses supplied physical inputs, never experimental labels or airfoil names.
"""
import numpy as np


def legacy_benchmark_gate(alpha_deg, reynolds, thickness_ratio, mean8_cd):
    """Return the frozen input-only mask for aligned finite numeric vectors.

    Bounds: 0 < Re <= 600000, |alpha_deg| <= 12,
    0.05 <= thickness_ratio <= 0.20, and mean8_cd > 0.

    Pass the ORIGINAL Reynolds input. Reconstructing Re from log10(Re) can
    change boundary inclusion through floating-point roundoff. A false mask
    permits baseline fallback only when the predictor's separate input checks
    also pass; it cannot make a nonpositive baseline or invalid features valid.
    """
    values = []
    for name, value in [("alpha_deg", alpha_deg), ("reynolds", reynolds),
                        ("thickness_ratio", thickness_ratio), ("mean8_cd", mean8_cd)]:
        arr = np.asarray(value)
        if arr.ndim != 1 or arr.dtype.kind not in "fiu" or not np.isfinite(arr).all():
            raise ValueError(name + " must be a finite numeric vector")
        values.append(arr.astype(float, copy=False))
    if len({v.shape for v in values}) != 1:
        raise ValueError("All four physical-input vectors must have the same shape")
    alpha, re, thickness, base = values
    return ((re > 0) & (re <= 600000.) & (np.abs(alpha) <= 12.) &
            (thickness >= .05) & (thickness <= .20) & (base > 0))
