"""Artificial feature-level policy example; NOT a fitted aerodynamic model.

Requires only NumPy and the preserved predictor source. No measurements, trained
weights, reference archives, geometry, network calls or accuracy claims.
Run from the checkout: python -B examples/synthetic_policy.py
"""
import importlib.util
from pathlib import Path

import numpy as np


def load_predictor():
    path = (Path(__file__).resolve().parents[1] / 'code/research/'
            'model_development_20260907_risk_policy/portable/predictor.py')
    spec = importlib.util.spec_from_file_location('public_synthetic_predictor', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artificial_artifact():
    """Construct explicit constants, not exported or learned model parameters."""
    tree = {'leaf': [True], 'feature': [0], 'left': [0], 'right': [0],
            'threshold': [0.0], 'value': [0.0]}
    policies = {
        label: {'schema': 'bilinear_half_anchor_harm_v1',
                'endpoints': [[0.0, 0.0], [1.0, 1.0]],
                'corners': [0.5, 0.5, 0.5, 0.5], 'penalty': 0.0}
        for label in ('risk_transfer', 'unpenalized_transfer', 'risk_group')
    }
    return {'schema': 'experimental-risk-policy-package-v1',
            'status': 'artificial_constants_not_trained_no_accuracy_claim',
            'core': {'schema': 'neuralfoil-feature-correction-v1',
                     'engine': 'relative_hist', 'feature_key': 'X62',
                     'strength': 1.0,
                     'hist': {'features': 62, 'baseline': 0.5, 'trees': [tree]}},
            'policies': policies}


def artificial_inputs():
    base = np.array([0.01, 0.02], dtype=np.float64)
    return (np.zeros((2, 62), dtype=np.float64), base,
            np.repeat(base[:, None], 8, axis=1), np.array([True, False]))


def main():
    module = load_predictor()
    x, base, sizes, gate = artificial_inputs()
    cd, strength = module.predict(artificial_artifact(), x, base, sizes, gate,
                                  label='unpenalized_transfer')
    print('SYNTHETIC constants only; no trained model or accuracy evaluation.')
    print('CD:', cd.tolist())
    print('Applied strength:', strength.tolist())
    print('False-gate row returns the supplied baseline exactly:', bool(cd[1] == base[1]))


if __name__ == '__main__':
    main()
