"""Common-cohort reconciliation, fixed stopping gate and conditional group bootstrap."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
POSITIVE = HERE.parent / "model_development_20260907_positive"
sys.path[:0] = [str(POSITIVE / "feasibility"), str(POSITIVE)]
import solve_feasibility as old
import reconcile_results as reconcile

CAPACITY = ["hist62_moderate", "hist62_regularized", "extra62_mixed", "extra24_mixed"]
REFERENCE = "reference_primary_both"
N_BOOTSTRAP = 20000
SEED = 2026090717


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_common(a, b):
    assert len(a) == len(b)
    for key in ["nf2_row_id", "group", "source", "entry", "airfoil", "configuration", "source_line", "block", "Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD"]:
        if key not in a or key not in b:
            continue
        aa, bb = a[key].to_numpy(), b[key].to_numpy()
        if pd.api.types.is_numeric_dtype(a[key]) and pd.api.types.is_numeric_dtype(b[key]):
            np.testing.assert_allclose(aa, bb, atol=1e-13, rtol=0, equal_nan=True, err_msg=key)
        else:
            assert np.array_equal(a[key].fillna("").astype(str).to_numpy(), b[key].fillna("").astype(str).to_numpy()), key


def join_branch(frame, branch, columns, prefix, hashes):
    for split in frame.split.unique():
        external = split in ["SG_exposed", "W_new_challenge"]
        path = HERE / branch / ("exposed_results" if external else "results") / (f"{split}_predictions.csv" if external else f"predictions_{split}.csv")
        hashes[str(path)] = sha(path)
        b = pd.read_csv(path, low_memory=False)
        mask = frame.split == split
        a = frame.loc[mask]
        if not external:
            assert not b.nf2_row_id.duplicated().any()
            assert set(a.nf2_row_id) == set(b.nf2_row_id)
            b = b.set_index("nf2_row_id").loc[a.nf2_row_id].reset_index()
        check_common(a, b)
        for name in columns:
            pred = b[name].to_numpy()
            assert np.isfinite(pred).all() and (pred > 0).all()
            frame.loc[mask, prefix + name] = pred
    return [prefix + name for name in columns]


def load_frame(branches):
    frame, components, hashes = old.load_inputs()
    path = POSITIVE / "historical_results/all_row_predictions.csv"
    prior = pd.read_csv(path, low_memory=False)
    hashes[str(path)] = sha(path)
    check_common(frame, prior)
    np.testing.assert_array_equal(frame.split.to_numpy(), prior.split.to_numpy())
    frame[REFERENCE] = prior.primary_both.to_numpy()
    labels = []
    if "capacity" in branches:
        columns = [f"{name}__{s:g}" for name in CAPACITY for s in [.5, 1.]] + ["both_minimax_selector"]
        labels += join_branch(frame, "capacity", columns, "capacity__", hashes)
    if "kernel" in branches:
        manifest = json.loads((HERE / "kernel/results/run_manifest.json").read_text())
        # Labels are read from the completed frozen registry, not guessed or selected by scores.
        registry = manifest.get("candidates", manifest.get("labels"))
        assert isinstance(registry, list) and registry
        columns = [name for name in registry if name not in ["identity", "xlarge_fixed", "cycle2_fixed__1", "gate_shrink__1"]]
        columns += ["both_minimax_selector"]
        labels += join_branch(frame, "kernel", columns, "kernel__", hashes)
    if "conditional" in branches:
        path = HERE / "conditional/results/all_row_predictions.csv"
        b = pd.read_csv(path, low_memory=False)
        hashes[str(path)] = sha(path)
        check_common(frame, b)
        np.testing.assert_array_equal(frame.split.to_numpy(), b.split.to_numpy())
        for variant in ["re2", "alpha2", "re_alpha4"]:
            name = "conditional__" + variant
            frame[name] = b[variant].to_numpy()
            labels.append(name)
    assert len(frame) == 29856
    assert np.isfinite(frame[labels + [REFERENCE]].to_numpy()).all()
    return frame, components, labels, hashes


def conditional_bootstrap(frame, labels):
    results = []
    for seed in [20260906, 20260908]:
        f = frame[frame.split.str.startswith(f"group_{seed}_")].copy()
        assert len(f) == 8371 and not f.nf2_row_id.duplicated().any()
        groups, inv = np.unique(f.group, return_inverse=True)
        y = f.measured_CD.to_numpy()
        reference = np.bincount(inv, weights=np.abs(f[REFERENCE].to_numpy() - y))
        xlarge = np.bincount(inv, weights=np.abs(f.xlarge_CD.to_numpy() - y))
        # Same seed/common group order across assignments makes paired uncertainty comparable;
        # the assignments are still overlapping, not two independent datasets.
        rng = np.random.default_rng(SEED)
        counts = rng.multinomial(len(groups), np.full(len(groups), 1 / len(groups)), size=N_BOOTSTRAP)
        re = counts @ reference
        xb = counts @ xlarge
        for label in labels:
            error = np.bincount(inv, weights=np.abs(f[label].to_numpy() - y))
            ce = counts @ error
            benefit = 100 * (1 - ce / re)
            pp = 100 * (re - ce) / xb
            lo, hi = np.quantile(benefit, [.025, .975])
            plo, phi = np.quantile(pp, [.025, .975])
            results.append({"candidate": label, "assignment": seed, "rows": len(f), "groups": len(groups),
                            "relative_remaining_MAE_reduction_percent": float(100 * (1 - error.sum() / reference.sum())),
                            "conditional_95pct_lower": float(lo), "conditional_95pct_upper": float(hi),
                            "xlarge_improvement_increment_percentage_points": float(100 * (reference.sum() - error.sum()) / xlarge.sum()),
                            "increment_conditional_95pct_lower_pp": float(plo), "increment_conditional_95pct_upper_pp": float(phi),
                            "bootstrap_fraction_benefit_positive": float(np.mean(benefit > 0)),
                            "interpretation": "descriptive conditional paired group bootstrap; not adjusted for adaptive selection"})
    return pd.DataFrame(results)


def stopping_gate(frame, labels, table, bootstrap):
    fields = ["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]
    external = table.panel.str.startswith("eligible_only/")
    re = table[(table.candidate == REFERENCE) & external]
    assert len(re) == 8
    ref_negative = int((re[fields].to_numpy() < 0).sum())
    ref_worst = float(re[fields].to_numpy().min())
    rows = []
    for candidate in labels:
        train = bootstrap[bootstrap.candidate == candidate]
        assert len(train) == 2
        historical_gain = bool((train.relative_remaining_MAE_reduction_percent >= 1).all())
        strict = table[(table.candidate == candidate) & table.panel.str.startswith("strict_source_")]
        assert len(strict) == 5
        source_safe = bool((strict[fields].to_numpy() >= 0).all())
        e = table[(table.candidate == candidate) & external]
        assert len(e) == 8
        count = int((e[fields].to_numpy() < 0).sum())
        worst = float(e[fields].to_numpy().min())
        safe = count <= ref_negative and worst >= ref_worst - 1e-6
        rows.append({"candidate": candidate, "historical_remaining_error_gain_both_at_least_1pct": historical_gain,
                     "all_five_strict_sources_nonnegative_both_baselines": source_safe,
                     "eligible_external_negative_panel_baseline_count": count,
                     "reference_eligible_external_negative_count": ref_negative,
                     "worst_eligible_external_improvement_percent": worst,
                     "reference_worst_eligible_external_improvement_percent": ref_worst,
                     "external_regression_guard_pass": safe,
                     "operational_frontier_advance": historical_gain and source_safe and safe})
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--branches", nargs="+", required=True, choices=["capacity", "kernel", "conditional"])
    args = parser.parse_args()
    out = HERE / ("assessment_" + args.stage)
    out.mkdir(exist_ok=False)
    frame, _, labels, hashes = load_frame(args.branches)
    panels = old.panels(frame)
    panels.update({k: v for k, v in reconcile.external_panels(frame).items() if k.startswith("eligible_only/")})
    table = pd.concat([old.metrics(frame, frame[label].to_numpy(), panels, label) for label in [REFERENCE] + labels], ignore_index=True)
    bootstrap = conditional_bootstrap(frame, labels)
    decisions = stopping_gate(frame, labels, table, bootstrap)
    table.to_csv(out / "panel_metrics.csv", index=False)
    bootstrap.to_csv(out / "conditional_paired_bootstrap.csv", index=False)
    decisions.to_csv(out / "operational_decisions.csv", index=False)
    frame.to_csv(out / "all_row_predictions.csv", index=False)
    for filename, expected in hashes.items():
        assert sha(filename) == expected
    manifest = {"stage": args.stage, "branches": args.branches, "labels": labels, "input_sha256": hashes,
                "script_sha256": sha(Path(__file__)), "root_protocol_current_sha256": sha(HERE / "PROTOCOL.md"),
                "bootstrap_draws": N_BOOTSTRAP, "bootstrap_seed": SEED,
                "numeric_common_field_join_tolerance_absolute": 1e-13,
                "operational_passes": decisions.loc[decisions.operational_frontier_advance, "candidate"].tolist(),
                "warning": "All outcomes already exposed; fixed-candidate comparison and paired CIs do not establish independent validation or an absolute limit."}
    (out / "report.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(decisions.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
