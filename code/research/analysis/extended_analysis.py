from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import seaborn as sns
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import analyze_study as base


ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
OUT = ROOT / "analysis"
REPO = ROOT / "source" / "neuralfoil_repo"
RNG = np.random.default_rng(20260904)
N_BOOT = 4000

COLORS = {
    "xfoil": "#6B7280",
    "xlarge": "#315B8A",
    "mean8": "#2E7D5B",
    "risk": "#B42318",
    "amber": "#B66A16",
    "ink": "#17212B",
    "muted": "#667085",
    "light": "#E9EEF3",
}


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10.5,
            "axes.labelsize": 9,
            "axes.titleweight": "bold",
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "figure.dpi": 150,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def cluster_bootstrap_mean(
    df: pd.DataFrame,
    value: str,
    cluster: str = "entry",
    n_boot: int = N_BOOT,
) -> dict[str, float | int]:
    agg = df.groupby(cluster, sort=False)[value].agg(["sum", "count"])
    sums = agg["sum"].to_numpy(float)
    counts = agg["count"].to_numpy(float)
    n = len(agg)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        idx = RNG.integers(0, n, n)
        draws[b] = sums[idx].sum() / counts[idx].sum()
    return {
        "estimate": float(df[value].mean()),
        "ci_low": float(np.quantile(draws, 0.025)),
        "ci_high": float(np.quantile(draws, 0.975)),
        "clusters": int(n),
        "rows": int(len(df)),
    }


def cluster_bootstrap_group_difference(
    df: pd.DataFrame,
    value: str,
    group: str,
    reference: object,
    comparison: object,
    cluster: str = "entry",
    n_boot: int = N_BOOT,
) -> dict[str, float | int | str]:
    levels = [reference, comparison]
    grouped = (
        df.loc[df[group].isin(levels)]
        .groupby([cluster, group], sort=False)[value]
        .agg(["sum", "count"])
    )
    clusters = grouped.index.get_level_values(0).unique()
    arrays: dict[object, tuple[np.ndarray, np.ndarray]] = {}
    for level in levels:
        level_frame = grouped.xs(level, level=group, drop_level=True).reindex(clusters).fillna(0)
        arrays[level] = (
            level_frame["sum"].to_numpy(float),
            level_frame["count"].to_numpy(float),
        )
    n = len(clusters)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        idx = RNG.integers(0, n, n)
        means = {}
        for level in levels:
            sums, counts = arrays[level]
            means[level] = sums[idx].sum() / counts[idx].sum()
        draws[b] = means[comparison] - means[reference]
    ref_mean = float(df.loc[df[group].eq(reference), value].mean())
    cmp_mean = float(df.loc[df[group].eq(comparison), value].mean())
    return {
        "contrast": f"{comparison} minus {reference}",
        "reference_mean": ref_mean,
        "comparison_mean": cmp_mean,
        "estimate": cmp_mean - ref_mean,
        "ci_low": float(np.quantile(draws, 0.025)),
        "ci_high": float(np.quantile(draws, 0.975)),
        "clusters": int(n),
        "rows": int(len(df)),
    }


def cluster_bootstrap_auc(
    df: pd.DataFrame,
    outcome: str,
    score: str,
    cluster: str = "entry",
    n_boot: int = 2500,
) -> dict[str, float | int]:
    d = df[[cluster, outcome, score]].dropna().copy()
    clusters, row_cluster = np.unique(d[cluster].astype(str), return_inverse=True)
    y = d[outcome].astype(int).to_numpy()
    s = d[score].to_numpy(float)
    probabilistic = bool(np.all((s >= 0) & (s <= 1)))
    n = len(clusters)
    auc = np.empty(n_boot)
    ap = np.empty(n_boot)
    brier = np.empty(n_boot)
    for b in range(n_boot):
        sampled = RNG.integers(0, n, n)
        multiplicity = np.bincount(sampled, minlength=n)
        weights = multiplicity[row_cluster]
        if weights[y == 1].sum() == 0 or weights[y == 0].sum() == 0:
            auc[b] = np.nan
            ap[b] = np.nan
            brier[b] = np.nan
            continue
        auc[b] = roc_auc_score(y, s, sample_weight=weights)
        ap[b] = average_precision_score(y, s, sample_weight=weights)
        if probabilistic:
            brier[b] = brier_score_loss(y, s, sample_weight=weights)
    return {
        "auroc": float(roc_auc_score(y, s)),
        "auroc_ci_low": float(np.nanquantile(auc, 0.025)),
        "auroc_ci_high": float(np.nanquantile(auc, 0.975)),
        "average_precision": float(average_precision_score(y, s)),
        "average_precision_ci_low": float(np.nanquantile(ap, 0.025)),
        "average_precision_ci_high": float(np.nanquantile(ap, 0.975)),
        "brier_score": float(brier_score_loss(y, s)) if probabilistic else None,
        "brier_ci_low": float(np.nanquantile(brier, 0.025)) if probabilistic else None,
        "brier_ci_high": float(np.nanquantile(brier, 0.975)) if probabilistic else None,
        "event_prevalence": float(y.mean()),
        "clusters": int(n),
        "rows": int(len(d)),
    }


