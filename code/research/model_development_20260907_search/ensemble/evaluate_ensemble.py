"""Frozen-family grouped OOF, deployment invariants, and leakage checks."""
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]/"model_development_20260906_v2"))
import develop_v2 as api
from ensemble_models import FAMILIES, fit, predict


def metrics(d, pred):
    err = np.abs(d["MEAS_CD"]-pred)
    return {"mae": float(err.mean()), "median_absolute_error": float(np.median(err)),
            "equal_group_mae": float(pd.DataFrame({"g": d["group"], "e": err}).groupby("g").e.mean().mean()),
            "source_mae": {str(s): float(err[d["source"] == s].mean()) for s in np.unique(d["source"])}}


def main():
    started = time.monotonic()
    d = api.load_data()
    n = len(d["BASE_CD"])
    ids = np.arange(n)
    assert n == 8371 and len(set(d["group"])) == 93
    folds = api.old.group_folds(d["group"], 5, 20260906)
    train, test = ids[~folds[0]], ids[folds[0]]
    # Full-array poisoning outside training indices tests that training statistics
    # and weights use only training rows. No new fit decisions follow this test.
    poisoned = {k: v.copy() if isinstance(v, np.ndarray) else v for k, v in d.items()}
    for key in ["MEAS_CD", "Re", "all_model_CD", "BASE_CD"]:
        poisoned[key][test] *= 19
    for key in ["group", "source"]:
        poisoned[key] = poisoned[key].astype(object)
        poisoned[key][test] = "HELD_OUT_POISON"
    invariant_results = []
    for family in FAMILIES:
        m1, m2 = fit(family, d, train), fit(family, poisoned, train)
        p1, p2 = predict(m1, d, test), predict(m2, d, test)
        np.testing.assert_array_equal(p1, p2)
        minimal = {k: d[k] for k in ["all_model_CD", "BASE_CD", "Re"]}
        np.testing.assert_array_equal(p1, predict(m1, minimal, test))
        assert np.isfinite(p1).all() and (p1 > 0).all()
        assert (p1 >= .5*d["BASE_CD"][test]).all() and (p1 <= 2*d["BASE_CD"][test]).all()
        invariant_results.append({"family": family, "passed": True})
    print("Leakage and prediction invariants passed", flush=True)
    report = {"rows": n, "groups": 93, "seed": 20260906,
              "invariants": invariant_results, "baseline_mean8": metrics(d, d["BASE_CD"]), "families": {}}
    predictions = pd.DataFrame({"nf2_row_id": d["nf2_row_id"], "group": d["group"], "source": d["source"],
                                "measured_CD": d["MEAS_CD"], "mean8_CD": d["BASE_CD"]})
    for family in FAMILIES:
        begin = time.monotonic()
        pred = np.full(n, np.nan)
        coverage = np.zeros(n, dtype=int)
        models = []
        for fold, mask in enumerate(folds):
            tr, te = ids[~mask], ids[mask]
            assert not set(d["group"][tr]) & set(d["group"][te])
            model = fit(family, d, tr)
            pred[te] = predict(model, d, te)
            coverage[te] += 1
            models.append({"fold": fold, **{k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in model.items()}})
        assert (coverage == 1).all() and np.isfinite(pred).all() and (pred > 0).all()
        worst, ratios = api.old.score_candidate(pred, d, ids)
        report["families"][family] = {**metrics(d, pred), "seconds": time.monotonic()-begin,
                                         "ratios_to_mean8": ratios, "worst_ratio": worst, "fold_models": models}
        predictions[family] = pred
        print(family, json.dumps({k: v for k, v in report["families"][family].items() if k != "fold_models"}), flush=True)
    report["total_seconds"] = time.monotonic()-started
    (HERE/"fixed_oof_report.json").write_text(json.dumps(report, indent=2)+"\n")
    predictions.to_csv(HERE/"fixed_oof_predictions.csv", index=False)


if __name__ == "__main__":
    main()
