"""Non-fitting, fixed-metric successor assessment; old artifacts are read-only."""
from pathlib import Path
import hashlib
import importlib.util
import json

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "model_development_20260907_geometry_frontier"
NEW = ["project_mean8", "project_xlarge", "proper_core", "proper_half"]
CANDIDATES = NEW[:2]
CONTROLS = NEW[2:] + ["unpenalized_transfer", "half_strength"]
LABELS = CANDIDATES + CONTROLS
EXTERNAL = ["SG_exposed", "W_new_challenge"]
OUT = HERE / "assessment"
TOL = 1e-12


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def verify(hashes):
    for path, expected in hashes.items():
        assert sha(path) == expected, path


def boolean(series):
    assert series.notna().all()
    assert set(series.astype(str).str.lower().unique()) <= {"true", "false"}
    return series.astype(str).str.lower().eq("true").to_numpy()


def make_panels(frame):
    panels = {}
    for seed in [20260906, 20260908]:
        mask = frame.split.str.startswith(f"group_{seed}_").to_numpy()
        panels[f"history_{seed}_pooled"] = np.flatnonzero(mask)
        assert mask.sum() == 8371 and frame.loc[mask, "nf2_row_id"].nunique() == 8371
        for source in sorted(frame.loc[mask, "source"].unique()):
            panels[f"history_{seed}_{source}"] = np.flatnonzero(mask & frame.source.eq(source).to_numpy())
    for split in sorted(s for s in frame.split.unique() if s.startswith("strict_source_")):
        panels[split] = np.flatnonzero(frame.split.eq(split).to_numpy())
    for split in EXTERNAL:
        mask = frame.split.eq(split).to_numpy()
        panels[f"{split}_pooled"] = np.flatnonzero(mask)
        for config in sorted(frame.loc[mask, "configuration"].unique()):
            panels[f"{split}_{config}"] = np.flatnonzero(mask & frame.configuration.eq(config).to_numpy())
        eligible = mask & frame.interval_applicable.to_numpy(bool)
        panels[f"eligible_only/{split}/pooled"] = np.flatnonzero(eligible)
        for config in sorted(frame.loc[mask, "configuration"].unique()):
            panels[f"eligible_only/{split}/{config}"] = np.flatnonzero(eligible & frame.configuration.eq(config).to_numpy())
    assert len(panels) == 31
    return panels