def add_xfoil_availability(unique: pd.DataFrame, common: pd.DataFrame) -> pd.DataFrame:
    keys = ["entry", "Re_key", "alpha_key"]
    available = common[keys].drop_duplicates().assign(xfoil_output_returned=True)
    d = unique.merge(available, how="left", on=keys, validate="one_to_one")
    d["xfoil_output_returned"] = d["xfoil_output_returned"].eq(True)
    d["abs_alpha"] = d["alpha"].abs()
    d["abs_cl_meas"] = d["CL_meas"].abs()
    return d


def availability_tables(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source = (
        d.groupby("source", as_index=False)
        .agg(
            eligible_conditions=("xfoil_output_returned", "size"),
            returned_conditions=("xfoil_output_returned", "sum"),
            availability_share=("xfoil_output_returned", "mean"),
            airfoil_entries=("entry", "nunique"),
        )
        .sort_values("source")
    )
    re_bins = [0, 45e3, 75e3, 150e3, 250e3, 350e3, 600e3]
    re_labels = ["<45k", "45-75k", "75-150k", "150-250k", "250-350k", "350-600k"]
    d["Re_band"] = pd.cut(d["Re"], bins=re_bins, labels=re_labels, right=False)
    re_table = (
        d.groupby("Re_band", observed=True)
        .agg(
            eligible_conditions=("xfoil_output_returned", "size"),
            returned_conditions=("xfoil_output_returned", "sum"),
            availability_share=("xfoil_output_returned", "mean"),
        )
        .reset_index()
    )
    alpha_bins = [-10, -4, 0, 4, 8, 12, 18]
    alpha_labels = ["-10:-4", "-4:0", "0:4", "4:8", "8:12", "12:18"]
    d["alpha_band"] = pd.cut(d["alpha"], bins=alpha_bins, labels=alpha_labels, right=False)
    alpha = (
        d.groupby("alpha_band", observed=True)
        .agg(
            eligible_conditions=("xfoil_output_returned", "size"),
            returned_conditions=("xfoil_output_returned", "sum"),
            availability_share=("xfoil_output_returned", "mean"),
        )
        .reset_index()
    )
    source.to_csv(OUT / "xfoil_availability_by_source.csv", index=False)
    re_table.to_csv(OUT / "xfoil_availability_by_re_extended.csv", index=False)
    alpha.to_csv(OUT / "xfoil_availability_by_alpha.csv", index=False)
    return source, re_table, alpha


def missingness_audit(d: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict]]:
    features = {
        "Re_k": d["Re"] / 1000,
        "abs_alpha_deg": d["abs_alpha"],
        "thickness_ratio": d["tc"],
        "abs_measured_lift": d["abs_cl_meas"],
        "measured_drag_counts": d["CD_meas"] * 1e4,
        "mean8_drag_abs_error_counts": d["err_cd_mean8"],
        "mean8_lift_abs_error": d["err_cl_mean8"],
        "model_size_disagreement_counts": d["spread_counts"],
        "reported_confidence": d["conf_xlarge"],
    }
    work = d[["entry", "xfoil_output_returned"]].copy()
    for name, values in features.items():
        work[name] = values
    rows = []
    contrasts: dict[str, dict] = {}
    for name in features:
        returned = work.loc[work["xfoil_output_returned"], name]
        absent = work.loc[~work["xfoil_output_returned"], name]
        pooled = np.sqrt((returned.var(ddof=1) + absent.var(ddof=1)) / 2)
        rows.append(
            {
                "quantity": name,
                "returned_mean": float(returned.mean()),
                "absent_mean": float(absent.mean()),
                "absent_minus_returned": float(absent.mean() - returned.mean()),
                "standardized_mean_difference": float((absent.mean() - returned.mean()) / pooled),
                "returned_median": float(returned.median()),
                "absent_median": float(absent.median()),
            }
        )
        contrasts[name] = cluster_bootstrap_group_difference(
            work,
            name,
            "xfoil_output_returned",
            True,
            False,
        )
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "xfoil_selection_audit.csv", index=False)
    return table, contrasts


