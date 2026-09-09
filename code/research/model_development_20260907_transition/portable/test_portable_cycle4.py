import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "model_development_20260907_search/portable"))
import portable_models as pm


class Cycle4PortableTests(unittest.TestCase):
    def test_all_references_predictor_only_full_half_and_domain(self):
        with np.load(ROOT / "inference_references.npz", allow_pickle=False) as archive:
            for family in ["transition_mixed", "gate_shrink"]:
                original = json.loads((ROOT / f"{family}.json").read_text())
                for cohort in ["historical", "SG_exposed", "W_new_challenge"]:
                    key = original["feature_key"]
                    d = {key: archive[f"{cohort}_{key}"], "BASE_CD": archive[f"{cohort}_BASE_CD"]}
                    gate = archive[f"{cohort}_inference_gate"]
                    for strength in [1., .5]:
                        artifact = dict(original, strength=strength)
                        np.testing.assert_allclose(pm.predict(artifact, d), archive[f"{cohort}_{family}_{strength:g}_raw"], rtol=0, atol=1e-12)
                        p = pm.predict(artifact, d, inference_gate=gate)
                        np.testing.assert_allclose(p, archive[f"{cohort}_{family}_{strength:g}_gated"], rtol=0, atol=1e-12)
                        np.testing.assert_array_equal(p[~gate], d["BASE_CD"][~gate])
                        changed = {**d, "MEAS_CD": np.full(len(gate), np.nan), "group": "irrelevant", "source": "irrelevant"}
                        np.testing.assert_array_equal(p, pm.predict(artifact, changed, inference_gate=gate))

    def test_runtime_does_not_import_sklearn(self):
        self.assertNotIn("sklearn", sys.modules)


if __name__ == "__main__":
    unittest.main()
