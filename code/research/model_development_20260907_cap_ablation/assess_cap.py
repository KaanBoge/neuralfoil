"""Fixed cap-ablation assessment. Imports and scoring never fit a model."""
from pathlib import Path
import hashlib
import importlib.util
import json

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "model_development_20260907_selective"
CAPACITY = HERE.parent / "model_development_20260907_frontier/capacity"
FAMILIES = ["capped", "upper_free", "positive_log"]
POINTS = [f"{prefix}{family}_{strength}" for prefix in ["", "proper_"]
          for family in FAMILIES for strength in ["full", "half"]]
PROJECTIONS = [f"project_{baseline}_{family}" for family in FAMILIES for baseline in ["mean8", "xlarge"]]
CANDIDATES = [f"{family}_{strength}" for family in FAMILIES[1:] for strength in ["full", "half"]]
CANDIDATES += [f"project_{baseline}_{family}" for family in FAMILIES[1:] for baseline in ["mean8", "xlarge"]]
NEW = POINTS + PROJECTIONS
LABELS = NEW + ["unpenalized_transfer", "half_strength"]
CONTROLS = [c for c in LABELS if c not in CANDIDATES]
OUT = HERE / "assessment"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(hashes):
    for p, h in hashes.items():
        assert sha(p) == h, p


def load():
    complete = read(HERE/"results/complete.json")
    freeze = read(HERE/"results/freeze.json")
    assert complete["core_count"] == freeze["core_count"] == 96
    assert complete["calibrator_count"] == freeze["calibrator_count"] == 48
    assert freeze["external_outcomes_opened"] is False
    assert complete["freeze_sha256"] == sha(HERE/"results/freeze.json")
    hashes = {}
    for record in [freeze, complete]:
        for key in ["source_input_sha256", "artifact_sha256", "output_sha256", "external_input_sha256"]:
            if key in record:
                verify(record[key])
                hashes.update(record[key])
    assert all(key in complete for key in ["artifact_sha256", "source_input_sha256", "output_sha256", "external_input_sha256"])
    # Authenticate prior reusable non-fitting helpers before importing them.
    p = PRIOR/"assess_selective.py"
    seal = read(PRIOR/"DELIVERY_QA.json")
    assert sha(p) == seal["addendum_evidence_sha256"][str(p)]
    spec = importlib.util.spec_from_file_location("cap_prior_assessment", p)
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    frame, panels, metrics, inherited = prior.load()
    hashes.update(inherited)
    hashes[str(p)] = sha(p)
    hashes[str(PRIOR/"DELIVERY_QA.json")] = sha(PRIOR/"DELIVERY_QA.json")
    for split in frame.split.unique():
        external = split in prior.EXTERNAL
        path = HERE/("exposed_results" if external else "results")/(
            f"{split}_predictions.csv" if external else f"predictions_{split}.csv")
        assert sha(path) == complete["output_sha256"][str(path)]
        fresh = pd.read_csv(path, low_memory=False)
        mask = frame.split.eq(split)
        old = frame.loc[mask]
        assert len(fresh) == len(old)
        if not external:
            assert not fresh.nf2_row_id.duplicated().any()
            assert set(fresh.nf2_row_id) == set(old.nf2_row_id)
            fresh = fresh.set_index("nf2_row_id").loc[old.nf2_row_id].reset_index()
        for field in ["Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD"]:
            np.testing.assert_allclose(fresh[field], old[field], atol=1e-13, rtol=0)
        g = prior.boolean(fresh.interval_applicable)
        np.testing.assert_array_equal(g, old.interval_applicable.to_numpy(bool))
        for field in NEW + [f"{prefix}_{family}" for family in FAMILIES for prefix in ["interval_lower", "interval_upper", "calibration_q"]]:
            frame.loc[mask, field] = fresh[field].to_numpy()
        for label in PROJECTIONS:
            field = label+"__intervened"
            frame.loc[mask, field] = prior.boolean(fresh[field])
        # Capped proper control and its calibrated interval match the preceding run.
        for new, oldname in [("proper_capped_full", "proper_core"), ("proper_capped_half", "proper_half"),
                             ("project_mean8_capped", "project_mean8"), ("project_xlarge_capped", "project_xlarge"),
                             ("interval_lower_capped", "interval_lower"), ("interval_upper_capped", "interval_upper")]:
            np.testing.assert_allclose(fresh[new], old[oldname], atol=1e-13, rtol=0)
        # Exact corresponding archived full-training control snapshots.
        cp = CAPACITY/("exposed_results" if external else "results")/(
            f"{split}_predictions.csv" if external else f"predictions_{split}.csv")
        cw = read(CAPACITY/("portable/manifest.json" if external else "../assessment_final/report.json"))
        expected = cw["hashes" if external else "input_sha256"][str(cp)]
        assert sha(cp) == expected
        hashes[str(cp)] = expected
        archived = pd.read_csv(cp)
        if not external:
            archived = archived.set_index("nf2_row_id").loc[old.nf2_row_id].reset_index()
        for label, oldname in [("capped_full", "hist62_regularized__1"), ("capped_half", "hist62_regularized__0.5")]:
            np.testing.assert_allclose(fresh[label], archived[oldname], atol=1e-13, rtol=0)
        for label in NEW:
            baseline = "xlarge_CD" if label.startswith("project_xlarge_") else "mean8_CD"
            np.testing.assert_allclose(fresh[label].to_numpy()[~g], fresh[baseline].to_numpy()[~g], atol=1e-13, rtol=0)
    assert len(frame) == 29856 and len(LABELS) == 20 and len(CANDIDATES) == 8
    assert np.isfinite(frame[LABELS]).all().all() and (frame[LABELS].to_numpy() > 0).all()
    for label in PROJECTIONS:
        frame[label+"__intervened"] = prior.boolean(frame[label+"__intervened"])
    metrics.LABELS, metrics.CANDIDATES, metrics.CONTROLS = LABELS, CANDIDATES, CONTROLS
    metrics.SEED = 2026090729
    for p in [HERE/"results/complete.json", HERE/"results/freeze.json", Path(__file__), HERE/"PROTOCOL.md"]:
        hashes[str(p)] = sha(p)
    return frame, panels, metrics, prior, hashes


