"""Non-fitting assessment of the single predeclared adaptive-scale experiment."""
from pathlib import Path
import hashlib
import importlib.util
import json

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
A = HERE.parent / "model_development_20260907_cap_ablation"
OUT = HERE / "assessment"
CANDIDATES = ["adaptive_project_mean8", "adaptive_project_xlarge"]
CONTROLS = ["project_mean8_upper_free", "project_xlarge_upper_free",
            "proper_upper_free_full", "proper_upper_free_half",
            "unpenalized_transfer", "half_strength"]
LABELS = CANDIDATES + CONTROLS


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(hashes):
    for path, expected in hashes.items():
        assert sha(path) == expected, path


def load():
    complete, frozen = [read(HERE / "results" / f"{name}.json") for name in ["complete", "freeze"]]
    assert complete["new_fit_count"] == frozen["new_fit_count"] == 64
    assert complete["inner_core_count"] == frozen["inner_core_count"] == 48
    assert complete["scale_count"] == frozen["scale_count"] == 16
    assert complete["calibrator_count"] == frozen["calibrator_count"] == 16
    assert frozen["external_outcomes_opened"] is False
    assert len(frozen["artifact_sha256"]) == 144
    assert complete["freeze_sha256"] == sha(HERE / "results/freeze.json")
    assert frozen["a_freeze_sha256"] == sha(A / "results/freeze.json")
    hashes = {}
    for record in [frozen, complete]:
        for key in ["source_input_sha256", "artifact_sha256", "output_sha256", "external_input_sha256"]:
            if key in record:
                verify(record[key])
                hashes.update(record[key])
    helper = A / "assess_cap.py"
    witness = read(A / "assessment/report.json")
    assert sha(helper) == witness["input_source_sha256"][str(helper)]
    spec = importlib.util.spec_from_file_location("fixed_a_assessment_for_b", helper)
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    frame, panels, metrics, prior, inherited = a.load()
    hashes.update(inherited)
    hashes[str(helper)] = sha(helper)
    hashes[str(A / "assessment/report.json")] = sha(A / "assessment/report.json")
    for split in frame.split.unique():
        external = split in prior.EXTERNAL
        path = HERE / ("exposed_results" if external else "results") / (
            f"{split}_predictions.csv" if external else f"predictions_{split}.csv")
        assert sha(path) == complete["output_sha256"][str(path)]
        fresh = pd.read_csv(path, low_memory=False)
        mask = frame.split.eq(split)
        old = frame.loc[mask]
        assert len(fresh) == len(old)
        if not external:
            assert not fresh.nf2_row_id.duplicated().any()
            assert set(fresh.nf2_row_id) == set(old.nf2_row_id)
            fresh = fresh.set_index("nf2_row_id").loc[old.nf2_row_id].reset_index()
        else:
            np.testing.assert_array_equal(fresh.configuration, old.configuration)
        for field in ["Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD",
                      "proper_upper_free_full", "proper_upper_free_half"]:
            np.testing.assert_allclose(fresh[field], old[field], atol=1e-13, rtol=0)
        gate = prior.boolean(fresh.interval_applicable)
        np.testing.assert_array_equal(gate, old.interval_applicable.to_numpy(bool))
        for field in CANDIDATES + ["interval_lower", "interval_upper", "calibration_q",
                                   "dimensionless_scale", "scale_CD"]:
            frame.loc[mask, field] = fresh[field].to_numpy()
        np.testing.assert_allclose(fresh.scale_CD, fresh.mean8_CD * fresh.dimensionless_scale,
                                   atol=1e-13, rtol=1e-13)
        assert np.isfinite(fresh[["scale_CD", "dimensionless_scale"]]).all().all()
        assert (fresh[["scale_CD", "dimensionless_scale"]].to_numpy() > 0).all()
        for label, baseline in zip(CANDIDATES, ["mean8_CD", "xlarge_CD"]):
            field = label + "__intervened"
            frame.loc[mask, field] = prior.boolean(fresh[field])
            np.testing.assert_allclose(fresh[label].to_numpy()[~gate], fresh[baseline].to_numpy()[~gate],
                                       atol=1e-13, rtol=0)
    assert len(frame) == 29856 and len(panels) == 31
    assert np.isfinite(frame[LABELS]).all().all() and (frame[LABELS].to_numpy() > 0).all()
    for label in CANDIDATES:
        frame[label + "__intervened"] = prior.boolean(frame[label + "__intervened"])
    metrics.LABELS, metrics.CANDIDATES, metrics.CONTROLS = LABELS, CANDIDATES, CONTROLS
    metrics.SEED = 2026090733
    for path in [HERE / "results/complete.json", HERE / "results/freeze.json", HERE / "PROTOCOL.md", Path(__file__)]:
        hashes[str(path)] = sha(path)
    return frame, panels, metrics, prior, hashes


def distribution(values, prefix):
    x = np.asarray(values, float)
    assert x.ndim == 1 and len(x) and np.isfinite(x).all()
    out = {prefix + "_min": float(x.min()), prefix + "_max": float(x.max()), prefix + "_mean": float(x.mean())}
    for q in [.01, .05, .5, .95, .99]:
        out[prefix + f"_p{int(q*100):02d}"] = float(np.quantile(x, q))
    return out