def load():
    # Completion is required before any external evaluation access here.
    complete = read(HERE / "results/complete.json")
    frozen = read(HERE / "results/freeze.json")
    assert frozen["core_count"] == frozen["calibrator_count"] == 16
    assert complete["core_count"] == complete["calibrator_count"] == 16
    assert frozen["external_outcomes_opened"] is False
    assert complete["freeze_sha256"] == sha(HERE/"results/freeze.json")
    assert len(frozen["artifact_sha256"]) == 80
    assert all(k in frozen for k in ["artifact_sha256", "source_input_sha256"])
    assert all(k in complete for k in ["artifact_sha256", "source_input_sha256", "output_sha256", "external_input_sha256"])
    # Producer records explicit authenticated inputs and all generated evidence.
    hashes = {}
    for record in [frozen, complete]:
        for field in ["source_input_sha256", "artifact_sha256", "output_sha256", "external_input_sha256"]:
            if field not in record:
                continue
            verify(record[field])
            hashes.update(record[field])
    for p in [HERE/"results/complete.json", HERE/"results/freeze.json"]:
        hashes[str(p)] = sha(p)
    witness = read(OLD / "assessment/report.json")
    path = OLD / "assessment/all_row_predictions.csv"
    assert sha(path) == witness["output_sha256"][str(path)]
    hashes[str(path)] = sha(path)
    hashes[str(OLD/"assessment/report.json")] = sha(OLD/"assessment/report.json")
    frame = pd.read_csv(path, low_memory=False)
    for split in frame.split.unique():
        ext = split in EXTERNAL
        p = HERE / ("exposed_results" if ext else "results") / (
            f"{split}_predictions.csv" if ext else f"predictions_{split}.csv")
        assert str(p) in complete["output_sha256"]
        assert sha(p) == complete["output_sha256"][str(p)]
        fresh = pd.read_csv(p, low_memory=False)
        mask = frame.split.eq(split)
        old = frame.loc[mask]
        assert len(fresh) == len(old)
        if not ext:
            assert not fresh.nf2_row_id.duplicated().any()
            assert set(old.nf2_row_id) == set(fresh.nf2_row_id)
            fresh = fresh.set_index("nf2_row_id").loc[old.nf2_row_id].reset_index()
        for field in ["Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD"]:
            np.testing.assert_allclose(old[field], fresh[field], rtol=0, atol=1e-13)
        if ext:
            assert np.array_equal(old.configuration.to_numpy(), fresh.configuration.to_numpy())
            g = boolean(fresh.inference_gate)
            np.testing.assert_array_equal(g, boolean(old.inference_gate))
        else:
            g = np.ones(len(fresh), bool)
        for field in NEW + ["interval_lower", "interval_upper", "calibration_q"]:
            frame.loc[mask, field] = fresh[field].to_numpy()
        for label in CANDIDATES:
            field = label + "__intervened"
            frame.loc[mask, field] = boolean(fresh[field])
            a = fresh["mean8_CD" if label == "project_mean8" else "xlarge_CD"].to_numpy()
            np.testing.assert_allclose(fresh[label].to_numpy()[~g], a[~g], rtol=0, atol=TOL)
        frame.loc[mask, "interval_applicable"] = g
    assert len(frame) == 29856 and np.isfinite(frame[LABELS]).all().all()
    assert (frame[LABELS].to_numpy() > 0).all()
    for f in ["interval_applicable"] + [c+"__intervened" for c in CANDIDATES]:
        frame[f] = boolean(frame[f])
    # Authenticated reuse of unchanged old metric/decision functions.
    helper = OLD / "assess_frontier.py"
    assert sha(helper) == witness["input_source_sha256"][str(helper)]
    hashes[str(helper)] = sha(helper)
    spec = importlib.util.spec_from_file_location("selective_old_metrics", helper)
    metrics = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics)
    # Only in-memory successor label/seed configuration, never edit the old file.
    metrics.CANDIDATES, metrics.CONTROLS, metrics.LABELS = CANDIDATES, CONTROLS, LABELS
    metrics.SEED = 2026090727
    panels = make_panels(frame)
    oldtable = pd.read_csv(OLD/"assessment/panel_metrics.csv")
    assert set(panels) == set(oldtable.panel)
    for panel, ix in panels.items():
        assert len(ix) == int(oldtable[oldtable.panel.eq(panel)].rows.iloc[0])
    hashes[str(OLD/"assessment/panel_metrics.csv")] = witness["output_sha256"][str(OLD/"assessment/panel_metrics.csv")]
    verify(hashes)
    return frame, panels, metrics, hashes


def coverage(frame, panels):
    rows, bundles = [], []
    for panel, ix in panels.items():
        part = frame.iloc[ix].copy()
        # External configurations are descriptive bundles, not certified groups.
        part["bundle"] = np.where(part.split.isin(EXTERNAL),
            part.split.astype(str) + ":" + part.configuration.astype(str), part.group.astype(str))
        eligible = part.interval_applicable.to_numpy(bool)
        y, lo, hi = [part[c].to_numpy(float) for c in ["measured_CD", "interval_lower", "interval_upper"]]
        covered = (lo <= y) & (y <= hi)
        tolerant = (lo-TOL <= y) & (y <= hi+TOL)
        part["covered"] = covered
        assessed = part[eligible]
        widths = (hi-lo)[eligible]
        group_status = []
        for bundle, p in part.groupby("bundle", sort=True):
            selected = p[p.interval_applicable]
            n = len(selected)
            success = None if n == 0 else bool(selected.covered.all())
            if success is not None:
                group_status.append(success)
            row = {"panel": panel, "bundle": bundle, "rows": len(p), "eligible_rows": n,
                   "fully_covered_eligible_bundle": success,
                   "eligible_row_coverage": None if n == 0 else float(selected.covered.mean()),
                   "bundle_interpretation": "descriptive_external_configuration" if p.split.isin(EXTERNAL).any() else "historical_identity"}
            for label, baseline in [("project_mean8", "mean8_CD"), ("project_xlarge", "xlarge_CD")]:
                delta = abs(p[label]-p.measured_CD) - abs(p[baseline]-p.measured_CD)
                row[label+"__any_harmed_row"] = bool((delta > TOL).any())
                row[label+"__worse_group_mae"] = bool(delta.mean() > TOL)
                row[label+"__intervened_rows"] = int(p[label+"__intervened"].sum())
            bundles.append(row)
        record = {"panel": panel, "rows": len(part), "eligible_rows": int(eligible.sum()),
                  "outside_gate_rows_unassessed": int((~eligible).sum()), "assessed_bundles": len(group_status),
                  "fully_covered_bundles": sum(group_status),
                  "eligible_row_coverage": float(covered[eligible].mean()) if eligible.any() else None,
                  "eligible_bundle_coverage": float(np.mean(group_status)) if group_status else None,
                  "covered_rows_at_1e12_tolerance": int(tolerant[eligible].sum()),
                  "covered_rows_exact_endpoints": int(covered[eligible].sum()),
                  "median_interval_width_CD": float(np.median(widths)) if len(widths) else None,
                  "mean_interval_width_CD": float(np.mean(widths)) if len(widths) else None,
                  "p90_interval_width_CD": float(np.quantile(widths, .9)) if len(widths) else None,
                  "unbounded_eligible_intervals": int(np.isinf(widths).sum())}
        for label, baseline in [("project_mean8", "mean8_CD"), ("project_xlarge", "xlarge_CD")]:
            intervention = part[label+"__intervened"].to_numpy(bool)
            delta = abs(part[label].to_numpy()-y) - abs(part[baseline].to_numpy()-y)
            assert not (intervention & ~eligible).any()
            violations = covered & eligible & (delta > TOL)
            assert not violations.any(), "Projection harmed a covered target"
            record.update({label+"__intervened_rows": int(intervention.sum()),
                label+"__intervention_fraction_all": float(intervention.mean()),
                label+"__intervention_fraction_eligible": float(intervention[eligible].mean()) if eligible.any() else None,
                label+"__worse_rows_vs_supplied_baseline": int((delta > TOL).sum()),
                label+"__harm_fraction_among_interventions": float((delta[intervention] > TOL).mean()) if intervention.any() else None,
                label+"__benefit_fraction_among_interventions": float((delta[intervention] < -TOL).mean()) if intervention.any() else None,
                label+"__mean_signed_excess_error_among_interventions_CD": float(delta[intervention].mean()) if intervention.any() else None,
                label+"__covered_target_projection_violations": int(violations.sum())})
        rows.append(record)
    return pd.DataFrame(rows), pd.DataFrame(bundles)


