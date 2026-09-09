"""Frozen, low-complexity smooth CD correction families; see PROTOCOL.md."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize
from sklearn.preprocessing import SplineTransformer

FAMILIES = ("smooth9_absolute", "smooth9_relative", "smooth16_relative")
DELTA = 0.05
PENALTY = 0.005


@dataclass
class SmoothModel:
    family: str
    key: str
    keep: np.ndarray
    spline: object
    center: np.ndarray
    coefficients: np.ndarray
    optimization: dict


def _weights(groups, sources):
    """Equal source mass and equal group mass within each source."""
    pairs = list(zip(sources.tolist(), groups.tolist()))
    counts, memberships = {}, {}
    for source, group in pairs:
        counts[(source, group)] = counts.get((source, group), 0) + 1
        memberships.setdefault(source, set()).add(group)
    return np.array([1 / (counts[pair] * len(memberships[pair[0]])) for pair in pairs])


def fit(family, d, idx):
    if family not in FAMILIES:
        raise ValueError(f"Unknown smooth family: {family}")
    key = "X16" if family == "smooth16_relative" else "X9"
    x = np.asarray(d[key][idx], dtype=float)
    base = np.asarray(d["BASE_CD"][idx], dtype=float)
    measured = np.asarray(d["MEAS_CD"][idx], dtype=float)
    if not len(x) or not np.isfinite(x).all() or not np.isfinite(measured).all() or not np.all(base > 0):
        raise ValueError("Finite nonempty training rows and positive baseline required")
    keep = np.ptp(x, axis=0) > 1e-12
    spline = None
    if keep.any():
        spline = SplineTransformer(n_knots=4, degree=3, knots="quantile", extrapolation="constant", include_bias=False)
        features = spline.fit_transform(x[:, keep])
    else:
        features = np.empty((len(x), 0))
    center = features.mean(axis=0)
    design = np.column_stack([np.ones(len(x)), features - center])
    weights = _weights(np.asarray(d["group"])[idx], np.asarray(d["source"])[idx])
    relative = family.endswith("relative")
    target = (measured - base) / (base if relative else 0.01)
    if relative:
        weights *= base
    weights /= weights.sum()

    def objective(beta):
        residual = design @ beta - target
        h = np.hypot(1, residual / DELTA)
        value = np.dot(weights, DELTA**2 * (h - 1)) + PENALTY * np.dot(beta[1:], beta[1:]) / 2
        grad = design.T @ (weights * residual / h)
        grad[1:] += PENALTY * beta[1:]
        return float(value), grad

    result = minimize(objective, np.zeros(design.shape[1]), jac=True, method="L-BFGS-B",
                      options={"maxiter": 1000, "gtol": 1e-7, "ftol": 1e-12})
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f"Smooth optimization failed: {result.message}")
    return SmoothModel(family, key, keep, spline, center, result.x,
                       {"iterations": int(result.nit), "objective": float(result.fun),
                        "parameters": len(result.x), "success": bool(result.success)})


def predict(model, d, idx):
    x = np.asarray(d[model.key][idx], dtype=float)
    base = np.asarray(d["BASE_CD"][idx], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(base).all() or not np.all(base > 0):
        raise ValueError("Finite features and positive baseline required")
    features = model.spline.transform(x[:, model.keep]) if model.spline is not None else np.empty((len(x), 0))
    raw = model.coefficients[0] + (features - model.center) @ model.coefficients[1:]
    correction = raw * (base if model.family.endswith("relative") else 0.01)
    return np.clip(base + correction, 0.5 * base, 2 * base)