def distribution_summary(common: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("XFOIL", "CD", "CD_xf", "CD_meas", 1e4),
        ("NeuralFoil xlarge", "CD", "CD_xlarge", "CD_meas", 1e4),
        ("NeuralFoil mean-of-eight", "CD", "CD_mean8", "CD_meas", 1e4),
        ("XFOIL", "CL", "CL_xf", "CL_meas", 1.0),
        ("NeuralFoil xlarge", "CL", "CL_xlarge", "CL_meas", 1.0),
        ("NeuralFoil mean-of-eight", "CL", "CL_mean8", "CL_meas", 1.0),
    ]
    rows = []
    for model, outcome, pred, measured, scale in specs:
        signed = (common[pred] - common[measured]) * scale
        absolute = signed.abs()
        threshold_1 = 20 if outcome == "CD" else 0.10
        threshold_2 = 50 if outcome == "CD" else 0.20
        rows.append(
            {
                "model": model,
                "outcome": outcome,
                "n": int(len(common)),
                "mae": float(absolute.mean()),
                "median_absolute_error": float(absolute.median()),
                "p90_absolute_error": float(absolute.quantile(0.90)),
                "p95_absolute_error": float(absolute.quantile(0.95)),
                "rmse": float(np.sqrt(np.mean(signed**2))),
                "mean_signed_bias": float(signed.mean()),
                "median_signed_bias": float(signed.median()),
                "underprediction_share": float((signed < 0).mean()),
                "above_threshold_1_share": float((absolute > threshold_1).mean()),
                "above_threshold_2_share": float((absolute > threshold_2).mean()),
                "threshold_1": threshold_1,
                "threshold_2": threshold_2,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "common_distribution_and_bias.csv", index=False)
    return out


def weighting_sensitivity(common: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict]]:
    models = {
        "XFOIL": ("err_cd_xfoil", "err_cl_xfoil"),
        "NeuralFoil xlarge": ("err_cd_xlarge", "err_cl_xlarge"),
        "NeuralFoil mean-of-eight": ("err_cd_mean8", "err_cl_mean8"),
    }
    rows = []
    for outcome_idx, outcome in enumerate(["CD", "CL"]):
        cols = {model: pair[outcome_idx] for model, pair in models.items()}
        for estimand in ["point-weighted", "airfoil-entry macro", "source macro"]:
            for model, col in cols.items():
                if estimand == "point-weighted":
                    value = common[col].mean()
                elif estimand == "airfoil-entry macro":
                    value = common.groupby("entry")[col].mean().mean()
                else:
                    value = common.groupby("source")[col].mean().mean()
                rows.append(
                    {
                        "outcome": outcome,
                        "estimand": estimand,
                        "model": model,
                        "absolute_error": float(value),
                    }
                )
    weight = pd.DataFrame(rows)
    weight.to_csv(OUT / "weighting_sensitivity.csv", index=False)

    source_rows = []
    contrasts: dict[str, dict] = {}
    for source, g in common.groupby("source", sort=True):
        for outcome, nf_col, xf_col in [
            ("CD", "err_cd_mean8", "err_cd_xfoil"),
            ("CL", "err_cl_mean8", "err_cl_xfoil"),
        ]:
            delta = f"delta_{outcome.lower()}_mean8_minus_xfoil"
            gg = g.copy()
            gg[delta] = gg[nf_col] - gg[xf_col]
            interval = cluster_bootstrap_mean(gg, delta)
            contrasts[f"{source}_{outcome}"] = interval
            source_rows.append(
                {
                    "source": source,
                    "outcome": outcome,
                    "conditions": int(len(g)),
                    "airfoil_entries": int(g["entry"].nunique()),
                    "xfoil_mae": float(g[xf_col].mean()),
                    "mean8_mae": float(g[nf_col].mean()),
                    "mean8_minus_xfoil": interval["estimate"],
                    "ci_low": interval["ci_low"],
                    "ci_high": interval["ci_high"],
                }
            )
    source_table = pd.DataFrame(source_rows)
    source_table.to_csv(OUT / "source_specific_head_to_head.csv", index=False)
    return weight, source_table, contrasts


