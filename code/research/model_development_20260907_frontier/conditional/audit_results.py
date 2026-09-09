"""Independent checks of every fitted corner artifact and preserved result rows."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
POSITIVE=HERE.parents[1]/"model_development_20260907_positive"


def main():
    manifest=json.loads((HERE/"manifest.json").read_text())
    for path,digest in manifest["helper_sha256"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
    logs=[]
    for split in manifest["names"]:
        centerpath=POSITIVE/"historical_results"/f"weights_{split}.json"
        centerfile=json.loads(centerpath.read_text())
        for variant in manifest["variants"]:
            model=json.loads((HERE/"results"/f"{split}_{variant}.json").read_text())
            assert hashlib.sha256(centerpath.read_bytes()).hexdigest()==model["center_file_sha256"]
            w=np.asarray(model["corner_weights"])
            center=np.asarray([centerfile["solutions"]["primary_both"]["weights"][k] for k in model["components"]])
            assert np.isfinite(w).all() and w.min()>=-1e-8
            np.testing.assert_allclose(w.sum(axis=1),1,atol=1e-8)
            assert np.abs(w-center).sum(axis=1).max()<=.5+2e-6
            # The anchor itself is always a feasible constant-corner solution.
            anchor_ratio=centerfile["solutions"]["primary_both"]["actual_worst_training_ratio"]
            assert model["actual_worst_training_ratio"]<=anchor_ratio+3e-6
            assert model["training_nf2_row_ids"]==centerfile["training_nf2_row_ids"]
            logs.append({"split":split,"variant":variant,"anchor_ratio":anchor_ratio,
                         "conditional_training_ratio":model["actual_worst_training_ratio"],"passed":True})
    rows=pd.read_csv(HERE/"results/all_row_predictions.csv",low_memory=False)
    assert len(rows)==29856 and not rows.duplicated(["input_file","input_row_index"]).any()
    for variant in manifest["variants"]:
        assert np.isfinite(rows[variant]).all() and (rows[variant]>0).all()
    metrics=pd.read_csv(HERE/"results/panel_metrics.csv")
    assert len(metrics)==23*6
    for row in metrics.itertuples():
        if row.panel.startswith("history_") and row.panel.endswith("_pooled"):
            seed=row.panel.split("_")[1]
            subset=rows[rows.split.str.startswith("group_"+seed+"_")]
            error=np.abs(subset[row.candidate]-subset.measured_CD)
            assert abs(error.mean()-row.mae_CD)<1e-14
    result={"all_48_models_passed":True,"all_29856_rows_preserved":True,"source_hashes_passed":True,
            "pooled_metric_recalculation_passed":True,"models":logs}
    (HERE/"results/numerical_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print("PASS: 48 model anchors, simplex/L1 bounds, preserved rows and independent pooled MAE recalculation")


if __name__=="__main__":main()
