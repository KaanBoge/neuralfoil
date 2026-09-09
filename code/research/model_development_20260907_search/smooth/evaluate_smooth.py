"""Report every frozen family using historical grouped OOF only."""
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
import smooth_models as sm

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "model_development_20260906_v2"))
import develop_v2 as v2


def main():
    started = time.monotonic()
    d = v2.load_data()
    ids = np.arange(len(d["BASE_CD"]))
    assert len(ids) == 8371 and len(set(d["group"])) == 93
    weights = sm._weights(d["group"], d["source"])
    np.testing.assert_allclose(weights / weights.mean(), v2.old.balanced_weights(d["group"], d["source"]))
    output = pd.DataFrame({k: d[k] for k in ["group", "source", "BASE_CD", "MEAS_CD"]})
    summaries, fits = [], []
    folds = v2.old.group_folds(d["group"], 5, 20260906)
    for family in sm.FAMILIES:
        pred = np.full(len(ids), np.nan)
        for fold, te in enumerate(folds):
            assert not set(d["group"][~te]) & set(d["group"][te])
            tick = time.monotonic()
            model = sm.fit(family, d, ids[~te])
            pred[te] = sm.predict(model, d, ids[te])
            fits.append(dict(family=family, fold=fold, seconds=time.monotonic()-tick,
                             **model.optimization,
                             **v2.old.metrics(d["MEAS_CD"][te], pred[te], d["BASE_CD"][te], d["group"][te])))
        assert np.isfinite(pred).all()
        assert np.all((pred >= .5*d["BASE_CD"]) & (pred <= 2*d["BASE_CD"]))
        output[family] = pred
        for label, mask in [("overall", np.ones(len(ids), dtype=bool))] + [(str(s), d["source"]==s) for s in sorted(set(d["source"]))]:
            summaries.append(dict(family=family, subset=label,
                                  **v2.old.metrics(d["MEAS_CD"][mask], pred[mask], d["BASE_CD"][mask], d["group"][mask])))
        print(json.dumps(summaries[-len(set(d["source"]))-1]), flush=True)
    output.to_csv(ROOT / "fixed_family_oof.csv", index=False)
    pd.DataFrame(summaries).to_csv(ROOT / "fixed_family_metrics.csv", index=False)
    (ROOT / "fixed_family_results.json").write_text(json.dumps(dict(seed=20260906, rows=len(ids), groups=93, fits=fits, summaries=summaries,
        seconds=time.monotonic()-started, warning="Exploratory fixed-family historical OOF; no correction for adaptive development or family selection."), indent=2)+"\n")


if __name__ == "__main__":
    main()