def airfoil_level_wins(common: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome, nf, xf in [
        ("CD", "err_cd_mean8", "err_cd_xfoil"),
        ("CL", "err_cl_mean8", "err_cl_xfoil"),
    ]:
        entry = common.groupby(["source", "entry"], as_index=False)[[nf, xf]].mean()
        entry["nf_better"] = entry[nf] < entry[xf]
        rows.append(
            {
                "source": "All sources",
                "outcome": outcome,
                "airfoil_entries": int(len(entry)),
                "nf_better_share": float(entry["nf_better"].mean()),
                "median_entry_difference": float((entry[nf] - entry[xf]).median()),
            }
        )
        for source, g in entry.groupby("source"):
            rows.append(
                {
                    "source": source,
                    "outcome": outcome,
                    "airfoil_entries": int(len(g)),
                    "nf_better_share": float(g["nf_better"].mean()),
                    "median_entry_difference": float((g[nf] - g[xf]).median()),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "airfoil_level_win_rates.csv", index=False)
    return out


def risk_diagnostics(clean: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict]]:
    d = clean.copy()
    d["large_error"] = d["err_cd_mean8"] > 20
    d["risk_from_confidence"] = -d["conf_xlarge"]
    d["risk_from_disagreement"] = d["spread_counts"]
    aucs = {
        "confidence": cluster_bootstrap_auc(d, "large_error", "risk_from_confidence"),
        "disagreement": cluster_bootstrap_auc(d, "large_error", "risk_from_disagreement"),
    }

    spread_q50 = d["spread_counts"].quantile(0.50)
    spread_q75 = d["spread_counts"].quantile(0.75)
    spread_q90 = d["spread_counts"].quantile(0.90)
    definitions = [
        ("All conditions", np.ones(len(d), dtype=bool)),
        ("Lowest 50% disagreement", d["spread_counts"] <= spread_q50),
        ("Highest 25% disagreement", d["spread_counts"] >= spread_q75),
        ("Highest 10% disagreement", d["spread_counts"] >= spread_q90),
        ("Reported confidence >0.90", d["conf_xlarge"] > 0.90),
    ]
    rows = []
    for label, mask in definitions:
        g = d.loc[mask]
        rows.append(
            {
                "stratum": label,
                "rows": int(len(g)),
                "airfoil_entries": int(g["entry"].nunique()),
                "large_error_share": float(g["large_error"].mean()),
                "median_abs_error_counts": float(g["err_cd_mean8"].median()),
                "p90_abs_error_counts": float(g["err_cd_mean8"].quantile(0.90)),
                "median_disagreement_counts": float(g["spread_counts"].median()),
                "median_confidence": float(g["conf_xlarge"].median()),
            }
        )
    strata = pd.DataFrame(rows)
    strata.to_csv(OUT / "risk_triage_strata.csv", index=False)
    return strata, aucs


def all_model_sizes(clean: pd.DataFrame, common: pd.DataFrame) -> pd.DataFrame:
    html = (REPO / "index.html").read_text()
    start = html.index("const NF = ") + len("const NF = ")
    end = html.index(";\n", start)
    archived = json.loads(html[start:end])
    timing = archived["model_comparison"]
    rows = []
    for size in base.SIZES:
        full_cd = (clean[f"CD_{size}"] - clean["CD_meas"]).abs() * 1e4
        full_cl = (clean[f"CL_{size}"] - clean["CL_meas"]).abs()
        common_cd = (common[f"CD_{size}"] - common["CD_meas"]).abs() * 1e4
        common_cl = (common[f"CL_{size}"] - common["CL_meas"]).abs()
        rows.append(
            {
                "model_output": size,
                "kind": "single network",
                "full_clean_drag_mae_counts": float(full_cd.mean()),
                "full_clean_lift_mae": float(full_cl.mean()),
                "full_clean_drag_median_counts": float(full_cd.median()),
                "full_clean_drag_p90_counts": float(full_cd.quantile(0.90)),
                "common_drag_mae_counts": float(common_cd.mean()),
                "common_lift_mae": float(common_cl.mean()),
                "archived_batch_10k_seconds": float(timing[size]["batch_10k_seconds"]),
                "archived_evaluations_per_second": float(timing[size]["evals_per_second"]),
            }
        )
    ensemble_seconds = float(sum(timing[s]["batch_10k_seconds"] for s in base.SIZES))
    rows.append(
        {
            "model_output": "mean-of-eight",
            "kind": "sequential ensemble estimate",
            "full_clean_drag_mae_counts": float(clean["err_cd_mean8"].mean()),
            "full_clean_lift_mae": float(clean["err_cl_mean8"].mean()),
            "full_clean_drag_median_counts": float(clean["err_cd_mean8"].median()),
            "full_clean_drag_p90_counts": float(clean["err_cd_mean8"].quantile(0.90)),
            "common_drag_mae_counts": float(common["err_cd_mean8"].mean()),
            "common_lift_mae": float(common["err_cl_mean8"].mean()),
            "archived_batch_10k_seconds": ensemble_seconds,
            "archived_evaluations_per_second": 10000 / ensemble_seconds,
        }
    )
    out = pd.DataFrame(rows)
    for outcome in ["full_clean_drag_mae_counts", "full_clean_lift_mae"]:
        efficient = []
        for i, row in out.iterrows():
            dominated = (
                (out[outcome] <= row[outcome])
                & (out["archived_evaluations_per_second"] >= row["archived_evaluations_per_second"])
                & (
                    (out[outcome] < row[outcome])
                    | (out["archived_evaluations_per_second"] > row["archived_evaluations_per_second"])
                )
            ).any()
            efficient.append(not bool(dominated))
        out[f"pareto_{'drag' if 'drag' in outcome else 'lift'}"] = efficient
    out["speed_relative_to_xlarge"] = (
        out["archived_evaluations_per_second"]
        / float(timing["xlarge"]["evals_per_second"])
    )
    out.to_csv(OUT / "all_model_sizes_accuracy_speed.csv", index=False)
    return out


def measurement_variability_proxy(clean: pd.DataFrame, common: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for population, d in [("full corrected-clean", clean), ("XFOIL-common", common)]:
        g = d.loc[d["u_cd_span"].gt(0)].copy()
        specs = [("NeuralFoil mean-of-eight", g["err_cd_mean8"])]
        if "err_cd_xfoil" in g:
            specs.insert(0, ("XFOIL", g["err_cd_xfoil"]))
        proxy = g["u_cd_span"] * 1e4
        for model, error in specs:
            rows.append(
                {
                    "population": population,
                    "model": model,
                    "rows_with_positive_proxy": int(len(g)),
                    "airfoil_entries": int(g["entry"].nunique()),
                    "median_proxy_half_spread_counts": float(proxy.median()),
                    "mae_counts": float(error.mean()),
                    "within_one_proxy_share": float((error <= proxy).mean()),
                    "within_two_proxy_share": float((error <= 2 * proxy).mean()),
                    "median_error_to_proxy_ratio": float((error / proxy).median()),
                    "mean_excess_beyond_proxy_counts": float(np.maximum(error - proxy, 0).mean()),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "measurement_variability_proxy.csv", index=False)
    return out


def stall_censoring_sensitivity() -> tuple[pd.DataFrame, dict[str, dict]]:
    d = pd.read_csv(base.DATA / "lsat-clmax.csv")
    d["right_censored_20deg"] = np.isclose(d["astall_mean8"], 20.0)
    d["clmax_error"] = d["clmax_mean8"] - d["clmax_meas"]
    d["clmax_abs_error"] = d["clmax_error"].abs()
    d["stall_angle_error"] = d["astall_mean8"] - d["astall_meas"]
    d["stall_angle_abs_error"] = d["stall_angle_error"].abs()
    d["overpredict_clmax"] = d["clmax_error"] > 0
    rows = []
    metrics: dict[str, dict] = {}
    for label, g in [
        ("All captured-measurement sweeps", d),
        ("Predicted interior peak only", d.loc[~d["right_censored_20deg"]]),
        ("Predicted boundary maximum", d.loc[d["right_censored_20deg"]]),
    ]:
        rows.append(
            {
                "analysis_set": label,
                "sweeps": int(len(g)),
                "airfoil_entries": int(g["entry"].nunique()),
                "clmax_bias": float(g["clmax_error"].mean()),
                "clmax_mae": float(g["clmax_abs_error"].mean()),
                "stall_angle_bias_deg": float(g["stall_angle_error"].mean()),
                "stall_angle_mae_deg": float(g["stall_angle_abs_error"].mean()),
                "clmax_overprediction_share": float(g["overpredict_clmax"].mean()),
            }
        )
        if len(g):
            metrics[label] = base.cluster_bootstrap_mean(
                g,
                ["clmax_error", "clmax_abs_error", "stall_angle_error", "stall_angle_abs_error"],
                cluster="entry",
                n_boot=4000,
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "stall_censoring_sensitivity.csv", index=False)
    return out, metrics


def exploratory_risk_model(clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, dict]]:
    d = clean.copy().reset_index(drop=True)
    d["large_error"] = d["err_cd_mean8"].gt(20).astype(int)
    features = pd.DataFrame(
        {
            "negative_confidence": -d["conf_xlarge"],
            "log_disagreement": np.log1p(d["spread_counts"]),
            "log_re": np.log10(d["Re"]),
            "alpha": d["alpha"],
            "abs_alpha": d["alpha"].abs(),
            "thickness": d["tc"],
            "nominal_geometry": d["geom_kind"].eq("nominal").astype(float),
        }
    )
    feature_sets = {
        "confidence": ["negative_confidence"],
        "disagreement": ["log_disagreement"],
        "multivariable": list(features.columns),
    }
    groups = d["entry"].astype(str)
    y = d["large_error"].to_numpy()
    cv = StratifiedGroupKFold(n_splits=10, shuffle=True, random_state=20260904)
    folds = list(cv.split(features, y, groups))
    fold_rows = []
    for fold_id, (_, test) in enumerate(folds, start=1):
        assigned = d.loc[test, ["source", "airfoil", "entry"]].drop_duplicates().copy()
        assigned["fold"] = fold_id
        fold_rows.append(assigned)
    fold_assignments = (
        pd.concat(fold_rows, ignore_index=True)
        .sort_values(["source", "airfoil", "entry"])
        .reset_index(drop=True)
    )
    if fold_assignments["entry"].duplicated().any() or len(fold_assignments) != d["entry"].nunique():
        raise RuntimeError("Risk-model source-airfoil fold assignment is not one-to-one")
    fold_assignments.to_csv(OUT / "risk_model_fold_assignments.csv", index=False)

    probabilities: dict[str, np.ndarray] = {}
    for name, cols in feature_sets.items():
        p = np.full(len(d), np.nan)
        for train, test in folds:
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs"),
            )
            model.fit(features.loc[train, cols], y[train])
            p[test] = model.predict_proba(features.loc[test, cols])[:, 1]
        if np.isnan(p).any():
            raise RuntimeError(f"Risk-model OOF predictions missing for {name}")
        probabilities[name] = p
        d[f"risk_probability_{name}"] = p

    metrics = {}
    for name in feature_sets:
        metrics[name] = cluster_bootstrap_auc(
            d,
            "large_error",
            f"risk_probability_{name}",
            n_boot=2500,
        )

    ranked = d["risk_probability_multivariable"].rank(method="first")
    d["calibration_decile"] = pd.qcut(ranked, 10, labels=False)
    calibration = (
        d.groupby("calibration_decile", as_index=False)
        .agg(
            rows=("large_error", "size"),
            mean_predicted_risk=("risk_probability_multivariable", "mean"),
            observed_large_error_share=("large_error", "mean"),
            median_abs_error_counts=("err_cd_mean8", "median"),
        )
    )
    calibration.to_csv(OUT / "risk_model_calibration.csv", index=False)

    selective_rows = []
    for name in feature_sets:
        order = np.argsort(probabilities[name])[::-1]
        total_error = float(d["err_cd_mean8"].sum())
        for fraction in np.linspace(0, 0.50, 11):
            n_defer = int(round(fraction * len(d)))
            deferred = order[:n_defer]
            keep = np.ones(len(d), dtype=bool)
            keep[deferred] = False
            captured = float(d.loc[~keep, "err_cd_mean8"].sum() / total_error) if n_defer else 0.0
            selective_rows.append(
                {
                    "risk_model": name,
                    "deferred_fraction": float(fraction),
                    "retained_rows": int(keep.sum()),
                    "retained_drag_mae_counts": float(d.loc[keep, "err_cd_mean8"].mean()),
                    "total_absolute_error_captured": captured,
                }
            )
    selective = pd.DataFrame(selective_rows)
    selective.to_csv(OUT / "risk_model_selective_curve.csv", index=False)

    threshold_rows = []
    for threshold in [10, 20, 50, 100]:
        yt = d["err_cd_mean8"].gt(threshold).astype(int).to_numpy()
        for name, cols in feature_sets.items():
            p = np.full(len(d), np.nan)
            for train, test in folds:
                model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs"))
                model.fit(features.loc[train, cols], yt[train])
                p[test] = model.predict_proba(features.loc[test, cols])[:, 1]
            threshold_rows.append(
                {
                    "threshold_counts": threshold,
                    "model": name,
                    "event_prevalence": float(yt.mean()),
                    "auroc": float(roc_auc_score(yt, p)),
                    "average_precision": float(average_precision_score(yt, p)),
                    "brier_score": float(brier_score_loss(yt, p)),
                }
            )
    threshold_table = pd.DataFrame(threshold_rows)
    threshold_table.to_csv(OUT / "risk_threshold_sensitivity.csv", index=False)

    loso_p = np.full(len(d), np.nan)
    per_source = {}
    cols = feature_sets["multivariable"]
    for source in sorted(d["source"].unique()):
        test = d["source"].eq(source).to_numpy()
        train = ~test
        model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, solver="lbfgs"))
        model.fit(features.loc[train, cols], y[train])
        loso_p[test] = model.predict_proba(features.loc[test, cols])[:, 1]
        per_source[source] = {
            "rows": int(test.sum()),
            "event_prevalence": float(y[test].mean()),
            "auroc": float(roc_auc_score(y[test], loso_p[test])),
            "average_precision": float(average_precision_score(y[test], loso_p[test])),
            "brier_score": float(brier_score_loss(y[test], loso_p[test])),
        }
    metrics["multivariable_leave_one_source_out"] = {
        "auroc": float(roc_auc_score(y, loso_p)),
        "average_precision": float(average_precision_score(y, loso_p)),
        "brier_score": float(brier_score_loss(y, loso_p)),
        "per_source": per_source,
    }

    oof = d[
        [
            "source", "airfoil", "entry", "Re", "alpha", "tc", "err_cd_mean8",
            "large_error", "risk_probability_confidence", "risk_probability_disagreement",
            "risk_probability_multivariable",
        ]
    ]
    oof.to_csv(OUT / "risk_model_oof.csv", index=False)
    return oof, calibration, selective, metrics


