"""Independent read-only artifact audit; writes results only beside this script."""
from pathlib import Path
import copy
import hashlib
import json
import pickle
import subprocess
import sys
import unittest
import numpy as np
import pandas as pd
from scipy.interpolate import BSpline

ROOT = Path(__file__).resolve().parent
DEPLOY = ROOT.parent / "deployment"
PROJECT = ROOT.parents[1]
C3 = PROJECT / "model_development_20260907_search"
C4 = PROJECT / "model_development_20260907_transition"
sys.path[:0] = [str(DEPLOY), str(C3 / "smooth"), str(C3 / "ensemble"), str(C4), str(PROJECT / "model_development_20260906_v2")]
import predictor
import smooth_models
import ensemble_models
import transition_models
import shape_inputs

CHECKS = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DeploymentAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads((DEPLOY / "retrospective_blend.json").read_text())
        manifest = json.loads((DEPLOY / "manifest.json").read_text())
        assert sha(DEPLOY / "retrospective_blend.json") == manifest["artifact_sha256"]
        assert sha(DEPLOY / "predictor.py") == manifest["predictor_sha256"]
        with np.load(DEPLOY / "inference_references.npz", allow_pickle=False) as refs:
            cls.refs = {key: refs[key].copy() for key in refs.files}
        m3 = json.loads((C3 / "exposed_results/fit_manifest.json").read_text())
        m4 = json.loads((C4 / "results/freeze.json").read_text())
        cls.models = {}
        for family, path, record in [("smooth9_relative", C3 / "exposed_results/fit_smooth9_relative.pkl", m3),
                                     ("simplex8_re_l1", C3 / "exposed_results/fit_simplex8_re_l1.pkl", m3),
                                     ("joint62_mixed", C4 / "results/fit_joint62_mixed.pkl", m4)]:
            assert sha(path) == record["artifacts"][family]["sha256"] == cls.artifact["source_pickle_sha256"][str(path)]
            with path.open("rb") as f:
                cls.models[family] = pickle.load(f)

    def features(self, cohort):
        return {key: self.refs[f"{cohort}_{key}"].copy() for key in ["BASE_CD", "X9", "X62", "all_model_CD", "Re"]}

    def test_all_row_parity_against_independent_native_components(self):
        rows = []
        for cohort in ["historical", "SG_exposed", "W_new_challenge"]:
            d = shape_inputs.load_historical() if cohort == "historical" else shape_inputs.load_exposed(cohort)
            ids = np.arange(len(d["BASE_CD"]))
            gate = self.refs[f"{cohort}_gate"]
            components = {"smooth9_relative__1": smooth_models.predict(self.models["smooth9_relative"], d, ids),
                          "simplex8_re_l1__1": ensemble_models.predict(self.models["simplex8_re_l1"], d, ids),
                          "joint62_mixed__1": transition_models.predict(self.models["joint62_mixed"], d, ids)}
            expected = np.where(gate, sum(self.artifact["weights"][key] * values for key, values in components.items()), d["BASE_CD"])
            actual, parts = predictor.predict(self.artifact, self.features(cohort), gate, return_components=True)
            errors = {key: float(np.max(np.abs(parts[key] - np.where(gate, values, d["BASE_CD"])))) for key, values in components.items()}
            np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-12)
            np.testing.assert_allclose(actual, self.refs[f"{cohort}_expected_CD"], rtol=0, atol=1e-12)
            for key in components:
                self.assertLess(errors[key], 1e-12)
            np.testing.assert_array_equal(actual[~gate], d["BASE_CD"][~gate])
            rows.append({"cohort": cohort, "rows": len(actual), "blend_max_abs_CD_difference": float(np.max(np.abs(actual - expected))),
                         "component_max_abs_CD_difference": errors, "fallback_rows": int((~gate).sum())})
        CHECKS["allrow_native_parity"] = rows

    def test_spline_knots_nextafter_extrapolation_and_empty(self):
        errors = []
        for spec in self.artifact["smooth"]["splines"]:
            t, k = np.asarray(spec["t"]), spec["k"]
            x = np.r_[t, np.nextafter(t, -np.inf), np.nextafter(t, np.inf), -1e100, 1e100,
                      np.linspace(t[k], t[-k - 1], 301)]
            independent = BSpline(t, np.asarray(spec["c"]), k)(np.clip(x, t[k], t[-k - 1]))[:, :-1]
            portable = predictor._spline(spec, x)
            np.testing.assert_allclose(portable, independent, rtol=0, atol=2e-14)
            errors.append(float(np.max(np.abs(portable - independent))))
            self.assertEqual(predictor._spline(spec, np.array([])).shape, (0, len(spec["c"][0]) - 1))
        CHECKS["spline_boundary_max_basis_error"] = max(errors)

    def test_empty_and_input_rejection(self):
        original = self.features("SG_exposed")
        empty = {key: value[:0] for key, value in original.items()}
        self.assertEqual(predictor.predict(self.artifact, empty, np.zeros(0, dtype=bool)).shape, (0,))
        valid_gate = self.refs["SG_exposed_gate"]
        tests = []
        for key in original:
            changed = {k: v.copy() for k, v in original.items()}
            changed[key].flat[0] = np.nan
            tests.append((f"{key}_NaN", changed, valid_gate))
            changed2 = {k: v.copy() for k, v in original.items()}
            changed2[key] = changed2[key][:-1]
            tests.append((f"{key}_wrong_rows", changed2, valid_gate))
        for key in ["BASE_CD", "Re", "all_model_CD"]:
            changed = {k: v.copy() for k, v in original.items()}
            changed[key].flat[0] = 0.
            tests.append((f"{key}_zero", changed, valid_gate))
        tests += [("integer_gate", original, valid_gate.astype(int)), ("wrong_gate_shape", original, valid_gate[:-1])]
        for name, features, gate in tests:
            with self.subTest(name=name), self.assertRaises(ValueError):
                predictor.predict(self.artifact, features, gate)
        CHECKS["malformed_input_rejections"] = [name for name, _, _ in tests]
        CHECKS["empty_batch"] = "returns empty float vector"

    def test_irrelevant_metadata_and_full_false_gate(self):
        features = self.features("SG_exposed")
        gate = self.refs["SG_exposed_gate"]
        expected = predictor.predict(self.artifact, features, gate)
        altered = {**features, "MEAS_CD": np.full(len(gate), np.nan), "measured_CD": "ignore",
                   "airfoil": "changed_design", "source": "changed_source", "group": "changed_group",
                   "configuration": "changed_configuration", "name": "changed_name"}
        np.testing.assert_array_equal(predictor.predict(self.artifact, altered, gate), expected)
        np.testing.assert_array_equal(predictor.predict(self.artifact, features, np.zeros(len(gate), dtype=bool)), features["BASE_CD"])
        CHECKS["metadata_invariance_and_false_gate"] = "exact"

    def test_fresh_numpy_only_import(self):
        command = "import sys; sys.path.insert(0, " + repr(str(DEPLOY)) + "); import predictor; assert 'scipy' not in sys.modules and 'sklearn' not in sys.modules"
        subprocess.run([sys.executable, "-c", command], check=True, capture_output=True)
        CHECKS["fresh_numpy_only_import"] = "passed"


