"""Feature-array JSON inference using NumPy only; no sklearn or pickle imports.

export_model accepts already loaded, trusted local fitted objects. The runtime
predict function uses only JSON fields, numerical features, and baseline CD.
This is an experimental feature contract, not a coordinate-to-aerodynamics API.
"""
from __future__ import annotations
import numpy as np

F16 = ["alpha", "lre", "t2", "tx2", "c2", "cx2", "leR", "teA", "lcd8", "cl8", "lsp", "conf", "topxtr", "botxtr", "dsize", "cm8"]
F24 = F16 + ["abs_alpha", "cl8_squared", "min_xtr", "max_xtr", "xtr_difference", "relative_drag_spread", "median_relative_drag", "lift_std_sizes"]
K18 = [f"upper_weights_{i}" for i in range(8)] + [f"lower_weights_{i}" for i in range(8)] + ["leading_edge_weight", "TE_thickness"]
F44 = F24 + [f"ncrit_{n}_{feature}" for n in [5, 7, 11, 13] for feature in ["ln_CD_ratio_to_9", "CL_minus_9", "confidence_minus_9", "Top_Xtr_minus_9", "Bot_Xtr_minus_9"]]
FEATURES = {"X24": F24, "X44": F44, "X42": F24 + K18, "X62": F44 + K18,
            "ncrit_CD": [f"xlarge_CD_ncrit_{n}" for n in [5, 7, 9, 11, 13]]}


def export_hist(model):
    """Extract numerical histogram trees; each node value already has learning rate."""
    if not hasattr(model, "_predictors") or model._baseline_prediction.size != 1:
        raise ValueError("A fitted single-output HistGradientBoostingRegressor is required")
    trees = []
    for iteration in model._predictors:
        if len(iteration) != 1:
            raise ValueError("Only one tree per boosting iteration is supported")
        nodes = iteration[0].nodes
        if nodes["is_categorical"].any():
            raise ValueError("Categorical splits are outside this feature contract")
        if not np.isfinite(nodes["value"]).all() or not np.isfinite(nodes["num_threshold"]).all():
            raise ValueError("Finite exported thresholds and values required")
        trees.append({"feature": nodes["feature_idx"].tolist(), "threshold": nodes["num_threshold"].tolist(),
                      "left": nodes["left"].tolist(), "right": nodes["right"].tolist(),
                      "leaf": nodes["is_leaf"].astype(bool).tolist(), "value": nodes["value"].tolist()})
    return {"features": int(model.n_features_in_), "baseline": float(model._baseline_prediction[0, 0]),
            "tree_values_include_learning_rate": True, "trees": trees}


def export_model(family, model, strength=1.0, source_sha256=None):
    """Create a JSON-safe artifact from a trusted loaded model; performs no I/O."""
    if not np.isfinite(strength) or not 0 <= strength <= 1:
        raise ValueError("Correction strength must lie in [0,1]")
    artifact = {"schema": "neuralfoil-feature-correction-v1", "family": family, "strength": float(strength),
                "status": "experimental_not_deployed", "source_pickle_sha256": source_sha256,
                "input_dtype": "float64", "finite_inputs_required": True,
                "reference_versions": {"neuralfoil": "0.3.3", "aerosandbox": "4.2.10", "sklearn_training": "1.7.1"},
                "feature_generation": "Original historical coordinate normalization and decimal quantization; see associated input manifests.",
                "domain_policy": "Caller may supply full-row inference_gate; false rows return mean8 exactly. Without this mask no domain validation is performed.",
                "geometry_interface": False, "external_status": "SG/W already exposed; parity is engineering verification, not independent scientific validation"}
    if family in ["identity", "xlarge_fixed"]:
        artifact.update(engine=family, feature_contract={"BASE_CD": "positive mean-eight CD"})
        if family == "xlarge_fixed":
            artifact["feature_contract"]["XLARGE_CD"] = "positive xlarge CD"
        return artifact
    if family == "gate_shrink":
        if model["family"] != family:
            raise ValueError("Family mismatch")
        artifact.update(engine="gate_shrink", feature_key="X24", base_hist=export_hist(model["base_model"]),
                        gate_hist=export_hist(model["gate"]))
        assert artifact["base_hist"]["features"] == 24 and artifact["gate_hist"]["features"] == 26
        artifact["gate_feature_contract"] = F24 + ["relative_bounded_base_correction", "absolute_bounded_base_correction_drag_counts"]
    elif family == "transition_simplex":
        coef = np.asarray(model["coef"], dtype=float)
        if coef.shape != (5,) or not np.isfinite(coef).all() or coef.min() < -1e-8 or abs(coef.sum() - 1) > 1e-8:
            raise ValueError("A five-coefficient convex transition mixture is required")
        artifact.update(engine="simplex", feature_key="ncrit_CD", coefficients=coef.tolist())
    else:
        if isinstance(model, dict):
            key, estimator = model["feature_key"], model["model"]
        else:
            key, estimator = "X24", model
        if key not in FEATURES or key == "ncrit_CD":
            raise ValueError(f"Unsupported histogram feature contract: {key}")
        artifact.update(engine="relative_hist", feature_key=key, hist=export_hist(estimator))
        assert artifact["hist"]["features"] == len(FEATURES[key])
    artifact["feature_contract"] = {"BASE_CD": "positive mean-eight CD", artifact["feature_key"]: FEATURES[artifact["feature_key"]]}
    artifact["correction_bounds"] = [0.5, 2.0]
    artifact["strength_semantics"] = "Linear CD blend after full-strength bounds, before optional domain fallback"
    return artifact


