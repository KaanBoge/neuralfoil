"""Contract, rank, proof, and invariance tests on synthetic data only."""
import copy
import unittest

import numpy as np

import selective as s


def model(q=.2, m=19):
    return {"schema": s.SCHEMA, "alpha": .1, "calibration_groups": m,
            "rank": s.rank(m, .1), "q": q, "unbounded": q is None}


class SelectiveTests(unittest.TestCase):
    def test_exact_rank_and_small_sample(self):
        self.assertEqual([s.rank(m, .1) for m in [0, 8, 9, 19, 29]], [1, 9, 9, 18, 27])
        for n in range(1, 45):
            r = s.calibrate(np.ones(n), np.ones(n), 1 + np.arange(n), np.array([str(i) for i in range(n)]))
            self.assertEqual(r["q"], None if n < 9 else float(s.rank(n, .1) - 1))

    def test_group_maximum_not_row_percentile(self):
        g = np.repeat(np.array([f"g{i}" for i in range(10)]), 3)
        score = np.tile([0., 0., 1.], 10) * np.repeat(np.arange(10), 3)
        r = s.calibrate(np.ones(30), np.ones(30), 1 + score, g)
        self.assertEqual(r["calibration_groups"], 10)
        self.assertEqual(r["q"], 9)
        self.assertEqual(r["group_scores"], list(range(10)))

    def test_duplicate_rows_do_not_inflate_groups(self):
        r = s.calibrate(np.ones(30), np.ones(30), np.ones(30), np.repeat(["a", "b", "c"], 10))
        self.assertTrue(r["unbounded"])
        self.assertIsNone(r["q"])

    def test_three_projection_cases(self):
        out = s.project(model(), np.ones(3), np.ones(3), [.5, 1, 2], np.ones(3, bool))
        np.testing.assert_array_equal(out["prediction"], [.8, 1, 1.2])
        np.testing.assert_array_equal(out["intervened"], [True, False, True])

    def test_exact_supplied_baseline_fallback(self):
        b = np.array([.011, .013, .017])
        a = np.array([.0111, .0129, .0181])
        for m in [model(), model(None, 8)]:
            out = s.project(m, b, b, a, np.zeros(3, bool))
            np.testing.assert_array_equal(out["prediction"], a)
            self.assertTrue(np.isneginf(out["lower"]).all())
            self.assertTrue(np.isposinf(out["upper"]).all())
        out = s.project(model(None, 8), b, b, a, np.ones(3, bool))
        np.testing.assert_array_equal(out["prediction"], a)
        self.assertTrue(out["applicable"].all())
        self.assertFalse(out["intervened"].any())

    def test_deterministic_no_harm_for_covered_targets(self):
        rng = np.random.default_rng(824)
        c, b, a = rng.uniform(.001, .1, size=(3, 10000))
        out = s.project(model(.3), c, b, a, np.ones(len(c), bool))
        for fraction in [0., .5, 1.]:
            y = out["lower"] * (1-fraction) + out["upper"] * fraction
            delta = abs(out["prediction"] - y) - abs(a-y)
            self.assertLessEqual(delta.max(), 1e-15)
            self.assertLessEqual(((out["prediction"]-y)**2 - (a-y)**2).max(), 1e-15)

    def test_can_harm_uncovered_target(self):
        out = s.project(model(.1), [1.], [1.], [.5], np.ones(1, bool))
        self.assertGreater(abs(out["prediction"][0] - .5), 0)

    def test_batch_permutation_and_no_mutation(self):
        rng = np.random.default_rng(825)
        c, b, a = rng.uniform(.001, .1, size=(3, 80))
        g = rng.random(80) > .2
        originals = [v.copy() for v in [c,b,a,g]]
        result = s.project(model(), c,b,a,g)
        perm = rng.permutation(80)
        reverse = np.argsort(perm)
        other = s.project(model(), c[perm],b[perm],a[perm],g[perm])
        for key in result:
            np.testing.assert_array_equal(result[key], other[key][reverse])
            chunks = [s.project(model(), c[i:i+7],b[i:i+7],a[i:i+7],g[i:i+7])[key] for i in range(0,80,7)]
            np.testing.assert_array_equal(result[key], np.concatenate(chunks))
        for original, current in zip(originals, [c,b,a,g]):
            np.testing.assert_array_equal(original, current)

    def test_zero_width_and_empty_inference(self):
        out = s.project(model(0), [1.], [2.], [3.], np.ones(1, bool))
        np.testing.assert_array_equal(out["prediction"], [1.])
        out = s.project(model(), np.array([]), np.array([]), np.array([]), np.array([], bool))
        self.assertEqual(len(out["prediction"]), 0)

    def test_refuse_bad_inputs(self):
        for alpha in [0, 1, -.1, np.nan, np.inf, True, ".1", [.1]]:
            with self.assertRaises((ValueError, TypeError)):
                s.rank(9, alpha)
        for changes in [{"q": -1}, {"q": np.inf}, {"q": None}, {"rank": 1},
                        {"unbounded": 1}, {"schema": "unknown"}, {"alpha": .2}]:
            broken = {**model(), **changes}
            with self.assertRaises(ValueError):
                s.project(broken, [1.], [1.], [1.], np.ones(1, bool))
        for value in [[np.nan], [np.inf], [0], [-1], ["1"]]:
            with self.assertRaises(ValueError):
                s.project(model(), [1.], value, [1.], np.ones(1, bool))
        with self.assertRaises(ValueError):
            s.project(model(), [1.], [1.], [1.], [1])
        with self.assertRaises(ValueError):
            s.calibrate([1.], [1.], [2.], [""])
        with self.assertRaises(ValueError):
            s.calibrate([1.], [1.], [2.], [None])
        with self.assertRaises(ValueError):
            s.calibrate([], [], [], np.array([], str))


if __name__ == "__main__":
    unittest.main()