def additional_eligible_metrics():
    path = ROOT.parent / "transfer_checks/all_held_predictions.csv"
    d = pd.read_csv(path)
    if d.eligible.dtype != bool or d.inference_gate.dtype != bool:
        raise ValueError("Expected boolean eligibility and inference gate in preserved transfer rows")
    np.testing.assert_array_equal(d.eligible.to_numpy(), d.inference_gate.to_numpy() & (d.measured_CD.to_numpy() > 0))
    tables = []
    conditions = [(name, d.holdout == name) for name in sorted(d.holdout.unique())]
    conditions += [("single_design_crossfit", ~d.holdout.str.contains("pair")), ("pair_crossfit", d.holdout.str.contains("pair"))]
    candidates = ["withheld_calibration_blend", "full_retrospective_both", "full_retrospective_xlarge"]
    for name, selected in conditions:
        for population in ["all_complete", "eligible_only"]:
            frame = d[selected & (d.eligible if population == "eligible_only" else True)]
            panels = [("pooled", np.ones(len(frame), dtype=bool))]
            panels += [(f"design_{foil}", (frame.airfoil == foil).to_numpy()) for foil in sorted(frame.airfoil.unique())]
            panels += [(f"configuration_{config}", (frame.configuration == config).to_numpy()) for config in sorted(frame.configuration.unique())]
            for label, mask in panels:
                f = frame[mask]
                for candidate in candidates:
                    e = np.abs(f[candidate].to_numpy() - f.measured_CD.to_numpy())
                    row = {"holdout": name, "population": population, "panel": label, "candidate": candidate, "rows": len(f),
                           "mae_drag_counts": float(e.mean() * 1e4), "median_drag_counts": float(np.median(e) * 1e4),
                           "p90_drag_counts": float(np.quantile(e, .9) * 1e4)}
                    for base in ["xlarge_CD", "mean8_CD"]:
                        b = np.abs(f[base].to_numpy() - f.measured_CD.to_numpy())
                        row[base + "_improvement_percent"] = float(100 * (1 - e.sum() / b.sum()))
                    tables.append(row)
    result = pd.DataFrame(tables)
    result.to_csv(ROOT / "transfer_population_metrics.csv", index=False)
    pooled = result[(result.panel == "pooled") & (result.candidate == "withheld_calibration_blend")]
    CHECKS["transfer_populations"] = pooled.to_dict("records")
    return path


def main():
    assert not (ROOT / "results.json").exists(), "Preserve completed independent audit"
    paths = list(DEPLOY.glob("*.py")) + [DEPLOY / "retrospective_blend.json", DEPLOY / "manifest.json", DEPLOY / "inference_references.npz", DEPLOY / "README.md"]
    hashes = {str(p): sha(p) for p in paths}
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentAudit)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    transfer_path = additional_eligible_metrics()
    hashes[str(transfer_path)] = sha(transfer_path)
    # Characterize a malformed-artifact edge without changing the trusted artifact.
    artifact = json.loads((DEPLOY / "retrospective_blend.json").read_text())
    broken = copy.deepcopy(artifact)
    broken["weights"][next(iter(broken["weights"]))] = float("nan")
    with np.load(DEPLOY / "inference_references.npz", allow_pickle=False) as refs:
        features = {key: refs[f"SG_exposed_{key}"] for key in ["BASE_CD", "X9", "X62", "all_model_CD", "Re"]}
        try:
            predictor.predict(broken, features, np.zeros(len(features["BASE_CD"]), dtype=bool))
            CHECKS["nonfinite_artifact_weights_all_false_gate"] = "accepted; nonblocking trusted-artifact validation gap"
        except ValueError:
            CHECKS["nonfinite_artifact_weights_all_false_gate"] = "rejected"
    for path, expected in hashes.items():
        assert sha(path) == expected, path
    result = {"tests_run": outcome.testsRun, "test_failures": len(outcome.failures), "test_errors": len(outcome.errors),
              "checks": CHECKS, "input_hashes_unchanged": hashes, "source_sha256": sha(__file__),
              "status": "Independent engineering audit and additional eligible sensitivity; no refit and no deployment changes"}
    (ROOT / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    print(json.dumps(CHECKS["transfer_populations"]), flush=True)


if __name__ == "__main__":
    main()
