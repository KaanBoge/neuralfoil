"""Arithmetic, archive coverage, selection and fallback checks."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import run_kernel as run

ROOT = Path(__file__).resolve().parent


def main():
    results = json.loads((run.OUT / "results.json").read_text())
    assert not results["failures"] and len(results["folds"]) == 15
    checks = []
    for log in results["folds"]:
        name = log["split"]
        frame = pd.read_csv(run.OUT / f"predictions_{name}.csv")
        old = pd.read_csv(run.C3 / "results" / f"predictions_{name}.csv")
        np.testing.assert_array_equal(frame.nf2_row_id, old.nf2_row_id)
        for control in run.CONTROLS:
            np.testing.assert_allclose(frame[control], old[control], rtol=0, atol=1e-15)
        np.testing.assert_array_equal(frame.both_minimax_selector, frame[log["selected"]])
        for family in run.models.FAMILIES:
            full, half = frame[family + "__1"].to_numpy(), frame[family + "__0.5"].to_numpy()
            np.testing.assert_allclose(half, frame.mean8_CD + .5 * (full - frame.mean8_CD), rtol=0, atol=2e-16)
            assert np.all(full >= .5 * frame.mean8_CD - 1e-15) and np.all(full <= 2 * frame.mean8_CD + 1e-15)
        scores = log["selection"]["candidate_scores"]
        minimum = min(row["worst_ratio"] for row in scores)
        winners = [row for row in scores if abs(row["worst_ratio"] - minimum) <= 1e-12]
        pooled = min(row["pooled_tiebreak"] for row in winners)
        allowed = [row["candidate"] for row in winners if abs(row["pooled_tiebreak"] - pooled) <= 1e-12]
        assert log["selected"] in allowed
        checks.append({"split": name, "rows": len(frame), "selected": log["selected"], "control_parity": True, "selector_consistent": True})
    frames = pd.concat([pd.read_csv(path) for path in run.OUT.glob("predictions_*.csv")], ignore_index=True)
    table = pd.read_csv(run.OUT / "metric_summary.csv")
    max_metric_error = 0.
    for row in table.itertuples(index=False):
        f = frames[frames.split.str.startswith(row.evaluation)]
        assert f.nf2_row_id.nunique() == len(f)
        if row.evaluation.startswith("group_"):
            assert len(f) == 8371
        error = np.abs(f[row.candidate] - f.measured_CD)
        baseline = np.abs(f[row.baseline] - f.measured_CD)
        improvement = 100 * (1 - error.sum() / baseline.sum())
        difference = abs(improvement - row.relative_reduction_percent)
        max_metric_error = max(max_metric_error, difference)
        assert difference < 1e-10
        assert abs(error.mean() * 1e4 - row.candidate_mae_counts) < 1e-10
    selected = results["selected"]
    external = []
    for name in ["SG_exposed", "W_new_challenge"]:
        f = pd.read_csv(ROOT / "exposed_results" / f"{name}_predictions.csv")
        gate = f.inference_gate.to_numpy(dtype=bool)
        for label in [f"{family}__{strength:g}" for family in run.models.FAMILIES for strength in [.5, 1.]] + ["both_minimax_selector"]:
            np.testing.assert_allclose(f.loc[~gate, label], f.loc[~gate, "mean8_CD"], rtol=0, atol=1e-15)
        np.testing.assert_allclose(f.both_minimax_selector, np.where(gate, f[selected], f.mean8_CD), rtol=0, atol=1e-15)
        external.append({"cohort": name, "rows": len(f), "eligible_rows": int(f.eligible.sum()), "fallback_rows": int((~gate).sum())})
    for path, expected in results["manifest"]["hashes"].items():
        assert run.sha(path) == expected, path
    run.dump(ROOT / "validation.json", {"status": "passed", "outer_checks": checks, "external_checks": external,
        "metric_rows_independently_recomputed": len(table), "max_improvement_percentage_point_difference": max_metric_error,
        "all_input_hashes_unchanged": True, "no_refit_in_verification": True})
    print(json.dumps({"passed": True, "outer_splits": len(checks), "metric_rows": len(table), "max_metric_difference": max_metric_error}), flush=True)


if __name__ == "__main__":
    main()

