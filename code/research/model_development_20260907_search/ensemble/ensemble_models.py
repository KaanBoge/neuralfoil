"""Prespecified convex NeuralFoil core mixtures; see PROTOCOL.md."""
from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.optimize import linprog

FAMILIES = ["median8", "simplex8_l1", "simplex8_re_l1", "simplex8_offset_l1"]


def _weights(groups, sources):
    groups, sources = np.asarray(groups, dtype=str), np.asarray(sources, dtype=str)
    _, pair, counts = np.unique(np.column_stack([sources, groups]), axis=0,
                                return_inverse=True, return_counts=True)
    w = np.empty(len(groups), dtype=float)
    for source in np.unique(sources):
        mask = sources == source
        w[mask] = 1 / (counts[pair[mask]] * len(np.unique(groups[mask])))
    return (1 + w / w.mean()) / (2 * len(w))


def _design(family, d, idx, endpoints=None):
    cd = np.asarray(d["all_model_CD"])[idx] * 1e4
    if family == "simplex8_re_l1":
        lr = np.log10(np.asarray(d["Re"])[idx])
        if endpoints is None:
            endpoints = np.quantile(lr, [.1, .9])
        lo, hi = endpoints
        t = np.clip((lr-lo)/max(hi-lo, 1e-12), 0, 1)
        cd = np.column_stack([cd*(1-t[:, None]), cd*t[:, None]])
    elif family == "simplex8_offset_l1":
        cd = np.column_stack([cd, np.ones(len(idx))])
    return cd, endpoints


def fit(family, d, idx):
    if family not in FAMILIES:
        raise ValueError(f"Unknown ensemble family: {family}")
    idx = np.asarray(idx)
    if len(idx) == 0:
        raise ValueError("Training indices cannot be empty")
    if family == "median8":
        return {"family": family}
    x, endpoints = _design(family, d, idx)
    y = np.asarray(d["MEAS_CD"])[idx]*1e4
    w = _weights(np.asarray(d["group"])[idx], np.asarray(d["source"])[idx])
    n, p = x.shape
    offset = family == "simplex8_offset_l1"
    # Decision variables: core weights[, signed offset], n absolute residuals,
    # and an optional absolute-offset auxiliary variable.
    extra = int(offset)
    z = sparse.csr_matrix((n, extra))
    a = sparse.vstack([
        sparse.hstack([sparse.csr_matrix(x), -sparse.eye(n), z]),
        sparse.hstack([-sparse.csr_matrix(x), -sparse.eye(n), z]),
    ], format="csr")
    rhs = np.concatenate([y, -y])
    c = np.concatenate([np.zeros(p), w, [0.1] if offset else []])
    bounds = [(0, 1)]*p + [(0, None)]*n + [(0, None)]*extra
    if offset:
        bounds[8] = (-20., 20.)
        penalty = sparse.lil_matrix((2, p+n+1))
        penalty[0, 8], penalty[0, -1] = 1, -1
        penalty[1, 8], penalty[1, -1] = -1, -1
        a = sparse.vstack([a, penalty.tocsr()], format="csr")
        rhs = np.concatenate([rhs, [0., 0.]])
    blocks = 2 if family == "simplex8_re_l1" else 1
    equality = sparse.lil_matrix((blocks, p+n+extra))
    for j in range(blocks):
        equality[j, j*8:(j+1)*8] = 1
    result = linprog(c, A_ub=a, b_ub=rhs, A_eq=equality.tocsr(),
                     b_eq=np.ones(blocks), bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(f"{family} linear program failed: {result.message}")
    coef = result.x[:p].copy()
    for j in range(blocks):
        weights = coef[j*8:(j+1)*8]
        assert np.min(weights) >= -1e-8 and abs(weights.sum()-1) < 1e-8
    return {"family": family, "coef": coef, "endpoints": endpoints,
            "objective_drag_counts": float(result.fun), "iterations": int(result.nit)}


def predict(model, d, idx):
    idx = np.asarray(idx)
    if model["family"] == "median8":
        raw = np.median(np.asarray(d["all_model_CD"])[idx], axis=1)
    else:
        x, _ = _design(model["family"], d, idx, model["endpoints"])
        raw = x @ model["coef"] / 1e4
    base = np.asarray(d["BASE_CD"])[idx]
    return np.clip(raw, .5*base, 2*base)
