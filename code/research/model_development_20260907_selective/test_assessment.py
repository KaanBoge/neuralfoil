"""Synthetic diagnostics exercise nontrivial interventions and unassessed groups."""
import unittest
import numpy as np
import pandas as pd
from assess_selective import coverage


class CoverageTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({"split": ["group_20260906_fold_0"]*4,
            "configuration": [np.nan]*4, "group": ["g1", "g1", "g2", "g3"],
            "interval_applicable": [True, True, True, False],
            "measured_CD": [1., 1.5, 2., 9.],
            "interval_lower": [.8, .8, .8, -np.inf],
            "interval_upper": [1.2, 1.2, 1.2, np.inf],
            "mean8_CD": [.5, 1., 2., .7], "xlarge_CD": [.4, .9, 2.1, .6],
            "project_mean8": [.8, 1., 1.2, .7], "project_xlarge": [.8, .9, 1.2, .6],
            "project_mean8__intervened": [True, False, True, False],
            "project_xlarge__intervened": [True, False, True, False]})

    def test_intervention_harm_and_unassessed_not_success(self):
        table, groups = coverage(self.frame(), {"test": np.arange(4)})
        row = table.iloc[0]
        self.assertEqual(row.eligible_rows, 3)
        self.assertEqual(row.assessed_bundles, 2)
        self.assertEqual(row.fully_covered_bundles, 0)
        self.assertEqual(row.eligible_row_coverage, 1/3)
        self.assertEqual(row["project_mean8__harm_fraction_among_interventions"], .5)
        self.assertEqual(row["project_mean8__benefit_fraction_among_interventions"], .5)
        self.assertEqual(row["project_xlarge__covered_target_projection_violations"], 0)
        self.assertTrue(pd.isna(groups[groups.bundle.eq("g3")].iloc[0].fully_covered_eligible_bundle))

    def test_no_intervention_fraction_is_undefined(self):
        frame = self.frame()
        for label, b in [("project_mean8", "mean8_CD"), ("project_xlarge", "xlarge_CD")]:
            frame[label] = frame[b]
            frame[label+"__intervened"] = False
        table, _ = coverage(frame, {"test": np.arange(4)})
        self.assertTrue(pd.isna(table.iloc[0]["project_mean8__harm_fraction_among_interventions"]))

    def test_covered_target_harm_is_refused(self):
        frame = self.frame()
        frame.loc[0, "project_mean8"] = 10.
        with self.assertRaises(AssertionError):
            coverage(frame, {"test": np.arange(4)})

    def test_outside_gate_intervention_is_refused(self):
        frame = self.frame()
        frame.loc[3, "project_mean8__intervened"] = True
        with self.assertRaises(AssertionError):
            coverage(frame, {"test": np.arange(4)})


if __name__ == "__main__":
    unittest.main()
