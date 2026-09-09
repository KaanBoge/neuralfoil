"""Recalculate claim anchors from authenticated, completed prior assessments.

No fitting, geometry-frontier outcomes, new experimental labels, or external I/O.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
PROJECT = ROUND.parent
RISK = PROJECT / "model_development_20260907_risk_policy"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = HERE / "verified_claims.json"
    assert not out.exists(), "Preserve the existing evidence snapshot"
    witness = RISK / "assessment/report.json"
    report = json.loads(witness.read_text())
    paths = [RISK / "assessment" / name for name in ["panel_metrics.csv", "group_metrics.csv", "decisions.csv"]]
    hashes = {str(witness): sha(witness)}
    for path in paths:
        expected = report["output_sha256"][str(path)]
        assert sha(path) == expected
        hashes[str(path)] = expected
    metrics = pd.read_csv(paths[0])
    groups = pd.read_csv(paths[1])
    decisions = pd.read_csv(paths[2])
    rows = []
    fields = ["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]
    for label in ["half_strength", "risk_transfer", "unpenalized_transfer", "risk_group"]:
        t = metrics[metrics.candidate == label]
        assert len(t) == 31 and len(t.panel.unique()) == 31
        item = {"procedure": label,
                "minimum_of_31_panel_views_against_both_baselines_percent": float(t[fields].to_numpy().min()),
                "eligible_external_negative_panel_baseline_pairs": int((t[t.panel.str.startswith("eligible_only/")][fields].to_numpy() < -1e-6).sum()),
                "history": []}
        for assignment in [20260906, 20260908]:
            h = t[t.panel == f"history_{assignment}_pooled"].iloc[0]
            g = groups[(groups.candidate == label) & (groups.assignment == assignment)]
            assert int(h.rows) == 8371 and len(g) == 93
            item["history"].append({"assignment": assignment, "rows": 8371, "identity_groups": 93,
                                    "xlarge_relative_MAE_reduction_percent": float(h.xlarge_CD_improvement_percent),
                                    "mean8_relative_MAE_reduction_percent": float(h.mean8_CD_improvement_percent),
                                    "candidate_MAE_CD": float(h.mae_CD),
                                    "groups_worse_than_xlarge": int((g.xlarge_improvement_percent < -1e-6).sum()),
                                    "worst_group_reduction_vs_xlarge_percent": float(g.xlarge_improvement_percent.min())})
        if label != "half_strength":
            item["passed_prior_risk_round_strict_tradeoff_rule"] = bool(decisions[decisions.candidate == label].iloc[0].tradeoff_advance)
        rows.append(item)
    portable = RISK / "portable/manifest.json"
    package = json.loads(portable.read_text())
    hashes[str(portable)] = sha(portable)
    for name, expected in package["package_hashes"].items():
        path = portable.parent / name
        assert sha(path) == expected
        hashes[str(path)] = expected
    hashes[str(Path(__file__))] = sha(Path(__file__))
    result = {"status": "VERIFIED_PRIOR_RISK_POLICY_CLAIM_ANCHORS",
              "scope": "Frozen risk-policy family only; not results of the still-running geometry round",
              "procedures": rows, "shared_metric": "relative reduction in CD MAE, not physical drag reduction",
              "evidence_status": "Adaptive/exposed research; overlapping assignments and panels; no independent confirmation",
              "artifact_sha256": package["package_hashes"]["experimental_policies.json"],
              "input_source_sha256": hashes,
              "forbidden_inferences": ["Every row improves", "Every airfoil improves", "Universal nine-percent reduction",
                                       "Upper bound is achieved accuracy", "Replay rows are independent test measurements",
                                       "Feature-only inference timing is end-to-end NeuralFoil speed", "Absolute optimum established"]}
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    for row in rows:
        print(row["procedure"], [h["xlarge_relative_MAE_reduction_percent"] for h in row["history"]],
              row["minimum_of_31_panel_views_against_both_baselines_percent"])


if __name__ == "__main__":
    main()
