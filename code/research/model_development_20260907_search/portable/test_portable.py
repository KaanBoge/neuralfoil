import json
from pathlib import Path
import unittest
import numpy as np
import portable_models as pm


def stump(features, index, threshold, left, right):
    return {"features": features, "baseline": 0., "tree_values_include_learning_rate": True,
            "trees": [{"feature": [index, 0, 0], "threshold": [threshold, 0., 0.],
                       "left": [1, 0, 0], "right": [2, 0, 0], "leaf": [False, True, True], "value": [0., left, right]}]}


class PortableTests(unittest.TestCase):
    def test_dictionary_histogram_contracts(self):
        from sklearn.ensemble import HistGradientBoostingRegressor
        rng = np.random.default_rng(63)
        for key, family in [("X44", "transition_mixed"), ("X42", "geometry42_mixed"), ("X62", "joint62_mixed")]:
            x = rng.normal(size=(60, len(pm.FEATURES[key]))).astype(np.float64)
            model = HistGradientBoostingRegressor(max_iter=3, max_leaf_nodes=3, min_samples_leaf=5,
                                                  early_stopping=False, random_state=4).fit(x, x[:, 0] * .1)
            artifact = json.loads(json.dumps(pm.export_model(family, {"family": family, "model": model, "feature_key": key})))
            base = np.full(len(x), .01)
            expected = base * (1 + np.clip(model.predict(x), -.5, 1))
            np.testing.assert_allclose(pm.predict(artifact, {key: x, "BASE_CD": base}), expected, rtol=0, atol=1e-12)

    def test_threshold_equality_and_no_learning_rate_double_count(self):
        h = stump(1, 0, .3, .1, .2)
        x = np.array([[np.nextafter(.3, -np.inf)], [.3], [np.nextafter(.3, np.inf)]])
        np.testing.assert_array_equal(pm._raw_hist(h, x), [.1, .1, .2])

    def test_gate_features_and_clipped_strength(self):
        x = np.zeros((2, 24))
        x[:, 0] = [-1, 1]
        d = {"BASE_CD": np.array([.01, .02]), "X24": x}
        a = {"schema": "neuralfoil-feature-correction-v1", "engine": "gate_shrink", "feature_key": "X24",
             "feature_contract": {"X24": pm.F24}, "strength": 1., "base_hist": stump(24, 0, 0, .5, -.25),
             "gate_hist": stump(26, 24, 0, -4., 4.)}
        np.testing.assert_allclose(pm.predict(a, d), [.015, .02], rtol=0, atol=1e-16)
        a["gate_hist"] = stump(26, 25, 49.999, -4., .4)
        np.testing.assert_allclose(pm.predict(a, d), [.012, .018], rtol=0, atol=1e-16)
        a["strength"] = .5
        np.testing.assert_allclose(pm.predict(a, d), [.011, .019], rtol=0, atol=1e-16)
        np.testing.assert_array_equal(pm.predict(a, d, inference_gate=np.array([False, False])), d["BASE_CD"])

    def test_simplex_and_subset_domain_mask(self):
        m = {"coef": np.array([0., .25, .5, .25, 0.])}
        artifact = json.loads(json.dumps(pm.export_model("transition_simplex", m)))
        d = {"BASE_CD": np.array([.01, .02, .03]), "ncrit_CD": np.tile([.01, .012, .014, .016, .018], (3, 1))}
        expected = np.clip(d["ncrit_CD"] @ m["coef"], .5 * d["BASE_CD"], 2 * d["BASE_CD"])
        np.testing.assert_allclose(pm.predict(artifact, d), expected, rtol=0, atol=1e-16)
        np.testing.assert_array_equal(pm.predict(artifact, d, idx=np.array([1]), inference_gate=np.array([True, False, True])), [.02])

    def test_reference_cohorts_without_labels(self):
        root = Path(__file__).resolve().parent
        with np.load(root / "inference_references.npz", allow_pickle=False) as refs:
            for family in ["gate_shrink", "cycle2_fixed"]:
                artifact = json.loads((root / f"{family}.json").read_text())
                for name in ["historical", "SG_exposed", "W_new_challenge"]:
                    d = {"X24": refs[f"{name}_X24"], "BASE_CD": refs[f"{name}_BASE_CD"]}
                    np.testing.assert_allclose(pm.predict(artifact, d), refs[f"{name}_{family}_full"], rtol=0, atol=1e-12)
                    np.testing.assert_allclose(pm.predict(artifact, d, inference_gate=refs[f"{name}_inference_gate"]),
                                               refs[f"{name}_{family}_with_domain_fallback"], rtol=0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
