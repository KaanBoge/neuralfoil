"""Six predeclared external-design meta-calibration holdouts; see PROTOCOL.md."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import sys
import time
import traceback
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
FEAS = ROOT.parent / "feasibility"
sys.path.insert(0, str(FEAS))
import solve_feasibility as feasibility
import portable_blend

FOLDS = [("hold_sg6050", ["sg6050"]), ("hold_sg6051", ["sg6051"]),
         ("hold_w1011", ["w1011"]), ("hold_w1015", ["w1015"]),
         ("hold_SG_pair", ["sg6050", "sg6051"]), ("hold_W_pair", ["w1011", "w1015"])]
BASELINES = ["xlarge_CD", "mean8_CD"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def partition(d, panel_map, held_designs):
    external = d.split.isin(["SG_exposed", "W_new_challenge"]).to_numpy()
    held = external & d.airfoil.isin(held_designs).to_numpy()
    assert held.any()
    assert set(d.loc[held, "airfoil"]) == set(held_designs)
    train_ids, test_ids = np.flatnonzero(~held), np.flatnonzero(held)
    remap = np.full(len(d), -1, dtype=int)
    remap[train_ids] = np.arange(len(train_ids))
    training_panels = {}
    for label, ix in panel_map.items():
        retained = ix[~held[ix]]
        if label.startswith("history_") or label.startswith("strict_source_"):
            np.testing.assert_array_equal(retained, ix)
        if len(retained):
            training_panels[label] = remap[retained]
            assert (training_panels[label] >= 0).all()
    train = d.iloc[train_ids].copy().reset_index(drop=True)
    assert not train.loc[train.split.isin(["SG_exposed", "W_new_challenge"]), "airfoil"].isin(held_designs).any()
    assert sum(len(x) for label, x in training_panels.items() if label.startswith("history_")) > 0
    return train, training_panels, test_ids


def held_panels(frame):
    result = {"held_pooled": np.arange(len(frame))}
    for design in sorted(frame.airfoil.unique()):
        result[f"design_{design}"] = np.flatnonzero(frame.airfoil == design)
    for configuration in sorted(frame.configuration.dropna().unique()):
        result[f"configuration_{configuration}"] = np.flatnonzero(frame.configuration == configuration)
    return result


def evaluate(task):
    name, held_designs, d, components, panel_map, retrospective = task
    tick = time.monotonic()
    train, training_panels, test_ids = partition(d, panel_map, held_designs)
    # A structural isolation test: held-label changes leave the actual LP dataframe unchanged.
    altered = d.copy()
    altered.loc[test_ids, "measured_CD"] = 1000.
    altered_train, altered_panels, altered_test = partition(altered, panel_map, held_designs)
    pd.testing.assert_frame_equal(train, altered_train, check_exact=True)
    np.testing.assert_array_equal(test_ids, altered_test)
    for key in training_panels:
        np.testing.assert_array_equal(training_panels[key], altered_panels[key])
    _, training_metrics, solution = feasibility.solve(train, components, training_panels, BASELINES)
    solution = dict(solution)
    solution["status"] = "within_run_external_design_withheld_meta_calibration; adaptive_components_not_blind_validation"
    solution["held_designs"] = held_designs
    frame = d.iloc[test_ids].copy().reset_index(drop=True)
    frame["global_input_row_index"] = test_ids
    frame["holdout"] = name
    component_values = {c: frame[c].to_numpy() for c in components}
    frame["withheld_calibration_blend"] = portable_blend.predict(solution, component_values)
    for label, full in retrospective.items():
        frame[f"full_retrospective_{label}"] = portable_blend.predict(full, component_values)
    tables = []
    pmap = held_panels(frame)
    for label in ["withheld_calibration_blend", "full_retrospective_both", "full_retrospective_xlarge"]:
        table = feasibility.metrics(frame, frame[label].to_numpy(), pmap, label)
        table["holdout"] = name
        tables.append(table)
    metrics = pd.concat(tables, ignore_index=True)
    return {"name": name, "solution": solution, "train_rows": len(train), "held_rows": len(frame),
            "training_panels": {k: len(v) for k, v in training_panels.items()},
            "training_external_designs": sorted(train.loc[train.split.isin(["SG_exposed", "W_new_challenge"]), "airfoil"].unique()),
            "historical_panels_unchanged": True, "held_label_mutation_leaves_lp_inputs_identical": True,
            "seconds": time.monotonic() - tick, "training_metrics": training_metrics, "metrics": metrics, "predictions": frame}


def main():
    assert not (ROOT / "started_manifest.json").exists(), "Preserve prior runs/failures"
    d, components, hashes = feasibility.load_inputs()
    panel_map = feasibility.panels(d)
    retrospective = {label: json.loads((FEAS / f"blend_{label}.json").read_text()) for label in ["both", "xlarge"]}
    for path in [Path(__file__), ROOT / "PROTOCOL.md", Path(feasibility.__file__), Path(portable_blend.__file__),
                 FEAS / "PROTOCOL.md", FEAS / "blend_both.json", FEAS / "blend_xlarge.json", FEAS / "report.json"]:
        hashes[str(path)] = digest(path)
    manifest = {"status": "Adaptive external-design transfer sensitivity, not blind confirmation",
                "folds": FOLDS, "baselines": BASELINES, "components": components,
                "input_instances": len(d), "external_rows": int(d.split.isin(["SG_exposed", "W_new_challenge"]).sum()),
                "input_sha256": hashes, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    dump(ROOT / "started_manifest.json", manifest)
    results, tables, frames, failures = [], [], [], []
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(evaluate, (name, designs, d, components, panel_map, retrospective)): name for name, designs in FOLDS}
        for job in as_completed(jobs):
            name = jobs[job]
            try:
                result = job.result()
                frame, metrics, training = result.pop("predictions"), result.pop("metrics"), result.pop("training_metrics")
                frame.to_csv(ROOT / f"predictions_{name}.csv", index=False)
                metrics.to_csv(ROOT / f"metrics_{name}.csv", index=False)
                training.to_csv(ROOT / f"training_metrics_{name}.csv", index=False)
                dump(ROOT / f"weights_{name}.json", result)
                results.append(result)
                tables.append(metrics)
                frames.append(frame)
                pooled = metrics[(metrics.candidate == "withheld_calibration_blend") & (metrics.panel == "held_pooled")].iloc[0]
                print(json.dumps({"finished": name, "calibration_both_margin_percent": 100 * result["solution"]["actual_min_improvement_fraction"],
                                  "held_xlarge_improvement_percent": float(pooled.xlarge_CD_improvement_percent),
                                  "held_mean8_improvement_percent": float(pooled.mean8_CD_improvement_percent),
                                  "seconds": result["seconds"]}), flush=True)
            except Exception:
                failure = {"holdout": name, "traceback": traceback.format_exc()}
                dump(ROOT / f"failure_{name}.json", failure)
                failures.append(failure)
    aggregate_tables = []
    if len(frames) == 6:
        allpred = pd.concat(frames, ignore_index=True)
        allpred.to_csv(ROOT / "all_held_predictions.csv", index=False)
        for name, mask in [("single_design_crossfit", ~allpred.holdout.str.contains("pair")), ("pair_crossfit", allpred.holdout.str.contains("pair"))]:
            subset = allpred[mask].reset_index(drop=True)
            assert len(subset) == 497 and subset.global_input_row_index.nunique() == 497
            for label in ["withheld_calibration_blend", "full_retrospective_both", "full_retrospective_xlarge"]:
                table = feasibility.metrics(subset, subset[label].to_numpy(), held_panels(subset), label)
                table["holdout"] = name
                aggregate_tables.append(table)
        pd.concat(tables + aggregate_tables, ignore_index=True).to_csv(ROOT / "all_metrics.csv", index=False)
    for path, expected in hashes.items():
        assert digest(path) == expected, path
    dump(ROOT / "results.json", {"manifest": manifest, "folds": sorted(results, key=lambda r: r["name"]), "failures": failures,
                                  "aggregate_metrics": pd.concat(aggregate_tables, ignore_index=True).to_dict("records") if aggregate_tables else []})


if __name__ == "__main__":
    main()