def _raw_hist(hist, x):
    if x.ndim != 2 or x.shape[1] != hist["features"] or not np.isfinite(x).all():
        raise ValueError("Histogram features must be finite and match declared shape")
    raw = np.full(len(x), hist["baseline"], dtype=np.float64)
    for tree in hist["trees"]:
        feature = np.asarray(tree["feature"], dtype=np.int64)
        threshold = np.asarray(tree["threshold"], dtype=np.float64)
        left, right = np.asarray(tree["left"], dtype=np.int64), np.asarray(tree["right"], dtype=np.int64)
        leaf, values = np.asarray(tree["leaf"], dtype=bool), np.asarray(tree["value"], dtype=np.float64)
        nodes = np.zeros(len(x), dtype=np.int64)
        for _ in range(len(leaf)):
            active = np.flatnonzero(~leaf[nodes])
            if not len(active):
                break
            current = nodes[active]
            go_left = x[active, feature[current]] <= threshold[current]
            nodes[active] = np.where(go_left, left[current], right[current])
        else:
            raise ValueError("Malformed tree does not terminate")
        raw += values[nodes]
    return raw


def _relative(raw, base):
    return base * (1 + np.clip(raw, -0.5, 1.0))


def predict(artifact, d, idx=None, inference_gate=None):
    """Return CD from feature arrays. Optional gate is a full-row boolean mask.

    Labels, group/source identity and raw coordinates are neither needed nor read.
    A supplied mask only applies fallback; physical/domain eligibility must be
    established by the caller using the original experiment's definition.
    """
    if artifact.get("schema") != "neuralfoil-feature-correction-v1":
        raise ValueError("Unsupported artifact schema")
    whole_base = np.asarray(d["BASE_CD"], dtype=np.float64)
    if whole_base.ndim != 1:
        raise ValueError("BASE_CD must be one-dimensional")
    idx = np.arange(len(whole_base)) if idx is None else np.asarray(idx)
    base = whole_base[idx]
    if not np.isfinite(base).all() or not np.all(base > 0):
        raise ValueError("Finite positive mean8 CD is required")
    engine = artifact["engine"]
    if engine == "identity":
        pred = base.copy()
    elif engine == "xlarge_fixed":
        pred = np.asarray(d["XLARGE_CD"], dtype=np.float64)[idx]
    else:
        x = np.asarray(d[artifact["feature_key"]], dtype=np.float64)[idx]
        if x.shape != (len(base), len(artifact["feature_contract"][artifact["feature_key"]])) or not np.isfinite(x).all():
            raise ValueError("Finite inputs of declared feature shape are required")
        if engine == "relative_hist":
            pred = _relative(_raw_hist(artifact["hist"], x), base)
        elif engine == "simplex":
            pred = x @ np.asarray(artifact["coefficients"], dtype=np.float64)
        elif engine == "gate_shrink":
            corrected = _relative(_raw_hist(artifact["base_hist"], x), base)
            gate_x = np.column_stack([x, (corrected - base) / base, np.abs(corrected - base) * 1e4])
            amount = np.clip(_raw_hist(artifact["gate_hist"], gate_x), 0, 1)
            pred = base + amount * (corrected - base)
        else:
            raise ValueError(f"Unsupported artifact engine: {engine}")
        pred = np.clip(pred, .5 * base, 2 * base)
    pred = base + artifact["strength"] * (pred - base)
    if inference_gate is not None:
        mask = np.asarray(inference_gate)
        if mask.dtype != np.dtype(bool) or mask.shape != whole_base.shape:
            raise ValueError("inference_gate must be a full-row boolean mask")
        pred = np.where(mask[idx], pred, base)
    if pred.shape != base.shape or not np.isfinite(pred).all() or not np.all(pred > 0):
        raise ValueError("Finite positive output required")
    return pred
