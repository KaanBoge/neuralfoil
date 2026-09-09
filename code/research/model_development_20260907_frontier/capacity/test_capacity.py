import unittest
import numpy as np
import capacity_models as models
import run_capacity as run


class CapacityTests(unittest.TestCase):
    def test_training_isolation_predictor_only_and_bounds(self):
        rng = np.random.default_rng(64)
        x = rng.normal(size=(180, 62))
        d = {"X62": x, "X24": x[:, :24], "BASE_CD": np.full(180, .01), "MEAS_CD": .01 + .001 * np.tanh(x[:, 0]),
             "group": np.repeat(np.arange(18), 10), "source": np.repeat(["a", "b"], 90)}
        tr, te = np.arange(150), np.arange(150, 180)
        for family in models.FAMILIES:
            m = models.fit(family, d, tr)
            p = models.predict(m, {m["feature_key"]: d[m["feature_key"]], "BASE_CD": d["BASE_CD"]}, te)
            altered = {k: v.copy() for k, v in d.items()}
            altered["MEAS_CD"][te] = 1000
            altered["X62"][te] = 1e4
            altered["X24"][te] = 1e4
            m2 = models.fit(family, altered, tr)
            np.testing.assert_array_equal(p, models.predict(m2, d, te))
            self.assertTrue(np.all((p >= .005) & (p <= .02)))

    def test_weight_parity_and_ratio_definition(self):
        groups = np.array(["a", "a", "b", "c"])
        sources = np.array(["s", "s", "s", "t"])
        np.testing.assert_allclose(models.balanced_weights(groups, sources), run.v2.old.balanced_weights(groups, sources), rtol=0, atol=1e-14)
        d = {"MEAS_CD": np.array([1., 2., 4., 8.]), "BASE_CD": np.array([2., 3., 6., 12.]),
             "XLARGE_CD": np.array([2., 4., 5., 10.]), "group": groups, "source": sources}
        p = np.array([1.5, 3., 5., 10.])
        r = run.group_ratios(d, np.arange(4), p)
        self.assertAlmostEqual(r["mean8:pooled"], 4.5 / 8.)
        self.assertAlmostEqual(r["mean8:equal_group"], (.75 + 1 + 2) / (1 + 2 + 4))
        self.assertAlmostEqual(r["xlarge:pooled"], 4.5 / 6.)


if __name__ == "__main__":
    unittest.main()
