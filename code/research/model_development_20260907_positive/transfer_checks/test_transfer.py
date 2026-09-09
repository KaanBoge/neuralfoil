import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
import run_transfer as run

ROOT = Path(__file__).resolve().parent


class TransferTests(unittest.TestCase):
    def test_all_folds_predictions_and_metric_arithmetic(self):
        result = json.loads((ROOT / "results.json").read_text())
        self.assertEqual(result["failures"], [])
        self.assertEqual(len(result["folds"]), 6)
        for record in result["folds"]:
            name = record["name"]
            frame = pd.read_csv(ROOT / f"predictions_{name}.csv")
            weights = record["solution"]["weights"]
            self.assertAlmostEqual(sum(weights.values()), 1., places=9)
            self.assertGreaterEqual(min(weights.values()), -1e-9)
            direct = frame[list(weights)].to_numpy() @ np.array(list(weights.values()))
            np.testing.assert_allclose(direct, frame.withheld_calibration_blend, rtol=0, atol=3e-16)
            self.assertEqual(set(frame.airfoil), set(record["solution"]["held_designs"]))
            self.assertFalse(set(record["training_external_designs"]) & set(frame.airfoil))
            self.assertEqual(frame.global_input_row_index.nunique(), len(frame))
            table = pd.read_csv(ROOT / f"metrics_{name}.csv")
            pooled = table[(table.candidate == "withheld_calibration_blend") & (table.panel == "held_pooled")].iloc[0]
            error = np.abs(frame.withheld_calibration_blend - frame.measured_CD)
            self.assertAlmostEqual(float(error.mean()), pooled.mae_CD, places=14)
            for base in ["xlarge_CD", "mean8_CD"]:
                expected = 100 * (1 - error.sum() / np.abs(frame[base] - frame.measured_CD).sum())
                self.assertAlmostEqual(expected, pooled[base + "_improvement_percent"], places=9)

    def test_training_input_label_isolation_and_historical_panels(self):
        d, _, _ = run.feasibility.load_inputs()
        panels = run.feasibility.panels(d)
        for _, designs in run.FOLDS:
            train, pmap, held = run.partition(d, panels, designs)
            changed = d.copy()
            changed.loc[held, "measured_CD"] = np.nan
            train2, pmap2, held2 = run.partition(changed, panels, designs)
            pd.testing.assert_frame_equal(train, train2, check_exact=True)
            np.testing.assert_array_equal(held, held2)
            for key in pmap:
                np.testing.assert_array_equal(pmap[key], pmap2[key])


if __name__ == "__main__":
    unittest.main()
