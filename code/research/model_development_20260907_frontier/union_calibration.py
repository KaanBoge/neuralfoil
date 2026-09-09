"""Declared 30-component retrospective union and complete-design withholding."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import warnings
import numpy as np
import pandas as pd
from scipy.optimize import OptimizeWarning, linprog as scipy_linprog
import frontier_assessment as assessment

HERE = Path(__file__).resolve().parent
OUT = HERE / "union_calibration"
old = assessment.old


def limited_linprog(*args, **kwargs):
    options = dict(kwargs.pop("options", {}))
    options["threads"] = 1
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=OptimizeWarning, message="Unrecognized options detected")
        return scipy_linprog(*args, **kwargs, options=options)


# Process-local scheduling choice, no changes to old helper files or models.
old.linprog = limited_linprog


def enforce_fallback(frame, pred):
    external = frame.split.isin(["SG_exposed", "W_new_challenge"]).to_numpy()
    gate = frame.inference_gate.map(lambda v: v is True or str(v).lower() == "true" or v == 1).to_numpy(bool)
    return np.where(external & ~gate, frame.mean8_CD.to_numpy(), pred)


def get_data():
    for path in [HERE / "capacity/results/results.json", HERE / "kernel/results/results.json", HERE / "conditional/results/report.json"]:
        assert path.exists(), f"All branch results must be complete: {path}"
    d, originals, labels, hashes = assessment.load_frame(["capacity", "kernel", "conditional"])
    columns = originals + [f"capacity__{family}__1" for family in assessment.CAPACITY]
    columns += ["kernel__kernel24_l1__1", "kernel__kernel62_l1__1"]
    columns += ["conditional__re2", "conditional__alpha2", "conditional__re_alpha4"]
    assert len(columns) == len(set(columns)) == 30
    external = d.split.isin(["SG_exposed", "W_new_challenge"])
    gate = d.inference_gate.map(lambda v: v is True or str(v).lower() == "true" or v == 1).to_numpy(bool)
    inactive = external.to_numpy() & ~gate
    assert inactive.sum() == 25
    aliases = []
    for column in columns:
        alias = "union_component__" + column
        d[alias] = np.where(inactive, d.mean8_CD, d[column])
        aliases.append(alias)
    # Keep original predictions intact. These aliases represent the actual
    # mean8-fallback deployment class, including when xlarge gets positive weight.
    return d, aliases, dict(zip(aliases, columns)), hashes


def subset(d, panel_map, hold_names):
    held = d.split.isin(["SG_exposed", "W_new_challenge"]) & d.airfoil.astype(str).str.lower().isin(hold_names)
    mask = ~held.to_numpy()
    original_indices = np.flatnonzero(mask)
    inverse = np.full(len(d), -1, dtype=int)
    inverse[original_indices] = np.arange(len(original_indices))
    train_panels = {}
    for name, indices in panel_map.items():
        kept = indices[mask[indices]]
        if len(kept):
            train_panels[name] = inverse[kept]
    train = d.loc[mask].reset_index(drop=True)
    assert not train.airfoil.astype(str).str.lower().isin(hold_names).any()
    assert (train.split.str.startswith("group_")).sum() == 2 * 8371
    return train, train_panels, np.flatnonzero(held)


def hold_one(task):
    name, hold_names, d, components, panel_map = task
    train, train_panels, held = subset(d, panel_map, hold_names)
    assert len(held)
    # Structural leakage regression: modifying every held label changes no input
    # to the actual LP training dataframe or its panels.
    changed = d.copy()
    changed.loc[held, "measured_CD"] = np.nan
    again, again_panels, again_held = subset(changed, panel_map, hold_names)
    pd.testing.assert_frame_equal(train, again)
    np.testing.assert_array_equal(held, again_held)
    for key, value in train_panels.items():
        np.testing.assert_array_equal(value, again_panels[key])
    _, fitted_metrics, solution = old.solve(train, components, train_panels, ["xlarge_CD", "mean8_CD"])
    weights = np.array([solution["weights"][c] for c in components])
    test = d.iloc[held].copy().reset_index(drop=True)
    test["withheld_union_blend"] = enforce_fallback(test, test[components].to_numpy() @ weights)
    assert np.isfinite(test.withheld_union_blend).all()
    panels = {"all_rows/pooled": np.arange(len(test))}
    gate = test.inference_gate.map(lambda v: v is True or str(v).lower() == "true" or v == 1).to_numpy(bool)
    panels["eligible_only/pooled"] = np.flatnonzero(gate)
    for configuration in sorted(test.configuration.unique()):
        active = test.configuration == configuration
        panels["all_rows/" + configuration] = np.flatnonzero(active)
        panels["eligible_only/" + configuration] = np.flatnonzero(active & gate)
    metrics = old.metrics(test, test.withheld_union_blend.to_numpy(), panels, name)
    solution.update({"holdout": name, "held_designs": hold_names, "held_rows": len(test),
                     "held_eligible_rows": int(gate.sum()), "held_label_mutation_isolated": True,
                     "status": "adaptive_complete_design_meta_calibration_withholding_not_blind_validation"})
    test.to_csv(OUT / f"predictions_{name}.csv", index=False)
    metrics.to_csv(OUT / f"metrics_{name}.csv", index=False)
    fitted_metrics.to_csv(OUT / f"calibration_metrics_{name}.csv", index=False)
    (OUT / f"weights_{name}.json").write_text(json.dumps(solution, indent=2) + "\n")
    return name, metrics[metrics.panel.str.endswith("/pooled")].to_dict("records")


def main():
    OUT.mkdir(exist_ok=False)
    d, components, aliases, hashes = get_data()
    panels = old.panels(d)
    records = {}
    tables = []
    initial = {"status": "RETROSPECTIVE_EXPOSED_OUTCOME_UNION_CALIBRATION_NOT_VALIDATION",
               "components": components, "component_aliases": aliases, "rows_with_repeated_contexts": len(d),
               "input_sha256": hashes, "source_sha256": assessment.sha(Path(__file__)),
               "protocol_sha256": assessment.sha(HERE / "UNION_PROTOCOL.md"),
               "assessment_helper_sha256": assessment.sha(HERE / "frontier_assessment.py"),
               "feasibility_helper_sha256": assessment.sha(Path(old.__file__)),
               "inference_gate_false_rows": 25, "solutions": records}
    (OUT / "started_manifest.json").write_text(json.dumps(initial, indent=2) + "\n")
    for objective, baselines in [("both", ["xlarge_CD", "mean8_CD"]), ("xlarge", ["xlarge_CD"])]:
        pred, table, solution = old.solve(d, components, panels, baselines)
        pred = enforce_fallback(d, pred)
        table = old.metrics(d, pred, panels, "union_blend_" + objective)
        solution["actual_min_improvement_fraction"] = min(float(table[b + "_improvement_percent"].min()) / 100 for b in baselines)
        d["union_blend_" + objective] = pred
        tables.append(table)
        records[objective] = solution
        (OUT / f"blend_{objective}.json").write_text(json.dumps(solution, indent=2) + "\n")
        print(json.dumps({"objective": objective, "margin_percent": solution["actual_min_improvement_fraction"] * 100,
                          "nonzero_weights": {aliases[k]: v for k, v in solution["weights"].items() if v > 1e-12}}), flush=True)
    pd.concat(tables, ignore_index=True).to_csv(OUT / "panel_metrics.csv", index=False)
    e_panels = {k: v for k, v in assessment.reconcile.external_panels(d).items() if k.startswith("eligible_only/")}
    pd.concat([old.metrics(d, d["union_blend_" + obj].to_numpy(), e_panels, "union_blend_" + obj) for obj in records]).to_csv(OUT / "eligible_external_metrics.csv", index=False)
    d.to_csv(OUT / "all_row_predictions.csv", index=False)
    (OUT / "calibration_report.json").write_text(json.dumps(initial, indent=2) + "\n")
    holds = [("hold_sg6050", ["sg6050"]), ("hold_sg6051", ["sg6051"]),
             ("hold_w1011", ["w1011"]), ("hold_w1015", ["w1015"]),
             ("hold_SG_pair", ["sg6050", "sg6051"]), ("hold_W_pair", ["w1011", "w1015"])]
    completed = []
    hold_input = d.drop(columns=["union_blend_both", "union_blend_xlarge"])
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(hold_one, (name, designs, hold_input, components, panels)) for name, designs in holds]):
            result = future.result()
            completed.append(result)
            print(json.dumps({"holdout_complete": result}), flush=True)
    for filename, expected in hashes.items():
        assert assessment.sha(filename) == expected
    (OUT / "complete_report.json").write_text(json.dumps({**initial, "withholding": completed}, indent=2) + "\n")


if __name__ == "__main__":
    main()
