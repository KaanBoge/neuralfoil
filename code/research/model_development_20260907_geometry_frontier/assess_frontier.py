"""Assess the six predeclared procedures only after both branch freezes.

No fitting, selection, file I/O, or assessment on import. Fixed predictions and
previously exposed outcomes give adaptive research evidence, not confirmation.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RISK = HERE.parent / "model_development_20260907_risk_policy"
GEOMETRY = ["geometry4", "geometry8", "geometry_condition4", "geometry8_free"]
NEURAL = ["neural62__0.5", "neural62__1"]
CANDIDATES = GEOMETRY + NEURAL
PERFORMANCE = "unpenalized_transfer"
ROBUSTNESS = "half_strength"
REFERENCES = [PERFORMANCE, ROBUSTNESS]
CONTROLS = REFERENCES + ["previous_global", "moderate_full_strength"]
LABELS = CANDIDATES + CONTROLS
ASSIGNMENTS = [20260906, 20260908]
EXTERNAL = ["SG_exposed", "W_new_challenge"]
FIELDS = ["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]
BASELINES = ["xlarge_CD", "mean8_CD"]
ROW_TOL, PP_TOL = 1e-12, 1e-6
N_BOOTSTRAP, SEED = 20000, 2026090723
OUT = HERE / "assessment"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify(hashes):
    for path, digest in hashes.items():
        assert sha(path) == digest, path


def gate(frame):
    return frame.inference_gate.map(
        lambda v: v is True or str(v).lower() == "true" or v == 1
    ).to_numpy(bool)


def authenticated_completion():
    """Do not access new scores if either declared branch is unfinished."""
    geo_path = HERE / "geometry/results/freeze.json"
    neural_path = HERE / "neural/results/freeze.json"
    complete_path = HERE / "geometry/results/complete.json"
    neural_report_path = HERE / "neural/results/report.json"
    assert all(p.is_file() for p in [geo_path, neural_path, complete_path, neural_report_path]), \
        "Both complete freezes are required; no partial model selection"
    geo, neural = read(geo_path), read(neural_path)
    complete, neural_report = read(complete_path), read(neural_report_path)
    assert geo["all_64_frozen_before_exposed"] is True
    assert len(geo["model_sha256"]) == complete["model_count"] == 64
    assert neural["external_scored_at_freeze"] is False
    assert len(neural["artifact_sha256"]) == neural["model_count"] == neural_report["model_count"] == 48
    hashes = {}
    for source in [geo["model_sha256"], neural["artifact_sha256"],
                   neural["source_input_sha256"], complete["source_sha256"],
                   complete["evaluation_sha256"]]:
        verify(source)
        for p, h in source.items():
            assert p not in hashes or hashes[p] == h
            hashes[p] = h
    for p in [geo_path, neural_path, complete_path, neural_report_path]:
        hashes[str(p)] = sha(p)
    return hashes


def load_frame():
    hashes = authenticated_completion()
    # Authenticate the previous consumer witness before importing its helper or
    # loading its prediction files. Fresh hashes alone are not provenance checks.
    witness_path = RISK / "assessment/report.json"
    witness = read(witness_path)
    verify(witness["input_source_sha256"])
    hashes.update(witness["input_source_sha256"])
    hashes[str(witness_path)] = sha(witness_path)
    helper_path = RISK / "assess_policy.py"
    assert sha(helper_path) == witness["input_source_sha256"][str(helper_path)]
    spec = importlib.util.spec_from_file_location("geometry_risk_assessment", helper_path)
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    frame, inherited = prior.load_frame()
    hashes.update(inherited)
    frame["moderate_full_strength"] = frame["capacity__hist62_moderate__1"]
    assert len(frame) == 29856 and len(frame.split.unique()) == 17
    for branch, labels in [("geometry", GEOMETRY), ("neural", NEURAL)]:
        for split in frame.split.unique():
            external = split in EXTERNAL
            path = HERE / branch / ("exposed_results" if external else "results") / (
                f"{split}_predictions.csv" if external else f"predictions_{split}.csv")
            hashes[str(path)] = sha(path)
            new = pd.read_csv(path, low_memory=False)
            mask = frame.split == split
            original = frame.loc[mask]
            for field in ["Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD"]:
                assert field in new, (path, field)
            if not external:
                assert not new.nf2_row_id.duplicated().any()
                assert set(new.nf2_row_id) == set(original.nf2_row_id)
                new = new.set_index("nf2_row_id").loc[original.nf2_row_id].reset_index()
            prior.shared.check_common(original, new)
            if "split" in new:
                assert (new.split == split).all()
            if external:
                g = gate(original)
                np.testing.assert_array_equal(g, gate(new))
                assert len(new) == {"SG_exposed": 242, "W_new_challenge": 255}[split]
                assert g.sum() == {"SG_exposed": 234, "W_new_challenge": 238}[split]
            for label in labels:
                pred = new[label].to_numpy()
                assert np.isfinite(pred).all() and (pred > 0).all()
                if external:
                    # Native exact fallback is audited separately; CSV snapshots
                    # can introduce decimal-roundtrip differences of about 1e-16.
                    np.testing.assert_allclose(pred[~g], original.mean8_CD.to_numpy()[~g],
                                               atol=1e-13, rtol=0)
                frame.loc[mask, label] = pred
    assert np.isfinite(frame[LABELS + BASELINES + ["measured_CD"]].to_numpy()).all()
    panels = prior.shared.old.panels(frame)
    panels.update({k: v for k, v in prior.shared.reconcile.external_panels(frame).items()
                   if k.startswith("eligible_only/")})
    assert len(panels) == 31
    for p in [Path(__file__), HERE / "test_assessment.py", HERE / "PROTOCOL.md", Path(prior.shared.__file__),
              Path(prior.shared.old.__file__), Path(prior.shared.reconcile.__file__)]:
        hashes[str(p)] = sha(p)
    return frame, panels, hashes


def panel_metrics(frame, panels):
    rows = []
    target = frame.measured_CD.to_numpy()
    for label in LABELS:
        error = abs(frame[label].to_numpy() - target)
        for name, ix in panels.items():
            e = error[ix]
            row = {"candidate": label, "panel": name, "rows": len(ix),
                   "mae_CD": float(e.mean()), "mae_drag_counts": float(e.mean() * 1e4),
                   "median_absolute_error_CD": float(np.median(e)),
                   "p90_absolute_error_CD": float(np.quantile(e, .9)),
                   "row_equality_tolerance_CD": ROW_TOL}
            for baseline in BASELINES:
                be = abs(frame[baseline].to_numpy()[ix] - target[ix])
                assert be.sum() > 0
                row.update({baseline + "_mae": float(be.mean()),
                            baseline + "_improvement_percent": float(100 * (1 - e.sum() / be.sum())),
                            baseline + "_worse_rows": int((e > be + ROW_TOL).sum()),
                            baseline + "_worse_fraction": float((e > be + ROW_TOL).mean())})
            rows.append(row)
    return pd.DataFrame(rows)


def bootstrap(frame):
    rows = []
    for assignment in ASSIGNMENTS:
        f = frame[frame.split.str.startswith(f"group_{assignment}_")]
        assert len(f) == f.nf2_row_id.nunique() == 8371
        groups, inverse = np.unique(f.group, return_inverse=True)
        assert len(groups) == 93
        y = f.measured_CD.to_numpy()
        counts = np.random.default_rng(SEED).multinomial(
            len(groups), np.full(len(groups), 1 / len(groups)), size=N_BOOTSTRAP)
        sums = {label: np.bincount(inverse, weights=abs(f[label].to_numpy() - y)) for label in LABELS}
        resampled = {label: counts @ values for label, values in sums.items()}
        for reference in REFERENCES:
            assert (resampled[reference] > 0).all()
            for label in LABELS:
                benefit = 100 * (1 - resampled[label] / resampled[reference])
                lo, hi = np.quantile(benefit, [.025, .975])
                rows.append({"candidate": label, "assignment": assignment, "reference": reference,
                             "rows": len(f), "groups": len(groups),
                             "remaining_MAE_reduction_percent": float(100 * (1 - sums[label].sum() / sums[reference].sum())),
                             "conditional_95pct_lower": float(lo), "conditional_95pct_upper": float(hi),
                             "bootstrap_fraction_benefit_positive": float((benefit > 0).mean()),
                             "draws": N_BOOTSTRAP, "seed": SEED,
                             "interpretation": "Fixed-prediction paired group bootstrap; adaptive/unadjusted, not confirmatory; assignments overlap"})
    return pd.DataFrame(rows)


def group_metrics(frame):
    rows = []
    for assignment in ASSIGNMENTS:
        f = frame[frame.split.str.startswith(f"group_{assignment}_")]
        assert f.group.nunique() == 93
        for group, part in f.groupby("group", sort=True):
            y = part.measured_CD.to_numpy()
            baseline = abs(part.xlarge_CD.to_numpy() - y).mean()
            assert baseline > 0
            for label in LABELS:
                error = abs(part[label].to_numpy() - y).mean()
                reduction = 100 * (1 - error / baseline)
                rows.append({"candidate": label, "assignment": assignment, "group": group,
                             "rows": len(part), "mae_CD": float(error), "xlarge_mae_CD": float(baseline),
                             "MAE_difference_vs_xlarge_CD": float(error - baseline),
                             "xlarge_improvement_percent": float(reduction),
                             "worse_than_xlarge": bool(reduction < -PP_TOL)})
    return pd.DataFrame(rows)


def harms(frame, panels):
    rows = []
    y = frame.measured_CD.to_numpy()
    for label in LABELS:
        error = abs(frame[label].to_numpy() - y)
        for reference in REFERENCES + BASELINES:
            difference = error - abs(frame[reference].to_numpy() - y)
            for name, ix in panels.items():
                delta = difference[ix]
                positive = np.maximum(delta, 0)
                worse, better = delta > ROW_TOL, delta < -ROW_TOL
                equal = ~(worse | better)
                rows.append({"candidate": label, "reference": reference, "panel": name, "rows": len(ix),
                             "mean_positive_excess_absolute_error_CD": float(positive.mean()),
                             "mean_positive_excess_absolute_error_drag_counts": float(positive.mean() * 1e4),
                             "mean_signed_excess_absolute_error_CD": float(delta.mean()),
                             "p90_positive_excess_absolute_error_CD": float(np.quantile(positive, .9)),
                             "worse_rows": int(worse.sum()), "better_rows": int(better.sum()),
                             "equal_rows": int(equal.sum()), "worse_fraction": float(worse.mean()),
                             "better_fraction": float(better.mean()), "equal_fraction": float(equal.mean()),
                             "row_equality_tolerance_CD": ROW_TOL})
    return pd.DataFrame(rows)


def identity_guard(groups, label, reference):
    rows, passes = {}, True
    for assignment in ASSIGNMENTS:
        c = groups[(groups.candidate == label) & (groups.assignment == assignment)]
        r = groups[(groups.candidate == reference) & (groups.assignment == assignment)]
        assert len(c) == len(r) == 93 and set(c.group) == set(r.group)
        cn = int((c.xlarge_improvement_percent < -PP_TOL).sum())
        rn = int((r.xlarge_improvement_percent < -PP_TOL).sum())
        cw = max(0., float(-c.xlarge_improvement_percent.min()))
        rw = max(0., float(-r.xlarge_improvement_percent.min()))
        ok = cn <= rn and cw <= rw + PP_TOL
        passes &= ok
        rows.update({f"{assignment}_negative_groups": cn, f"{assignment}_reference_negative_groups": rn,
                     f"{assignment}_worst_group_deterioration_percent": cw,
                     f"{assignment}_reference_worst_group_deterioration_percent": rw,
                     f"{assignment}_identity_guard_pass": ok,
                     f"{assignment}_worst_positive_group_MAE_difference_CD": max(0., float(c.MAE_difference_vs_xlarge_CD.max())),
                     f"{assignment}_reference_worst_positive_group_MAE_difference_CD": max(0., float(r.MAE_difference_vs_xlarge_CD.max()))})
    return bool(passes), rows


def decisions(table, boot, groups):
    rows = []
    ext = table.panel.str.startswith("eligible_only/")
    ref = table[(table.candidate == PERFORMANCE) & ext][FIELDS].to_numpy()
    assert ref.shape == (8, 2)
    ref_negative, ref_min = int((ref < -PP_TOL).sum()), float(ref.min())
    for label in CANDIDATES:
        t = table[table.candidate == label]
        assert len(t) == 31
        strict = t[t.panel.str.startswith("strict_source_")][FIELDS].to_numpy()
        e = t[t.panel.str.startswith("eligible_only/")][FIELDS].to_numpy()
        assert strict.shape == (5, 2) and e.shape == (8, 2)
        strict_pass = bool((strict >= -PP_TOL).all())
        count, worst = int((e < -PP_TOL).sum()), float(e.min())
        external_pass = count <= ref_negative and worst >= ref_min - PP_TOL
        row = {"candidate": label, "strict_source_guard_pass": strict_pass,
               "eligible_external_negative_panel_baseline_pairs": count,
               "performance_reference_negative_pairs": ref_negative,
               "minimum_eligible_external_improvement_percent": worst,
               "performance_reference_minimum_eligible_improvement_percent": ref_min,
               "performance_external_guard_pass": external_pass,
               "minimum_all31_improvement_both_percent": float(t[FIELDS].to_numpy().min()),
               "all31_nonnegative_both_baselines": bool((t[FIELDS].to_numpy() >= -PP_TOL).all())}
        for reference, prefix in [(PERFORMANCE, "performance"), (ROBUSTNESS, "robustness")]:
            b = boot[(boot.candidate == label) & (boot.reference == reference)]
            assert len(b) == 2
            gain = bool((b.remaining_MAE_reduction_percent >= 1 - PP_TOL).all())
            group_pass, diagnostics = identity_guard(groups, label, reference)
            row[prefix + "_historical_gain_both_at_least_1pct"] = gain
            row[prefix + "_identity_guard_both_assignments"] = group_pass
            row.update({prefix + "_" + key: value for key, value in diagnostics.items()})
            row[prefix + "_advance"] = bool(gain and group_pass and (
                strict_pass and external_pass if reference == PERFORMANCE else row["all31_nonnegative_both_baselines"]))
        rows.append(row)
    return pd.DataFrame(rows)


def summary(table, boot, groups):
    rows = []
    for label in LABELS:
        t = table[table.candidate == label].set_index("panel")
        row = {"candidate": label, "role": "new_fixed_procedure" if label in CANDIDATES else "fixed_control",
               "minimum_all31_improvement_both_percent": float(t[FIELDS].to_numpy().min()),
               "minimum_eligible8_improvement_both_percent": float(t.loc[t.index.str.startswith("eligible_only/"), FIELDS].to_numpy().min()),
               "worst_strict_source_improvement_both_percent": float(t.loc[t.index.str.startswith("strict_source_"), FIELDS].to_numpy().min())}
        for assignment in ASSIGNMENTS:
            for field in FIELDS + ["mae_CD", "median_absolute_error_CD", "p90_absolute_error_CD"]:
                row[f"{assignment}_{field}"] = float(t.loc[f"history_{assignment}_pooled", field])
            g = groups[(groups.candidate == label) & (groups.assignment == assignment)]
            row[f"{assignment}_negative_identity_groups"] = int((g.xlarge_improvement_percent < -PP_TOL).sum())
            row[f"{assignment}_worst_group_improvement_percent"] = float(g.xlarge_improvement_percent.min())
            for reference in REFERENCES:
                b = boot[(boot.candidate == label) & (boot.assignment == assignment) & (boot.reference == reference)].iloc[0]
                row[f"{assignment}_remaining_MAE_reduction_vs_{reference}_percent"] = float(b.remaining_MAE_reduction_percent)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    assert not OUT.exists(), "Do not overwrite an assessment; preserve prior results"
    frame, panels, hashes = load_frame()
    table, boot, groups = panel_metrics(frame, panels), bootstrap(frame), group_metrics(frame)
    decision = decisions(table, boot, groups)
    # Independent prior snapshots catch control, split, or denominator drift.
    expected = {PERFORMANCE: [20.46642313445449, 19.691792006854325],
                ROBUSTNESS: [14.900038028772776, 14.215591441802932]}
    for label, values in expected.items():
        for assignment, value in zip(ASSIGNMENTS, values):
            actual = table[(table.candidate == label) & (table.panel == f"history_{assignment}_pooled")].iloc[0].xlarge_CD_improvement_percent
            np.testing.assert_allclose(actual, value, rtol=0, atol=1e-10)
    outputs = {"panel_metrics": table, "bootstrap": boot, "group_metrics": groups,
               "decisions": decision, "candidate_summary": summary(table, boot, groups),
               "harm_metrics": harms(frame, panels)}
    metadata = ["split", "nf2_row_id", "group", "source", "entry", "airfoil", "configuration",
                "source_line", "block", "Re", "alpha", "inference_gate", "measured_CD"]
    outputs["all_row_predictions"] = frame[[c for c in metadata if c in frame] + BASELINES + LABELS]
    verify(hashes)
    OUT.mkdir()
    for name, values in outputs.items():
        values.to_csv(OUT / (name + ".csv"), index=False)
    report = {"status": "completed_six_fixed_procedure_assessment_adaptive_not_confirmatory",
              "candidates": CANDIDATES, "controls": CONTROLS, "rows_with_repeated_contexts": len(frame),
              "panels": 31, "bootstrap_draws": N_BOOTSTRAP, "bootstrap_seed": SEED,
              "row_tolerance_CD": ROW_TOL, "comparison_tolerance_percentage_points": PP_TOL,
              "performance_advances": decision.loc[decision.performance_advance, "candidate"].tolist(),
              "robustness_advances": decision.loc[decision.robustness_advance, "candidate"].tolist(),
              "input_source_sha256": hashes,
              "output_sha256": {str(OUT / (name + ".csv")): sha(OUT / (name + ".csv")) for name in outputs},
              "warning": "All six fixed procedures retained; overlapping panels and assignments; adaptively reused outcomes; bootstrap omits search and multiplicity uncertainty. No automatic promotion, deployment, or universal accuracy claim.",
              "metric_semantics": "Relative MAE reductions use error-sum ratios. Group guards use relative group-MAE deterioration against raw xlarge. Harm magnitude uses max(delta,0), while only row classification uses the stated equality tolerance. Native exact fallback is checked in branch audits, separately from CSV tolerance."}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(decision[["candidate", "performance_advance", "robustness_advance"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
