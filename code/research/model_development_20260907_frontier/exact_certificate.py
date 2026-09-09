"""Exact-rational lower/upper bounds for the archived parsed-float convex class."""
from pathlib import Path
from fractions import Fraction as F
import hashlib
import json
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "model_development_20260907_positive/feasibility"
OUT = HERE / "fixed_class_limit"
sys.path.insert(0, str(PRIOR))
import solve_feasibility as previous


def packed(x):
    return {"numerator": str(x.numerator), "denominator": str(x.denominator)}


def main():
    assert not (OUT / "exact_report.json").exists(), "Preserve completed certificate"
    d, components, hashes = previous.load_inputs()
    panel_map = previous.panels(d)
    n, k = len(d), len(components)
    # F(float) preserves the exact binary value parsed by the original loader.
    # Do not round, subtract floats first, or reinterpret raw decimal text.
    p = [[F(float(v)) for v in row] for row in d[components].to_numpy()]
    y = [F(float(v)) for v in d.measured_CD]
    baseline_errors = {b: [abs(F(float(v)) - target) for v, target in zip(d[b], y)] for b in ["xlarge_CD", "mean8_CD"]}
    numerical = json.loads((OUT / "report.json").read_text())
    report = {"scope": "Exact bounds for 21 global convex weights on 23 fixed panels of the original pandas-parsed binary-float dataset; not a universal physical/model limit",
              "arithmetic": "Python Fraction: every bound/feasibility comparison is rational; decimal displays are approximations",
              "input_sha256": hashes, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "solutions": {}}
    for name, baselines in [("both", ["xlarge_CD", "mean8_CD"]), ("xlarge", ["xlarge_CD"])]:
        started = time.monotonic()
        records = [(label, baseline, list(map(int, idx))) for baseline in baselines for label, idx in panel_map.items()]
        denominators = [sum((baseline_errors[b][i] for i in idx), F(0)) for _, b, idx in records]
        assert all(v > 0 for v in denominators)
        path = OUT / f"certificate_{name}_highs-ds.npz"
        with np.load(path, allow_pickle=False) as archive:
            q = [F(float(v)) for v in archive["inequality_dual"]]
        assert len(q) == 2 * n + len(records)
        positive = [max(-value, F(0)) for value in q[2*n:]]
        normalizer = sum(positive, F(0))
        assert normalizer > 0
        beta = [v / normalizer for v in positive]
        assert sum(beta, F(0)) == 1 and all(v >= 0 for v in beta)
        a = [F(0) for _ in range(n)]
        for weight, denominator, (_, _, idx) in zip(beta, denominators, records):
            if weight:
                contribution = weight / denominator
                for i in idx:
                    a[i] += contribution
        u = [max(-a[i], min(a[i], 10000 * (-q[i] + q[n+i]) / normalizer)) for i in range(n)]
        assert all(abs(value) <= bound for value, bound in zip(u, a))
        active = [i for i, value in enumerate(u) if value]
        linear_costs = [sum((u[i] * p[i][j] for i in active), F(0)) for j in range(k)]
        target_cost = sum((u[i] * y[i] for i in active), F(0))
        upper = 1 + target_cost - min(linear_costs)
        source = next(r for r in numerical["solutions"][name] if r["method"] == "highs-ds")
        w = [max(F(float(source["weights"][c])), F(0)) for c in components]
        total = sum(w, F(0))
        w = [v / total for v in w]
        assert sum(w, F(0)) == 1 and all(v >= 0 for v in w)
        used = [j for j, value in enumerate(w) if value]
        error = [abs(sum((w[j] * row[j] for j in used), F(0)) - target) for row, target in zip(p, y)]
        margins = [1 - sum((error[i] for i in idx), F(0)) / denominator for (_, _, idx), denominator in zip(records, denominators)]
        lower = min(margins)
        gap = upper - lower
        assert gap >= 0 and gap < F(1, 10**10), (name, float(gap))
        assert upper < F(9, 100)
        solution = {"lower_fraction": packed(lower), "upper_fraction": packed(upper), "gap_fraction": packed(gap),
                    "lower_percent_display": float(100 * lower), "upper_percent_display": float(100 * upper),
                    "gap_percentage_points_display": float(100 * gap), "nine_percent_impossible_in_this_exact_class": True,
                    "component_weights": {c: packed(value) for c, value in zip(components, w)},
                    "nonzero_panel_beta": [{"panel": records[j][0], "baseline": records[j][1], "beta": packed(value),
                                            "baseline_total_CD": packed(denominators[j])} for j, value in enumerate(beta) if value],
                    "nonzero_signed_row_weights": [{"row_index": i, "u": packed(u[i]), "a_bound": packed(a[i])} for i in active],
                    "linear_component_costs": {c: packed(value) for c, value in zip(components, linear_costs)},
                    "target_linear_cost": packed(target_cost), "seconds": time.monotonic() - started,
                    "dual_source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        report["solutions"][name] = solution
        print(json.dumps({key: solution[key] for key in ["lower_percent_display", "upper_percent_display", "gap_percentage_points_display", "seconds"]}), flush=True)
    for filename, expected in hashes.items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == expected
    (OUT / "exact_report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