def main():
    assert not OUT.exists(), "Preserve an existing assessment"
    frame, panels, metrics, hashes = load()
    table, boot, groups = metrics.panel_metrics(frame, panels), metrics.bootstrap(frame), metrics.group_metrics(frame)
    old_table = pd.read_csv(OLD/"assessment/panel_metrics.csv")
    for label in ["unpenalized_transfer", "half_strength"]:
        a = table[table.candidate.eq(label)].sort_values("panel")
        b = old_table[old_table.candidate.eq(label)].sort_values("panel")
        for field in ["mae_CD"] + metrics.FIELDS:
            np.testing.assert_allclose(a[field], b[field], rtol=0, atol=1e-10)
    cov, bundles = coverage(frame, panels)
    decision = metrics.decisions(table, boot, groups)
    result = {"panel_metrics": table, "bootstrap": boot, "group_metrics": groups,
              "harm_metrics": metrics.harms(frame, panels), "coverage_metrics": cov,
              "bundle_coverage": bundles, "candidate_summary": metrics.summary(table, boot, groups),
              "decisions": decision, "all_row_predictions": frame}
    for p in [Path(__file__), HERE/"PROTOCOL.md", HERE/"selective.py", HERE/"test_selective.py"]:
        hashes[str(p)] = sha(p)
    verify(hashes)
    OUT.mkdir()
    for name, data in result.items():
        data.to_csv(OUT/(name+".csv"), index=False)
    report = {"status": "completed_fixed_selective_experiment_adaptive_not_confirmatory",
              "model_count": 16, "alpha": .1, "candidates": CANDIDATES, "controls": CONTROLS,
              "rows_with_repeated_contexts": len(frame), "panels": len(panels),
              "bootstrap_draws": 20000, "bootstrap_seed": 2026090727,
              "performance_advances": decision.loc[decision.performance_advance, "candidate"].tolist(),
              "robustness_advances": decision.loc[decision.robustness_advance, "candidate"].tolist(),
              "empirically_certified": False, "deployed": False,
              "coverage_semantics": "Eligible finite bundles only; external configurations descriptive. Conditional exchangeability theorem, not established target-population coverage. No selected-case or noiseless-truth guarantee.",
              "input_source_sha256": hashes,
              "output_sha256": {str(OUT/(name+".csv")): sha(OUT/(name+".csv")) for name in result}}
    (OUT/"report.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(decision[["candidate", "performance_advance", "robustness_advance"]].to_string(index=False))
    print(cov[cov.panel.isin(["history_20260906_pooled", "history_20260908_pooled", "SG_exposed_pooled", "W_new_challenge_pooled"])].to_string(index=False))


if __name__ == "__main__":
    main()
