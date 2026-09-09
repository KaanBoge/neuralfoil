"""Numerical safeguards for the development runner; no source-data mutation."""
import unittest
import numpy as np
import develop_drag as dev


class DevelopmentTests(unittest.TestCase):
    def test_group_folds_are_exhaustive_and_disjoint(self):
        groups = np.array([f"g{i//3}" for i in range(99)])
        masks = dev.group_folds(groups, 5, 20260906)
        self.assertTrue(np.all(np.sum(masks, axis=0) == 1))
        for mask in masks:
            self.assertFalse(set(groups[mask]) & set(groups[~mask]))

    def test_weights_balance_sources_and_groups(self):
        g = np.array(["a", "a", "a", "b", "c", "c", "d", "d", "d", "d"])
        s = np.array(["s1"]*4+["s2"]*6)
        w = dev.balanced_weights(g, s)
        self.assertAlmostEqual(w.mean(), 1)
        self.assertAlmostEqual(w[s=="s1"].sum(), w[s=="s2"].sum())
        self.assertAlmostEqual(w[g=="a"].sum(), w[g=="b"].sum())
        self.assertAlmostEqual(w[g=="c"].sum(), w[g=="d"].sum())

    def test_corrections_clip_positive_and_identity_strength(self):
        base = np.array([.01, .02, .03])
        raw = np.array([-1e4, 0, 1e4])
        for family in ["ridge_log", "gb_l1_log", "gb_l1_add", "gb_huber_add"]:
            got = dev.correct(family, raw, base, 1)
            np.testing.assert_allclose(got, [.005, .02, .06])
            np.testing.assert_allclose(dev.correct(family, raw, base, 0), base)

    def test_ratio_is_paired_ratio_of_sums(self):
        y = np.array([.01, .04, .1])
        base = np.array([.02, .02, .11])
        pred = np.array([.015, .03, .11])
        result = dev.metrics(y, pred, base, np.array(["a", "a", "b"]), bootstrap=True)
        self.assertAlmostEqual(result["relative_reduction_percent"], 37.5)
        self.assertEqual(result["rows"], 3)
        self.assertEqual(result["conditional_cluster_bootstrap"]["replicates"], 20000)


if __name__ == "__main__":
    unittest.main()
