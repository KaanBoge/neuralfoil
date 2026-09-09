"""Numerically bound a finite exposed-calibration convex hull, not all future models."""
from pathlib import Path
import hashlib
import json
import sys
import time
import warnings
import numpy as np
from scipy import sparse
from scipy.optimize import linprog, OptimizeWarning

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "model_development_20260907_positive/feasibility"
OUT = HERE / "fixed_class_limit"
sys.path.insert(0, str(PRIOR))
import solve_feasibility as previous


def problem(d, components, panels, baselines):
    p = d[components].to_numpy() * 1e4
    y = d.measured_CD.to_numpy() * 1e4
    n, k = p.shape
    zero = sparse.csr_matrix((n, 1))
    a = sparse.vstack([sparse.hstack([sparse.csr_matrix(p), -sparse.eye(n), zero]),
                       sparse.hstack([-sparse.csr_matrix(p), -sparse.eye(n), zero])], format="csr")
    # Under convex weights |P_i w-y_i| cannot exceed the largest component error.
    # Bounding slack by that maximum leaves at least one slack representation of
    # every possible prediction and therefore preserves the optimal objective.
    emax = np.max(np.abs(p - y[:, None]), axis=1)
    pc = sparse.lil_matrix((len(panels) * len(baselines), k + n + 1))
    panel_records = []
    maximum_possible_ratio = 0.
    for baseline in baselines:
        be = np.abs(d[baseline].to_numpy() * 1e4 - y)
        for name, idx in panels.items():
            total = float(be[idx].sum())
            assert total > 0
            j = len(panel_records)
            pc[j, k + idx] = 1 / total
            pc[j, -1] = 1
            maximum_possible_ratio = max(maximum_possible_ratio, float(emax[idx].sum() / total))
            panel_records.append({"panel": name, "baseline": baseline, "baseline_total_counts": total})
    a = sparse.vstack([a, pc.tocsr()], format="csr")
    b = np.concatenate([y, -y, np.ones(len(panel_records))])
    eq = sparse.lil_matrix((1, k + n + 1))
    eq[0, :k] = 1
    c = np.zeros(k + n + 1)
    c[-1] = -1
    lo = np.concatenate([np.zeros(k + n), [-maximum_possible_ratio]])
    hi = np.concatenate([np.ones(k), emax, [1.]])
    assert np.isfinite(lo).all() and np.isfinite(hi).all() and (lo <= hi).all()
    return c, a, b, eq.tocsr(), np.ones(1), lo, hi, panel_records


def certified_lower_bound(c, a, b, eq, rhs, lo, hi, result):
    """Residual-corrected weak-duality bound, evaluated in floating-point arithmetic.

    For Ax<=b use multipliers q<=0. Put r=c-A.T q-E.T z.
    Then c'x >= b'q+rhs'z + min_{lo<=x<=hi} r'x for every feasible x.
    Sign clipping ensures q<=0 without assuming approximate dual feasibility.
    All bounds are finite so residuals have a finite, explicit correction.
    This is not an interval-arithmetic or exact-rational formal proof.
    """
    q = np.minimum(result.ineqlin.marginals, 0.)
    z = result.eqlin.marginals
    residual = c - a.T @ q - eq.T @ z
    box_correction = np.minimum(residual * lo, residual * hi)
    dual_rhs = float(np.dot(b.astype(np.longdouble), q.astype(np.longdouble)) +
                     np.dot(rhs.astype(np.longdouble), z.astype(np.longdouble)))
    lower = dual_rhs + float(box_correction.astype(np.longdouble).sum())
    conventional_stationarity = c - a.T @ result.ineqlin.marginals - eq.T @ z - result.lower.marginals - result.upper.marginals
    return lower, {"dual_rhs": dual_rhs, "finite_box_correction": float(box_correction.sum()),
                   "conventional_stationarity_max_abs": float(np.abs(conventional_stationarity).max()),
                   "unclipped_inequality_dual_positive_max": float(np.maximum(result.ineqlin.marginals, 0).max())}, q, z


def main():
    OUT.mkdir(exist_ok=False)
    d, components, hashes = previous.load_inputs()
    panels = previous.panels(d)
    report = {"status": "finite_fixed_prediction_class_exposed_calibration_limit_only",
              "rows_including_repeated_contexts": len(d), "components": components,
              "panels": list(panels), "input_sha256": hashes,
              "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "helper_sha256": hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest(), "solutions": {}}
    for name, baselines in [("both", ["xlarge_CD", "mean8_CD"]), ("xlarge", ["xlarge_CD"])]:
        c, a, b, eq, rhs, lo, hi, records = problem(d, components, panels, baselines)
        name_results = []
        for method in ["highs-ipm", "highs-ds"]:
            started = time.monotonic()
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=OptimizeWarning, message="Unrecognized options detected")
                result = linprog(c, A_ub=a, b_ub=b, A_eq=eq, b_eq=rhs, bounds=list(zip(lo, hi)),
                                 method=method, options={"threads": 1, "primal_feasibility_tolerance": 1e-9,
                                     "dual_feasibility_tolerance": 1e-9, "ipm_optimality_tolerance": 1e-10})
            assert result.success, result.message
            w = np.maximum(result.x[:len(components)], 0.)
            w /= w.sum()
            pred = d[components].to_numpy() @ w
            table = previous.metrics(d, pred, panels, name + "_" + method)
            achieved = min(float(table[base + "_improvement_percent"].min()) / 100 for base in baselines)
            lower, checks, q, z = certified_lower_bound(c, a, b, eq, rhs, lo, hi, result)
            upper_margin = -lower
            gap = upper_margin - achieved
            assert gap >= -1e-9 and gap < 1e-6, gap
            assert np.max(a @ result.x - b) < 1e-6
            assert np.max(np.abs(eq @ result.x - rhs)) < 1e-9
            prior = json.loads((PRIOR / f"blend_{name}.json").read_text())
            assert abs(achieved - prior["actual_min_improvement_fraction"]) < 1e-7
            rec = {"method": method, "baselines": baselines, "achieved_min_improvement_percent": 100 * achieved,
                   "numerical_upper_bound_improvement_percent": 100 * upper_margin,
                   "bound_gap_percentage_points": 100 * gap,
                   "primal_max_inequality_violation": float(np.max(a @ result.x - b)),
                   "weights": dict(zip(components, map(float, w))), "dual_checks": checks,
                   "seconds": time.monotonic() - started, "iterations": int(result.nit)}
            name_results.append(rec)
            table.to_csv(OUT / f"metrics_{name}_{method}.csv", index=False)
            np.savez_compressed(OUT / f"certificate_{name}_{method}.npz", primal=result.x,
                                inequality_dual=q, equality_dual=z, lower_bounds=lo, upper_bounds=hi)
            print(json.dumps(rec), flush=True)
        assert abs(name_results[0]["achieved_min_improvement_percent"] - name_results[1]["achieved_min_improvement_percent"]) < 1e-6
        report["solutions"][name] = name_results
    for filename, expected in hashes.items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == expected
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