def make_manifest() -> pd.DataFrame:
    """Record the intermediate analysis/draft snapshot used by this stage.

    This is deliberately distinct from ``reproducibility_manifest.csv``, which
    is the final whole-project manifest written only after the manuscript
    artifacts have been frozen.
    """
    roots = [
        REPO / "study" / "data",
        REPO / "study" / "tools",
        REPO / "study" / "docs",
        ROOT / "analysis",
        ROOT / "draft",
    ]
    rows = []
    excluded = {
        "verified_metrics_extended.json",
        "analysis_snapshot_manifest.csv",
        "reproducibility_manifest.csv",
    }
    for root in roots:
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            if path.name in excluded or "__pycache__" in path.parts:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rows.append(
                {
                    "relative_path": str(path.relative_to(ROOT)),
                    "bytes": path.stat().st_size,
                    "sha256": digest,
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "analysis_snapshot_manifest.csv", index=False)
    return out


def figure_selection(
    d: pd.DataFrame,
    source: pd.DataFrame,
    re_table: pd.DataFrame,
    alpha: pd.DataFrame,
    contrasts: dict[str, dict],
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(8.5, 6.2))

    ax = axes[0, 0]
    ax.bar(source["source"], source["availability_share"] * 100, color=COLORS["xfoil"])
    ax.set_ylim(0, 100)
    ax.set_ylabel("XFOIL output available (%)")
    ax.set_title("Availability by source")
    ax.grid(axis="x", visible=False)
    for i, v in enumerate(source["availability_share"] * 100):
        ax.text(i, v + 1.2, f"{v:.1f}%", ha="center", fontsize=7.5)

    ax = axes[0, 1]
    x = np.arange(len(re_table))
    ax.bar(x, re_table["availability_share"] * 100, color=COLORS["xfoil"])
    ax.set_xticks(x, re_table["Re_band"], rotation=25, ha="right")
    ax.set_ylim(0, 100)
    ax.set_ylabel("XFOIL output available (%)")
    ax.set_title("Availability by Reynolds band")
    ax.grid(axis="x", visible=False)

    ax = axes[1, 0]
    x = np.arange(len(alpha))
    ax.bar(x, alpha["availability_share"] * 100, color=COLORS["amber"])
    ax.set_xticks(x, alpha["alpha_band"], rotation=25, ha="right")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Angle-of-attack band (degrees)")
    ax.set_ylabel("XFOIL output available (%)")
    ax.set_title("Availability by angle of attack")
    ax.grid(axis="x", visible=False)

    ax = axes[1, 1]
    groups = [True, False]
    labels = ["XFOIL output\nreturned", "XFOIL output\nabsent"]
    means = [d.loc[d["xfoil_output_returned"].eq(g), "err_cd_mean8"].mean() for g in groups]
    cis = []
    for g in groups:
        stat = cluster_bootstrap_mean(d.loc[d["xfoil_output_returned"].eq(g)], "err_cd_mean8")
        cis.append((stat["ci_low"], stat["ci_high"]))
    yerr = [
        [means[i] - cis[i][0] for i in range(2)],
        [cis[i][1] - means[i] for i in range(2)],
    ]
    ax.bar(np.arange(2), means, color=[COLORS["mean8"], COLORS["risk"]], width=0.62)
    ax.errorbar(np.arange(2), means, yerr=yerr, fmt="none", color=COLORS["ink"], capsize=3, lw=0.9)
    ax.set_xticks(np.arange(2), labels)
    ax.set_ylabel("Mean-of-eight drag MAE (counts)")
    ax.set_title("NeuralFoil error in selected populations")
    ax.grid(axis="x", visible=False)
    delta = contrasts["mean8_drag_abs_error_counts"]
    ax.text(
        0.5,
        0.96,
        f"absent − returned = {delta['estimate']:.1f}\n95% CI {delta['ci_low']:.1f} to {delta['ci_high']:.1f}",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=7.5,
        color=COLORS["muted"],
    )

    fig.suptitle("XFOIL output absence defines a selected, condition-dependent comparison set", y=0.995, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.09, right=0.99, top=0.91, bottom=0.10, wspace=0.29, hspace=0.42)
    fig.savefig(FIG / "figure_7_xfoil_selection.png")
    plt.close(fig)


def figure_robustness(common: pd.DataFrame, source_table: pd.DataFrame, weight: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(9.0, 3.35))

    ax = axes[0]
    cd = weight.loc[weight["outcome"].eq("CD")]
    estimands = ["point-weighted", "airfoil-entry macro", "source macro"]
    models = ["XFOIL", "NeuralFoil xlarge", "NeuralFoil mean-of-eight"]
    colors = [COLORS["xfoil"], COLORS["xlarge"], COLORS["mean8"]]
    x = np.arange(len(estimands))
    width = 0.24
    for j, (model, color) in enumerate(zip(models, colors)):
        vals = (
            cd.loc[cd["model"].eq(model)]
            .set_index("estimand")
            .reindex(estimands)["absolute_error"]
        )
        ax.bar(x + (j - 1) * width, vals, width=width, label=model.replace("NeuralFoil ", "NF "), color=color)
    ax.set_xticks(x, ["Point", "Airfoil\nmacro", "Source\nmacro"])
    ax.set_ylabel("Drag MAE (counts)")
    ax.set_title("Weighting sensitivity")
    ax.legend(frameon=False, fontsize=7)
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    cd_src = source_table.loc[source_table["outcome"].eq("CD")].sort_values("source")
    y = np.arange(len(cd_src))
    ax.axvline(0, color="#98A2B3", lw=0.8)
    ax.errorbar(
        cd_src["mean8_minus_xfoil"],
        y,
        xerr=[
            cd_src["mean8_minus_xfoil"] - cd_src["ci_low"],
            cd_src["ci_high"] - cd_src["mean8_minus_xfoil"],
        ],
        fmt="o",
        color=COLORS["mean8"],
        ecolor=COLORS["ink"],
        capsize=2.5,
        lw=0.9,
    )
    ax.set_yticks(y, cd_src["source"])
    ax.set_xlabel("NF mean-of-eight − XFOIL (drag counts)")
    ax.set_title("Source-specific paired effects")

    ax = axes[2]
    errors = {
        "XFOIL": common["err_cd_xfoil"].to_numpy(),
        "NF xlarge": common["err_cd_xlarge"].to_numpy(),
        "NF mean-of-eight": common["err_cd_mean8"].to_numpy(),
    }
    for (label, values), color in zip(errors.items(), colors):
        grid = np.sort(values)
        survival = 1 - np.arange(1, len(grid) + 1) / len(grid)
        ax.step(grid, survival * 100, where="post", label=label, color=color, lw=1.2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, max(common["err_cd_xfoil"].max(), common["err_cd_mean8"].max()) * 1.05)
    ax.set_ylim(0.05, 100)
    ax.set_xlabel("Absolute drag error (counts, log scale)")
    ax.set_ylabel("Conditions exceeding error (%)")
    ax.set_title("Tail-risk distribution")
    ax.legend(frameon=False, fontsize=7)

    fig.suptitle("The overall comparison is sensitive in magnitude but not reducible to a single average", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.075, right=0.99, top=0.81, bottom=0.20, wspace=0.39)
    fig.savefig(FIG / "figure_8_robustness_and_tails.png")
    plt.close(fig)


def figure_risk(
    calibration: pd.DataFrame,
    selective: pd.DataFrame,
    metrics: dict[str, dict],
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(8.9, 3.3))

    ax = axes[0]
    keys = ["confidence", "disagreement", "multivariable"]
    names = ["Confidence", "Disagreement", "Multivariable"]
    vals = [metrics[k]["auroc"] for k in keys]
    lo = [metrics[k]["auroc_ci_low"] for k in keys]
    hi = [metrics[k]["auroc_ci_high"] for k in keys]
    colors = [COLORS["xlarge"], COLORS["mean8"], COLORS["risk"]]
    ax.bar(np.arange(3), vals, color=colors, width=0.62)
    ax.errorbar(
        np.arange(3), vals,
        yerr=[[vals[i] - lo[i] for i in range(3)], [hi[i] - vals[i] for i in range(3)]],
        fmt="none", color=COLORS["ink"], capsize=3, lw=0.9,
    )
    ax.axhline(0.5, color="#98A2B3", lw=0.8, ls="--")
    ax.set_xticks(np.arange(3), names, rotation=18, ha="right")
    ax.set_ylim(0.45, 0.9)
    ax.set_ylabel("AUROC for drag error >20 counts")
    ax.set_title("Grouped OOF discrimination")
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    ax.plot(
        calibration["mean_predicted_risk"] * 100,
        calibration["observed_large_error_share"] * 100,
        marker="o", color=COLORS["risk"],
    )
    ax.plot([0, 100], [0, 100], ls="--", lw=0.8, color="#98A2B3")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Mean predicted risk (%)")
    ax.set_ylabel("Observed large-error rate (%)")
    ax.set_title("Internal calibration deciles")

    ax = axes[2]
    for key, label, color in zip(keys, names, colors):
        g = selective.loc[selective["risk_model"].eq(key)]
        ax.plot(
            g["deferred_fraction"] * 100,
            g["retained_drag_mae_counts"],
            marker="o", label=label, color=color,
        )
    ax.set_xlabel("Highest-risk conditions deferred (%)")
    ax.set_ylabel("MAE in retained conditions (counts)")
    ax.set_title("Selective-analysis sensitivity")
    ax.legend(frameon=False, fontsize=7)

    fig.suptitle("An exploratory grouped risk model improves triage but is not externally calibrated", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.23, wspace=0.38)
    fig.savefig(FIG / "figure_9_risk_diagnostics.png")
    plt.close(fig)


def figure_all_sizes(all_sizes: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.7, 3.35))
    singles = all_sizes.loc[all_sizes["kind"].eq("single network")]
    ensemble = all_sizes.loc[all_sizes["model_output"].eq("mean-of-eight")].iloc[0]
    for ax, outcome, ylabel in [
        (axes[0], "full_clean_drag_mae_counts", "Drag MAE (counts)"),
        (axes[1], "full_clean_lift_mae", "Lift MAE"),
    ]:
        ax.scatter(
            singles["archived_evaluations_per_second"], singles[outcome],
            s=37, color=COLORS["xlarge"], edgecolor="white", linewidth=0.6, zorder=3,
        )
        for _, row in singles.iterrows():
            ax.annotate(
                row["model_output"],
                (row["archived_evaluations_per_second"], row[outcome]),
                xytext=(4, 3), textcoords="offset points", fontsize=7,
            )
        ax.scatter(
            ensemble["archived_evaluations_per_second"], ensemble[outcome],
            s=54, marker="D", color=COLORS["mean8"], edgecolor="white", linewidth=0.6,
            label="Mean-of-eight", zorder=4,
        )
        ax.annotate(
            "mean-of-eight",
            (ensemble["archived_evaluations_per_second"], ensemble[outcome]),
            xytext=(5, -11), textcoords="offset points", fontsize=7, color=COLORS["mean8"],
        )
        ax.set_xscale("log")
        ax.set_xlabel("Archived batch throughput (evaluations/s, log scale)")
        ax.set_ylabel(ylabel)
        ax.grid(axis="x", which="both", alpha=0.3)
    axes[0].set_title("Drag accuracy–throughput tradeoff")
    axes[1].set_title("Lift accuracy–throughput tradeoff")
    fig.suptitle("Larger NeuralFoil networks do not monotonically improve agreement with measurements", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.10, right=0.99, top=0.82, bottom=0.21, wspace=0.31)
    fig.savefig(FIG / "figure_11_model_size_pareto.png")
    plt.close(fig)


