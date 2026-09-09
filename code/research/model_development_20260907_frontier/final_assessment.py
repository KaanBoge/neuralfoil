"""Completed frontier assessment; does not modify frozen model/assessment helpers."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import frontier_assessment as shared

HERE = Path(__file__).resolve().parent
OUT = HERE / "assessment_final"


def main():
    required = [HERE / "capacity/results/results.json", HERE / "kernel/results/results.json",
                HERE / "conditional/results/report.json", HERE / "union_historical/results/report.json"]
    assert all(p.exists() for p in required), "Every branch and union must finish first"
    OUT.mkdir(exist_ok=False)
    frame, _, labels, hashes = shared.load_frame(["capacity", "kernel", "conditional"])
    path = HERE / "union_historical/results/all_row_predictions.csv"
    union = pd.read_csv(path, low_memory=False)
    shared.check_common(frame, union)
    np.testing.assert_array_equal(frame.split.to_numpy(), union.split.to_numpy())
    label = "union_historical__primary_union_both"
    frame[label] = union.primary_union_both.to_numpy()
    labels.append(label)
    hashes[str(path)] = shared.sha(path)
    panels = shared.old.panels(frame)
    panels.update({k: v for k, v in shared.reconcile.external_panels(frame).items() if k.startswith("eligible_only/")})
    table = pd.concat([shared.old.metrics(frame, frame[c].to_numpy(), panels, c) for c in [shared.REFERENCE] + labels], ignore_index=True)
    bootstrap = shared.conditional_bootstrap(frame, labels)
    decisions = shared.stopping_gate(frame, labels, table, bootstrap)
    table.to_csv(OUT / "panel_metrics.csv", index=False)
    bootstrap.to_csv(OUT / "conditional_paired_bootstrap.csv", index=False)
    decisions.to_csv(OUT / "operational_decisions.csv", index=False)
    frame.to_csv(OUT / "all_row_predictions.csv", index=False)
    summaries = []
    fields = ["xlarge_CD_improvement_percent", "mean8_CD_improvement_percent"]
    for candidate in [shared.REFERENCE] + labels:
        t = table[table.candidate == candidate].set_index("panel")
        row = {"candidate": candidate,
               "history_first_xlarge_improvement_percent": float(t.loc["history_20260906_pooled", fields[0]]),
               "history_second_xlarge_improvement_percent": float(t.loc["history_20260908_pooled", fields[0]]),
               "worst_strict_source_improvement_both_percent": float(t.loc[t.index.str.startswith("strict_source_"), fields].to_numpy().min()),
               "worst_eligible_external_improvement_both_percent": float(t.loc[t.index.str.startswith("eligible_only/"), fields].to_numpy().min()),
               "eligible_external_negative_panel_baseline_pairs": int((t.loc[t.index.str.startswith("eligible_only/"), fields].to_numpy() < 0).sum()),
               "minimum_all23_improvement_both_percent": float(t.loc[~t.index.str.startswith("eligible_only/"), fields].to_numpy().min()),
               "SG_eligible_xlarge_improvement_percent": float(t.loc["eligible_only/SG_exposed/pooled", fields[0]]),
               "W_eligible_xlarge_improvement_percent": float(t.loc["eligible_only/W_new_challenge/pooled", fields[0]])}
        summaries.append(row)
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "candidate_summary.csv", index=False)
    for filename, expected in hashes.items():
        assert shared.sha(filename) == expected
    result = {"status": "completed_adaptive_frontier_comparison_not_confirmatory_validation",
              "candidate_count_excluding_reference": len(labels), "candidate_labels": labels,
              "input_sha256": hashes, "source_sha256": shared.sha(Path(__file__)),
              "shared_assessment_sha256": shared.sha(Path(shared.__file__)),
              "root_protocol_sha256": shared.sha(HERE / "PROTOCOL.md"),
              "bootstrap_draws": shared.N_BOOTSTRAP, "bootstrap_seed": shared.SEED,
              "practical_advances": decisions.loc[decisions.operational_frontier_advance, "candidate"].tolist(),
              "all23_positive_candidates_both": summary.loc[summary.minimum_all23_improvement_both_percent > 0, "candidate"].tolist(),
              "warning": "Positive exposed benchmark panels and conditional paired CIs are not independent validation or proof that all possible improvements are exhausted."}
    (OUT / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(summary.to_string(index=False), flush=True)
    print("Operational advances:", result["practical_advances"], flush=True)


if __name__ == "__main__":
    main()
