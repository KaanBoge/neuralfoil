from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

import analyze_study as base


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
FIG = ROOT / "figures"
SIZES = [
    "xxsmall", "xsmall", "small", "medium",
    "large", "xlarge", "xxlarge", "xxxlarge",
]
LAMBDA = 3e-2
SEED = 824
COUNTS = 1e4


def make_design(clean: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    d = clean.loc[
        clean["Re"].le(6e5)
        & clean["alpha"].abs().le(12)
        & clean["tc"].between(0.05, 0.20)
        & clean["CD_meas"].gt(0)
        & clean["CD_mean8"].gt(0)
    ].copy()
    spread = d["spread_counts"].to_numpy() / COUNTS
    lre = np.log10(d["Re"].to_numpy())
    a = d["alpha"].to_numpy()
    tc = d["tc"].to_numpy()
    lcd = np.log(d["CD_mean8"].to_numpy())
    lsp = np.log(np.maximum(spread, 1e-6))
    conf = d["conf_xlarge"].to_numpy()
    cl8 = d["CL_mean8"].to_numpy()
    X = np.column_stack(
        [
            np.ones(len(d)), lre, lre**2, a, a**2, a**3, tc, tc**2,
            lcd, lsp, conf, cl8, cl8**2, lre * a, lre * tc, a * tc,
            lre * lcd, a * cl8, lre * cl8, lsp * lre, lcd * a,
        ]
    )
    y = np.clip(np.log(d["CD_meas"].to_numpy() / d["CD_mean8"].to_numpy()), -1.5, 1.5)
    return d.reset_index(drop=True), X, y


def fit_predict(X: np.ndarray, y: np.ndarray, train: np.ndarray, test: np.ndarray) -> np.ndarray:
    mu = X[train].mean(axis=0)
    sd = X[train].std(axis=0)
    sd[sd == 0] = 1
    mu[0], sd[0] = 0, 1
    x_train = (X[train] - mu) / sd
    x_test = (X[test] - mu) / sd
    ridge = LAMBDA * train.sum() * np.eye(X.shape[1])
    w = np.linalg.solve(x_train.T @ x_train + ridge, x_train.T @ y[train])
    return x_test @ w


def evaluate(d: pd.DataFrame, pred: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    base_cd = d.loc[mask, "CD_mean8"].to_numpy()
    measured = d.loc[mask, "CD_meas"].to_numpy()
    corrected = base_cd * np.exp(np.clip(pred[mask], np.log(0.5), np.log(2.0)))
    raw_error = np.abs(base_cd - measured) * COUNTS
    corrected_error = np.abs(corrected - measured) * COUNTS
    return {
        "rows": int(mask.sum()),
        "airfoil_names": int(d.loc[mask, "airfoil"].nunique()),
        "entries": int(d.loc[mask, "entry"].nunique()),
        "raw_mae_counts": float(raw_error.mean()),
        "corrected_mae_counts": float(corrected_error.mean()),
        "paired_change_counts": float((corrected_error - raw_error).mean()),
        "raw_median_counts": float(np.median(raw_error)),
        "corrected_median_counts": float(np.median(corrected_error)),
        "raw_p90_counts": float(np.quantile(raw_error, 0.90)),
        "corrected_p90_counts": float(np.quantile(corrected_error, 0.90)),
    }


def main() -> None:
    clean, _, _ = base.load_low_speed()
    d, X, y = make_design(clean)
    rng = np.random.default_rng(SEED)

    airfoils = np.array(sorted(d["airfoil"].unique()))
    rng.shuffle(airfoils)
    folds = [set(airfoils[i::5]) for i in range(5)]
    oof = np.full(len(d), np.nan)
    fold_rows = []
    for i, holdout in enumerate(folds):
        test = d["airfoil"].isin(holdout).to_numpy()
        train = ~test
        oof[test] = fit_predict(X, y, train, test)
        row = {"comparison": f"Grouped fold {i + 1}", **evaluate(d, oof, test)}
        fold_rows.append(row)

    if np.isnan(oof).any():
        raise RuntimeError("Grouped OOF prediction left unscored rows")

    transfer_rows = []
    for train_label, test_label, train in [
        ("Volumes 1-3", "SoarTech 8", d["source"].ne("stec8").to_numpy()),
        ("SoarTech 8", "Volumes 1-3", d["source"].eq("stec8").to_numpy()),
    ]:
        test = ~train
        pred = np.zeros(len(d))
        pred[test] = fit_predict(X, y, train, test)
        transfer_rows.append(
            {
                "comparison": f"Train {train_label}; test {test_label}",
                **evaluate(d, pred, test),
            }
        )

    loso_rows = []
    for source in sorted(d["source"].unique()):
        test = d["source"].eq(source).to_numpy()
        train = ~test
        pred = np.zeros(len(d))
        pred[test] = fit_predict(X, y, train, test)
        loso_rows.append(
            {
                "comparison": f"Leave source {source} out",
                **evaluate(d, pred, test),
            }
        )

    base_cd = d["CD_mean8"].to_numpy()
    measured = d["CD_meas"].to_numpy()
    corrected = base_cd * np.exp(np.clip(oof, np.log(0.5), np.log(2.0)))
    d["zcd_clean_v1_oof"] = oof
    d["CD_clean_v1_oof"] = corrected
    d["err_cd_base"] = np.abs(base_cd - measured) * COUNTS
    d["err_cd_clean_v1_oof"] = np.abs(corrected - measured) * COUNTS
    d["delta_clean_v1_minus_base"] = d["err_cd_clean_v1_oof"] - d["err_cd_base"]
    interval = base.cluster_bootstrap_mean(
        d,
        ["err_cd_base", "err_cd_clean_v1_oof", "delta_clean_v1_minus_base"],
        cluster="entry",
        n_boot=4000,
    )

    row_out = d[
        [
            "source", "airfoil", "entry", "Re", "alpha", "CD_meas", "CD_mean8",
            "zcd_clean_v1_oof", "CD_clean_v1_oof", "err_cd_base",
            "err_cd_clean_v1_oof", "delta_clean_v1_minus_base",
        ]
    ]
    row_out.to_csv(OUT / "post_audit_clean_v1_oof.csv", index=False)
    summary = pd.DataFrame(fold_rows + transfer_rows + loso_rows)
    summary.to_csv(OUT / "post_audit_clean_v1_summary.csv", index=False)

    entry = d.groupby("entry", as_index=False)[["err_cd_base", "err_cd_clean_v1_oof"]].mean()
    results = {
        "status": "post-audit exploratory clean-only refit; not an independently validated release",
        "model": "original prespecified 21-term ridge basis with training-only scaling",
        "lambda": LAMBDA,
        "seed": SEED,
        "in_domain_rows": int(len(d)),
        "airfoil_names": int(d["airfoil"].nunique()),
        "entries": int(d["entry"].nunique()),
        "grouped_oof": interval,
        "airfoil_macro": {
            "base_mae_counts": float(entry["err_cd_base"].mean()),
            "corrected_mae_counts": float(entry["err_cd_clean_v1_oof"].mean()),
            "corrected_better_entry_share": float((entry["err_cd_clean_v1_oof"] < entry["err_cd_base"]).mean()),
        },
        "folds": fold_rows,
        "two_way_facility_transfer": transfer_rows,
        "leave_one_source_out": loso_rows,
        "original_ship_rule_passed": bool(
            interval["delta_clean_v1_minus_base"]["estimate"] < 0
            and all(r["paired_change_counts"] < 0 for r in transfer_rows)
        ),
    }
    (OUT / "post_audit_clean_v1_metrics.json").write_text(json.dumps(results, indent=2) + "\n")

    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "savefig.dpi": 600})
    fig, axes = plt.subplots(1, 3, figsize=(8.7, 3.25))

    ax = axes[0]
    folds_df = summary.loc[summary["comparison"].str.startswith("Grouped")]
    x = np.arange(len(folds_df))
    ax.bar(x - 0.18, folds_df["raw_mae_counts"], width=0.36, label="Base", color="#6B7280")
    ax.bar(x + 0.18, folds_df["corrected_mae_counts"], width=0.36, label="Clean-only OOF", color="#2E7D5B")
    ax.set_xticks(x, [f"F{i}" for i in range(1, 6)])
    ax.set_ylabel("Drag MAE (counts)")
    ax.set_title("Airfoil-disjoint folds")
    ax.legend(frameon=False, fontsize=7)
    ax.grid(axis="x", visible=False)

    ax = axes[1]
    transfer_df = summary.loc[summary["comparison"].str.startswith("Train")]
    x = np.arange(len(transfer_df))
    ax.bar(x - 0.18, transfer_df["raw_mae_counts"], width=0.36, color="#6B7280")
    ax.bar(x + 0.18, transfer_df["corrected_mae_counts"], width=0.36, color="#B66A16")
    ax.set_xticks(x, ["Test\nSoarTech 8", "Test\nVolumes 1-3"])
    ax.set_ylabel("Drag MAE (counts)")
    ax.set_title("Two-way facility transfer")
    ax.grid(axis="x", visible=False)

    ax = axes[2]
    for col, label, color in [
        ("err_cd_base", "Base", "#6B7280"),
        ("err_cd_clean_v1_oof", "Clean-only OOF", "#2E7D5B"),
    ]:
        values = np.sort(d[col].to_numpy())
        survival = 1 - np.arange(1, len(values) + 1) / len(values)
        ax.step(values, survival * 100, where="post", label=label, color=color, lw=1.2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, max(d["err_cd_base"].max(), d["err_cd_clean_v1_oof"].max()) * 1.05)
    ax.set_ylim(0.05, 100)
    ax.set_xlabel("Absolute drag error (counts)")
    ax.set_ylabel("Conditions exceeding error (%)")
    ax.set_title("OOF tail behavior")
    ax.legend(frameon=False, fontsize=7)

    fig.suptitle("Post-audit clean-only refit of the original low-complexity correction", y=1.00, fontsize=11, weight="bold")
    fig.subplots_adjust(left=0.08, right=0.99, top=0.80, bottom=0.20, wspace=0.38)
    fig.savefig(FIG / "figure_10_clean_only_refit.png", bbox_inches="tight")
    plt.close(fig)

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