def tails(frame, panels):
    rows = []
    names = [f"history_{s}_pooled" for s in [20260906, 20260908]]
    names += [f"{s}_pooled" for s in ["SG_exposed", "W_new_challenge"]]
    names += [f"eligible_only/{s}/pooled" for s in ["SG_exposed", "W_new_challenge"]]
    for panel in names:
        f = frame.iloc[panels[panel]]
        y, b = f.measured_CD.to_numpy(), f.mean8_CD.to_numpy()
        strata = {"above_old_upper": y > 2*b, "below_old_lower": y < .5*b,
                  "within_old_bounds": (y >= .5*b) & (y <= 2*b)}
        assert sum(int(x.sum()) for x in strata.values()) == len(f)
        for stratum, ix in strata.items():
            for label in LABELS:
                p = f[label].to_numpy()
                error = abs(p-y)
                row = {"panel": panel, "stratum": stratum, "candidate": label, "rows": int(ix.sum()),
                       "mae_CD": float(error[ix].mean()) if ix.any() else None,
                       "predictions_above_old_upper": int((p[ix] > 2*b[ix]).sum()),
                       "predictions_below_old_lower": int((p[ix] < .5*b[ix]).sum()),
                       "interpretation": "Outcome-defined descriptive stratum; not an inference gate or primary endpoint"}
                for base in ["mean8_CD", "xlarge_CD"]:
                    e = abs(f[base].to_numpy()-y)
                    row[base+"_mae"] = float(e[ix].mean()) if ix.any() else None
                    row[base+"_improvement_percent"] = float(100*(1-error[ix].sum()/e[ix].sum())) if ix.any() and e[ix].sum() > 0 else None
                rows.append(row)
    return pd.DataFrame(rows)


def main():
    assert not OUT.exists(), "Preserve existing assessment"
    frame, panels, metrics, prior, hashes = load()
    table, boot, groups = metrics.panel_metrics(frame, panels), metrics.bootstrap(frame), metrics.group_metrics(frame)
    decisions = metrics.decisions(table, boot, groups)
    coverages, bundles = [], []
    for family in FAMILIES:
        f = frame.copy()
        for field in ["interval_lower", "interval_upper"]:
            f[field] = f[field+"_"+family]
        for base in ["mean8", "xlarge"]:
            f["project_"+base] = f[f"project_{base}_{family}"]
            f["project_"+base+"__intervened"] = f[f"project_{base}_{family}__intervened"]
        c, g = prior.coverage(f, panels)
        c["family"], g["family"] = family, family
        coverages.append(c)
        bundles.append(g)
    outputs = {"panel_metrics": table, "bootstrap": boot, "group_metrics": groups,
               "harm_metrics": metrics.harms(frame, panels), "decisions": decisions,
               "candidate_summary": metrics.summary(table, boot, groups), "tail_metrics": tails(frame, panels),
               "coverage_metrics": pd.concat(coverages, ignore_index=True),
               "bundle_coverage": pd.concat(bundles, ignore_index=True), "all_row_predictions": frame}
    assert len(boot) == 80 and len(table) == 620 and len(decisions) == 8
    verify(hashes)
    OUT.mkdir()
    for name, values in outputs.items():
        values.to_csv(OUT/(name+".csv"), index=False)
    report = {"status": "complete_fixed_cap_ablation_adaptive_not_confirmatory", "core_count": 96,
              "calibrator_count": 48, "candidates": CANDIDATES, "controls": CONTROLS,
              "panels": 31, "rows_with_repeated_contexts": len(frame),
              "bootstrap_draws": 20000, "bootstrap_seed": 2026090729,
              "performance_advances": decisions.loc[decisions.performance_advance,"candidate"].tolist(),
              "robustness_advances": decisions.loc[decisions.robustness_advance,"candidate"].tolist(),
              "input_source_sha256": hashes,
              "output_sha256": {str(OUT/(n+".csv")): sha(OUT/(n+".csv")) for n in outputs},
              "warning": "No deployable selector, independent confirmation, universal improvement or absolute optimality. Log comparator is not a single-factor cap ablation. Conditional bootstrap omits adaptive-search/refit/calibration uncertainty."}
    (OUT/"report.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(decisions[["candidate","performance_advance","robustness_advance"]].to_string(index=False))


if __name__ == "__main__":
    main()
