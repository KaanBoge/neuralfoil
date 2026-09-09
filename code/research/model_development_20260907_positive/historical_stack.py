"""Predeclared training-only convex stacking, separate from exposed calibration."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
C3 = PROJECT / "model_development_20260907_search"
C4 = PROJECT / "model_development_20260907_transition"
OUT = HERE / "historical_results"
sys.path.insert(0, str(PROJECT / "model_development_20260906_v2"))
import develop_v2 as v2

C3_NAMES = ["cycle1_fixed", "cycle2_fixed", "invariant_balanced", "invariant_mixed",
            "reflection_averaged", "gate_benefit", "gate_shrink", "smooth9_absolute",
            "smooth9_relative", "smooth16_relative", "median8", "simplex8_l1",
            "simplex8_re_l1", "simplex8_offset_l1"]
C4_NAMES = ["transition_mixed", "transition_balanced", "transition_simplex",
            "geometry42_mixed", "joint62_mixed"]
COMPONENTS = ["identity", "xlarge_fixed"] + [n + "__1" for n in C3_NAMES + C4_NAMES]
NEW = [n + "__1" for n in C4_NAMES]
OBJECTIVES = {"primary_both": ["xlarge_CD", "mean8_CD"], "secondary_xlarge": ["xlarge_CD"]}
TIE_TOL = 1e-7
CHECK_TOL = 2e-6


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_training(name):
    """Only enclosing training metadata/archives enter this function, never outer predictions."""
    d = v2.load_data()
    paths = [C3 / "results" / f"{name}_inner_group.npz"]
    paths += sorted((C3 / "results").glob(f"{name}_inner_transfer_*.npz"))
    frames, hashes, enclosing = [], {}, None
    for j, path in enumerate(paths):
        other = C4 / "results" / path.name
        hashes[str(path)], hashes[str(other)] = sha(path), sha(other)
        with np.load(path) as a, np.load(other) as b:
            for key in ["indices", "train_indices", "test_indices"]:
                if key in a:
                    np.testing.assert_array_equal(a[key], b[key])
            idx = a["indices"] if j == 0 else a["test_indices"]
            assert len(idx) == len(np.unique(idx))
            if j == 0:
                enclosing = idx.copy()
            else:
                tr = a["train_indices"]
                assert set(idx) <= set(enclosing) and set(tr) <= set(enclosing)
                assert not set(idx) & set(tr)
                assert not set(d["group"][idx]) & set(d["group"][tr])
            for key in ["identity", "xlarge_fixed", "cycle2_fixed__1", "gate_shrink__1"]:
                np.testing.assert_array_equal(a[key], b[key])
            np.testing.assert_array_equal(a["identity"], d["BASE_CD"][idx])
            np.testing.assert_array_equal(a["xlarge_fixed"], d["XLARGE_CD"][idx])
            frame = pd.DataFrame({key: d[value][idx] for key, value in {
                "nf2_row_id": "nf2_row_id", "group": "group", "source": "source",
                "measured_CD": "MEAS_CD", "mean8_CD": "BASE_CD", "xlarge_CD": "XLARGE_CD"}.items()})
            frame["historical_index"] = idx
            frame["context"] = "group" if j == 0 else path.stem.split("_inner_", 1)[1]
            for component in COMPONENTS:
                frame[component] = (b if component in NEW else a)[component]
            frames.append(frame)
    return pd.concat(frames, ignore_index=True), enclosing, hashes


def training_panels(frame):
    panels = {}

    def add(name, mask, balanced=False):
        idx = np.flatnonzero(mask)
        assert len(idx)
        if balanced:
            _, inv, counts = np.unique(frame.group.to_numpy()[idx], return_inverse=True, return_counts=True)
            weights = 1 / (len(counts) * counts[inv])
        else:
            weights = np.full(len(idx), 1 / len(idx))
        np.testing.assert_allclose(weights.sum(), 1., atol=1e-14)
        panels[name] = (idx, weights)

    group = frame.context == "group"
    add("group_pooled", group)
    add("group_equal_identity", group, True)
    for source in sorted(frame.loc[group, "source"].unique()):
        add("group_source_" + source, group & (frame.source == source))
    for context in sorted(set(frame.context) - {"group"}):
        mask = frame.context == context
        assert frame.loc[mask, "source"].nunique() == 1
        add(context + "_pooled", mask)
        add(context + "_equal_identity", mask, True)
    return panels


def solve(frame, panels, baselines):
    started = time.monotonic()
    x = frame[COMPONENTS].to_numpy() * 1e4
    y = frame.measured_CD.to_numpy() * 1e4
    assert np.isfinite(x).all() and np.isfinite(y).all() and (x > 0).all()
    n, k = x.shape
    zero = sparse.csr_matrix((n, 1))
    absolute = sparse.vstack([sparse.hstack([sparse.csr_matrix(x), -sparse.eye(n), zero]),
                              sparse.hstack([-sparse.csr_matrix(x), -sparse.eye(n), zero])], format="csr")
    pc = sparse.lil_matrix((len(panels) * len(baselines), k + n + 1))
    panel_info = []
    for baseline in baselines:
        be = np.abs(frame[baseline].to_numpy() * 1e4 - y)
        for panel, (idx, weights) in panels.items():
            denominator = float(weights @ be[idx])
            assert np.isfinite(denominator) and denominator > 0
            j = len(panel_info)
            pc[j, k + idx] = weights / denominator
            pc[j, -1] = -1
            panel_info.append((panel, baseline, denominator))
    a = sparse.vstack([absolute, pc.tocsr()], format="csr")
    rhs = np.concatenate([y, -y, np.zeros(len(panel_info))])
    equality = sparse.lil_matrix((1, k + n + 1))
    equality[0, :k] = 1
    eq = equality.tocsr()
    cost = np.zeros(k + n + 1)
    cost[-1] = 1
    bounds = [(0, 1)] * k + [(0, None)] * n + [(0, None)]
    first = linprog(cost, A_ub=a, b_ub=rhs, A_eq=eq, b_eq=[1.], bounds=bounds, method="highs-ipm")
    assert first.success, first.message
    idx, weights = panels["group_pooled"]
    second_cost = np.zeros(k + n + 1)
    second_cost[k + idx] = weights
    bounds[-1] = (0, float(first.x[-1]) + TIE_TOL)
    second = linprog(second_cost, A_ub=a, b_ub=rhs, A_eq=eq, b_eq=[1.], bounds=bounds, method="highs-ipm")
    assert second.success, second.message
    w = second.x[:k]
    assert w.min() >= -1e-9 and abs(w.sum() - 1) < 1e-9
    pred = x @ w
    error = np.abs(pred - y)
    scores = []
    for panel, baseline, denominator in panel_info:
        idx, weights = panels[panel]
        ratio = float(weights @ error[idx] / denominator)
        scores.append({"panel": panel, "baseline": baseline, "rows": len(idx),
                       "baseline_mae_counts": denominator, "actual_ratio": ratio})
    maximum = max(s["actual_ratio"] for s in scores)
    assert maximum <= first.x[-1] + TIE_TOL + CHECK_TOL, (maximum, first.x[-1])
    assert maximum >= first.x[-1] - CHECK_TOL, (maximum, first.x[-1])
    violation = float(np.max(a @ second.x - rhs))
    assert violation < CHECK_TOL
    return {"weights": dict(zip(COMPONENTS, map(float, w))), "baselines": baselines,
            "first_optimal_ratio": float(first.x[-1]), "actual_worst_training_ratio": maximum,
            "maximum_lp_constraint_violation": violation, "training_panels": scores,
            "seconds": time.monotonic() - started, "solver_iterations": [int(first.nit), int(second.nit)],
            "prediction_ratio_mean8_range": [float(np.min(pred / (frame.mean8_CD.to_numpy() * 1e4))),
                                             float(np.max(pred / (frame.mean8_CD.to_numpy() * 1e4)))]}


def fit_one(name):
    frame, enclosing, hashes = load_training(name)
    panels = training_panels(frame)
    artifact = {"split": name, "status": "adaptive_historical_only_inner_oof_stacking",
                "components": COMPONENTS, "unique_training_rows": len(enclosing),
                "prediction_context_rows": len(frame), "training_nf2_row_ids": frame.loc[frame.context == "group", "nf2_row_id"].tolist(),
                "training_groups": sorted(frame.group.unique()), "input_sha256": hashes,
                "contexts": {str(k): int(v) for k, v in frame.context.value_counts().items()}, "solutions": {}}
    for objective, baselines in OBJECTIVES.items():
        artifact["solutions"][objective] = solve(frame, panels, baselines)
    (OUT / f"weights_{name}.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return name, {key: value["actual_worst_training_ratio"] for key, value in artifact["solutions"].items()}


def evaluate():
    # Deliberately called only after all 16 fits have finished. No evaluation frame enters fit_one.
    sys.path.insert(0, str(HERE / "feasibility"))
    import solve_feasibility as feasibility
    frame, components, hashes = feasibility.load_inputs()
    assert set(components) == set(COMPONENTS)
    frame = frame.copy()
    for objective in OBJECTIVES:
        frame[objective] = np.nan
    split_metrics = []
    for split in frame.split.unique():
        external = split in ["SG_exposed", "W_new_challenge"]
        artifact = json.loads((OUT / f"weights_{'final' if external else split}.json").read_text())
        ix = np.flatnonzero(frame.split == split)
        part = frame.iloc[ix]
        if not external:
            assert not set(part.nf2_row_id) & set(artifact["training_nf2_row_ids"])
            assert not set(part.group) & set(artifact["training_groups"])
        for objective, solution in artifact["solutions"].items():
            pred = part[COMPONENTS].to_numpy() @ np.array([solution["weights"][c] for c in COMPONENTS])
            if external:
                gate_raw = part.inference_gate
                gate = gate_raw.map(lambda v: v is True or str(v).lower() == "true" or v == 1).to_numpy(bool)
                assert gate.sum() == {"SG_exposed": 234, "W_new_challenge": 238}[split]
                pred[~gate] = part.mean8_CD.to_numpy()[~gate]
            assert np.isfinite(pred).all() and (pred > 0).all()
            frame.loc[frame.index[ix], objective] = pred
    panel_map = feasibility.panels(frame)
    tables = []
    group_tables = []
    for objective in OBJECTIVES:
        pred = frame[objective].to_numpy()
        assert np.isfinite(pred).all()
        tables.append(feasibility.metrics(frame, pred, panel_map, objective))
        for split in frame.split.unique():
            ix = np.flatnonzero(frame.split == split)
            split_metrics.append(feasibility.metrics(frame, pred, {split: ix}, objective))
            for group in sorted(frame.loc[frame.split == split, "group"].dropna().unique()):
                gi = np.flatnonzero((frame.split == split) & (frame.group == group))
                group_tables.append(feasibility.metrics(frame, pred, {f"{split}:{group}": gi}, objective))
    metrics = pd.concat(tables, ignore_index=True)
    metrics.to_csv(OUT / "panel_metrics.csv", index=False)
    pd.concat(split_metrics, ignore_index=True).to_csv(OUT / "split_metrics.csv", index=False)
    pd.concat(group_tables, ignore_index=True).to_csv(OUT / "identity_group_metrics.csv", index=False)
    frame.to_csv(OUT / "all_row_predictions.csv", index=False)
    metrics.loc[(metrics.xlarge_CD_improvement_percent < 0) | (metrics.mean8_CD_improvement_percent < 0)].to_csv(OUT / "worsening_panels.csv", index=False)
    report = {"status": "adaptive_exploratory_outer_assessment_plus_exposed_external_diagnostics",
              "input_sha256": hashes, "prediction_context_rows": len(frame),
              "components": COMPONENTS, "ratios_to_mean8": {}, "worst_panels_percent": {}}
    for objective in OBJECTIVES:
        report["ratios_to_mean8"][objective] = [float((frame[objective] / frame.mean8_CD).min()), float((frame[objective] / frame.mean8_CD).max())]
        report["worst_panels_percent"][objective] = metrics.loc[metrics.candidate == objective, ["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]].min().to_dict()
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["worst_panels_percent"]), flush=True)


def main():
    OUT.mkdir(exist_ok=False)
    names = [p.stem.replace("predictions_", "", 1) for p in sorted((C3 / "results").glob("predictions_*.csv"))] + ["final"]
    assert len(names) == 16
    (OUT / "manifest.json").write_text(json.dumps({"source_sha256": sha(Path(__file__)),
        "protocol_sha256": sha(HERE / "PROTOCOL.md"), "components": COMPONENTS,
        "objectives": OBJECTIVES, "names": names, "tie_tolerance": TIE_TOL,
        "numerical_check_tolerance": CHECK_TOL}, indent=2) + "\n")
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(fit_one, name) for name in names]):
            print(json.dumps(future.result()), flush=True)
    evaluate()


if __name__ == "__main__":
    main()
