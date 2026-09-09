"""Four predeclared capacity alternatives; no I/O on import."""
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor

FAMILIES = ["hist62_moderate", "hist62_regularized", "extra62_mixed", "extra24_mixed"]


def balanced_weights(groups, sources):
    counts, members = {}, {}
    pairs = list(zip(sources.tolist(), groups.tolist()))
    for source, group in pairs:
        counts[source, group] = counts.get((source, group), 0) + 1
        members.setdefault(source, set()).add(group)
    w = np.array([1 / (counts[pair] * len(members[pair[0]])) for pair in pairs])
    return w / w.mean()


def fit(family, d, idx):
    if family not in FAMILIES:
        raise ValueError(family)
    key = "X24" if family == "extra24_mixed" else "X62"
    x = np.asarray(d[key][idx], dtype=float)
    base, y = d["BASE_CD"][idx], d["MEAS_CD"][idx]
    if not len(x) or not np.isfinite(x).all() or not np.isfinite(y).all() or not np.all(base > 0):
        raise ValueError("Finite nonempty training inputs required")
    w = (1 + balanced_weights(d["group"][idx], d["source"][idx])) / 2
    w *= base
    w /= w.mean()
    target = np.clip((y - base) / base, -.5, 1.)
    if family.startswith("hist"):
        moderate = family.endswith("moderate")
        model = HistGradientBoostingRegressor(loss="absolute_error", max_iter=400,
            max_leaf_nodes=31 if moderate else 15, min_samples_leaf=40 if moderate else 120,
            learning_rate=.035, l2_regularization=2 if moderate else 5,
            early_stopping=False, categorical_features=None, random_state=824)
    else:
        model = ExtraTreesRegressor(n_estimators=256, criterion="squared_error", min_samples_leaf=20,
            max_features=.7, random_state=824, n_jobs=1, bootstrap=False, max_depth=None, min_samples_split=2)
    model.fit(x, target, sample_weight=w)
    return {"family": family, "feature_key": key, "model": model}


def predict(model, d, idx):
    x = np.asarray(d[model["feature_key"]][idx], dtype=float)
    base = d["BASE_CD"][idx]
    if not np.isfinite(x).all() or not np.isfinite(base).all() or not np.all(base > 0):
        raise ValueError("Finite numerical predictors and positive mean8 required")
    raw = model["model"].predict(x)
    return np.clip(base * (1 + np.clip(raw, -.5, 1.)), .5 * base, 2 * base)
