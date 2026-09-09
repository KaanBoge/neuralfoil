from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "source" / "neuralfoil_repo" / "study" / "data"
FIG = ROOT / "figures"
OUT = ROOT / "analysis"
FIG.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

SIZES = [
    "xxsmall", "xsmall", "small", "medium",
    "large", "xlarge", "xxlarge", "xxxlarge",
]
COUNTS = 1e4
RNG = np.random.default_rng(20260901)

COLORS = {
    "xfoil": "#7A7A7A",
    "classic": "#4472C4",
    "mean8": "#70AD47",
    "corrected": "#D97706",
    "risk": "#B42318",
    "muted": "#667085",
    "navy": "#17365D",
    "light": "#EAF0F7",
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


def add_key(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if "entry" not in d:
        d["entry"] = d["source"].astype(str) + "|" + d["airfoil"].astype(str)
    d["Re_key"] = d["Re"].round().astype(int)
    d["alpha_key"] = d["alpha"].round(2)
    return d


def attach_raw_configuration(nf: pd.DataFrame) -> pd.DataFrame:
    """Recover the per-row LSAT configuration label without duplicating ties.

    The published ``lsat_run.py`` wrote the entry-level geometry label into
    ``lsat-nf.csv``.  The parsed corpus retains the row-level label.  Some
    measurements are numerically duplicated across clean and modified rows, so
    a one-to-one merge also needs a deterministic occurrence index.
    """
    corpus = pd.read_csv(DATA / "lsat-corpus.csv")
    c = corpus.copy()
    n = nf.copy()
    for d in (c, n):
        d["Re_match"] = d["Re"].round(3)
        d["alpha_match"] = d["alpha"].round(4)
    c["CL_match"] = c["CL"].round(5)
    c["CD_match"] = c["CD"].round(6)
    n["CL_match"] = n["CL_meas"].round(5)
    n["CD_match"] = n["CD_meas"].round(6)
    match = ["source", "airfoil", "Re_match", "alpha_match", "CL_match", "CD_match"]
    c["match_occurrence"] = c.groupby(match, sort=False).cumcount()
    n["match_occurrence"] = n.groupby(match, sort=False).cumcount()
    n = n.merge(
        c[match + ["match_occurrence", "config"]].rename(columns={"config": "raw_config"}),
        on=match + ["match_occurrence"],
        how="left",
        validate="one_to_one",
    )
    if n["raw_config"].isna().any():
        raise RuntimeError("Per-row configuration recovery left unmatched NeuralFoil rows")
    return n.drop(columns=["Re_match", "alpha_match", "CL_match", "CD_match", "match_occurrence"])


def cluster_bootstrap_mean(
    df: pd.DataFrame,
    value_cols: list[str],
    cluster: str = "entry",
    n_boot: int = 4000,
) -> dict[str, dict[str, float]]:
    grouped = df.groupby(cluster, sort=False)[value_cols].agg(["sum", "count"])
    clusters = grouped.index.to_numpy()
    ncl = len(clusters)
    result: dict[str, dict[str, float]] = {}
    for col in value_cols:
        sums = grouped[(col, "sum")].to_numpy(float)
        counts = grouped[(col, "count")].to_numpy(float)
        boots = np.empty(n_boot)
        for b in range(n_boot):
            idx = RNG.integers(0, ncl, ncl)
            boots[b] = sums[idx].sum() / counts[idx].sum()
        result[col] = {
            "estimate": float(df[col].mean()),
            "ci_low": float(np.quantile(boots, 0.025)),
            "ci_high": float(np.quantile(boots, 0.975)),
            "clusters": int(ncl),
            "rows": int(len(df)),
        }
    return result


def cluster_bootstrap_proportion(
    df: pd.DataFrame,
    value_col: str,
    cluster: str = "entry",
    n_boot: int = 4000,
) -> dict[str, float]:
    tmp = df[[cluster, value_col]].copy()
    tmp[value_col] = tmp[value_col].astype(float)
    return cluster_bootstrap_mean(tmp, [value_col], cluster, n_boot)[value_col]


def load_low_speed() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    nf = attach_raw_configuration(pd.read_csv(DATA / "lsat-nf.csv"))
    nf = add_key(nf)
    # Both labels are required: the parsed row must be clean and the geometry
    # entry itself must not encode a flap, trip, roughness, or other modifier.
    clean = nf.loc[nf["config"].eq("clean") & nf["raw_config"].eq("clean")].copy()
    clean["CD_mean8"] = clean[[f"CD_{s}" for s in SIZES]].mean(axis=1)
    clean["CL_mean8"] = clean[[f"CL_{s}" for s in SIZES]].mean(axis=1)
    clean["spread_counts"] = (
        clean[[f"CD_{s}" for s in SIZES]].quantile(0.90, axis=1)
        - clean[[f"CD_{s}" for s in SIZES]].quantile(0.10, axis=1)
    ) * COUNTS
    clean["err_cd_mean8"] = (clean["CD_mean8"] - clean["CD_meas"]).abs() * COUNTS
    clean["err_cd_xlarge"] = (clean["CD_xlarge"] - clean["CD_meas"]).abs() * COUNTS
    clean["err_cl_mean8"] = (clean["CL_mean8"] - clean["CL_meas"]).abs()
    clean["err_cl_xlarge"] = (clean["CL_xlarge"] - clean["CL_meas"]).abs()

    keys = ["entry", "Re_key", "alpha_key"]
    # Preserve repeated measured conditions one-to-one.  A plain merge on the
    # rounded condition key creates a Cartesian product for duplicate rows.
    clean["oof_occurrence"] = clean.groupby(keys, sort=False).cumcount()
    oof3 = add_key(pd.read_csv(DATA / "oof3.csv"))
    oof2 = add_key(pd.read_csv(DATA / "oof2.csv"))
    for d in (oof3, oof2):
        d["oof_occurrence"] = d.groupby(keys, sort=False).cumcount()
    oof3 = oof3[[*keys, "oof_occurrence", "zCD_oof"]]
    oof2 = oof2[[*keys, "oof_occurrence", "zCD_oof", "dCL_oof"]].rename(
        columns={"zCD_oof": "zCD_oof_v2"}
    )
    merge_keys = [*keys, "oof_occurrence"]
    clean = clean.merge(oof3, how="left", on=merge_keys, validate="one_to_one").merge(
        oof2, how="left", on=merge_keys, validate="one_to_one"
    )
    clean["in_domain"] = clean["zCD_oof"].notna()
    clean["zCD_oof"] = clean["zCD_oof"].fillna(0.0)
    clean["zCD_oof_v2"] = clean["zCD_oof_v2"].fillna(0.0)
    clean["dCL_oof"] = clean["dCL_oof"].fillna(0.0)
    clean["CD_corrected"] = clean["CD_mean8"] * np.exp(
        clean["zCD_oof"].clip(np.log(0.5), np.log(2.0))
    )
    clean["CD_v2"] = clean["CD_mean8"] * np.exp(
        clean["zCD_oof_v2"].clip(np.log(0.5), np.log(2.0))
    )
    clean["CL_corrected"] = clean["CL_mean8"] + clean["dCL_oof"].clip(-0.5, 0.5)
    clean["err_cd_corrected"] = (clean["CD_corrected"] - clean["CD_meas"]).abs() * COUNTS
    clean["err_cd_v2"] = (clean["CD_v2"] - clean["CD_meas"]).abs() * COUNTS
    clean["err_cl_corrected"] = (clean["CL_corrected"] - clean["CL_meas"]).abs()

    # The published head-to-head code used one row per unique matched condition,
    # retaining the last duplicate key. Reproduce that rule explicitly.
    unique = clean.drop_duplicates(keys, keep="last").copy()
    xf = add_key(pd.read_csv(DATA / "lsat-xfoil.csv"))
    xf = xf.drop_duplicates(keys, keep="last")
    common = unique.merge(
        xf[[*keys, "CL_xf", "CD_xf"]], how="inner", on=keys, validate="one_to_one"
    )
    common["err_cd_xfoil"] = (common["CD_xf"] - common["CD_meas"]).abs() * COUNTS
    common["err_cl_xfoil"] = (common["CL_xf"] - common["CL_meas"]).abs()
    return clean, unique, common


def verified_metrics(clean: pd.DataFrame, unique: pd.DataFrame, common: pd.DataFrame) -> dict:
    metrics: dict = {
        "clean_rows": int(len(clean)),
        "unique_clean_conditions": int(len(unique)),
        "airfoil_entries": int(clean["entry"].nunique()),
        "xfoil_common_conditions": int(len(common)),
        "xfoil_output_return_share_of_unique_clean": float(len(common) / len(unique)),
        "correction_in_domain_rows": int(clean["in_domain"].sum()),
        "published_label_clean_rows": 10608,
        "rows_removed_after_raw_configuration_audit": int(10608 - len(clean)),
        "xfoil_output_return_share_published_denominator": float(len(common) / 10567),
    }

    common_values = [
        "err_cd_xfoil", "err_cd_xlarge", "err_cd_mean8", "err_cd_corrected",
        "err_cl_xfoil", "err_cl_xlarge", "err_cl_mean8", "err_cl_corrected",
    ]
    metrics["common_cluster_bootstrap"] = cluster_bootstrap_mean(common, common_values)
    common_macro = common.groupby("entry", as_index=False)[common_values].mean()
    metrics["common_airfoil_macro_bootstrap"] = cluster_bootstrap_mean(
        common_macro, common_values
    )

    full_values = ["err_cd_xlarge", "err_cd_mean8", "err_cl_xlarge", "err_cl_mean8"]
    metrics["full_clean_core_cluster_bootstrap"] = cluster_bootstrap_mean(clean, full_values)
    full_macro = clean.groupby("entry", as_index=False)[full_values].mean()
    metrics["full_clean_core_airfoil_macro_bootstrap"] = cluster_bootstrap_mean(
        full_macro, full_values
    )
    metrics["full_clean_core_distribution"] = {}
    for col in full_values:
        metrics["full_clean_core_distribution"][col] = {
            "median": float(clean[col].median()),
            "p90": float(clean[col].quantile(0.90)),
            "p95": float(clean[col].quantile(0.95)),
            "maximum": float(clean[col].max()),
        }
    core_paired = clean.copy()
    core_paired["delta_cd_mean8_minus_xlarge"] = core_paired["err_cd_mean8"] - core_paired["err_cd_xlarge"]
    core_paired["delta_cl_mean8_minus_xlarge"] = core_paired["err_cl_mean8"] - core_paired["err_cl_xlarge"]
    metrics["full_clean_core_paired_differences"] = cluster_bootstrap_mean(
        core_paired,
        ["delta_cd_mean8_minus_xlarge", "delta_cl_mean8_minus_xlarge"],
    )

    paired = common.copy()
    paired["delta_cd_corrected_minus_xfoil"] = paired["err_cd_corrected"] - paired["err_cd_xfoil"]
    paired["delta_cd_corrected_minus_classic"] = paired["err_cd_corrected"] - paired["err_cd_xlarge"]
    paired["delta_cl_corrected_minus_xfoil"] = paired["err_cl_corrected"] - paired["err_cl_xfoil"]
    paired["delta_cl_corrected_minus_classic"] = paired["err_cl_corrected"] - paired["err_cl_xlarge"]
    metrics["common_paired_differences"] = cluster_bootstrap_mean(
        paired,
        [
            "delta_cd_corrected_minus_xfoil",
            "delta_cd_corrected_minus_classic",
            "delta_cl_corrected_minus_xfoil",
            "delta_cl_corrected_minus_classic",
        ],
    )

    ind = clean.loc[clean["in_domain"]].copy()
    ind["delta_cd_v2_minus_base"] = ind["err_cd_v2"] - ind["err_cd_mean8"]
    ind["delta_cd_v3_minus_base"] = ind["err_cd_corrected"] - ind["err_cd_mean8"]
    ind["delta_cl_v2_minus_base"] = ind["err_cl_corrected"] - ind["err_cl_mean8"]
    metrics["legacy_mixed_cohort_oof_correction_sensitivity"] = cluster_bootstrap_mean(
        ind,
        ["delta_cd_v2_minus_base", "delta_cd_v3_minus_base", "delta_cl_v2_minus_base"],
    )
    metrics["legacy_mixed_cohort_absolute_errors"] = cluster_bootstrap_mean(
        ind,
        [
            "err_cd_mean8", "err_cd_v2", "err_cd_corrected",
            "err_cl_mean8", "err_cl_corrected",
        ],
    )

    # Confidence is a ranking score in the original model, not a probability.
    # Evaluate discrimination and high-score failure without treating it as coverage.
    bad = clean["err_cd_mean8"].gt(20.0)
    good = ~bad
    high_conf = clean["conf_xlarge"].gt(0.90)
    metrics["confidence_audit"] = {
        "overall_error_gt20_share": float(bad.mean()),
        "high_conf_rows": int(high_conf.sum()),
        "high_conf_error_gt20_share": float(bad[high_conf].mean()),
        "low_conf_error_gt20_share": float(bad[~high_conf].mean()),
        "auc_confidence_for_error_le20": float(roc_auc_score(good, clean["conf_xlarge"])),
        "auc_negative_spread_for_error_le20": float(roc_auc_score(good, -clean["spread_counts"])),
        "spearman_confidence_vs_abs_error": float(spearmanr(clean["conf_xlarge"], clean["err_cd_mean8"]).statistic),
        "spearman_spread_vs_abs_error": float(spearmanr(clean["spread_counts"], clean["err_cd_mean8"]).statistic),
    }
    hc = clean.loc[high_conf].assign(bad=bad[high_conf].to_numpy())
    metrics["confidence_audit"]["high_conf_bad_share_cluster_ci"] = cluster_bootstrap_proportion(hc, "bad")

    return metrics


def make_deciles(clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = clean.copy()
    d["spread_decile"] = pd.qcut(
        d["spread_counts"].rank(method="first"), 10, labels=False
    )
    d["confidence_decile"] = pd.qcut(
        d["conf_xlarge"].rank(method="first"), 10, labels=False
    )
    spread = (
        d.groupby("spread_decile", as_index=False)
        .agg(
            n=("err_cd_mean8", "size"),
            spread_lo=("spread_counts", "min"),
            spread_hi=("spread_counts", "max"),
            spread_median=("spread_counts", "median"),
            error_median=("err_cd_mean8", "median"),
            error_mean=("err_cd_mean8", "mean"),
            error_le20_share=("err_cd_mean8", lambda x: float((x <= 20).mean())),
        )
    )
    conf = (
        d.groupby("confidence_decile", as_index=False)
        .agg(
            n=("err_cd_mean8", "size"),
            confidence_lo=("conf_xlarge", "min"),
            confidence_hi=("conf_xlarge", "max"),
            confidence_median=("conf_xlarge", "median"),
            error_median=("err_cd_mean8", "median"),
            error_mean=("err_cd_mean8", "mean"),
            error_le20_share=("err_cd_mean8", lambda x: float((x <= 20).mean())),
        )
    )
    spread.to_csv(OUT / "spread_deciles_corrected.csv", index=False)
    conf.to_csv(OUT / "confidence_deciles.csv", index=False)
    return spread, conf


def re_band_table(clean: pd.DataFrame, common: pd.DataFrame) -> pd.DataFrame:
    bins = [0, 45e3, 75e3, 150e3, 250e3, 350e3, 600e3]
    labels = ["<45k", "45-75k", "75-150k", "150-250k", "250-350k", "350-600k"]
    d = clean.copy()
    d["Re_band"] = pd.cut(d["Re"], bins=bins, labels=labels, right=False)
    rows = []
    for band, g in d.groupby("Re_band", observed=True):
        rows.append(
            {
                "Re_band": str(band),
                "n": int(len(g)),
                "mean8_median": float(g["err_cd_mean8"].median()),
                "mean8_p90": float(g["err_cd_mean8"].quantile(0.90)),
                "mean8_mae": float(g["err_cd_mean8"].mean()),
                "corrected_mae": float(g["err_cd_corrected"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "reynolds_error_map_verified.csv", index=False)
    return out


def cohort_and_availability_tables(clean: pd.DataFrame, unique: pd.DataFrame, common: pd.DataFrame) -> None:
    cohort = pd.DataFrame(
        [
            ["Parsed LSAT rows", 14773, "Rows in lsat-corpus.csv"],
            ["NeuralFoil-evaluated rows", 13394, "Rows with matched geometry and completed inference"],
            ["Rows labeled clean in published output", 10608, "Entry-level label written by lsat_run.py"],
            ["Modified rows removed by row-level audit", 1955, "Raw parser label was modified"],
            ["Corrected clean rows", len(clean), "Both raw row and geometry-entry labels clean"],
            ["Unique corrected-clean conditions", len(unique), "Entry, rounded Reynolds number, and angle"],
            ["XFOIL-returned common conditions", len(common), "Conditional benchmark set"],
            ["Legacy correction OOF rows", int(clean["in_domain"].sum()), "Mixed-cohort model training; sensitivity only"],
        ],
        columns=["stage", "rows", "definition"],
    )
    cohort.to_csv(OUT / "cohort_flow.csv", index=False)

    xf_keys = common[["entry", "Re_key", "alpha_key"]].drop_duplicates().assign(xfoil_output_returned=True)
    d = unique.merge(xf_keys, on=["entry", "Re_key", "alpha_key"], how="left")
    d["xfoil_output_returned"] = d["xfoil_output_returned"].eq(True)
    bins = [0, 45e3, 75e3, 150e3, 250e3, 350e3, 600e3]
    labels = ["<45k", "45-75k", "75-150k", "150-250k", "250-350k", "350-600k"]
    d["Re_band"] = pd.cut(d["Re"], bins=bins, labels=labels, right=False)
    availability = (
        d.groupby("Re_band", observed=True)
        .agg(
            eligible_conditions=("xfoil_output_returned", "size"),
            returned_conditions=("xfoil_output_returned", "sum"),
            availability_share=("xfoil_output_returned", "mean"),
        )
        .reset_index()
    )
    availability.to_csv(OUT / "xfoil_availability_by_re.csv", index=False)


def transonic_summary() -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = json.loads((DATA / "selected-model.json").read_text())
    candidates = []
    for name, values in selected["all_results"].items():
        candidates.append({"candidate": name, "loso_mae_counts": float(values[0])})
    cand = pd.DataFrame(candidates)

    hold = json.loads((DATA / "holdout-scores.json").read_text())
    rows = []
    for source, sweeps in hold.items():
        rows.append(
            {
                "source": source,
                "sweeps": len(sweeps),
                "stock_mae_counts": float(np.mean([v["mae_stock"] for v in sweeps.values()])),
                "model_mae_counts": float(np.mean([v["mae_model"] for v in sweeps.values()])),
                "mdd_stock_mae": float(
                    np.mean(
                        [
                            abs(v["mdd_stock"] - float(v["mdd_meas"]))
                            for v in sweeps.values()
                            if v["mdd_meas"] not in (None, "None")
                        ]
                    )
                ),
                "mdd_model_mae": float(
                    np.mean(
                        [
                            abs(v["mdd_model"] - float(v["mdd_meas"]))
                            for v in sweeps.values()
                            if v["mdd_meas"] not in (None, "None")
                        ]
                    )
                ),
            }
        )
    hold_df = pd.DataFrame(rows)
    cand.to_csv(OUT / "transonic_candidates.csv", index=False)
    hold_df.to_csv(OUT / "transonic_holdout_summary.csv", index=False)
    return cand, hold_df


def stall_metrics() -> tuple[pd.DataFrame, dict]:
    d = pd.read_csv(DATA / "lsat-clmax.csv")
    d["clmax_error"] = d["clmax_mean8"] - d["clmax_meas"]
    d["clmax_abs_error"] = d["clmax_error"].abs()
    d["stall_angle_error"] = d["astall_mean8"] - d["astall_meas"]
    d["stall_angle_abs_error"] = d["stall_angle_error"].abs()
    d["overpredict"] = d["clmax_error"].gt(0)
    vals = cluster_bootstrap_mean(
        d,
        ["clmax_error", "clmax_abs_error", "stall_angle_error", "stall_angle_abs_error"],
    )
    vals["overpredict_share"] = cluster_bootstrap_proportion(d, "overpredict")
    return d, vals


def figure_study_design() -> None:
    fig, ax = plt.subplots(figsize=(9.4, 3.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def box(x, y, w, h, title, detail, color):
        p = FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.03,rounding_size=0.08",
            linewidth=1.1, edgecolor=color, facecolor="#FFFFFF",
        )
        ax.add_patch(p)
        ax.text(x + 0.16, y + h - 0.22, title, color=color, weight="bold", va="top", fontsize=8.6)
        ax.text(x + 0.16, y + h - 0.68, detail, color="#344054", va="top", fontsize=7.3, linespacing=1.3)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12, lw=1.2, color="#98A2B3"))

    box(0.35, 3.25, 2.45, 1.65, "Parsed LSAT corpus",
        "14,773 measured drag rows\nPer-row configuration retained",
        COLORS["navy"])
    box(3.25, 3.25, 2.45, 1.65, "NeuralFoil evaluated",
        "13,394 matched rows\nEight network sizes",
        COLORS["classic"])
    box(6.15, 3.25, 2.55, 1.65, "Published 'clean' label",
        "10,608 rows\nEntry label replaced row label",
        COLORS["corrected"])
    arrow(2.8, 4.08, 3.25, 4.08)
    arrow(5.7, 4.08, 6.15, 4.08)

    box(6.15, 0.55, 2.55, 1.55, "Removed by audit",
        "1,955 modified rows\nTrips, flaps, and related cases",
        COLORS["risk"])
    box(9.15, 2.20, 2.55, 2.05, "Corrected-clean analysis",
        "8,653 rows; 135 entries\n8,652 unique conditions\n7,897 XFOIL matches (91.3%)\n8,388 legacy OOF sensitivity rows",
        COLORS["mean8"])
    arrow(7.42, 3.25, 7.42, 2.10)
    arrow(8.70, 4.08, 9.15, 3.25)
    ax.text(6, 5.72, "Cohort reconstruction after the configuration-label audit",
            ha="center", va="top", fontsize=11, weight="bold", color="#101828")
    fig.savefig(FIG / "figure_1_study_design.png")
    plt.close(fig)


def figure_head_to_head(common: pd.DataFrame, metrics: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65), gridspec_kw={"width_ratios": [1, 1, 1.3]})
    models = ["XFOIL", "Classic NF", "Mean-of-8", "Corrected NF"]
    cd_cols = ["err_cd_xfoil", "err_cd_xlarge", "err_cd_mean8", "err_cd_corrected"]
    cl_cols = ["err_cl_xfoil", "err_cl_xlarge", "err_cl_mean8", "err_cl_corrected"]
    colors = [COLORS["xfoil"], COLORS["classic"], COLORS["mean8"], COLORS["corrected"]]
    boot = metrics["common_cluster_bootstrap"]

    for ax, cols, ylabel, title in [
        (axes[0], cd_cols, "Mean absolute drag error (counts)", "Drag"),
        (axes[1], cl_cols, "Mean absolute lift error", "Lift"),
    ]:
        vals = [boot[c]["estimate"] for c in cols]
        lo = [boot[c]["estimate"] - boot[c]["ci_low"] for c in cols]
        hi = [boot[c]["ci_high"] - boot[c]["estimate"] for c in cols]
        ax.bar(np.arange(4), vals, color=colors, width=0.68, edgecolor="white")
        ax.errorbar(np.arange(4), vals, yerr=[lo, hi], fmt="none", color="#101828", capsize=2.5, lw=0.9)
        ax.set_xticks(np.arange(4), ["XFOIL", "Classic", "Mean-8", "Legacy OOF*"], rotation=26, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.1f}" if title == "Drag" else f"{v:.3f}", ha="center", va="bottom", fontsize=7.5)

    bins = [0, 75e3, 150e3, 250e3, 600e3]
    labels = ["<75k", "75-150k", "150-250k", "250-600k"]
    common = common.copy()
    common["Re_band"] = pd.cut(common["Re"], bins=bins, labels=labels, right=False)
    x = np.arange(len(labels))
    xf = common.groupby("Re_band", observed=True)["err_cd_xfoil"].mean().reindex(labels)
    co = common.groupby("Re_band", observed=True)["err_cd_corrected"].mean().reindex(labels)
    axes[2].bar(x - 0.18, xf, width=0.36, color=COLORS["xfoil"], label="XFOIL")
    axes[2].bar(x + 0.18, co, width=0.36, color=COLORS["corrected"], label="Legacy OOF*")
    axes[2].set_xticks(x, labels, rotation=25, ha="right")
    axes[2].set_ylabel("Drag MAE (counts)")
    axes[2].set_title("Drag error by Reynolds band")
    axes[2].legend(frameon=False, loc="upper right")
    axes[2].grid(axis="x", visible=False)

    fig.suptitle(
        f"Matched-condition benchmark on {len(common):,} XFOIL-returned cases",
        y=1.03, fontsize=11, weight="bold",
    )
    fig.tight_layout()
    fig.savefig(FIG / "figure_2_head_to_head.png")
    plt.close(fig)


def figure_operating_envelope(clean: pd.DataFrame, re_table: pd.DataFrame, spread: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(8.4, 6.0))

    ax = axes[0, 0]
    x = np.arange(len(re_table))
    ax.plot(x, re_table["mean8_median"], marker="o", color=COLORS["classic"], label="Median")
    ax.plot(x, re_table["mean8_p90"], marker="s", color=COLORS["risk"], label="90th percentile")
    ax.set_xticks(x, re_table["Re_band"], rotation=25, ha="right")
    ax.set_ylabel("Absolute drag error (counts)")
    ax.set_title("Reynolds-number stratification", fontsize=9.5)
    ax.legend(frameon=False)

    ax = axes[0, 1]
    abins = [-10, -4, 0, 4, 8, 12, 18]
    alabs = ["-10:-4", "-4:0", "0:4", "4:8", "8:12", "12:18"]
    d = clean.copy()
    d["alpha_band"] = pd.cut(d["alpha"], bins=abins, labels=alabs, right=False)
    g = d.groupby("alpha_band", observed=True)["err_cd_mean8"].agg(["median", lambda x: x.quantile(0.9)]).reindex(alabs)
    ax.plot(np.arange(len(g)), g["median"], marker="o", color=COLORS["classic"], label="Median")
    ax.plot(np.arange(len(g)), g["<lambda_0>"], marker="s", color=COLORS["risk"], label="90th percentile")
    ax.set_xticks(np.arange(len(g)), alabs, rotation=25, ha="right")
    ax.set_xlabel("Angle-of-attack band (degrees)")
    ax.set_ylabel("Absolute drag error (counts)")
    ax.set_title("Angle-of-attack stratification", fontsize=9.5)

    ax = axes[1, 0]
    tbins = [0, 0.07, 0.09, 0.12, 0.15, 0.30]
    tlabs = ["<7%", "7-9%", "9-12%", "12-15%", "15-30%"]
    d["tc_band"] = pd.cut(d["tc"], bins=tbins, labels=tlabs, right=False)
    g = d.groupby("tc_band", observed=True)["err_cd_mean8"].agg(["median", lambda x: x.quantile(0.9)]).reindex(tlabs)
    ax.plot(np.arange(len(g)), g["median"], marker="o", color=COLORS["classic"], label="Median")
    ax.plot(np.arange(len(g)), g["<lambda_0>"], marker="s", color=COLORS["risk"], label="90th percentile")
    ax.set_xticks(np.arange(len(g)), tlabs, rotation=25, ha="right")
    ax.set_xlabel("Maximum thickness ratio")
    ax.set_ylabel("Absolute drag error (counts)")
    ax.set_title("Thickness stratification", fontsize=9.5)

    ax = axes[1, 1]
    ax.plot(spread["spread_median"], spread["error_median"], marker="o", color=COLORS["mean8"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Median eight-network disagreement (counts)")
    ax.set_ylabel("Median measured drag error (counts)")
    ax.set_title("Disagreement as a risk indicator", fontsize=9.5)
    ax.annotate("small reversal", xy=(spread.loc[2, "spread_median"], spread.loc[2, "error_median"]),
                xytext=(13, 7), textcoords="offset points", fontsize=7, color=COLORS["muted"],
                arrowprops={"arrowstyle": "->", "lw": 0.7, "color": COLORS["muted"]})

    fig.suptitle("Measured error structure of the uncorrected mean-of-eight core", y=0.995, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.09, right=0.98, top=0.91, bottom=0.10, wspace=0.28, hspace=0.42)
    fig.savefig(FIG / "figure_3_operating_envelope.png")
    plt.close(fig)


def figure_trust_signals(clean: pd.DataFrame, spread: pd.DataFrame, conf: pd.DataFrame, metrics: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.1))
    ax = axes[0]
    ax.plot(conf["confidence_median"], conf["error_median"], marker="o", color=COLORS["classic"])
    ax.set_xlabel("Median reported confidence score")
    ax.set_ylabel("Median measured drag error (counts)")
    ax.set_title("Error ranking", fontsize=9.5)

    ax = axes[1]
    ax.plot(conf["confidence_median"], conf["error_le20_share"] * 100, marker="o", color=COLORS["corrected"])
    ax.set_xlabel("Median reported confidence score")
    ax.set_ylabel("Conditions within 20 counts (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Threshold performance", fontsize=9.5)

    ax = axes[2]
    ca = metrics["confidence_audit"]
    labels = ["All\nconditions", "Score\n> 0.90", "Score\n≤ 0.90"]
    vals = [
        ca["overall_error_gt20_share"] * 100,
        ca["high_conf_error_gt20_share"] * 100,
        ca["low_conf_error_gt20_share"] * 100,
    ]
    ax.bar(np.arange(3), vals, color=[COLORS["muted"], COLORS["risk"], COLORS["light"]], edgecolor="#98A2B3")
    ax.set_xticks(np.arange(3), labels)
    ax.set_ylabel("Error > 20 counts (%)")
    ax.set_title("Large-error prevalence", fontsize=9.5)
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=7.7)
    ax.grid(axis="x", visible=False)

    fig.suptitle("The reported confidence score is informative but not calibrated to measurement error", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.82, bottom=0.22, wspace=0.38)
    fig.savefig(FIG / "figure_4_trust_signals.png")
    plt.close(fig)


def figure_transonic(cand: pd.DataFrame, hold: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.1))
    order = ["null", "F1", "F2", "F3"]
    c = cand.set_index("candidate").reindex(order)
    axes[0].bar(np.arange(4), c["loso_mae_counts"], color=[COLORS["xfoil"], COLORS["corrected"], "#8E6C8A", "#5B8E7D"])
    axes[0].set_xticks(np.arange(4), order)
    axes[0].set_ylabel("LOSO MAE (counts)")
    axes[0].set_title("Calibration-source selection")
    for i, v in enumerate(c["loso_mae_counts"]):
        axes[0].text(i, v + 3, f"{v:.0f}", ha="center", fontsize=7.5)

    x = np.arange(len(hold))
    axes[1].bar(x - 0.18, hold["stock_mae_counts"], width=0.36, color=COLORS["classic"], label="Stock")
    axes[1].bar(x + 0.18, hold["model_mae_counts"], width=0.36, color=COLORS["risk"], label="Selected F1")
    axes[1].set_xticks(x, hold["source"])
    axes[1].set_ylabel("Per-sweep increment MAE (counts)")
    axes[1].set_title("Archived holdout")
    axes[1].legend(frameon=False)

    axes[2].bar(x - 0.18, hold["mdd_stock_mae"], width=0.36, color=COLORS["classic"], label="Stock")
    axes[2].bar(x + 0.18, hold["mdd_model_mae"], width=0.36, color=COLORS["risk"], label="Selected F1")
    axes[2].set_xticks(x, hold["source"])
    axes[2].set_ylabel("Mean absolute M_dd error")
    axes[2].set_title("Drag-divergence onset")
    axes[2].legend(frameon=False)

    for ax in axes:
        ax.grid(axis="x", visible=False)
    fig.suptitle("The selected low-parameter transonic recalibration failed to transfer", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.19, wspace=0.37)
    fig.savefig(FIG / "figure_5_transonic_holdout.png")
    plt.close(fig)


def figure_corrections(clean: pd.DataFrame, stall: pd.DataFrame) -> None:
    ind = clean.loc[clean["in_domain"]].copy()
    fig, axes = plt.subplots(1, 3, figsize=(8.4, 3.1))
    cd_vals = [ind["err_cd_mean8"].mean(), ind["err_cd_v2"].mean(), ind["err_cd_corrected"].mean()]
    axes[0].bar(np.arange(3), cd_vals, color=[COLORS["mean8"], "#9C6ADE", COLORS["corrected"]])
    axes[0].set_xticks(np.arange(3), ["Base", "legacy v2", "legacy v3"], rotation=20, ha="right")
    axes[0].set_ylabel("Out-of-fold drag MAE (counts)")
    axes[0].set_title("Drag sensitivity", fontsize=9.5)
    for i, v in enumerate(cd_vals):
        axes[0].text(i, v + 0.8, f"{v:.1f}", ha="center", fontsize=7.5)

    cl_vals = [ind["err_cl_mean8"].mean(), ind["err_cl_corrected"].mean()]
    axes[1].bar(np.arange(2), cl_vals, color=[COLORS["mean8"], COLORS["corrected"]])
    axes[1].set_xticks(np.arange(2), ["Base", "legacy v2"])
    axes[1].set_ylabel("Out-of-fold lift MAE")
    axes[1].set_title("Lift sensitivity", fontsize=9.5)
    for i, v in enumerate(cl_vals):
        axes[1].text(i, v + 0.002, f"{v:.3f}", ha="center", fontsize=7.5)

    sns.histplot(stall["clmax_error"], bins=28, ax=axes[2], color=COLORS["classic"], edgecolor="white")
    axes[2].axvline(0, color="#101828", lw=0.8)
    axes[2].axvline(stall["clmax_error"].mean(), color=COLORS["risk"], lw=1.3, label=f"Mean {stall['clmax_error'].mean():+.3f}")
    axes[2].set_xlabel("Predicted minus measured C_L,max")
    axes[2].set_ylabel("Sweeps")
    axes[2].set_title("Stall bias", fontsize=9.5)
    axes[2].legend(frameon=False)
    for ax in axes[:2]:
        ax.grid(axis="x", visible=False)

    fig.suptitle("Legacy correction sensitivity and remaining stall bias", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.23, wspace=0.40)
    fig.savefig(FIG / "figure_6_corrections_and_stall.png")
    plt.close(fig)


def main() -> None:
    setup_style()
    clean, unique, common = load_low_speed()
    metrics = verified_metrics(clean, unique, common)
    cohort_and_availability_tables(clean, unique, common)
    spread, conf = make_deciles(clean)
    re_table = re_band_table(clean, common)
    cand, hold = transonic_summary()
    stall, stall_stats = stall_metrics()
    metrics["stall_cluster_bootstrap"] = stall_stats

    # Additional transparent notes for the manuscript audit.
    metrics["audit_notes"] = {
        "published_entry_level_configuration_overwrote_row_level_label": True,
        "legacy_corrections_trained_on_mixed_clean_and_modified_rows": True,
        "clean_only_retraining_blocked_by_untracked_lsat_nf2_and_geometry_inputs": True,
        "published_spread_deciles_double_counted_boundary_ties": True,
        "corrected_spread_decile_rows_sum": int(spread["n"].sum()),
        "spread_deciles_strictly_monotone_in_median_error": bool(np.all(np.diff(spread["error_median"]) >= 0)),
        "head_to_head_uses_unique_condition_keys": True,
        "public_repo_missing_extended_capture_and_geometry_inputs": [
            "study/data/lsat-nf2.csv",
            "study/data/lsat-geometry.json",
            "study/data/tn3607_geom.npy",
            "study/data/tn1546_geom.npy (regenerable from study/tools/tn1546_geom.py)",
        ],
    }
    (OUT / "verified_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    figure_study_design()
    figure_head_to_head(common, metrics)
    figure_operating_envelope(clean, re_table, spread)
    figure_trust_signals(clean, spread, conf, metrics)
    figure_transonic(cand, hold)
    figure_corrections(clean, stall)

    print(json.dumps(metrics, indent=2))
    print("\nFigures written to", FIG)


if __name__ == "__main__":
    main()
