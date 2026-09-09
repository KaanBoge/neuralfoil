"""Final, deterministic inference checks for the NeuralFoil manuscript.

This module intentionally leaves the existing analysis and manuscript builders
unchanged.  It reads the frozen study artifacts, recomputes the small set of
inference checks requested during final review, and writes standalone tidy CSV
and strict-JSON summaries.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_study as base
import clean_only_correction_audit as clean_ridge


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
DATA = ROOT / "source" / "neuralfoil_repo" / "study" / "data"

MASTER_SEED = 20260905
N_BOOT = 20_000
N_BOOT_RISK = 2_500
BOOTSTRAP_CHUNK = 1_000
RISK_BOOTSTRAP_CHUNK = 100
CI_LEVEL = 0.95

JSON_PATH = OUT / "final_inference_audit.json"
CENSORING_CSV = OUT / "final_inference_censoring.csv"
PAIRED_CSV = OUT / "final_inference_paired_bootstrap.csv"
TRANSFER_CSV = OUT / "final_inference_clean_ridge_transfer.csv"
STRICT_TRANSFER_CSV = OUT / "final_inference_clean_ridge_strict_transfer.csv"
FOLD_SENSITIVITY_CSV = OUT / "final_inference_clean_ridge_fold_sensitivity.csv"
FOLD_SENSITIVITY_SUMMARY_CSV = (
    OUT / "final_inference_clean_ridge_fold_sensitivity_summary.csv"
)
RISK_CALIBRATION_CSV = OUT / "final_inference_risk_calibration.csv"
TRANSONIC_CSV = OUT / "final_inference_transonic_sweeps.csv"
MODEL_SIZE_CSV = OUT / "final_inference_model_size_rank.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def named_rng(name: str) -> tuple[np.random.Generator, dict[str, Any]]:
    """Return an order-independent RNG derived from a stable analysis name."""

    digest = hashlib.sha256(name.encode("utf-8")).digest()
    spawn_key = (
        int.from_bytes(digest[0:4], "little"),
        int.from_bytes(digest[4:8], "little"),
    )
    seed_sequence = np.random.SeedSequence(MASTER_SEED, spawn_key=spawn_key)
    metadata = {
        "name": name,
        "master_seed": MASTER_SEED,
        "spawn_key": list(spawn_key),
        "name_sha256": hashlib.sha256(name.encode("utf-8")).hexdigest(),
    }
    return np.random.default_rng(seed_sequence), metadata


def percentile_interval(draws: np.ndarray) -> tuple[float, float]:
    tail = (1.0 - CI_LEVEL) / 2.0
    low, high = np.quantile(draws, [tail, 1.0 - tail])
    return float(low), float(high)


def cluster_bootstrap_mean(
    frame: pd.DataFrame,
    value: str,
    cluster: str,
    stream_name: str,
    *,
    stratify: str | None = None,
) -> dict[str, Any]:
    """Percentile cluster bootstrap of a point-weighted ratio-of-sums mean.

    When ``stratify`` is supplied, the original number of clusters in every
    stratum is preserved and clusters are resampled independently within each
    stratum.  All rows belonging to a sampled cluster are retained.
    """

    required = [value, cluster] + ([stratify] if stratify else [])
    work = frame[required].dropna().copy()
    if work.empty:
        raise ValueError(f"No complete rows for {stream_name}")

    partitions = (
        [(str(level), group) for level, group in work.groupby(stratify, sort=True)]
        if stratify
        else [("all", work)]
    )
    aggregates: list[tuple[str, np.ndarray, np.ndarray]] = []
    for level, group in partitions:
        agg = group.groupby(cluster, sort=True)[value].agg(["sum", "count"])
        if agg.empty:
            raise ValueError(f"Empty cluster stratum {level!r} for {stream_name}")
        aggregates.append(
            (
                level,
                agg["sum"].to_numpy(dtype=float),
                agg["count"].to_numpy(dtype=float),
            )
        )

    rng, seed_metadata = named_rng(stream_name)
    draws = np.empty(N_BOOT, dtype=float)
    for start in range(0, N_BOOT, BOOTSTRAP_CHUNK):
        stop = min(start + BOOTSTRAP_CHUNK, N_BOOT)
        size = stop - start
        numerator = np.zeros(size, dtype=float)
        denominator = np.zeros(size, dtype=float)
        for _, sums, counts in aggregates:
            n_cluster = len(sums)
            multiplicity = rng.multinomial(
                n_cluster,
                np.full(n_cluster, 1.0 / n_cluster),
                size=size,
            )
            numerator += multiplicity @ sums
            denominator += multiplicity @ counts
        if np.any(denominator <= 0):
            raise RuntimeError(f"Zero bootstrap denominator for {stream_name}")
        draws[start:stop] = numerator / denominator

    ci_low, ci_high = percentile_interval(draws)
    return {
        "estimate": float(work[value].mean()),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "bootstrap_standard_error": float(draws.std(ddof=1)),
        "bootstrap_replicates": N_BOOT,
        "ci_level": CI_LEVEL,
        "ci_method": "nonparametric percentile cluster bootstrap",
        "rows": int(len(work)),
        "clusters": int(work[cluster].nunique()),
        "strata": int(work[stratify].nunique()) if stratify else 1,
        "cluster_variable": cluster,
        "stratification_variable": stratify,
        "rng_stream_name": seed_metadata["name"],
        "rng_master_seed": seed_metadata["master_seed"],
        "rng_spawn_key_0": seed_metadata["spawn_key"][0],
        "rng_spawn_key_1": seed_metadata["spawn_key"][1],
        "rng_name_sha256": seed_metadata["name_sha256"],
    }


def add_censoring_row(
    rows: list[dict[str, Any]],
    *,
    analysis_set: str,
    sweeps: int,
    entries: int,
    boundary_sweeps: int,
    quantity: str,
    status: str,
    unit: str,
    estimate: float | None,
    lower_bound: float | None,
    upper_bound: float | None,
    interpretation: str,
) -> None:
    rows.append(
        {
            "analysis_set": analysis_set,
            "sweeps": sweeps,
            "source_airfoil_entries": entries,
            "boundary_sweeps": boundary_sweeps,
            "quantity": quantity,
            "status": status,
            "unit": unit,
            "estimate": estimate,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "interpretation": interpretation,
        }
    )


def censoring_summary() -> pd.DataFrame:
    data = pd.read_csv(DATA / "lsat-clmax.csv")
    data["boundary"] = np.isclose(data["astall_mean8"], 20.0)
    data["peak_error"] = data["clmax_mean8"] - data["clmax_meas"]
    data["stall_error"] = data["astall_mean8"] - data["astall_meas"]

    if len(data) != 471 or int(data["boundary"].sum()) != 25:
        raise RuntimeError("Unexpected stall artifact dimensions")
    boundary = data.loc[data["boundary"]]
    if boundary["entry"].nunique() != 8:
        raise RuntimeError("Unexpected number of boundary source-airfoil entries")

    rows: list[dict[str, Any]] = []
    analysis_sets = [
        ("all_sweeps", data),
        ("interior_predicted_peaks", data.loc[~data["boundary"]]),
        ("boundary_maxima", boundary),
    ]

    for label, group in analysis_sets:
        is_boundary = group["boundary"].to_numpy(dtype=bool)
        peak_error = group["peak_error"].to_numpy(dtype=float)
        stall_error = group["stall_error"].to_numpy(dtype=float)
        n = len(group)
        n_boundary = int(is_boundary.sum())
        common = {
            "analysis_set": label,
            "sweeps": int(n),
            "entries": int(group["entry"].nunique()),
            "boundary_sweeps": n_boundary,
        }

        grid_metrics = [
            ("grid_peak_lift_signed_bias", peak_error.mean(), "C_L"),
            ("grid_peak_lift_mae", np.abs(peak_error).mean(), "C_L"),
            ("grid_peak_lift_overprediction_share", (peak_error > 0).mean(), "proportion"),
            ("grid_stall_angle_signed_bias", stall_error.mean(), "degree"),
            ("grid_stall_angle_mae", np.abs(stall_error).mean(), "degree"),
        ]
        for quantity, estimate, unit in grid_metrics:
            add_censoring_row(
                rows,
                **common,
                quantity=quantity,
                status="grid_coded_descriptive",
                unit=unit,
                estimate=float(estimate),
                lower_bound=None,
                upper_bound=None,
                interpretation="Exact for the maximum searched only over -5 to 20 degrees; not a continuum peak when the maximum is at 20 degrees.",
            )

        if n_boundary == 0:
            identified = [
                ("peak_lift_signed_bias", peak_error.mean(), "C_L"),
                ("peak_lift_mae", np.abs(peak_error).mean(), "C_L"),
                ("peak_lift_overprediction_share", (peak_error > 0).mean(), "proportion"),
                ("stall_angle_signed_bias", stall_error.mean(), "degree"),
                ("stall_angle_mae", np.abs(stall_error).mean(), "degree"),
            ]
            for quantity, estimate, unit in identified:
                value = float(estimate)
                add_censoring_row(
                    rows,
                    **common,
                    quantity=quantity,
                    status="identified_within_archived_grid_resolution",
                    unit=unit,
                    estimate=value,
                    lower_bound=value,
                    upper_bound=value,
                    interpretation="Uncensored interior-grid endpoint; discretization and measurement uncertainty remain.",
                )
            continue

        interior = ~is_boundary
        # At a boundary maximum, the peak over any extension of the prediction
        # domain is at least the value observed at 20 degrees.  Consequently the
        # signed peak error has a lower bound.  Absolute error can shrink to zero
        # when the grid-boundary value is below the measured peak.
        peak_bias_lower = float(peak_error.mean())
        peak_mae_lower = float(
            (
                np.abs(peak_error[interior]).sum()
                + np.maximum(peak_error[is_boundary], 0.0).sum()
            )
            / n
        )
        peak_over_lower = float((peak_error > 0).mean())
        peak_over_upper = float(
            ((peak_error > 0).sum() + ((peak_error <= 0) & is_boundary).sum()) / n
        )

        # The unobserved predicted stall angle for a right-censored row is at
        # least 20 degrees.  The closest possible value to the measured angle is
        # therefore max(20 - measured angle, 0) in absolute error.
        measured_angle = group["astall_meas"].to_numpy(dtype=float)
        stall_bias_lower = float(stall_error.mean())
        stall_mae_lower = float(
            (
                np.abs(stall_error[interior]).sum()
                + np.maximum(20.0 - measured_angle[is_boundary], 0.0).sum()
            )
            / n
        )

        bounded = [
            (
                "peak_lift_signed_bias",
                "lower_bound",
                "C_L",
                peak_bias_lower,
                None,
                "True peak lift is at least the value at the upper grid boundary; no finite upper bound is supplied.",
            ),
            (
                "peak_lift_mae",
                "lower_bound",
                "C_L",
                peak_mae_lower,
                None,
                "Minimum absolute error over all peak lifts consistent with the right-censored boundary values.",
            ),
            (
                "peak_lift_overprediction_share",
                "interval_bound",
                "proportion",
                peak_over_lower,
                peak_over_upper,
                "Boundary rows currently below the measured peak may or may not become overpredictions beyond 20 degrees.",
            ),
            (
                "stall_angle_signed_bias",
                "lower_bound",
                "degree",
                stall_bias_lower,
                None,
                "Right-censored predicted stall angles are at least 20 degrees; no finite upper bound is supplied.",
            ),
            (
                "stall_angle_mae",
                "lower_bound",
                "degree",
                stall_mae_lower,
                None,
                "Minimum absolute stall-angle error consistent with right-censoring at 20 degrees.",
            ),
        ]
        for quantity, status, unit, lower, upper, interpretation in bounded:
            add_censoring_row(
                rows,
                **common,
                quantity=quantity,
                status=status,
                unit=unit,
                estimate=None,
                lower_bound=lower,
                upper_bound=upper,
                interpretation=interpretation,
            )

    return pd.DataFrame(rows)


def paired_comparison_summary(common: pd.DataFrame) -> pd.DataFrame:
    work = common.copy()
    work["delta_drag_counts"] = work["err_cd_mean8"] - work["err_cd_xfoil"]
    work["delta_lift"] = work["err_cl_mean8"] - work["err_cl_xfoil"]

    specifications = [
        ("source_airfoil_entry", "entry", None),
        ("nominal_airfoil", "airfoil", None),
        ("source_stratified_entry", "entry", "source"),
    ]
    outcomes = [
        ("drag", "delta_drag_counts", "drag_count"),
        ("lift", "delta_lift", "C_L"),
    ]
    rows: list[dict[str, Any]] = []
    for outcome, value, unit in outcomes:
        for specification, cluster, stratify in specifications:
            stream_name = f"paired_mean8_minus_xfoil::{outcome}::{specification}"
            result = cluster_bootstrap_mean(
                work,
                value,
                cluster,
                stream_name,
                stratify=stratify,
            )
            rows.append(
                {
                    "contrast": "NeuralFoil mean-of-eight minus XFOIL",
                    "outcome": outcome,
                    "unit": unit,
                    "bootstrap_specification": specification,
                    **result,
                }
            )

    output = pd.DataFrame(rows)
    expected = {"drag": -5.304839021147271, "lift": -0.006630976794985437}
    for outcome, value in expected.items():
        estimates = output.loc[output["outcome"].eq(outcome), "estimate"].to_numpy()
        if not np.allclose(estimates, value, rtol=0.0, atol=1e-12):
            raise RuntimeError(f"Unexpected paired {outcome} estimate")
    return output


def fixed_transfer_rows(clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate ordinary and nominal-airfoil-exclusive source transfer.

    The strict specification removes every training row whose nominal airfoil
    name occurs in the held-source test set.  Both models remain fixed while
    test source-airfoil entries are resampled, so the intervals describe test
    composition uncertainty rather than model-training uncertainty.
    """

    design, features, target = clean_ridge.make_design(clean)
    source = design["source"]
    specifications = [
        (
            "train_volumes_1_3_test_soartech_8",
            "Train Volumes 1-3; test SoarTech 8",
            source.ne("stec8").to_numpy(),
            source.eq("stec8").to_numpy(),
        ),
        (
            "train_soartech_8_test_volumes_1_3",
            "Train SoarTech 8; test Volumes 1-3",
            source.eq("stec8").to_numpy(),
            source.ne("stec8").to_numpy(),
        ),
        (
            "leave_volume_1_out",
            "Leave Volume 1 out",
            source.ne("vol1").to_numpy(),
            source.eq("vol1").to_numpy(),
        ),
        (
            "leave_volume_2_out",
            "Leave Volume 2 out",
            source.ne("vol2").to_numpy(),
            source.eq("vol2").to_numpy(),
        ),
        (
            "leave_volume_3_out",
            "Leave Volume 3 out",
            source.ne("vol3").to_numpy(),
            source.eq("vol3").to_numpy(),
        ),
    ]

    rows: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    for key, label, train, test in specifications:
        predicted_log_ratio = clean_ridge.fit_predict(features, target, train, test)
        held_airfoils = set(design.loc[test, "airfoil"])
        strict_train = train & ~design["airfoil"].isin(held_airfoils).to_numpy()
        if not strict_train.any() or np.any(strict_train & test):
            raise RuntimeError(f"Invalid strict training mask for {key}")
        strict_predicted_log_ratio = clean_ridge.fit_predict(
            features, target, strict_train, test
        )

        base_drag = design.loc[test, "CD_mean8"].to_numpy(dtype=float)
        measured_drag = design.loc[test, "CD_meas"].to_numpy(dtype=float)
        corrected_drag = base_drag * np.exp(
            np.clip(predicted_log_ratio, np.log(0.5), np.log(2.0))
        )
        strict_corrected_drag = base_drag * np.exp(
            np.clip(strict_predicted_log_ratio, np.log(0.5), np.log(2.0))
        )
        test_frame = design.loc[test, ["source", "airfoil", "entry"]].copy()
        test_frame["base_error_counts"] = np.abs(base_drag - measured_drag) * 1e4
        test_frame["corrected_error_counts"] = np.abs(corrected_drag - measured_drag) * 1e4
        test_frame["strict_corrected_error_counts"] = (
            np.abs(strict_corrected_drag - measured_drag) * 1e4
        )
        test_frame["paired_change_counts"] = (
            test_frame["corrected_error_counts"] - test_frame["base_error_counts"]
        )
        test_frame["strict_minus_base_counts"] = (
            test_frame["strict_corrected_error_counts"]
            - test_frame["base_error_counts"]
        )
        test_frame["strict_minus_standard_counts"] = (
            test_frame["strict_corrected_error_counts"]
            - test_frame["corrected_error_counts"]
        )

        result = cluster_bootstrap_mean(
            test_frame,
            "paired_change_counts",
            "entry",
            f"clean_ridge_fixed_test::{key}",
        )
        rows.append(
            {
                "evaluation_key": key,
                "evaluation": label,
                "training_rows": int(train.sum()),
                "test_rows": int(test.sum()),
                "test_sources": ";".join(sorted(test_frame["source"].unique())),
                "test_airfoil_names": int(test_frame["airfoil"].nunique()),
                "test_source_airfoil_entries": int(test_frame["entry"].nunique()),
                "base_mae_counts": float(test_frame["base_error_counts"].mean()),
                "corrected_mae_counts": float(test_frame["corrected_error_counts"].mean()),
                "contrast": "corrected minus base absolute drag error",
                "unit": "drag_count",
                **result,
                "uncertainty_scope": "Fixed fitted transfer model; bootstrap resamples test source-airfoil clusters only.",
            }
        )

        overlap_airfoils = sorted(set(design.loc[train, "airfoil"]) & held_airfoils)
        strict_common = {
            "evaluation_key": key,
            "evaluation": label,
            "standard_training_rows": int(train.sum()),
            "strict_training_rows": int(strict_train.sum()),
            "training_rows_removed": int(train.sum() - strict_train.sum()),
            "overlapping_nominal_airfoil_names": int(len(overlap_airfoils)),
            "overlap_airfoils": ";".join(overlap_airfoils),
            "test_rows": int(test.sum()),
            "test_sources": ";".join(sorted(test_frame["source"].unique())),
            "test_airfoil_names": int(test_frame["airfoil"].nunique()),
            "test_source_airfoil_entries": int(test_frame["entry"].nunique()),
            "base_mae_counts": float(test_frame["base_error_counts"].mean()),
            "standard_corrected_mae_counts": float(
                test_frame["corrected_error_counts"].mean()
            ),
            "strict_corrected_mae_counts": float(
                test_frame["strict_corrected_error_counts"].mean()
            ),
            "unit": "drag_count",
            "uncertainty_scope": "Fixed fitted transfer models; bootstrap resamples test source-airfoil clusters only.",
        }
        for contrast_key, value, contrast_label in [
            (
                "strict_minus_base",
                "strict_minus_base_counts",
                "strict-exclusion corrected minus base absolute drag error",
            ),
            (
                "strict_minus_standard",
                "strict_minus_standard_counts",
                "strict-exclusion corrected minus ordinary-transfer corrected absolute drag error",
            ),
        ]:
            strict_result = cluster_bootstrap_mean(
                test_frame,
                value,
                "entry",
                f"clean_ridge_strict_fixed_test::{key}::{contrast_key}",
            )
            strict_rows.append(
                {
                    **strict_common,
                    "contrast_key": contrast_key,
                    "contrast": contrast_label,
                    **strict_result,
                }
            )

    output = pd.DataFrame(rows)
    expected = {
        "train_volumes_1_3_test_soartech_8": -2.3597317505466915,
        "train_soartech_8_test_volumes_1_3": -0.11341347039146785,
        "leave_volume_1_out": -5.270517388594537,
        "leave_volume_2_out": -3.903170424677633,
        "leave_volume_3_out": 1.5714956447600488,
    }
    for key, value in expected.items():
        observed = float(output.loc[output["evaluation_key"].eq(key), "estimate"].iloc[0])
        if not np.isclose(observed, value, rtol=0.0, atol=1e-12):
            raise RuntimeError(f"Unexpected clean-ridge transfer estimate for {key}")

    strict_output = pd.DataFrame(strict_rows)
    strict_expected = {
        "train_volumes_1_3_test_soartech_8": (-2.200709761744724, 355, 7),
        "train_soartech_8_test_volumes_1_3": (-0.5039126801863442, 506, 7),
        "leave_volume_1_out": (-5.258733332629056, 644, 9),
        "leave_volume_2_out": (-3.7858064938793135, 266, 3),
        "leave_volume_3_out": (1.5483575112351664, 238, 2),
    }
    for key, (value, removed, overlaps) in strict_expected.items():
        subset = strict_output.loc[
            strict_output["evaluation_key"].eq(key)
            & strict_output["contrast_key"].eq("strict_minus_base")
        ]
        if len(subset) != 1:
            raise RuntimeError(f"Missing strict transfer result for {key}")
        row = subset.iloc[0]
        checks = (
            np.isclose(row["estimate"], value, rtol=0.0, atol=1e-12),
            int(row["training_rows_removed"]) == removed,
            int(row["overlapping_nominal_airfoil_names"]) == overlaps,
        )
        if not all(checks):
            raise RuntimeError(f"Unexpected strict clean-ridge result for {key}")
        standard_estimate = float(
            output.loc[output["evaluation_key"].eq(key), "estimate"].iloc[0]
        )
        strict_vs_standard = float(
            strict_output.loc[
                strict_output["evaluation_key"].eq(key)
                & strict_output["contrast_key"].eq("strict_minus_standard"),
                "estimate",
            ].iloc[0]
        )
        if not np.isclose(
            strict_vs_standard,
            value - standard_estimate,
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError(f"Non-additive strict transfer contrasts for {key}")
    return output, strict_output


def clean_ridge_fold_sensitivity(
    clean: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Repeat nominal-airfoil-disjoint five-fold OOF scoring for 50 seeds."""

    design, features, target = clean_ridge.make_design(clean)
    airfoils = np.array(sorted(design["airfoil"].unique()), dtype=object)
    base_drag = design["CD_mean8"].to_numpy(dtype=float)
    measured_drag = design["CD_meas"].to_numpy(dtype=float)
    base_error = np.abs(base_drag - measured_drag) * 1e4

    rows: list[dict[str, Any]] = []
    for seed in range(824, 874):
        # default_rng(seed) is SeedSequence-derived.  The explicit stream name
        # records the semantic use of each prescribed fold seed.
        stream_name = f"clean_ridge_grouped_oof::fold_seed_{seed}"
        seed_sequence = np.random.SeedSequence(seed)
        rng = np.random.default_rng(seed_sequence)
        shuffled = airfoils.copy()
        rng.shuffle(shuffled)
        folds = [set(shuffled[index::5]) for index in range(5)]
        assignment_text = "|".join(
            ",".join(sorted(holdout)) for holdout in folds
        )

        oof = np.full(len(design), np.nan, dtype=float)
        fold_base: list[float] = []
        fold_corrected: list[float] = []
        fold_delta: list[float] = []
        for holdout in folds:
            test = design["airfoil"].isin(holdout).to_numpy()
            train = ~test
            predicted_log_ratio = clean_ridge.fit_predict(
                features, target, train, test
            )
            oof[test] = predicted_log_ratio
            corrected_drag = base_drag[test] * np.exp(
                np.clip(predicted_log_ratio, np.log(0.5), np.log(2.0))
            )
            corrected_error = np.abs(corrected_drag - measured_drag[test]) * 1e4
            fold_base.append(float(base_error[test].mean()))
            fold_corrected.append(float(corrected_error.mean()))
            fold_delta.append(float((corrected_error - base_error[test]).mean()))

        if np.isnan(oof).any():
            raise RuntimeError(f"Fold seed {seed} left unscored rows")
        corrected_drag = base_drag * np.exp(
            np.clip(oof, np.log(0.5), np.log(2.0))
        )
        corrected_error = np.abs(corrected_drag - measured_drag) * 1e4
        rows.append(
            {
                "fold_seed": seed,
                "folds": 5,
                "rows": int(len(design)),
                "nominal_airfoil_names": int(len(airfoils)),
                "source_airfoil_entries": int(design["entry"].nunique()),
                "pooled_base_mae_counts": float(base_error.mean()),
                "pooled_corrected_mae_counts": float(corrected_error.mean()),
                "pooled_paired_change_counts": float(
                    (corrected_error - base_error).mean()
                ),
                "equal_fold_base_mae_counts": float(np.mean(fold_base)),
                "equal_fold_corrected_mae_counts": float(
                    np.mean(fold_corrected)
                ),
                "equal_fold_paired_change_counts": float(np.mean(fold_delta)),
                "minimum_fold_paired_change_counts": float(np.min(fold_delta)),
                "maximum_fold_paired_change_counts": float(np.max(fold_delta)),
                "rng_stream_name": stream_name,
                "rng_seed_sequence_entropy": seed,
                "fold_assignment_sha256": hashlib.sha256(
                    assignment_text.encode("utf-8")
                ).hexdigest(),
            }
        )

    output = pd.DataFrame(rows)
    if output["fold_seed"].tolist() != list(range(824, 874)):
        raise RuntimeError("Unexpected clean-ridge fold-seed series")
    seed_824 = output.loc[output["fold_seed"].eq(824)].iloc[0]
    expected_824 = {
        "pooled_corrected_mae_counts": 29.63126416819964,
        "pooled_paired_change_counts": -3.7699126617955945,
        "equal_fold_paired_change_counts": -3.736821864892824,
    }
    for metric, expected in expected_824.items():
        if not np.isclose(seed_824[metric], expected, rtol=0.0, atol=1e-12):
            raise RuntimeError(f"Unexpected seed-824 fold sensitivity {metric}")

    summary_rows: list[dict[str, Any]] = []
    for metric in [
        "pooled_corrected_mae_counts",
        "pooled_paired_change_counts",
        "equal_fold_corrected_mae_counts",
        "equal_fold_paired_change_counts",
    ]:
        values = output[metric].to_numpy(dtype=float)
        summary_rows.append(
            {
                "metric": metric,
                "unit": "drag_count",
                "fold_assignments": int(len(values)),
                "seed_first": 824,
                "seed_last": 873,
                "mean": float(values.mean()),
                "standard_deviation": float(values.std(ddof=1)),
                "minimum": float(values.min()),
                "quantile_0_025": float(np.quantile(values, 0.025)),
                "median": float(np.median(values)),
                "quantile_0_975": float(np.quantile(values, 0.975)),
                "maximum": float(values.max()),
                "share_below_zero": float((values < 0).mean()),
                "interpretation": "Sensitivity distribution across deterministic grouped-fold assignments; not a sampling confidence interval.",
            }
        )
    summary = pd.DataFrame(summary_rows)
    pooled_delta = summary.loc[
        summary["metric"].eq("pooled_paired_change_counts")
    ].iloc[0]
    if not np.isclose(
        pooled_delta["mean"], -3.7082214954251747, rtol=0.0, atol=1e-12
    ):
        raise RuntimeError("Unexpected 50-seed pooled clean-ridge sensitivity")
    return output, summary


def _expit(values: np.ndarray) -> np.ndarray:
    """Stable logistic transform without an additional runtime dependency."""

    output = np.empty_like(values, dtype=float)
    positive = values >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponential = np.exp(values[~positive])
    output[~positive] = exponential / (1.0 + exponential)
    return output


def _fit_logistic_calibration(
    outcome: np.ndarray,
    logit_probability: np.ndarray,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Newton fit for calibration intercept and slope."""

    if weights is None:
        weights = np.ones_like(outcome, dtype=float)
    beta = np.array([0.0, 1.0], dtype=float)
    for _ in range(60):
        probability = _expit(beta[0] + beta[1] * logit_probability)
        residual = weights * (outcome - probability)
        variance_weight = weights * probability * (1.0 - probability)
        score = np.array(
            [residual.sum(), np.dot(residual, logit_probability)], dtype=float
        )
        information = np.array(
            [
                [
                    variance_weight.sum(),
                    np.dot(variance_weight, logit_probability),
                ],
                [
                    np.dot(variance_weight, logit_probability),
                    np.dot(variance_weight, logit_probability**2),
                ],
            ],
            dtype=float,
        )
        step = np.linalg.solve(information, score)
        beta += step
        if np.max(np.abs(step)) < 1e-12:
            return beta
    raise RuntimeError("Calibration Newton fit did not converge")


def risk_calibration_summary() -> pd.DataFrame:
    """Cluster-bootstrap calibration of frozen multivariable OOF risks."""

    risk_path = OUT / "risk_model_oof.csv"
    risk = pd.read_csv(risk_path)
    required = [
        "source",
        "airfoil",
        "entry",
        "large_error",
        "risk_probability_multivariable",
    ]
    if risk[required].isna().any().any():
        raise RuntimeError("Missing values in frozen risk-model OOF artifact")
    outcome = risk["large_error"].to_numpy(dtype=float)
    probability = risk["risk_probability_multivariable"].to_numpy(dtype=float)
    if (
        len(risk) != 8653
        or risk["entry"].nunique() != 135
        or not np.isin(outcome, [0.0, 1.0]).all()
        or not ((probability > 0.0) & (probability < 1.0)).all()
    ):
        raise RuntimeError("Unexpected frozen risk-model OOF cohort")

    clipped = np.clip(probability, 1e-12, 1.0 - 1e-12)
    logit_probability = np.log(clipped / (1.0 - clipped))
    calibration = _fit_logistic_calibration(outcome, logit_probability)
    bin_id = pd.qcut(
        pd.Series(probability).rank(method="first"),
        10,
        labels=False,
    ).to_numpy(dtype=int)
    prevalence = float(outcome.mean())
    brier = float(np.mean((probability - outcome) ** 2))
    null_brier = float(prevalence * (1.0 - prevalence))
    brier_skill = float(1.0 - brier / null_brier)
    ece = float(
        sum(
            abs(outcome[bin_id == index].sum() - probability[bin_id == index].sum())
            for index in range(10)
        )
        / len(risk)
    )

    cluster_codes, clusters = pd.factorize(risk["entry"], sort=True)
    n_cluster = len(clusters)
    cluster_count = np.bincount(cluster_codes, minlength=n_cluster).astype(float)
    cluster_outcome = np.bincount(
        cluster_codes, weights=outcome, minlength=n_cluster
    ).astype(float)
    cluster_squared_error = np.bincount(
        cluster_codes,
        weights=(probability - outcome) ** 2,
        minlength=n_cluster,
    ).astype(float)
    cluster_bin_outcome = np.zeros((n_cluster, 10), dtype=float)
    cluster_bin_probability = np.zeros((n_cluster, 10), dtype=float)
    for index in range(10):
        mask = bin_id == index
        cluster_bin_outcome[:, index] = np.bincount(
            cluster_codes[mask], weights=outcome[mask], minlength=n_cluster
        )
        cluster_bin_probability[:, index] = np.bincount(
            cluster_codes[mask], weights=probability[mask], minlength=n_cluster
        )

    stream_name = "risk_calibration::source_airfoil_entry"
    rng, seed_metadata = named_rng(stream_name)
    metric_names = [
        "calibration_intercept",
        "calibration_slope",
        "ece_10_fixed_deciles",
        "brier_score",
        "prevalence_only_brier",
        "brier_skill",
        "event_prevalence",
    ]
    draws = {metric: np.empty(N_BOOT_RISK, dtype=float) for metric in metric_names}
    for start in range(0, N_BOOT_RISK, RISK_BOOTSTRAP_CHUNK):
        stop = min(start + RISK_BOOTSTRAP_CHUNK, N_BOOT_RISK)
        size = stop - start
        multiplicity = rng.multinomial(
            n_cluster,
            np.full(n_cluster, 1.0 / n_cluster),
            size=size,
        )
        row_weights = multiplicity[:, cluster_codes].astype(float, copy=False)

        beta = np.repeat(calibration[None, :], size, axis=0)
        for _ in range(60):
            eta = (
                beta[:, [0]]
                + beta[:, [1]] * logit_probability[None, :]
            )
            fitted = _expit(eta)
            residual = row_weights * (outcome[None, :] - fitted)
            variance_weight = row_weights * fitted * (1.0 - fitted)
            score_0 = residual.sum(axis=1)
            score_1 = residual @ logit_probability
            info_00 = variance_weight.sum(axis=1)
            info_01 = variance_weight @ logit_probability
            info_11 = variance_weight @ (logit_probability**2)
            determinant = info_00 * info_11 - info_01**2
            if np.any(determinant <= 0.0):
                raise RuntimeError("Singular bootstrap calibration information")
            step_0 = (score_0 * info_11 - score_1 * info_01) / determinant
            step_1 = (score_1 * info_00 - score_0 * info_01) / determinant
            beta[:, 0] += step_0
            beta[:, 1] += step_1
            if np.max(np.maximum(np.abs(step_0), np.abs(step_1))) < 1e-10:
                break
        else:
            raise RuntimeError("Bootstrap calibration Newton fit did not converge")

        total = multiplicity @ cluster_count
        event_total = multiplicity @ cluster_outcome
        bootstrap_prevalence = event_total / total
        bootstrap_brier = (multiplicity @ cluster_squared_error) / total
        bootstrap_null_brier = bootstrap_prevalence * (1.0 - bootstrap_prevalence)
        bootstrap_ece = (
            np.abs(
                multiplicity @ cluster_bin_outcome
                - multiplicity @ cluster_bin_probability
            ).sum(axis=1)
            / total
        )

        draws["calibration_intercept"][start:stop] = beta[:, 0]
        draws["calibration_slope"][start:stop] = beta[:, 1]
        draws["ece_10_fixed_deciles"][start:stop] = bootstrap_ece
        draws["brier_score"][start:stop] = bootstrap_brier
        draws["prevalence_only_brier"][start:stop] = bootstrap_null_brier
        draws["brier_skill"][start:stop] = 1.0 - (
            bootstrap_brier / bootstrap_null_brier
        )
        draws["event_prevalence"][start:stop] = bootstrap_prevalence

    point_estimates = {
        "calibration_intercept": float(calibration[0]),
        "calibration_slope": float(calibration[1]),
        "ece_10_fixed_deciles": ece,
        "brier_score": brier,
        "prevalence_only_brier": null_brier,
        "brier_skill": brier_skill,
        "event_prevalence": prevalence,
    }
    units = {
        "calibration_intercept": "log_odds",
        "calibration_slope": "dimensionless",
        "ece_10_fixed_deciles": "probability",
        "brier_score": "score",
        "prevalence_only_brier": "score",
        "brier_skill": "dimensionless",
        "event_prevalence": "proportion",
    }
    descriptions = {
        "calibration_intercept": "Intercept in logit Pr(Y=1)=a+b*logit(frozen OOF probability); ideal value 0.",
        "calibration_slope": "Slope in logit Pr(Y=1)=a+b*logit(frozen OOF probability); ideal value 1.",
        "ece_10_fixed_deciles": "Expected calibration error using ten equal-count bins fixed from the original OOF ranking.",
        "brier_score": "Mean squared error of the frozen multivariable OOF probability.",
        "prevalence_only_brier": "Brier score of the replicate-specific constant-prevalence predictor.",
        "brier_skill": "One minus model Brier score divided by prevalence-only Brier score; positive favors the model.",
        "event_prevalence": "Share of rows with drag error greater than the prespecified large-error threshold.",
    }
    rows: list[dict[str, Any]] = []
    for metric in metric_names:
        low, high = percentile_interval(draws[metric])
        rows.append(
            {
                "metric": metric,
                "estimate": point_estimates[metric],
                "ci_low": low,
                "ci_high": high,
                "bootstrap_standard_error": float(draws[metric].std(ddof=1)),
                "unit": units[metric],
                "description": descriptions[metric],
                "rows": int(len(risk)),
                "source_airfoil_clusters": n_cluster,
                "bootstrap_replicates": N_BOOT_RISK,
                "ci_level": CI_LEVEL,
                "ci_method": "nonparametric percentile source-airfoil cluster bootstrap",
                "rng_stream_name": seed_metadata["name"],
                "rng_master_seed": seed_metadata["master_seed"],
                "rng_spawn_key_0": seed_metadata["spawn_key"][0],
                "rng_spawn_key_1": seed_metadata["spawn_key"][1],
                "rng_name_sha256": seed_metadata["name_sha256"],
            }
        )
    output = pd.DataFrame(rows)
    expected = {
        "calibration_intercept": -0.0065008239685103554,
        "calibration_slope": 0.9829469702906878,
        "ece_10_fixed_deciles": 0.028719569681608745,
        "brier_score": 0.16196788459591044,
        "brier_skill": 0.32563810126358395,
        "event_prevalence": 0.4009014214723217,
    }
    for metric, value in expected.items():
        observed = float(output.loc[output["metric"].eq(metric), "estimate"].iloc[0])
        if not np.isclose(observed, value, rtol=0.0, atol=2e-12):
            raise RuntimeError(f"Unexpected risk calibration metric {metric}")
    return output


def model_size_rank_summary(clean: pd.DataFrame) -> pd.DataFrame:
    """Joint cluster bootstrap for model-size ranks and simultaneous contrasts."""

    work = clean.copy()
    model_outputs = [*base.SIZES, "mean-of-eight"]
    for size in base.SIZES:
        work[f"drag::{size}"] = np.abs(work[f"CD_{size}"] - work["CD_meas"]) * 1e4
        work[f"lift::{size}"] = np.abs(work[f"CL_{size}"] - work["CL_meas"])
    work["drag::mean-of-eight"] = work["err_cd_mean8"]
    work["lift::mean-of-eight"] = work["err_cl_mean8"]

    rows: list[dict[str, Any]] = []
    for outcome, unit, reference in [
        ("drag", "drag_count", "medium"),
        ("lift", "C_L", "xxsmall"),
    ]:
        columns = [f"{outcome}::{name}" for name in model_outputs]
        grouped = work.groupby("entry", sort=True)[columns].agg(["sum", "count"])
        sums = np.column_stack(
            [grouped[(column, "sum")].to_numpy(dtype=float) for column in columns]
        )
        counts = grouped[(columns[0], "count")].to_numpy(dtype=float)
        n_cluster = len(grouped)
        point = work[columns].mean().to_numpy(dtype=float)
        bootstrap = np.empty((N_BOOT, len(columns)), dtype=float)

        stream_name = f"model_size_joint_rank::{outcome}"
        rng, seed_metadata = named_rng(stream_name)
        for start in range(0, N_BOOT, BOOTSTRAP_CHUNK):
            stop = min(start + BOOTSTRAP_CHUNK, N_BOOT)
            size = stop - start
            multiplicity = rng.multinomial(
                n_cluster,
                np.full(n_cluster, 1.0 / n_cluster),
                size=size,
            )
            bootstrap[start:stop] = (multiplicity @ sums) / (multiplicity @ counts)[:, None]

        winner = np.argmin(bootstrap, axis=1)
        winner_frequency = np.bincount(winner, minlength=len(model_outputs)) / N_BOOT
        reference_index = model_outputs.index(reference)
        delta_point = point - point[reference_index]
        delta_bootstrap = bootstrap - bootstrap[:, [reference_index]]
        comparison_indices = [
            index for index in range(len(model_outputs)) if index != reference_index
        ]
        standard_errors = delta_bootstrap[:, comparison_indices].std(axis=0, ddof=1)
        if np.any(standard_errors <= 0):
            raise RuntimeError(f"Degenerate model-size bootstrap for {outcome}")
        standardized = np.abs(
            (
                delta_bootstrap[:, comparison_indices]
                - delta_point[comparison_indices][None, :]
            )
            / standard_errors[None, :]
        )
        max_t_critical = float(np.quantile(standardized.max(axis=1), CI_LEVEL))

        for index, model_output in enumerate(model_outputs):
            if index == reference_index:
                point_low = point_high = simultaneous_low = simultaneous_high = 0.0
                standard_error = 0.0
            else:
                point_low, point_high = percentile_interval(delta_bootstrap[:, index])
                se_index = comparison_indices.index(index)
                standard_error = float(standard_errors[se_index])
                simultaneous_low = float(delta_point[index] - max_t_critical * standard_error)
                simultaneous_high = float(delta_point[index] + max_t_critical * standard_error)
            rows.append(
                {
                    "outcome": outcome,
                    "unit": unit,
                    "model_output": model_output,
                    "reference_output": reference,
                    "point_mae": float(point[index]),
                    "delta_vs_reference": float(delta_point[index]),
                    "delta_pointwise_ci_low": float(point_low),
                    "delta_pointwise_ci_high": float(point_high),
                    "delta_simultaneous_ci_low": float(simultaneous_low),
                    "delta_simultaneous_ci_high": float(simultaneous_high),
                    "bootstrap_standard_error": standard_error,
                    "bootstrap_winner_frequency": float(winner_frequency[index]),
                    "bootstrap_replicates": N_BOOT,
                    "source_airfoil_clusters": n_cluster,
                    "simultaneous_family_size": len(comparison_indices),
                    "simultaneous_method": "single-level cluster-bootstrap max-t band for all nonreference contrasts",
                    "max_t_critical": max_t_critical,
                    "rng_stream_name": seed_metadata["name"],
                    "rng_master_seed": seed_metadata["master_seed"],
                    "rng_spawn_key_0": seed_metadata["spawn_key"][0],
                    "rng_spawn_key_1": seed_metadata["spawn_key"][1],
                    "rng_name_sha256": seed_metadata["name_sha256"],
                }
            )

    output = pd.DataFrame(rows)
    observed_winners = {
        outcome: group.loc[group["point_mae"].idxmin(), "model_output"]
        for outcome, group in output.groupby("outcome")
    }
    if observed_winners != {"drag": "medium", "lift": "xxsmall"}:
        raise RuntimeError(f"Unexpected observed model-size winners: {observed_winners}")
    return output


def transonic_sweep_summary() -> pd.DataFrame:
    scores_path = DATA / "holdout-scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for source, sweeps in scores.items():
        stock = np.array([float(item["mae_stock"]) for item in sweeps.values()])
        model = np.array([float(item["mae_model"]) for item in sweeps.values()])
        change = model - stock
        improved = int((change < 0).sum())
        worsened = int((change > 0).sum())
        tied = int((change == 0).sum())
        rows.append(
            {
                "source": source,
                "sweeps": int(len(change)),
                "stock_mean_sweep_mae_counts": float(stock.mean()),
                "model_mean_sweep_mae_counts": float(model.mean()),
                "mean_paired_change_counts": float(change.mean()),
                "median_paired_change_counts": float(np.median(change)),
                "improved_sweeps": improved,
                "worsened_sweeps": worsened,
                "tied_sweeps": tied,
                "improved_fraction": float(improved / len(change)),
                "improved_over_total": f"{improved}/{len(change)}",
                "minimum_paired_change_counts": float(change.min()),
                "maximum_paired_change_counts": float(change.max()),
            }
        )

    output = pd.DataFrame(rows)
    expected = {
        "Harris": (4, 1, 29.11679046268225, 39.40032579171856),
        "TN1546": (8, 3, -2.6008493878503636, 1.4316256499057385),
    }
    for source, (sweeps, improved, mean_change, median_change) in expected.items():
        row = output.loc[output["source"].eq(source)].iloc[0]
        checks = (
            int(row["sweeps"]) == sweeps,
            int(row["improved_sweeps"]) == improved,
            np.isclose(row["mean_paired_change_counts"], mean_change, atol=1e-12),
            np.isclose(row["median_paired_change_counts"], median_change, atol=1e-12),
        )
        if not all(checks):
            raise RuntimeError(f"Unexpected transonic sweep summary for {source}")
    return output


def to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return [to_builtin(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    if pd.isna(value):
        return None
    return value


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return to_builtin(frame.to_dict(orient="records"))


def write_outputs(
    censoring: pd.DataFrame,
    paired: pd.DataFrame,
    transfers: pd.DataFrame,
    strict_transfers: pd.DataFrame,
    fold_sensitivity: pd.DataFrame,
    fold_sensitivity_summary: pd.DataFrame,
    risk_calibration: pd.DataFrame,
    transonic: pd.DataFrame,
    model_sizes: pd.DataFrame,
) -> None:
    censoring.to_csv(CENSORING_CSV, index=False)
    paired.to_csv(PAIRED_CSV, index=False)
    transfers.to_csv(TRANSFER_CSV, index=False)
    strict_transfers.to_csv(STRICT_TRANSFER_CSV, index=False)
    fold_sensitivity.to_csv(FOLD_SENSITIVITY_CSV, index=False)
    fold_sensitivity_summary.to_csv(FOLD_SENSITIVITY_SUMMARY_CSV, index=False)
    risk_calibration.to_csv(RISK_CALIBRATION_CSV, index=False)
    transonic.to_csv(TRANSONIC_CSV, index=False)
    model_sizes.to_csv(MODEL_SIZE_CSV, index=False)

    inputs = [
        OUT / "analyze_study.py",
        OUT / "clean_only_correction_audit.py",
        OUT / "risk_model_oof.csv",
        DATA / "lsat-clmax.csv",
        DATA / "lsat-corpus.csv",
        DATA / "lsat-nf.csv",
        DATA / "lsat-xfoil.csv",
        DATA / "oof2.csv",
        DATA / "oof3.csv",
        DATA / "holdout-scores.json",
    ]
    payload = {
        "metadata": {
            "analysis": "final inference audit",
            "master_seed": MASTER_SEED,
            "bootstrap_replicates": N_BOOT,
            "risk_bootstrap_replicates": N_BOOT_RISK,
            "ci_level": CI_LEVEL,
            "numpy_version": np.__version__,
            "pandas_version": pd.__version__,
            "script_sha256": sha256_file(Path(__file__)),
            "input_sha256": {str(path.relative_to(ROOT)): sha256_file(path) for path in inputs},
            "output_files": [
                str(CENSORING_CSV.relative_to(ROOT)),
                str(PAIRED_CSV.relative_to(ROOT)),
                str(TRANSFER_CSV.relative_to(ROOT)),
                str(STRICT_TRANSFER_CSV.relative_to(ROOT)),
                str(FOLD_SENSITIVITY_CSV.relative_to(ROOT)),
                str(FOLD_SENSITIVITY_SUMMARY_CSV.relative_to(ROOT)),
                str(RISK_CALIBRATION_CSV.relative_to(ROOT)),
                str(TRANSONIC_CSV.relative_to(ROOT)),
                str(MODEL_SIZE_CSV.relative_to(ROOT)),
            ],
        },
        "censoring": records(censoring),
        "paired_mean8_minus_xfoil": records(paired),
        "clean_ridge_fixed_test_transfer": records(transfers),
        "clean_ridge_strict_nominal_airfoil_exclusion": records(strict_transfers),
        "clean_ridge_fold_assignment_sensitivity": records(fold_sensitivity),
        "clean_ridge_fold_assignment_summary": records(fold_sensitivity_summary),
        "risk_model_calibration": records(risk_calibration),
        "transonic_sweep_robustness": records(transonic),
        "model_size_rank_stability": records(model_sizes),
    }
    strict_payload = to_builtin(payload)
    JSON_PATH.write_text(
        json.dumps(strict_payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    # A strict round trip verifies that no non-standard NaN/Infinity tokens were
    # emitted.  ``allow_nan=False`` above is the enforcement point.
    json.loads(JSON_PATH.read_text(encoding="utf-8"))


def print_verification(
    censoring: pd.DataFrame,
    paired: pd.DataFrame,
    transfers: pd.DataFrame,
    strict_transfers: pd.DataFrame,
    fold_sensitivity: pd.DataFrame,
    fold_sensitivity_summary: pd.DataFrame,
    risk_calibration: pd.DataFrame,
    transonic: pd.DataFrame,
    model_sizes: pd.DataFrame,
) -> None:
    print("FINAL INFERENCE AUDIT")
    print(f"master seed={MASTER_SEED}; bootstrap replicates={N_BOOT:,}")

    bounds = censoring.loc[
        censoring["analysis_set"].eq("all_sweeps")
        & censoring["quantity"].isin(
            [
                "peak_lift_signed_bias",
                "peak_lift_mae",
                "peak_lift_overprediction_share",
                "stall_angle_signed_bias",
                "stall_angle_mae",
            ]
        )
    ]
    print("\nCensoring / partial identification (all 471 sweeps)")
    for row in bounds.itertuples(index=False):
        upper = "unbounded" if pd.isna(row.upper_bound) else f"{row.upper_bound:.9f}"
        print(f"  {row.quantity}: [{row.lower_bound:.9f}, {upper}]")

    print("\nPaired NeuralFoil mean-of-eight minus XFOIL")
    for row in paired.itertuples(index=False):
        print(
            f"  {row.outcome:4s} | {row.bootstrap_specification:25s} | "
            f"{row.estimate:+.9f} ({row.ci_low:+.9f}, {row.ci_high:+.9f})"
        )

    print("\nPost-audit clean-ridge fixed-test contrasts")
    for row in transfers.itertuples(index=False):
        print(
            f"  {row.evaluation:41s} | {row.estimate:+.9f} "
            f"({row.ci_low:+.9f}, {row.ci_high:+.9f})"
        )

    print("\nStrict nominal-airfoil-exclusive fixed-test contrasts")
    strict_base = strict_transfers.loc[
        strict_transfers["contrast_key"].eq("strict_minus_base")
    ]
    for row in strict_base.itertuples(index=False):
        print(
            f"  {row.evaluation:41s} | {row.estimate:+.9f} "
            f"({row.ci_low:+.9f}, {row.ci_high:+.9f}); "
            f"removed={row.training_rows_removed}"
        )

    pooled_delta = fold_sensitivity_summary.loc[
        fold_sensitivity_summary["metric"].eq("pooled_paired_change_counts")
    ].iloc[0]
    equal_delta = fold_sensitivity_summary.loc[
        fold_sensitivity_summary["metric"].eq(
            "equal_fold_paired_change_counts"
        )
    ].iloc[0]
    print("\nClean-ridge 50-seed fold-assignment sensitivity")
    print(
        f"  pooled delta mean={pooled_delta['mean']:+.9f}; "
        f"range=({pooled_delta['minimum']:+.9f}, {pooled_delta['maximum']:+.9f})"
    )
    print(
        f"  equal-fold delta mean={equal_delta['mean']:+.9f}; "
        f"range=({equal_delta['minimum']:+.9f}, {equal_delta['maximum']:+.9f}); "
        f"assignments={len(fold_sensitivity)}"
    )

    print("\nFrozen-OOF risk-model calibration")
    for metric in [
        "calibration_intercept",
        "calibration_slope",
        "ece_10_fixed_deciles",
        "brier_skill",
    ]:
        row = risk_calibration.loc[risk_calibration["metric"].eq(metric)].iloc[0]
        print(
            f"  {metric:28s} | {row['estimate']:+.9f} "
            f"({row['ci_low']:+.9f}, {row['ci_high']:+.9f})"
        )

    print("\nTransonic sweep robustness")
    for row in transonic.itertuples(index=False):
        print(
            f"  {row.source:7s} | median change={row.median_paired_change_counts:+.9f} | "
            f"improved={row.improved_over_total}"
        )

    print("\nModel-size rank stability and closest competitors")
    for outcome, reference, closest in [
        ("drag", "medium", "mean-of-eight"),
        ("lift", "xxsmall", "mean-of-eight"),
    ]:
        ref_row = model_sizes.loc[
            model_sizes["outcome"].eq(outcome)
            & model_sizes["model_output"].eq(reference)
        ].iloc[0]
        close_row = model_sizes.loc[
            model_sizes["outcome"].eq(outcome)
            & model_sizes["model_output"].eq(closest)
        ].iloc[0]
        print(
            f"  {outcome:4s} | {reference} winner frequency="
            f"{ref_row['bootstrap_winner_frequency']:.6f}; "
            f"{closest} minus {reference}={close_row['delta_vs_reference']:+.9f}, "
            f"simultaneous CI=({close_row['delta_simultaneous_ci_low']:+.9f}, "
            f"{close_row['delta_simultaneous_ci_high']:+.9f})"
        )

    print("\nVerified output files")
    for path in [
        CENSORING_CSV,
        PAIRED_CSV,
        TRANSFER_CSV,
        STRICT_TRANSFER_CSV,
        FOLD_SENSITIVITY_CSV,
        FOLD_SENSITIVITY_SUMMARY_CSV,
        RISK_CALIBRATION_CSV,
        TRANSONIC_CSV,
        MODEL_SIZE_CSV,
        JSON_PATH,
    ]:
        print(f"  {path.name}: {path.stat().st_size:,} bytes; sha256={sha256_file(path)}")


def main() -> None:
    clean, unique, common = base.load_low_speed()
    if (len(clean), len(unique), len(common)) != (8653, 8652, 7897):
        raise RuntimeError("Unexpected corrected low-speed cohort dimensions")

    censoring = censoring_summary()
    paired = paired_comparison_summary(common)
    transfers, strict_transfers = fixed_transfer_rows(clean)
    fold_sensitivity, fold_sensitivity_summary = clean_ridge_fold_sensitivity(clean)
    risk_calibration = risk_calibration_summary()
    transonic = transonic_sweep_summary()
    model_sizes = model_size_rank_summary(clean)
    write_outputs(
        censoring,
        paired,
        transfers,
        strict_transfers,
        fold_sensitivity,
        fold_sensitivity_summary,
        risk_calibration,
        transonic,
        model_sizes,
    )
    print_verification(
        censoring,
        paired,
        transfers,
        strict_transfers,
        fold_sensitivity,
        fold_sensitivity_summary,
        risk_calibration,
        transonic,
        model_sizes,
    )


if __name__ == "__main__":
    main()
