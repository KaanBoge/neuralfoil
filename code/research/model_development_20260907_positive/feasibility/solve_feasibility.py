"""Retrospective exposed-outcome calibration, explicitly not validation."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
C3 = PROJECT/"model_development_20260907_search"
C4 = PROJECT/"model_development_20260907_transition"
NEW = ["transition_mixed__1", "transition_balanced__1", "transition_simplex__1", "geometry42_mixed__1", "joint62_mixed__1"]


def load_inputs():
    frames, hashes = [], {}
    paths = sorted((C3/"results").glob("predictions_*.csv"))
    paths += [C3/"exposed_results"/f"{name}_predictions.csv" for name in ["SG_exposed", "W_new_challenge"]]
    components = None
    for path in paths:
        other = C4/path.relative_to(C3)
        a, b = pd.read_csv(path), pd.read_csv(other)
        for p in [path, other]:
            hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        if components is None:
            components = ["identity", "xlarge_fixed"]+[c for c in a if c.endswith("__1")]+NEW
            assert len(components) == 21
        assert len(a) == len(b)
        if "nf2_row_id" in a:
            assert not a.duplicated(["split", "nf2_row_id"]).any()
            assert not b.duplicated(["split", "nf2_row_id"]).any()
            b = b.set_index(["split", "nf2_row_id"]).loc[pd.MultiIndex.from_frame(a[["split", "nf2_row_id"]])].reset_index()
        for key in ["nf2_row_id", "split", "group", "source", "entry", "airfoil", "configuration", "block", "source_line", "Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD"]:
            if key in a:
                np.testing.assert_array_equal(a[key].to_numpy(), b[key].to_numpy(), err_msg=f"{path.name}:{key}")
        for key in NEW:
            a[key] = b[key].to_numpy()
        if "nf2_row_id" not in a:
            a["split"] = path.stem.replace("_predictions", "")
        a["input_row_index"] = np.arange(len(a))
        a["input_file"] = str(path)
        frames.append(a)
    d = pd.concat(frames, ignore_index=True)
    assert np.isfinite(d[components+["measured_CD", "mean8_CD", "xlarge_CD"]].to_numpy()).all()
    assert (d[components].to_numpy() > 0).all()
    return d, components, hashes


def panels(d):
    out = {}
    for seed in [20260906, 20260908]:
        mask = d.split.str.startswith(f"group_{seed}_")
        assert mask.sum() == 8371
        out[f"history_{seed}_pooled"] = np.flatnonzero(mask)
        for source in sorted(d.loc[mask, "source"].unique()):
            out[f"history_{seed}_{source}"] = np.flatnonzero(mask & (d.source == source))
    strict = sorted(s for s in d.split.unique() if s.startswith("strict_source_"))
    assert len(strict) == 5
    for name in strict:
        out[name] = np.flatnonzero(d.split == name)
    for cohort, field, expected in [("SG_exposed", "airfoil", 2), ("W_new_challenge", "configuration", 4)]:
        mask = d.split == cohort
        out[cohort+"_pooled"] = np.flatnonzero(mask)
        names = sorted(d.loc[mask, field].unique())
        assert len(names) == expected
        for name in names:
            out[cohort+"_"+name] = np.flatnonzero(mask & (d[field] == name))
    assert len(out) == 23
    cover = np.zeros(len(d), dtype=int)
    for ix in out.values():
        assert len(ix)
        cover[ix] += 1
    assert (cover > 0).all()
    return out


def metrics(d, pred, panel_map, label):
    rows = []
    for name, ix in panel_map.items():
        y = d.measured_CD.to_numpy()[ix]
        e = np.abs(pred[ix]-y)
        row = {"candidate": label, "panel": name, "rows": len(ix), "mae_CD": float(e.mean()),
               "median_absolute_error_CD": float(np.median(e)), "p90_absolute_error_CD": float(np.quantile(e, .9))}
        for baseline in ["xlarge_CD", "mean8_CD"]:
            error = np.abs(d[baseline].to_numpy()[ix]-y)
            assert error.sum() > 0
            row[baseline+"_mae"] = float(error.mean())
            row[baseline+"_improvement_percent"] = float(100*(1-e.sum()/error.sum()))
            row[baseline+"_worse_rows"] = int((e > error+1e-14).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def solve(d, components, panel_map, baselines):
    t0 = time.monotonic()
    x = d[components].to_numpy()*1e4
    y = d.measured_CD.to_numpy()*1e4
    n, k = x.shape
    # Variables are k weights, n absolute errors, and minimum improvement t.
    zero = sparse.csr_matrix((n, 1))
    a = sparse.vstack([sparse.hstack([sparse.csr_matrix(x), -sparse.eye(n), zero]),
                       sparse.hstack([-sparse.csr_matrix(x), -sparse.eye(n), zero])], format="csr")
    rhs = [y, -y]
    panel_constraints = sparse.lil_matrix((len(panel_map)*len(baselines), k+n+1))
    thresholds = []
    counter = 0
    for baseline in baselines:
        be = np.abs(d[baseline].to_numpy()*1e4-y)
        for ix in panel_map.values():
            total = float(be[ix].sum())
            panel_constraints[counter, k+ix] = 1/total
            panel_constraints[counter, -1] = 1
            thresholds.append(1.)
            counter += 1
    a = sparse.vstack([a, panel_constraints.tocsr()], format="csr")
    rhs.append(np.asarray(thresholds))
    equality = sparse.lil_matrix((1, k+n+1))
    equality[0, :k] = 1
    cost = np.zeros(k+n+1)
    cost[-1] = -1
    result = linprog(cost, A_ub=a, b_ub=np.concatenate(rhs), A_eq=equality.tocsr(), b_eq=[1.],
                     bounds=[(0, 1)]*k+[(0, None)]*n+[(None, 1)], method="highs-ipm")
    assert result.success, result.message
    w = result.x[:k]
    assert w.min() >= -1e-9 and abs(w.sum()-1) < 1e-9
    pred = d[components].to_numpy()@w
    table = metrics(d, pred, panel_map, "blend_"+"_".join(baselines))
    actual_margin = min(table[b+"_improvement_percent"].min()/100 for b in baselines)
    assert actual_margin >= result.x[-1]-2e-7, (actual_margin, result.x[-1])
    np.testing.assert_allclose(np.abs(pred*1e4-y), np.maximum(x@w-y, y-x@w), atol=1e-10)
    return pred, table, {"baselines": baselines, "weights": dict(zip(components, map(float, w))),
                         "solver_min_improvement_fraction": float(result.x[-1]),
                         "actual_min_improvement_fraction": float(actual_margin),
                         "strictly_positive_at_1e_7_tolerance": bool(actual_margin > 1e-7),
                         "seconds": time.monotonic()-t0, "iterations": int(result.nit),
                         "status": "retrospective_exposed_outcome_calibration_not_heldout_validation"}


def main():
    assert not (HERE/"report.json").exists(), "Preserve completed results"
    d, components, hashes = load_inputs()
    panel_map = panels(d)
    singles = pd.concat([metrics(d, d[c].to_numpy(), panel_map, c) for c in components], ignore_index=True)
    singles.to_csv(HERE/"single_component_metrics.csv", index=False)
    minima = singles.groupby("candidate")[["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]].min()
    print("Single candidate minima", minima.to_json(), flush=True)
    report = {"status": "RETROSPECTIVE_FEASIBILITY_USING_EXPOSED_OUTCOMES_NOT_VALIDATION", "rows": len(d),
              "components": components, "panels": {k: len(v) for k, v in panel_map.items()}, "input_sha256": hashes,
              "single_candidates_positive_all_xlarge": minima.index[minima.xlarge_CD_improvement_percent > 1e-5].tolist(),
              "single_candidates_positive_all_both": minima.index[(minima > 1e-5).all(axis=1)].tolist(), "solutions": {}}
    all_metrics = []
    for name, baselines in [("xlarge", ["xlarge_CD"]), ("both", ["xlarge_CD", "mean8_CD"])]:
        pred, table, solution = solve(d, components, panel_map, baselines)
        d["retrospective_blend_"+name] = pred
        all_metrics.append(table)
        report["solutions"][name] = solution
        (HERE/f"blend_{name}.json").write_text(json.dumps(solution, indent=2)+"\n")
        print(name, json.dumps(solution), flush=True)
    pd.concat(all_metrics).to_csv(HERE/"blend_panel_metrics.csv", index=False)
    d.to_csv(HERE/"all_row_predictions.csv", index=False)
    (HERE/"report.json").write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()
