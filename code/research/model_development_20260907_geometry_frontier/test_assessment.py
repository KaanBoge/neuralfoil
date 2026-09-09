"""Synthetic assessment checks: no study data, predictions, or model fitting."""
import unittest
import numpy as np
import pandas as pd
import assess_frontier as a


class AssessmentTests(unittest.TestCase):
    def test_ratio_of_error_sums_not_mean_row_percentages(self):
        f = pd.DataFrame({"measured_CD": [0., 0.], "xlarge_CD": [1., 9.], "mean8_CD": [1., 9.]})
        for label in a.LABELS:
            f[label] = [2., 3.]
        result = a.panel_metrics(f, {"synthetic": np.arange(2)})
        np.testing.assert_allclose(result.xlarge_CD_improvement_percent, 50.)
        self.assertTrue((result.xlarge_CD_worse_rows == 1).all())
        self.assertTrue((result.mae_drag_counts == 25000).all())

    def test_row_equality_tolerance_does_not_truncate_harm_magnitude(self):
        f = pd.DataFrame({"measured_CD": [0., 0.], "xlarge_CD": [1., 1.], "mean8_CD": [1., 1.]})
        for label in a.LABELS:
            f[label] = [1., 1.]
        f[a.CANDIDATES[0]] = [1. + a.ROW_TOL / 2, 1. + 2 * a.ROW_TOL]
        table = a.harms(f, {"synthetic": np.arange(2)})
        row = table[(table.candidate == a.CANDIDATES[0]) & (table.reference == "mean8_CD")].iloc[0]
        self.assertEqual(row.worse_rows, 1)
        self.assertEqual(row.equal_rows, 1)
        self.assertGreater(row.mean_positive_excess_absolute_error_CD, a.ROW_TOL)

    def fixture(self):
        panels = [f"strict_source_{i}" for i in range(5)] + [f"eligible_only/{i}" for i in range(8)] + [f"other_{i}" for i in range(18)]
        table = pd.DataFrame([{"candidate": label, "panel": panel,
                               "xlarge_CD_improvement_percent": 5., "mean8_CD_improvement_percent": 5.}
                              for label in a.LABELS for panel in panels])
        boot = pd.DataFrame([{"candidate": label, "reference": ref, "assignment": assignment,
                              "remaining_MAE_reduction_percent": 2.}
                             for label in a.LABELS for ref in a.REFERENCES for assignment in a.ASSIGNMENTS])
        groups = pd.DataFrame([{"candidate": label, "assignment": assignment, "group": str(g),
                                "xlarge_improvement_percent": 5., "MAE_difference_vs_xlarge_CD": -.001}
                               for label in a.LABELS for assignment in a.ASSIGNMENTS for g in range(93)])
        return table, boot, groups

    def test_strict_guards_and_two_references(self):
        table, boot, groups = self.fixture()
        label = a.CANDIDATES[0]
        result = a.decisions(table, boot, groups)
        self.assertTrue(result.performance_advance.all() and result.robustness_advance.all())
        # An insufficient gain against the performance reference must not borrow
        # the larger benefit against the easier half-strength reference.
        boot.loc[(boot.candidate == label) & (boot.reference == a.PERFORMANCE), "remaining_MAE_reduction_percent"] = .5
        row = a.decisions(table, boot, groups).set_index("candidate").loc[label]
        self.assertFalse(row.performance_advance)
        self.assertTrue(row.robustness_advance)
        # One newly harmed group fails even when all pooled panels improve.
        mask = (groups.candidate == label) & (groups.assignment == a.ASSIGNMENTS[0]) & (groups.group == "0")
        groups.loc[mask, "xlarge_improvement_percent"] = -1.
        row = a.decisions(table, boot, groups).set_index("candidate").loc[label]
        self.assertFalse(row.robustness_advance)

    def test_negative_external_pair_can_pass_primary_but_not_secondary(self):
        table, boot, groups = self.fixture()
        label = a.CANDIDATES[0]
        for candidate in [label, a.PERFORMANCE]:
            mask = (table.candidate == candidate) & (table.panel == "eligible_only/0")
            table.loc[mask, "mean8_CD_improvement_percent"] = -3.
        row = a.decisions(table, boot, groups).set_index("candidate").loc[label]
        self.assertTrue(row.performance_advance)
        self.assertFalse(row.robustness_advance)
        self.assertEqual(row.eligible_external_negative_panel_baseline_pairs, 1)
        table.loc[(table.candidate == label) & (table.panel == "eligible_only/0"), "mean8_CD_improvement_percent"] = -3.01
        self.assertFalse(a.decisions(table, boot, groups).set_index("candidate").loc[label].performance_advance)

    def test_each_assignment_must_pass_and_worst_group_must_not_worsen(self):
        table, boot, groups = self.fixture()
        label = a.CANDIDATES[0]
        for candidate in [label] + a.REFERENCES:
            mask = (groups.candidate == candidate) & (groups.group == "0")
            groups.loc[mask, "xlarge_improvement_percent"] = -10.
        self.assertTrue(a.decisions(table, boot, groups).set_index("candidate").loc[label].performance_advance)
        mask = (groups.candidate == label) & (groups.assignment == a.ASSIGNMENTS[1]) & (groups.group == "0")
        groups.loc[mask, "xlarge_improvement_percent"] = -10.01
        row = a.decisions(table, boot, groups).set_index("candidate").loc[label]
        self.assertFalse(row.performance_advance or row.robustness_advance)


if __name__ == "__main__":
    unittest.main()
