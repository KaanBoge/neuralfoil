"""Apply retrospective weights to named component predictions without labels.

These calibrated weights use exposed outcomes and are not validated deployment
recommendations. Their application requires the named original component models
and their preserved inference convention; JSON alone does not contain those fits.
"""
import numpy as np


def predict(artifact, component_predictions):
    weights = artifact["weights"]
    if abs(sum(weights.values())-1) > 1e-8 or min(weights.values()) < -1e-10:
        raise ValueError("Expected a nonnegative simplex")
    active = [(name, weight) for name, weight in weights.items() if weight != 0]
    values = [np.asarray(component_predictions[name], dtype=float) for name, _ in active]
    if any(v.shape != values[0].shape or not np.isfinite(v).all() for v in values):
        raise ValueError("Component predictions must be finite with matching shapes")
    return sum(weight*value for (_, weight), value in zip(active, values))
