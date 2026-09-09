from __future__ import annotations

"""Final dependence, split, and duplicate-key sensitivity checks.

The main audit treats a source-airfoil entry as the resampling and grouped-
cross-validation unit. Ten nominal airfoil names occur in more than one source
entry, so this script repeats the most important estimates with the stricter
airfoil-name grouping. It also quantifies cross-validation split sensitivity
and the effect of the single duplicated rounded condition key.
"""

import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import analyze_study as base


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
BOOTSTRAP_SEED = 20260905
CV_SEED = 20260904
SPLIT_SEEDS = tuple(range(20260905, 20260925))
N_BOOT = 4000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cluster_bootstrap_mean(
    frame: pd.DataFrame,
    value: str,
    cluster: str,
    *,
    seed: int = BOOTSTRAP_SEED,
    n_boot: int = N_BOOT,
) -> dict[str, float | int]:
    grouped = frame.groupby(cluster, sort=False)[value].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(float)
    counts = grouped["count"].to_numpy(float)
    n_clusters = len(grouped)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for index in range(n_boot):
        sampled = rng.integers(0, n_clusters, n_clusters)
        draws[index] = sums[sampled].sum() / counts[sampled].sum()
    return {
        "estimate": float(frame[value].mean()),
        "ci_low": float(np.quantile(draws, 0.025)),
        "ci_high": float(np.quantile(draws, 0.975)),
        "rows": int(len(frame)),
        "clusters": int(n_clusters),
        "bootstrap_replicates": int(n_boot),
        "seed": int(seed),
    }


def cluster_bootstrap_group_difference(
    frame: pd.DataFrame,
    value: str,
    group: str,
    cluster: str,
    *,
    reference: bool = True,
    comparison: bool = False,
    seed: int = BOOTSTRAP_SEED,
    n_boot: int = N_BOOT,
) -> dict[str, float | int | str]:
    levels = [reference, comparison]
    grouped = frame.groupby([cluster, group], sort=False)[value].agg(["sum", "count"])
    clusters = grouped.index.get_level_values(0).unique()
    arrays: dict[bool, tuple[np.ndarray, np.ndarray]] = {}
    for level in levels:
        level_frame = (
            grouped.xs(level, level=group, drop_level=True)
            .reindex(clusters)
            .fillna(0)
        )
        arrays[level] = (
            level_frame["sum"].to_numpy(float),
            level_frame["count"].to_numpy(float),
        )

    rng = np.random.default_rng(seed)
    draws = []
    n_clusters = len(clusters)
    for _ in range(n_boot):
        sampled = rng.integers(0, n_clusters, n_clusters)
        means = {}
        valid = True
        for level in levels:
            sums, counts = arrays[level]
            denominator = counts[sampled].sum()
            if denominator == 0:
                valid = False
                break
            means[level] = sums[sampled].sum() / denominator
        if valid:
            draws.append(means[comparison] - means[reference])

    reference_mean = float(frame.loc[frame[group].eq(reference), value].mean())
    comparison_mean = float(frame.loc[frame[group].eq(comparison), value].mean())
    draw_array = np.asarray(draws, dtype=float)
    return {
        "contrast": f"{comparison} minus {reference}",
        "reference_mean": reference_mean,
        "comparison_mean": comparison_mean,
        "estimate": comparison_mean - reference_mean,
        "ci_low": float(np.quantile(draw_array, 0.025)),
        "ci_high": float(np.quantile(draw_array, 0.975)),
        "rows": int(len(frame)),
        "clusters": int(n_clusters),
        "bootstrap_replicates": int(len(draw_array)),
        "seed": int(seed),
    }


def make_risk_features(clean: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    features = pd.DataFrame(
        {
            "negative_confidence": -clean["conf_xlarge"],
            "log_disagreement": np.log1p(clean["spread_counts"]),
            "log_re": np.log10(clean["Re"]),
            "alpha": clean["alpha"],
            "abs_alpha": clean["alpha"].abs(),
            "thickness": clean["tc"],
            "nominal_geometry": clean["geom_kind"].eq("nominal").astype(float),
        }
    )
    outcome = clean["err_cd_mean8"].gt(20).astype(int).to_numpy()
    return features, outcome


def grouped_risk_predictions(
    clean: pd.DataFrame,
    features: pd.DataFrame,
    outcome: np.ndarray,
    *,
    group_column: str,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_sets = {
        "confidence": ["negative_confidence"],
        "disagreement": ["log_disagreement"],
        "multivariable": list(features.columns),
        "multivariable_no_nominal_geometry": [
            column for column in features.columns if column != "nominal_geometry"
        ],
    }
    folds = list(
        StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=seed).split(
            features,
            outcome,
            clean[group_column].astype(str),
        )
    )
    predictions = clean[["source", "airfoil", "entry", "Re", "alpha"]].copy()
    predictions["large_error"] = outcome
    rows = []
    for name, columns in feature_sets.items():
        probability = np.full(len(clean), np.nan)
        for train, test in folds:
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs"),
            )
            model.fit(features.iloc[train][columns], outcome[train])
            probability[test] = model.predict_proba(features.iloc[test][columns])[:, 1]
        if np.isnan(probability).any():
            raise RuntimeError(f"Missing OOF probabilities for {group_column}/{name}")
        predictions[f"risk_probability_{name}"] = probability
        rows.append(
            {
                "group_unit": group_column,
                "cv_seed": seed,
                "risk_model": name,
                "rows": int(len(clean)),
                "groups": int(clean[group_column].nunique()),
                "event_prevalence": float(outcome.mean()),
                "mean_predicted_risk": float(probability.mean()),
                "auroc": float(roc_auc_score(outcome, probability)),
                "average_precision": float(average_precision_score(outcome, probability)),
                "brier_score": float(brier_score_loss(outcome, probability)),
            }
        )
    return predictions, pd.DataFrame(rows)