def main() -> None:
    setup_style()
    clean, unique, common = base.load_low_speed()
    available = add_xfoil_availability(unique, common)
    source_avail, re_avail, alpha_avail = availability_tables(available)
    selection_table, selection_contrasts = missingness_audit(available)
    distributions = distribution_summary(common)
    weighting, source_table, source_contrasts = weighting_sensitivity(common)
    wins = airfoil_level_wins(common)
    strata, aucs = risk_diagnostics(clean)
    all_sizes = all_model_sizes(clean, common)
    measurement_proxy = measurement_variability_proxy(clean, common)
    stall_sensitivity, stall_intervals = stall_censoring_sensitivity()
    risk_oof, risk_calibration, risk_selective, risk_model_metrics = exploratory_risk_model(clean)
    manifest = make_manifest()

    figure_selection(available, source_avail, re_avail, alpha_avail, selection_contrasts)
    figure_robustness(common, source_table, weighting)
    figure_risk(risk_calibration, risk_selective, risk_model_metrics)
    figure_all_sizes(all_sizes)

    metrics = {
        "analysis_seed": 20260904,
        "bootstrap_replicates": {
            "mean_difference_and_stall": 4000,
            "risk_score_and_risk_model": 2500,
        },
        "xfoil_selection_contrasts": selection_contrasts,
        "risk_discrimination": aucs,
        "exploratory_risk_model": risk_model_metrics,
        "source_specific_contrasts": source_contrasts,
        "airfoil_level_win_rates": wins.to_dict(orient="records"),
        "all_model_sizes": all_sizes.to_dict(orient="records"),
        "measurement_variability_proxy": measurement_proxy.to_dict(orient="records"),
        "stall_censoring_sensitivity": stall_sensitivity.to_dict(orient="records"),
        "stall_cluster_bootstrap": stall_intervals,
        "analysis_snapshot_manifest": {
            "scope": "intermediate analysis and draft snapshot; not the final project manifest",
            "files": int(len(manifest)),
            "total_bytes": int(manifest["bytes"].sum()),
            "manifest_sha256": hashlib.sha256((OUT / "analysis_snapshot_manifest.csv").read_bytes()).hexdigest(),
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "matplotlib": plt.matplotlib.__version__,
            "seaborn": sns.__version__,
        },
    }
    (OUT / "verified_metrics_extended.json").write_text(json.dumps(metrics, indent=2) + "\n")

    print(json.dumps({
        "selection_drag": selection_contrasts["mean8_drag_abs_error_counts"],
        "selection_lift": selection_contrasts["mean8_lift_abs_error"],
        "risk_discrimination": aucs,
        "risk_model": risk_model_metrics,
        "analysis_snapshot_manifest_files": len(manifest),
    }, indent=2))


if __name__ == "__main__":
    main()
