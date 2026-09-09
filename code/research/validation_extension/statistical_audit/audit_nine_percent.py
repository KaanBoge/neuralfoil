#!/usr/bin/env python3
"""Audit a >=9% drag-MAE reduction using two frozen, previously evaluated models.

No fitting, tuning, model selection, or existing-project mutation occurs. Cohort
reconstruction independently implements the archived audited key/occurrence rules.
The primary statistic is 100*(sum baseline absolute error - sum candidate absolute
error)/sum baseline absolute error. Each bootstrap draw uses paired cluster sums
for BOTH the numerator and denominator, not a fixed baseline denominator.

Run from any directory with the project's NumPy/pandas Python environment:
    python audit_nine_percent.py --project /path/to/NeuralFoil_Research_Paper

Outputs are confined to this script's directory. They describe exploratory,
post-hoc, frozen-prediction evidence and cannot establish a universal guarantee.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
SIZES = ["xxsmall", "xsmall", "small", "medium", "large", "xlarge", "xxlarge", "xxxlarge"]
COUNTS = 1e4
THRESHOLD_PERCENT = 9.0
N_BOOT = 20_000
MASTER_SEED = 20260906
KEYS = ["entry", "Re_key", "alpha_key"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_close(actual, expected, name: str, atol: float = 1e-9) -> None:
    if not np.allclose(actual, expected, rtol=0, atol=atol):
        raise ValueError(f"{name}: values differ from the archived audit")


def keyed(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "entry" not in result:
        result["entry"] = result["source"].astype(str) + "|" + result["airfoil"].astype(str)
    result["Re_key"] = result["Re"].round().astype(int)
    result["alpha_key"] = result["alpha"].round(2)
    return result


def match_configuration(corpus: pd.DataFrame, inference: pd.DataFrame) -> pd.DataFrame:
    raw, inferred = corpus.copy(), inference.copy()
    for frame in (raw, inferred):
        frame["Re_match"] = frame["Re"].round(3)
        frame["alpha_match"] = frame["alpha"].round(4)
    raw["CL_match"], raw["CD_match"] = raw["CL"].round(5), raw["CD"].round(6)
    inferred["CL_match"] = inferred["CL_meas"].round(5)
    inferred["CD_match"] = inferred["CD_meas"].round(6)
    match = ["source", "airfoil", "Re_match", "alpha_match", "CL_match", "CD_match"]
    for frame in (raw, inferred):
        frame["match_occurrence"] = frame.groupby(match, sort=False).cumcount()
    result = inferred.merge(
        raw[match + ["match_occurrence", "config"]].rename(columns={"config": "raw_config"}),
        on=match + ["match_occurrence"], how="left", validate="one_to_one", sort=False,
    )
    assert len(result) == len(inference) == 13_394
    assert result["raw_config"].notna().all()
    return keyed(result)


def make_cohorts(project: Path) -> tuple[dict[str, pd.DataFrame], dict, list[Path]]:
    data = project / "source/neuralfoil_repo/study/data"
    paths = {name: data / name for name in ["lsat-corpus.csv", "lsat-nf.csv", "oof3.csv", "lsat-xfoil.csv"]}
    ridge_path = project / "analysis/post_audit_clean_v1_oof.csv"
    verified_path = project / "analysis/verified_metrics.json"
    ridge_metrics_path = project / "analysis/post_audit_clean_v1_metrics.json"
    corpus = pd.read_csv(paths["lsat-corpus.csv"])
    inference = pd.read_csv(paths["lsat-nf.csv"])
    assert len(corpus) == 14_773
    nf = match_configuration(corpus, inference)
    assert nf["config"].eq("clean").sum() == 10_608
    assert (nf["config"].eq("clean") & nf["raw_config"].ne("clean")).sum() == 1_955
    clean = nf.loc[nf["config"].eq("clean") & nf["raw_config"].eq("clean")].copy()
    assert len(clean) == 8_653 and clean["entry"].nunique() == 135 and clean["airfoil"].nunique() == 124
    clean["CD_mean8"] = clean[[f"CD_{size}" for size in SIZES]].mean(axis=1)
    clean["oof_occurrence"] = clean.groupby(KEYS, sort=False).cumcount()
    oof = keyed(pd.read_csv(paths["oof3.csv"]))
    assert len(oof) == 10_312
    oof["oof_occurrence"] = oof.groupby(KEYS, sort=False).cumcount()
    merge_keys = KEYS + ["oof_occurrence"]
    clean = clean.merge(oof[merge_keys + ["zCD_oof"]], how="left", on=merge_keys,
                        validate="one_to_one", sort=False)
    assert len(clean) == 8_653 and clean["zCD_oof"].notna().sum() == 8_388
    clean["CD_legacy"] = clean["CD_mean8"] * np.exp(clean["zCD_oof"].fillna(0).clip(np.log(.5), np.log(2)))
    unique = clean.drop_duplicates(KEYS, keep="last").copy()
    assert len(unique) == 8_652
    xf = keyed(pd.read_csv(paths["lsat-xfoil.csv"])).drop_duplicates(KEYS, keep="last")
    common = unique.merge(xf[KEYS + ["CD_xf"]], how="inner", on=KEYS, validate="one_to_one", sort=False)
    assert len(common) == 7_897 and common["entry"].nunique() == 135
    assert not common.duplicated(KEYS).any()
    common["baseline_error"] = (common["CD_xlarge"] - common["CD_meas"]).abs() * COUNTS
    common["candidate_error"] = (common["CD_legacy"] - common["CD_meas"]).abs() * COUNTS

    # Match the frozen clean-only refit back to the independently recovered clean
    # domain, preserving repeated condition occurrences rather than expanding joins.
    domain = clean.loc[clean["Re"].le(6e5) & clean["alpha"].abs().le(12)
                       & clean["tc"].between(.05, .20) & clean["CD_meas"].gt(0)
                       & clean["CD_mean8"].gt(0)].copy()
    assert len(domain) == 8_388
    domain["ridge_occurrence"] = domain.groupby(KEYS, sort=False).cumcount()
    ridge = keyed(pd.read_csv(ridge_path))
    assert len(ridge) == 8_388 and ridge["entry"].nunique() == 134 and ridge["airfoil"].nunique() == 123
    ridge["ridge_occurrence"] = ridge.groupby(KEYS, sort=False).cumcount()
    ridge_keys = KEYS + ["ridge_occurrence"]
    check = ridge.merge(domain[ridge_keys + ["source", "airfoil", "Re", "alpha", "CD_meas", "CD_mean8"]],
                        on=ridge_keys, how="outer", suffixes=("", "_recovered"),
                        validate="one_to_one", indicator=True, sort=False)
    assert len(check) == 8_388 and check["_merge"].eq("both").all()
    for name in ["source", "airfoil"]:
        assert check[name].eq(check[name + "_recovered"]).all()
    for name in ["Re", "alpha", "CD_meas", "CD_mean8"]:
        assert_close(check[name], check[name + "_recovered"], "clean-ridge mapping " + name, atol=1e-10)
    ridge["CD_recomputed"] = ridge["CD_mean8"] * np.exp(ridge["zcd_clean_v1_oof"].clip(np.log(.5), np.log(2)))
    assert_close(ridge["CD_recomputed"], ridge["CD_clean_v1_oof"], "clean-ridge correction formula", atol=1e-12)
    ridge["baseline_error"] = (ridge["CD_mean8"] - ridge["CD_meas"]).abs() * COUNTS
    ridge["candidate_error"] = (ridge["CD_recomputed"] - ridge["CD_meas"]).abs() * COUNTS
    assert_close(ridge["baseline_error"], ridge["err_cd_base"], "clean-ridge base errors")
    assert_close(ridge["candidate_error"], ridge["err_cd_clean_v1_oof"], "clean-ridge corrected errors")
    verified = json.loads(verified_path.read_text())
    ridge_metrics = json.loads(ridge_metrics_path.read_text())
    assert_close(common["baseline_error"].mean(), verified["common_cluster_bootstrap"]["err_cd_xlarge"]["estimate"], "legacy baseline MAE")
    assert_close(common["candidate_error"].mean(), verified["common_cluster_bootstrap"]["err_cd_corrected"]["estimate"], "legacy corrected MAE")
    assert_close(ridge["baseline_error"].mean(), ridge_metrics["grouped_oof"]["err_cd_base"]["estimate"], "ridge baseline MAE")
    assert_close(ridge["candidate_error"].mean(), ridge_metrics["grouped_oof"]["err_cd_clean_v1_oof"]["estimate"], "ridge corrected MAE")
    cohorts = {"legacy_v3_vs_xlarge_common": common, "clean_ridge_vs_mean8_domain": ridge}
    for frame in cohorts.values():
        assert np.isfinite(frame[["baseline_error", "candidate_error"]].to_numpy()).all()
        assert frame[["baseline_error", "candidate_error"]].ge(0).all().all()
    checks = {
        "raw_corpus_rows": len(corpus), "inference_rows_matched_one_to_one": len(nf),
        "overwritten_clean_label_rows": 10_608, "modified_rows_removed": 1_955,
        "clean_rows": len(clean), "unique_clean_conditions": len(unique),
        "common_returned_conditions": len(common), "absent_xfoil_conditions": len(unique) - len(common),
        "clean_ridge_rows_matched_one_to_one": len(ridge),
        "cohort_key_sha256": {name: hashlib.sha256(frame[KEYS].to_csv(index=False).encode()).hexdigest()
                               for name, frame in cohorts.items()},
        "legacy_common_rows_with_frozen_correction": int(common["zCD_oof"].notna().sum()),
        "legacy_common_rows_using_uncorrected_mean8_fallback": int(common["zCD_oof"].isna().sum()),
        "all_key_formula_and_archived_metric_checks_passed": True,
    }
    return cohorts, checks, list(paths.values()) + [ridge_path, verified_path, ridge_metrics_path]


def row_audit(frame: pd.DataFrame) -> dict:
    base = frame["baseline_error"].to_numpy()
    candidate = frame["candidate_error"].to_numpy()
    defined = base > 0
    reduction = 100 * (base[defined] - candidate[defined]) / base[defined]
    result = {
        "rows": len(frame), "baseline_zero_rows": int((~defined).sum()),
        "relative_reduction_defined_rows": int(defined.sum()),
        "worse_rows": int((candidate > base).sum()), "equal_error_rows": int((candidate == base).sum()),
        "improved_rows": int((candidate < base).sum()),
        "below_9_percent_rows": int((reduction < THRESHOLD_PERCENT).sum()),
        "at_least_9_percent_rows": int((reduction >= THRESHOLD_PERCENT).sum()),
        "zero_baseline_zero_candidate_rows": int(((base == 0) & (candidate == 0)).sum()),
        "zero_baseline_positive_candidate_rows": int(((base == 0) & (candidate > 0)).sum()),
    }
    assert result["worse_rows"] + result["equal_error_rows"] + result["improved_rows"] == len(frame)
    assert result["below_9_percent_rows"] + result["at_least_9_percent_rows"] == int(defined.sum())
    return result


def point_summary(frame: pd.DataFrame) -> dict:
    base = frame["baseline_error"]
    candidate = frame["candidate_error"]
    baseline_sum = float(base.sum())
    reduction = 100 * (baseline_sum - float(candidate.sum())) / baseline_sum if baseline_sum > 0 else None
    return {
        "rows": len(frame), "source_airfoil_entries": int(frame["entry"].nunique()),
        "nominal_airfoil_names": int(frame["airfoil"].nunique()),
        "baseline_mae_counts": float(base.mean()), "candidate_mae_counts": float(candidate.mean()),
        "baseline_median_error_counts": float(base.median()), "candidate_median_error_counts": float(candidate.median()),
        "baseline_p90_error_counts": float(base.quantile(.9)), "candidate_p90_error_counts": float(candidate.quantile(.9)),
        "baseline_iqr_error_counts": float(base.quantile(.75) - base.quantile(.25)),
        "candidate_iqr_error_counts": float(candidate.quantile(.75) - candidate.quantile(.25)),
        "paired_error_change_counts": float((candidate - base).mean()),
        "relative_mae_reduction_percent": reduction,
        "point_estimate_at_least_9_percent": reduction is not None and reduction >= THRESHOLD_PERCENT,
        **row_audit(frame),
    }


def bootstrap(frame: pd.DataFrame, cluster: str, stream: str) -> dict:
    hashed = hashlib.sha256(stream.encode()).digest()
    spawn_key = [int.from_bytes(hashed[:4], "little"), int.from_bytes(hashed[4:8], "little")]
    rng = np.random.default_rng(np.random.SeedSequence(MASTER_SEED, spawn_key=spawn_key))
    groups = frame.groupby(cluster, sort=True)[["baseline_error", "candidate_error"]].sum()
    sums = groups.to_numpy()
    draws = np.empty(N_BOOT)
    for start in range(0, N_BOOT, 1000):
        stop = min(start + 1000, N_BOOT)
        chosen = rng.integers(0, len(groups), size=(stop - start, len(groups)))
        resampled = sums[chosen].sum(axis=1)
        assert np.all(resampled[:, 0] > 0)
        draws[start:stop] = 100 * (resampled[:, 0] - resampled[:, 1]) / resampled[:, 0]
    lower, upper = np.quantile(draws, [.025, .975])
    one_sided = float(np.quantile(draws, .05))
    return {
        "cluster": cluster, "clusters": len(groups), "replicates": N_BOOT,
        "two_sided_95_percentile_interval": [float(lower), float(upper)],
        "one_sided_95_lower_percentile_bound": one_sided,
        "one_sided_lower_bound_at_least_9_percent": bool(one_sided >= THRESHOLD_PERCENT),
        "seed": {"master": MASTER_SEED, "stream": stream, "spawn_key": spawn_key},
        "units": "percentage points of relative MAE reduction",
    }


def analyze(name: str, frame: pd.DataFrame) -> tuple[dict, list[dict]]:
    result = {
        "overall": point_summary(frame),
        "primary_source_airfoil_cluster_bootstrap": bootstrap(frame, "entry", name + "::overall::entry"),
        "nominal_airfoil_cluster_sensitivity": bootstrap(frame, "airfoil", name + "::overall::airfoil"),
    }
    rows = []
    group_counts = {}
    for level in ["source", "entry", "airfoil"]:
        grouped_rows = []
        for label, group in frame.groupby(level, sort=True):
            row = {"comparison": name, "group_level": level, "group": label, **point_summary(group)}
            if level == "source":
                interval = bootstrap(group, "entry", name + "::source::" + str(label))
                row["two_sided_95_low"] = interval["two_sided_95_percentile_interval"][0]
                row["two_sided_95_high"] = interval["two_sided_95_percentile_interval"][1]
                row["one_sided_95_lower"] = interval["one_sided_95_lower_percentile_bound"]
                row["one_sided_lower_bound_at_least_9_percent"] = interval["one_sided_lower_bound_at_least_9_percent"]
                row["bootstrap_stream"] = interval["seed"]["stream"]
            grouped_rows.append(row)
        assert sum(row["rows"] for row in grouped_rows) == len(frame)
        for count_name in ["worse_rows", "equal_error_rows", "improved_rows", "below_9_percent_rows",
                           "at_least_9_percent_rows", "baseline_zero_rows"]:
            assert sum(row[count_name] for row in grouped_rows) == result["overall"][count_name]
        for metric in ["baseline_mae_counts", "candidate_mae_counts"]:
            weighted_mean = sum(row[metric] * row["rows"] for row in grouped_rows) / len(frame)
            assert_close(weighted_mean, result["overall"][metric], level + " weighted " + metric)
        group_counts[level] = {
            "groups": len(grouped_rows),
            "groups_worse": sum(row["paired_error_change_counts"] > 0 for row in grouped_rows),
            "groups_below_9_percent": sum(row["relative_mae_reduction_percent"] < THRESHOLD_PERCENT for row in grouped_rows),
            "groups_at_least_9_percent": sum(row["relative_mae_reduction_percent"] >= THRESHOLD_PERCENT for row in grouped_rows),
            "minimum_group_reduction_percent": min(row["relative_mae_reduction_percent"] for row in grouped_rows),
            "maximum_group_reduction_percent": max(row["relative_mae_reduction_percent"] for row in grouped_rows),
        }
        if level == "source":
            result["source_summaries"] = grouped_rows
        rows.extend(grouped_rows)
    result["group_threshold_counts"] = group_counts
    return result, rows


def build_report(result: dict) -> str:
    lines = ["# Audit of the proposed universal 9% improvement claim", "",
             "Assessment: share with explicit caveats. The observed pooled reductions do not establish a universal guarantee; both frozen candidates worsen some recorded conditions and airfoil groups.", "",
             "This post-hoc analysis evaluates two different fixed comparisons. It performs no new training, hyperparameter search, winner selection, or exclusion of extreme errors. All error values are absolute drag-coefficient errors in drag counts (one count = 0.0001 in C_D).", "",
             "## Overall paired results", "",
             "| Fixed comparison | Rows | Baseline MAE | Candidate MAE | Relative reduction | Two-sided 95% interval | One-sided 95% lower bound |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, comparison in result["comparisons"].items():
        summary = comparison["overall"]
        interval = comparison["primary_source_airfoil_cluster_bootstrap"]
        low, high = interval["two_sided_95_percentile_interval"]
        lines.append(f"| {name} | {summary['rows']:,} | {summary['baseline_mae_counts']:.5f} | {summary['candidate_mae_counts']:.5f} | {summary['relative_mae_reduction_percent']:.3f}% | {low:.3f}% to {high:.3f}% | {interval['one_sided_95_lower_percentile_bound']:.3f}% |")
    lines += ["", "A favorable pooled point estimate is different from evidence that the reduction is at least 9%. The one-sided bound directly addresses that threshold for the stated empirical sampling model. It remains conditional and exploratory, and cannot establish performance for every individual condition, source, metric, or future population.", "", "## Recorded counterexamples and subgroup variation", ""]
    components = result["legacy_component_accounting_common"]
    lines[-2:-2] = [
        "## What the legacy improvement includes", "",
        f"On the same 7,897 common conditions, xlarge MAE is {components['xlarge_mae_counts']:.5f}, mean-of-eight MAE is {components['mean8_mae_counts']:.5f}, and legacy-corrected MAE is {components['legacy_corrected_mae_counts']:.5f} counts. Averaging alone reduces MAE by {components['mean8_vs_xlarge_relative_reduction_percent']:.3f}% relative to xlarge; adding the frozen v3 correction reduces it by {components['legacy_vs_mean8_relative_reduction_percent']:.3f}% relative to mean-of-eight. The complete mean-of-eight-plus-correction comparison is {components['legacy_vs_xlarge_relative_reduction_percent']:.3f}% relative to xlarge. These percentages have different denominators and must not be added. The paired absolute-error reductions, {components['averaging_absolute_reduction_counts']:.5f} plus {components['correction_absolute_reduction_counts']:.5f}, do sum to {components['total_absolute_reduction_counts']:.5f} counts.", "",
    ]
    sensitivity_text = []
    for name, comparison in result["comparisons"].items():
        sensitivity = comparison["nominal_airfoil_cluster_sensitivity"]
        low, high = sensitivity["two_sided_95_percentile_interval"]
        sensitivity_text.append(f"{name}: {low:.3f}% to {high:.3f}% (two-sided), {sensitivity['one_sided_95_lower_percentile_bound']:.3f}% (one-sided lower).")
    lines[-2:-2] = ["Nominal-airfoil clustering gives " + " ".join(sensitivity_text)
                     + " The clean-ridge one-sided bounds lie close to 9%; the two-sided intervals extend below 9%. The numerical threshold result must therefore be reported with its specified confidence level, clustering choice, and exploratory status.", ""]
    for name, comparison in result["comparisons"].items():
        summary = comparison["overall"]
        entry = comparison["group_threshold_counts"]["entry"]
        nominal = comparison["group_threshold_counts"]["airfoil"]
        source = comparison["group_threshold_counts"]["source"]
        lines += [f"**{name}.** {summary['worse_rows']:,}/{summary['rows']:,} rows worsened; {summary['below_9_percent_rows']:,}/{summary['relative_reduction_defined_rows']:,} rows with positive baseline error had less than 9% reduction. {entry['groups_worse']}/{entry['groups']} source-airfoil entries worsened and {entry['groups_below_9_percent']}/{entry['groups']} fell below 9%. Pooling repeated airfoil names across sources, {nominal['groups_worse']}/{nominal['groups']} nominal-airfoil groups worsened and {nominal['groups_below_9_percent']}/{nominal['groups']} fell below 9%. {source['groups_below_9_percent']}/{source['groups']} source groups fell below 9%.", ""]
    lines += ["| Fixed comparison | Source | Rows | Baseline MAE | Candidate MAE | Relative reduction | One-sided 95% lower bound |", "|---|---|---:|---:|---:|---:|---:|"]
    for name, comparison in result["comparisons"].items():
        for source in comparison["source_summaries"]:
            lines.append(f"| {name} | {source['group']} | {source['rows']:,} | {source['baseline_mae_counts']:.4f} | {source['candidate_mae_counts']:.4f} | {source['relative_mae_reduction_percent']:.3f}% | {source['one_sided_95_lower']:.3f}% |")
    lines += ["", "## Definitions and methods", "",
              "Relative reduction is 100 × (sum baseline absolute error − sum candidate absolute error) / sum baseline absolute error. It is a ratio of pooled paired sums, not an average of per-row percentages. Every bootstrap draw resamples complete groups with replacement and recomputes both sums. The fixed specification uses 20,000 draws, a two-sided percentile interval (2.5th and 97.5th percentiles), and a one-sided 95% lower bound (5th percentile). Named deterministic streams and input SHA-256 values are recorded in results.json.", "",
              "Source-airfoil entry is the primary cluster. Overall nominal-airfoil resampling is a sensitivity to repeated geometries across sources. Source intervals resample entries within the given source; these are pointwise exploratory intervals, not simultaneous guarantees. Individual-entry and nominal-airfoil subgroup results are descriptive because rows within those groups are dependent. The source summaries pool each source's existing OOF predictions; they are not new leave-one-source-out training tests.", "",
              "The legacy comparison reproduces the audited 7,897 unique clean conditions with returned XFOIL output. Its baseline is NeuralFoil xlarge; its candidate is the eight-size mean plus the frozen drag-v3 boosted log-residual correction, with an unchanged mean-of-eight fallback where no correction exists. Thus the gain includes averaging as well as correction. Legacy correction fits originally included modified configurations, and exact retraining still requires missing inputs.", "",
              "The ridge comparison uses all 8,388 reconstructed clean-domain rows and compares the frozen clean-only ridge OOF prediction against the uncorrected mean of eight. It uses a different baseline and population from the historical 9% claim. The ridge model was not refit; its frozen OOF outputs were used. Original paired error means and all cohort identities are independently rechecked against the prior audit artifacts.", "",
              "A row is worse when candidate absolute error exceeds baseline absolute error. Its percentage reduction is undefined when baseline absolute error is zero; such rows are counted separately and are not silently assigned a percentage. Group thresholds use each group's own ratio of summed errors. No outlier is removed. Median, IQR and 90th-percentile errors accompany means in results.json and group_results.csv.", "",
              "## Limits and reproducibility", "",
              "All intervals condition on the frozen OOF predictions, historical model specification, selected corpus, and analyst choices. They exclude retraining variability, adaptive model development, measurement/facility systematics, geometry error, and unobserved conditions. Four historical source labels cannot represent all airfoils, flow regimes, Reynolds numbers, Mach numbers, or outputs. A drag-MAE reduction does not imply an equivalent improvement in lift, stall, drag divergence, every prediction, or arbitrary future operating conditions.", "",
              "Reproduce with `python audit_nine_percent.py --project /path/to/NeuralFoil_Research_Paper` using the NumPy/pandas versions in results.json. The script writes only into this statistical_audit directory. The existing manuscript, model artifacts, source data, and analysis outputs remain unchanged. Required inputs are enumerated with hashes in results.json. Group CSV rows provide every observed source and airfoil result, not only favorable groups.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=OUT.parents[1])
    args = parser.parse_args()
    project = args.project.resolve()
    cohorts, checks, inputs = make_cohorts(project)
    comparisons, group_rows = {}, []
    for name, frame in cohorts.items():
        comparisons[name], rows = analyze(name, frame)
        group_rows.extend(rows)
    common = cohorts["legacy_v3_vs_xlarge_common"]
    xlarge_mae = float(common["baseline_error"].mean())
    mean8_mae = float(((common["CD_mean8"] - common["CD_meas"]).abs() * COUNTS).mean())
    corrected_mae = float(common["candidate_error"].mean())
    components = {
        "rows": len(common), "xlarge_mae_counts": xlarge_mae,
        "mean8_mae_counts": mean8_mae, "legacy_corrected_mae_counts": corrected_mae,
        "mean8_vs_xlarge_relative_reduction_percent": 100 * (xlarge_mae - mean8_mae) / xlarge_mae,
        "legacy_vs_mean8_relative_reduction_percent": 100 * (mean8_mae - corrected_mae) / mean8_mae,
        "legacy_vs_xlarge_relative_reduction_percent": 100 * (xlarge_mae - corrected_mae) / xlarge_mae,
        "averaging_absolute_reduction_counts": xlarge_mae - mean8_mae,
        "correction_absolute_reduction_counts": mean8_mae - corrected_mae,
        "total_absolute_reduction_counts": xlarge_mae - corrected_mae,
        "status": "descriptive accounting on the same frozen common cohort; no new fit or independent validation",
    }
    assert_close(components["averaging_absolute_reduction_counts"] + components["correction_absolute_reduction_counts"],
                 components["total_absolute_reduction_counts"], "same-cohort component accounting")
    result = {
        "status": "exploratory post-hoc audit of frozen predictions; not universal or confirmatory proof",
        "threshold_percent": THRESHOLD_PERCENT, "bootstrap_replicates": N_BOOT,
        "ci_specification": "paired ratio-of-sums; percentile 2.5/97.5 two-sided and percentile 5 one-sided lower",
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "cohort_validation": checks,
        "inputs": {p.relative_to(project).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)} for p in inputs},
        "script_sha256": digest(Path(__file__)), "comparisons": comparisons,
        "legacy_component_accounting_common": components,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    pd.DataFrame(group_rows).to_csv(OUT / "group_results.csv", index=False)
    (OUT / "REPORT.md").write_text(build_report(result))
    print(json.dumps({name: {"overall": item["overall"], "bootstrap": item["primary_source_airfoil_cluster_bootstrap"],
                            "nominal_airfoil_sensitivity": item["nominal_airfoil_cluster_sensitivity"],
                            "group_counts": item["group_threshold_counts"]} for name, item in comparisons.items()}, indent=2))


if __name__ == "__main__":
    main()
