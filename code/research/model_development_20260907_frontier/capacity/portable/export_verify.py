"""Export a clearly postselected half-strength historical-only robustness model."""
from pathlib import Path
import hashlib
import json
import pickle
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CAPACITY = HERE.parent
PROJECT = CAPACITY.parents[1]
LIB = PROJECT / "model_development_20260907_search/portable"
sys.path[:0] = [str(CAPACITY), str(LIB)]
import run_capacity as run
import portable_models as portable


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not (HERE / "manifest.json").exists(), "Preserve completed export"
    freeze_path = CAPACITY / "results/freeze.json"
    freeze = json.loads(freeze_path.read_text())
    run_manifest = json.loads((CAPACITY / "results/run_manifest.json").read_text())
    for path, expected in run_manifest["hashes"].items():
        assert sha(path) == expected, path
    family = "hist62_regularized"
    model_path = CAPACITY / "results" / f"fit_{family}.pkl"
    expected_sha = freeze["artifacts"][family]["sha256"]
    assert sha(model_path) == expected_sha
    with model_path.open("rb") as handle:
        model = pickle.load(handle)
    artifact = portable.export_model(family, model, strength=.5, source_sha256=expected_sha)
    artifact["status"] = "postselected_robustness_alternative_not_independent_validation_not_deployed"
    artifact["selection_warning"] = "All settings were declared before fitting, but this alternative was highlighted after exposed benchmark evaluation; original historical-only minimax selected gate_shrink__1."
    artifact["training"] = "Historical rows only; no external meta-weight fitting"
    metric_path = CAPACITY / "results/metric_summary.csv"
    metric_frame = pd.read_csv(metric_path)
    history = metric_frame[(metric_frame.candidate == "hist62_regularized__0.5") &
                           (metric_frame.baseline == "xlarge_CD") & metric_frame.evaluation.str.startswith("group_")]
    history = history.sort_values("evaluation")
    assert len(history) == 2
    artifact["historical_tradeoff_vs_xlarge_percent"] = {"this_half_strength": history.relative_reduction_percent.tolist(),
        "preceding_historical_primary_global_stack_rounded": [18.65, 18.24]}
    destination = HERE / "hist62_regularized_half.json"
    destination.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")
    loaded = json.loads(destination.read_text())
    checks, refs = [], {}
    paths = [Path(__file__), Path(portable.__file__), model_path, freeze_path, CAPACITY / "results/run_manifest.json",
             destination, CAPACITY / "fixed_panel_comparison.json", metric_path]
    for cohort in ["historical", "SG_exposed", "W_new_challenge"]:
        d = run.inputs.load_historical() if cohort == "historical" else run.inputs.load_exposed(cohort)
        n = len(d["BASE_CD"])
        if cohort == "historical":
            gate, frame = np.ones(n, dtype=bool), None
        else:
            path = CAPACITY / "exposed_results" / f"{cohort}_predictions.csv"
            paths.append(path)
            frame = pd.read_csv(path, usecols=["inference_gate", "hist62_regularized__0.5"])
            gate = frame.inference_gate.to_numpy(dtype=bool)
        minimal = {"X62": d["X62"], "BASE_CD": d["BASE_CD"]}
        full = run.models.predict(model, d, np.arange(n))
        expected = d["BASE_CD"] + .5 * (full - d["BASE_CD"])
        actual = portable.predict(loaded, minimal)
        gated = portable.predict(loaded, minimal, inference_gate=gate)
        max_error = float(np.max(np.abs(actual - expected)))
        assert max_error < 1e-12
        np.testing.assert_allclose(gated, np.where(gate, expected, d["BASE_CD"]), rtol=0, atol=1e-12)
        np.testing.assert_array_equal(gated[~gate], d["BASE_CD"][~gate])
        np.testing.assert_array_equal(portable.predict(loaded, minimal, inference_gate=np.zeros(n, dtype=bool)), d["BASE_CD"])
        np.testing.assert_array_equal(actual, portable.predict(loaded, {**minimal, "MEAS_CD": np.full(n, np.nan), "source": "ignored", "airfoil": "ignored"}))
        csv_error = None
        if frame is not None:
            csv_error = float(np.max(np.abs(gated - frame["hist62_regularized__0.5"].to_numpy())))
            assert csv_error < 1e-12
        for key, value in minimal.items():
            refs[f"{cohort}_{key}"] = value
        refs[f"{cohort}_gate"] = gate
        refs[f"{cohort}_expected_raw"] = expected
        refs[f"{cohort}_expected_gated"] = np.where(gate, expected, d["BASE_CD"])
        checks.append({"cohort": cohort, "rows": n, "native_max_abs_CD_error": max_error,
                       "exposed_csv_max_abs_CD_error": csv_error, "fallback_rows": int((~gate).sum()),
                       "labels_irrelevant": True, "fallback_exact": True})
    np.savez_compressed(HERE / "inference_references.npz", **refs)
    paths.append(HERE / "inference_references.npz")
    run.dump(HERE / "manifest.json", {"status": artifact["status"], "checks": checks,
                                      "hashes": {str(path): sha(path) for path in paths}, "no_deployment_changes": True})
    print(json.dumps(checks), flush=True)


if __name__ == "__main__":
    main()
