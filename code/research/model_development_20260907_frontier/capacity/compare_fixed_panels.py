"""Descriptive fixed-family comparison on the unchanged 23-panel definitions."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd
import run_capacity as run

ROOT = Path(__file__).resolve().parent
FEAS = run.PROJECT / "model_development_20260907_positive/feasibility"
sys.path.insert(0, str(FEAS))
import solve_feasibility as feasibility


def main():
    paths = sorted(run.OUT.glob("predictions_*.csv"))
    frames = [pd.read_csv(path) for path in paths]
    for name in ["SG_exposed", "W_new_challenge"]:
        path = ROOT / "exposed_results" / f"{name}_predictions.csv"
        frame = pd.read_csv(path)
        frame["split"] = name
        frames.append(frame)
        paths.append(path)
    d = pd.concat(frames, ignore_index=True)
    external = d.split.isin(["SG_exposed", "W_new_challenge"])
    eligible = d[~external | d.eligible.fillna(False)].reset_index(drop=True)
    results = {}
    for population, frame, output in [("all_complete", d, "fixed_23panel_metrics.csv"),
                                       ("eligible_external", eligible, "fixed_eligible_23panel_metrics.csv")]:
        panels = feasibility.panels(frame)
        tables = []
        for family in run.models.FAMILIES:
            for strength in [.5, 1.]:
                label = f"{family}__{strength:g}"
                tables.append(feasibility.metrics(frame, frame[label].to_numpy(), panels, label))
        table = pd.concat(tables, ignore_index=True)
        destination = ROOT / output
        if destination.exists():
            existing = pd.read_csv(destination)
            pd.testing.assert_frame_equal(existing, table.reset_index(drop=True), check_exact=False, atol=1e-12, rtol=1e-12)
        else:
            table.to_csv(destination, index=False)
        minima = table.groupby("candidate")[["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]].min()
        results[population] = {"panels": {key: len(value) for key, value in panels.items()},
                               "minima_percent": minima.to_dict("index"), "csv_sha256": run.sha(destination)}
    sources = paths + [Path(__file__), Path(feasibility.__file__), run.OUT / "freeze.json"]
    run.dump(ROOT / "fixed_panel_comparison.json", {"status": "Post-run descriptive comparison; family choice adaptive, no external fitting",
        "source_hashes": {str(path): run.sha(path) for path in sources}, "results": results})
    print(json.dumps(results["eligible_external"]["minima_percent"]), flush=True)


if __name__ == "__main__":
    main()
