"""Keep all-row deployment diagnostics separate from eligible-only comparisons."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import numpy as np
import pandas as pd
import scipy
import sklearn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "feasibility"))
import solve_feasibility as feasibility


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def external_panels(frame):
    out = {}
    for cohort, field in [("SG_exposed", "airfoil"), ("W_new_challenge", "configuration")]:
        mask = frame.split == cohort
        gate = frame.inference_gate.map(lambda v: v is True or str(v).lower() == "true" or v == 1)
        assert (mask & gate).sum() == {"SG_exposed": 234, "W_new_challenge": 238}[cohort]
        for scope, active in [("all_rows", mask), ("eligible_only", mask & gate)]:
            out[f"{scope}/{cohort}/pooled"] = np.flatnonzero(active)
            for value in sorted(frame.loc[mask, field].unique()):
                out[f"{scope}/{cohort}/{value}"] = np.flatnonzero(active & (frame[field] == value))
    return out


def collect():
    tables = []
    sources = {}
    for directory, candidates in [("feasibility", ["cycle1_fixed__1", "cycle2_fixed__1", "transition_mixed__1",
            "gate_shrink__1", "retrospective_blend_both", "retrospective_blend_xlarge"]),
            ("historical_results", ["primary_both", "secondary_xlarge"])]:
        path = HERE / directory / "all_row_predictions.csv"
        if not path.exists():
            if directory == "historical_results":
                continue
            raise FileNotFoundError(path)
        sources[str(path)] = digest(path)
        frame = pd.read_csv(path, low_memory=False)
        panels = external_panels(frame)
        for candidate in candidates:
            pred = frame[candidate].to_numpy()
            table = feasibility.metrics(frame, pred, panels, candidate)
            table.insert(0, "prediction_origin", directory)
            tables.append(table)
    table = pd.concat(tables, ignore_index=True)
    table["mae_drag_counts"] = table.mae_CD * 1e4
    table.to_csv(HERE / "external_comparisons.csv", index=False)
    # Also reconcile the zero-deletion all-panel calibration claim independently.
    frame = pd.read_csv(HERE / "feasibility/all_row_predictions.csv", low_memory=False)
    calibrated = feasibility.metrics(frame, frame.retrospective_blend_both.to_numpy(), feasibility.panels(frame), "retrospective_blend_both")
    assert len(calibrated) == 23 and len(frame) == 29856
    assert (calibrated[["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]] > 0).all().all()
    eligible = table[(table.candidate == "retrospective_blend_both") & table.panel.str.startswith("eligible_only/")]
    assert len(eligible) == 8
    assert (eligible[["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]] > 0).all().all()
    report = {"source_sha256": sources, "script_sha256": digest(Path(__file__)),
              "all_row_calibration_panels_positive": 23, "eligible_external_calibration_panels_positive": 8,
              "historical_stacking_complete": "historical_results" in set(table.prediction_origin),
              "cohort_sizes": {"historical_unique": 8371, "SG_all": 242, "SG_eligible": 234, "W_all": 255, "W_eligible": 238},
              "warning": "Calibration is not validation. All-row and eligible-only percentages have different denominators."}
    (HERE / "reconciliation.json").write_text(json.dumps(report, indent=2) + "\n")
    return table


def verify_provenance():
    results = HERE / "historical_results"
    if not (results / "report.json").exists():
        return
    manifest = json.loads((results / "manifest.json").read_text())
    assert digest(HERE / "historical_stack.py") == manifest["source_sha256"]
    assert digest(HERE / "PROTOCOL.md") == manifest["protocol_sha256"]
    inputs = {}
    for path in results.glob("weights_*.json"):
        artifact = json.loads(path.read_text())
        for filename, expected in artifact["input_sha256"].items():
            actual = digest(Path(filename))
            assert actual == expected, filename
            inputs[filename] = actual
    assert len(list(results.glob("weights_*.json"))) == 16
    for filename, expected in json.loads((results / "report.json").read_text())["input_sha256"].items():
        actual = digest(Path(filename))
        assert actual == expected, filename
        inputs[filename] = actual
    project = HERE.parent
    extra = [HERE / "feasibility/solve_feasibility.py",
             project / "model_development_20260906_v2/develop_v2.py",
             project / "model_development_20260906/develop_drag.py",
             project / "model_development_20260906/reproduction/dataset_occurrence.npz",
             project / "model_development_20260906/methods_audit/entry_group_map.csv",
             project / "model_development_20260906/methods_audit/ambiguous_nf2_row_ids.csv"]
    audit = {"fitting_source_protocol_and_archive_hashes_still_match": True,
             "runtime_recorded_at_completion": {"python": sys.version, "platform": platform.platform(),
                 "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__},
             "rechecked_input_sha256": inputs,
             "additional_dependencies_recorded_at_completion_not_before_fit": {str(p): digest(p) for p in extra},
             "output_sha256": {str(p): digest(p) for p in results.iterdir() if p.is_file()}}
    (HERE / "completion_provenance.json").write_text(json.dumps(audit, indent=2) + "\n")


if __name__ == "__main__":
    t = collect()
    verify_provenance()
    print(t.loc[(t.candidate.isin(["retrospective_blend_both", "primary_both", "secondary_xlarge"])) &
                t.panel.str.startswith("eligible_only/"),
                ["candidate", "panel", "rows", "mae_drag_counts", "xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]].to_string(index=False))
