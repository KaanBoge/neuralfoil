"""NumPy-only retrospective blend inference. No pickle/sklearn/scipy required."""
import numpy as np
from numbers import Real


def validate_weights(weights):
    expected = {"smooth9_relative__1", "simplex8_re_l1__1", "joint62_mixed__1"}
    if not isinstance(weights, dict) or set(weights) != expected:
        raise ValueError("Expected the declared three-component simplex")
    values = list(weights.values())
    if any(not isinstance(v, Real) or isinstance(v, (bool, np.bool_)) for v in values):
        raise ValueError("Blend weights must be numeric real values")
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all() or (values < 0).any() or abs(values.sum()-1) > 1e-10:
        raise ValueError("Blend weights must be finite, nonnegative and sum to one")


def _spline(spec, values):
    t = np.asarray(spec["t"])
    k = spec["k"]
    x = np.clip(values, t[k], t[-k-1])
    basis = ((x[:, None] >= t[:-1]) & (x[:, None] < t[1:])).astype(float)
    for degree in range(1, k+1):
        count = len(t)-degree-1
        left_den = t[degree:degree+count]-t[:count]
        right_den = t[degree+1:degree+count+1]-t[1:count+1]
        left = np.divide(x[:, None]-t[:count], left_den, out=np.zeros((len(x), count)), where=left_den != 0)
        right = np.divide(t[degree+1:degree+count+1]-x[:, None], right_den, out=np.zeros((len(x), count)), where=right_den != 0)
        basis = left*basis[:, :count]+right*basis[:, 1:count+1]
    return (basis@np.asarray(spec["c"]))[:, :-1]


def _hist(hist, x):
    out = np.full(len(x), hist["baseline"])
    for tree in hist["trees"]:
        f = np.asarray(tree["feature"], dtype=int)
        t = np.asarray(tree["threshold"])
        left, right = np.asarray(tree["left"], dtype=int), np.asarray(tree["right"], dtype=int)
        leaf, value = np.asarray(tree["leaf"], dtype=bool), np.asarray(tree["value"])
        nodes = np.zeros(len(x), dtype=int)
        for _ in range(len(leaf)):
            active = np.flatnonzero(~leaf[nodes])
            if not len(active):
                break
            at = nodes[active]
            nodes[active] = np.where(x[active, f[at]] <= t[at], left[at], right[at])
        else:
            raise ValueError("Malformed nonterminating tree")
        out += value[nodes]
    return out


def predict(artifact, features, inference_gate, return_components=False):
    """Return CD with required boolean gate; false rows return mean-eight exactly.

    Inputs: BASE_CD(n,), X9(n,9), X62(n,62), all_model_CD(n,8), Re(n,).
    Features must follow the preserved original coordinate/quantization contract.
    No target, airfoil name, source, group, or configuration field is accessed.
    """
    if artifact.get("schema") != "retrospective-neuralfoil-blend-v1":
        raise ValueError("Unsupported artifact schema")
    weights = artifact["weights"]
    validate_weights(weights)
    base = np.asarray(features["BASE_CD"], dtype=float)
    gate = np.asarray(inference_gate)
    if base.ndim != 1 or not np.isfinite(base).all() or (base <= 0).any():
        raise ValueError("Finite positive one-dimensional BASE_CD required")
    if gate.dtype != bool or gate.shape != base.shape:
        raise ValueError("inference_gate must be a boolean vector matching BASE_CD")
    n = len(base)
    arrays = {key: np.asarray(features[key], dtype=float) for key in ["X9", "X62", "all_model_CD", "Re"]}
    for key, shape in [("X9", (n,9)), ("X62", (n,62)), ("all_model_CD", (n,8)), ("Re", (n,))]:
        if arrays[key].shape != shape or not np.isfinite(arrays[key]).all():
            raise ValueError(f"Finite {key} with shape {shape} required")
    if (arrays["Re"] <= 0).any() or (arrays["all_model_CD"] <= 0).any():
        raise ValueError("Positive Reynolds numbers and core CD required")
    smooth = artifact["smooth"]
    x = arrays["X9"][:, np.asarray(smooth["keep"], dtype=bool)]
    splines = [_spline(spec, x[:, j]) for j, spec in enumerate(smooth["splines"])]
    design = np.column_stack(splines) if splines else np.empty((n, 0))
    coef = np.asarray(smooth["coefficients"])
    raw = coef[0]+(design-np.asarray(smooth["center"]))@coef[1:]
    smooth_cd = np.clip(base+raw*base, .5*base, 2*base)
    simplex = artifact["simplex"]
    lo, hi = simplex["endpoints"]
    t = np.clip((np.log10(arrays["Re"])-lo)/max(hi-lo, 1e-12), 0, 1)
    core = arrays["all_model_CD"]*1e4
    design = np.column_stack([core*(1-t[:, None]), core*t[:, None]])
    simplex_cd = np.clip(design@np.asarray(simplex["coef"])/1e4, .5*base, 2*base)
    joint_cd = np.clip(base*(1+np.clip(_hist(artifact["joint_hist"], arrays["X62"]), -.5, 1)), .5*base, 2*base)
    components = {"smooth9_relative__1": smooth_cd, "simplex8_re_l1__1": simplex_cd, "joint62_mixed__1": joint_cd}
    result = np.where(gate, sum(weights[k]*v for k,v in components.items()), base)
    if not np.isfinite(result).all() or (result <= 0).any():
        raise ValueError("Output must remain finite and positive")
    if return_components:
        return result, {k: np.where(gate, v, base) for k,v in components.items()}
    return result