def main() -> None:
    clean, unique, common = base.load_low_speed()
    clean = clean.reset_index(drop=True)
    unique = unique.reset_index(drop=True)
    common = common.reset_index(drop=True)

    grouping_rows = []
    for label, neuralfoil_error, comparator_error in [
        ("paired_drag_mean8_minus_xfoil", "err_cd_mean8", "err_cd_xfoil"),
        ("paired_lift_mean8_minus_xfoil", "err_cl_mean8", "err_cl_xfoil"),
    ]:
        work = common.copy()
        work["contrast_value"] = work[neuralfoil_error] - work[comparator_error]
        for cluster in ["entry", "airfoil"]:
            result = cluster_bootstrap_mean(work, "contrast_value", cluster)
            grouping_rows.append({"quantity": label, "cluster_unit": cluster, **result})

    keys = ["entry", "Re_key", "alpha_key"]
    availability = common[keys].drop_duplicates().assign(xfoil_output_returned=True)
    selected = unique.merge(availability, how="left", on=keys, validate="one_to_one")
    selected["xfoil_output_returned"] = (
        selected["xfoil_output_returned"].eq(True)
    )
    for cluster in ["entry", "airfoil"]:
        result = cluster_bootstrap_group_difference(
            selected,
            "err_cd_mean8",
            "xfoil_output_returned",
            cluster,
        )
        grouping_rows.append(
            {
                "quantity": "mean8_drag_error_absent_minus_returned",
                "cluster_unit": cluster,
                **result,
            }
        )
    grouping = pd.DataFrame(grouping_rows)
    grouping.to_csv(OUT / "grouping_sensitivity.csv", index=False)

    # XFOIL returns are observed for only a subset of unique eligible conditions.
    # A best-case composite assigns zero error to every absent output. The
    # break-even penalty gives the mean absent-output error at which that
    # composite equals the NeuralFoil mean-of-eight MAE on all eligible rows.
    returned_xfoil_error_sum = float(common["err_cd_xfoil"].sum())
    total_conditions = int(len(unique))
    returned_conditions = int(len(common))
    absent_conditions = total_conditions - returned_conditions
    neuralfoil_all_mae = float(unique["err_cd_mean8"].mean())
    xfoil_zero_penalty_mae = returned_xfoil_error_sum / total_conditions
    break_even_absent_penalty = (
        neuralfoil_all_mae * total_conditions - returned_xfoil_error_sum
    ) / absent_conditions
    absence_sensitivity = pd.DataFrame(
        [
            {
                "eligible_unique_conditions": total_conditions,
                "xfoil_returned_conditions": returned_conditions,
                "xfoil_absent_conditions": absent_conditions,
                "neuralfoil_mean8_all_condition_mae_counts": neuralfoil_all_mae,
                "xfoil_best_case_zero_absent_penalty_mae_counts": xfoil_zero_penalty_mae,
                "break_even_mean_absent_penalty_counts": break_even_absent_penalty,
                "interpretation": (
                    "Descriptive composite sensitivity only; absent XFOIL errors are "
                    "unobserved and the comparison pipelines use different geometry representations."
                ),
            }
        ]
    )
    absence_sensitivity.to_csv(
        OUT / "xfoil_absence_composite_sensitivity.csv", index=False
    )

    features, outcome = make_risk_features(clean)
    risk_frames = []
    airfoil_predictions = None
    for group_column in ["entry", "airfoil"]:
        predictions, metrics = grouped_risk_predictions(
            clean,
            features,
            outcome,
            group_column=group_column,
            seed=CV_SEED,
        )
        risk_frames.append(metrics)
        if group_column == "airfoil":
            airfoil_predictions = predictions
    risk_grouping = pd.concat(risk_frames, ignore_index=True)
    risk_grouping.to_csv(OUT / "risk_grouping_sensitivity.csv", index=False)
    if airfoil_predictions is None:
        raise RuntimeError("Airfoil-group predictions were not generated")
    airfoil_predictions.to_csv(OUT / "risk_airfoil_group_oof.csv", index=False)

    split_frames = []
    for seed in SPLIT_SEEDS:
        _, metrics = grouped_risk_predictions(
            clean,
            features,
            outcome,
            group_column="airfoil",
            seed=seed,
        )
        split_frames.append(metrics)
    split_sensitivity = pd.concat(split_frames, ignore_index=True)
    split_sensitivity.to_csv(OUT / "risk_airfoil_split_sensitivity.csv", index=False)

    xfoil = base.add_key(pd.read_csv(base.DATA / "lsat-xfoil.csv"))
    xfoil = xfoil.drop_duplicates(keys, keep="last")
    duplicate_rows = []
    for keep in ["first", "last"]:
        deduplicated = clean.drop_duplicates(keys, keep=keep)
        comparison = deduplicated.merge(
            xfoil[[*keys, "CL_xf", "CD_xf"]],
            how="inner",
            on=keys,
            validate="one_to_one",
        )
        comparison["mean8_drag_error"] = (
            comparison["CD_mean8"] - comparison["CD_meas"]
        ).abs() * 1e4
        comparison["xfoil_drag_error"] = (
            comparison["CD_xf"] - comparison["CD_meas"]
        ).abs() * 1e4
        duplicate_rows.append(
            {
                "duplicate_rule": keep,
                "unique_conditions": int(len(deduplicated)),
                "common_conditions": int(len(comparison)),
                "mean8_drag_mae_counts": float(comparison["mean8_drag_error"].mean()),
                "xfoil_drag_mae_counts": float(comparison["xfoil_drag_error"].mean()),
                "mean8_minus_xfoil_counts": float(
                    (comparison["mean8_drag_error"] - comparison["xfoil_drag_error"]).mean()
                ),
            }
        )
    duplicate = pd.DataFrame(duplicate_rows)
    duplicate.to_csv(OUT / "duplicate_condition_sensitivity.csv", index=False)

    repeated_names = (
        clean[["airfoil", "source", "entry"]]
        .drop_duplicates()
        .groupby("airfoil")
        .agg(source_count=("source", "nunique"), entry_count=("entry", "nunique"))
        .query("entry_count > 1")
    )
    multi = risk_grouping.loc[
        risk_grouping["risk_model"].eq("multivariable")
    ].set_index("group_unit")
    split_multi = split_sensitivity.loc[
        split_sensitivity["risk_model"].eq("multivariable")
    ]
    summary = {
        "analysis_status": "post-audit dependence and split sensitivity",
        "metadata": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "package_versions": {
                package: importlib.metadata.version(package)
                for package in ("numpy", "pandas", "scikit-learn")
            },
            "script": {
                "path": str(Path(__file__).resolve().relative_to(ROOT)),
                "size_bytes": Path(__file__).stat().st_size,
                "sha256": sha256_file(Path(__file__)),
            },
            "supporting_code": {
                "path": str(Path(base.__file__).resolve().relative_to(ROOT)),
                "size_bytes": Path(base.__file__).stat().st_size,
                "sha256": sha256_file(Path(base.__file__)),
            },
            "inputs": [
                {
                    "path": str(path.relative_to(ROOT)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in (
                    base.DATA / "lsat-corpus.csv",
                    base.DATA / "lsat-nf.csv",
                    base.DATA / "lsat-xfoil.csv",
                )
            ],
        },
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": N_BOOT,
        "primary_cv_seed": CV_SEED,
        "split_sensitivity_seeds": list(SPLIT_SEEDS),
        "repeated_nominal_airfoil_names": int(len(repeated_names)),
        "source_airfoil_entries": int(clean["entry"].nunique()),
        "distinct_airfoil_names": int(clean["airfoil"].nunique()),
        "grouping_sensitivity": grouping.astype(object)
        .where(pd.notna(grouping), None)
        .to_dict(orient="records"),
        "risk_grouping_sensitivity": risk_grouping.to_dict(orient="records"),
        "multivariable_risk_airfoil_group": multi.loc["airfoil"].to_dict(),
        "multivariable_no_nominal_geometry": risk_grouping.loc[
            risk_grouping["risk_model"].eq("multivariable_no_nominal_geometry")
        ].to_dict(orient="records"),
        "multivariable_risk_split_range": {
            "auroc_min": float(split_multi["auroc"].min()),
            "auroc_median": float(split_multi["auroc"].median()),
            "auroc_max": float(split_multi["auroc"].max()),
            "average_precision_min": float(split_multi["average_precision"].min()),
            "average_precision_median": float(split_multi["average_precision"].median()),
            "average_precision_max": float(split_multi["average_precision"].max()),
            "brier_min": float(split_multi["brier_score"].min()),
            "brier_median": float(split_multi["brier_score"].median()),
            "brier_max": float(split_multi["brier_score"].max()),
        },
        "duplicate_condition_sensitivity": duplicate.to_dict(orient="records"),
        "xfoil_absence_composite_sensitivity": absence_sensitivity.to_dict(
            orient="records"
        )[0],
    }
    (OUT / "final_sensitivity_metrics.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