def scale_diagnostics():
    complete = read(HERE / "results/complete.json")
    summaries, scores = [], []
    for info in complete["splits"]:
        context = info["context"]
        cal = read(HERE / "results" / f"calibrator_{context}.json")
        for role, filename in [("proper_training", "scale_training"), ("calibration", "calibration"),
                               ("all_history_not_holdout" if context == "final" else "outer_holdout", "inference")]:
            with np.load(HERE / "results" / f"{filename}_{context}.npz", allow_pickle=False) as z:
                s, b = z["dimensionless_scale"], z["BASE_CD"]
                row = {"context": context, "role": role, "rows": len(s)}
                row.update(distribution(s, "dimensionless_scale"))
                row.update(distribution(b*s, "scale_CD"))
                if cal["q"] is not None:
                    row.update(distribution(2*cal["q"]*b*s, "potential_interval_width_CD"))
                summaries.append(row)
        for group, score in zip(cal["group_ids"], cal["group_scores"]):
            scores.append({"context": context, "group": group, "score": score,
                           "calibration_groups": cal["calibration_groups"], "rank": cal["rank"], "q": cal["q"]})
    cal = read(HERE / "results/calibrator_final.json")
    for context in ["SG_exposed", "W_new_challenge"]:
        with np.load(HERE / "exposed_results" / f"{context}_inference.npz", allow_pickle=False) as z:
            for role, mask in [("complete_exposed", np.ones(len(z["BASE_CD"]), bool)), ("eligible_exposed", z["gate"])]:
                s, b = z["dimensionless_scale"][mask], z["BASE_CD"][mask]
                row = {"context": context, "role": role, "rows": len(s)}
                row.update(distribution(s, "dimensionless_scale"))
                row.update(distribution(b*s, "scale_CD"))
                if cal["q"] is not None:
                    row.update(distribution(2*cal["q"]*b*s, "potential_interval_width_CD"))
                summaries.append(row)
    return pd.DataFrame(summaries), pd.DataFrame(scores)


def main():
    assert not OUT.exists(), "Preserve previous assessments"
    frame, panels, metrics, prior, hashes = load()
    table, boot, groups = metrics.panel_metrics(frame, panels), metrics.bootstrap(frame), metrics.group_metrics(frame)
    decisions = metrics.decisions(table, boot, groups)
    coverages, bundles = [], []
    for method in ["fixed_mean8_scale", "adaptive_scale"]:
        f = frame.copy()
        if method == "fixed_mean8_scale":
            for field in ["interval_lower", "interval_upper"]:
                f[field] = f[field + "_upper_free"]
        for base in ["mean8", "xlarge"]:
            label = f"project_{base}_upper_free" if method == "fixed_mean8_scale" else f"adaptive_project_{base}"
            f["project_" + base] = f[label]
            f["project_" + base + "__intervened"] = f[label + "__intervened"]
        cov, bundle = prior.coverage(f, panels)
        cov["method"], bundle["method"] = method, method
        coverages.append(cov)
        bundles.append(bundle)
    scales, scores = scale_diagnostics()
    outputs = {"panel_metrics": table, "bootstrap": boot, "group_metrics": groups,
               "harm_metrics": metrics.harms(frame, panels), "decisions": decisions,
               "candidate_summary": metrics.summary(table, boot, groups),
               "coverage_metrics": pd.concat(coverages, ignore_index=True),
               "bundle_coverage": pd.concat(bundles, ignore_index=True),
               "scale_distributions": scales, "calibration_scores": scores, "all_row_predictions": frame}
    assert len(table) == 248 and len(boot) == 32 and len(decisions) == 2
    assert len(outputs["coverage_metrics"]) == 62 and len(scales) == 52
    verify(hashes)
    OUT.mkdir()
    for name, data in outputs.items():
        data.to_csv(OUT / (name + ".csv"), index=False)
    report = {"status": "complete_fixed_adaptive_scale_exploratory_not_confirmatory", "new_fit_count": 64,
              "inherited_proper_core_count": 16, "calibrator_count": 16,
              "candidates": CANDIDATES, "controls": CONTROLS, "panels": 31,
              "rows_with_repeated_contexts": len(frame), "bootstrap_draws": 20000, "bootstrap_seed": 2026090733,
              "performance_advances": decisions.loc[decisions.performance_advance, "candidate"].tolist(),
              "robustness_advances": decisions.loc[decisions.robustness_advance, "candidate"].tolist(),
              "deployed": False, "empirically_certified": False,
              "input_source_sha256": hashes,
              "output_sha256": {str(OUT / (name + ".csv")): sha(OUT / (name + ".csv")) for name in outputs},
              "warning": "Input scale is not physical measurement uncertainty. Reused outcomes remain exploratory; no conditional selected-case, universal, optimum or popularity guarantee. Bootstrap conditions on saved predictions."}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(decisions[["candidate", "performance_advance", "robustness_advance"]].to_string(index=False))
    names = ["history_20260906_pooled", "history_20260908_pooled", "SG_exposed_pooled", "W_new_challenge_pooled"]
    cols = ["method", "panel", "fully_covered_bundles", "assessed_bundles", "median_interval_width_CD",
            "project_mean8__intervened_rows", "project_xlarge__intervened_rows"]
    c = outputs["coverage_metrics"]
    print(c.loc[c.panel.isin(names), cols].to_string(index=False))


if __name__ == "__main__":
    main()
