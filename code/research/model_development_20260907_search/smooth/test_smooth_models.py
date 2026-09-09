import unittest
import numpy as np
import smooth_models as sm


class SmoothTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(4)
        x = rng.normal(size=(100, 16))
        x[:, -1] = 1
        self.d = dict(X9=x[:, :9].copy(), X16=x.copy(), BASE_CD=np.full(100, .01),
                      MEAS_CD=.01 + .001 * np.tanh(x[:, 0]),
                      group=np.repeat(np.arange(10), 10), source=np.repeat(["a", "b"], 50))

    def test_train_only_and_inference_label_independent(self):
        tr, te = np.arange(80), np.arange(80, 100)
        for family in sm.FAMILIES:
            model = sm.fit(family, self.d, tr)
            expected = sm.predict(model, self.d, te)
            altered = {k: v.copy() for k, v in self.d.items()}
            altered["MEAS_CD"][te] = 400
            altered["X9"][te] = 1e5
            altered["X16"][te] = 1e5
            model2 = sm.fit(family, altered, tr)
            np.testing.assert_array_equal(model.coefficients, model2.coefficients)
            minimal = {k: self.d[k] for k in (model.key, "BASE_CD")}
            np.testing.assert_allclose(expected, sm.predict(model, minimal, te))
            bounded = sm.predict(model, altered, te)
            self.assertTrue(np.isfinite(bounded).all())
            self.assertTrue(np.all((bounded >= .005) & (bounded <= .02)))

    def test_identity_and_constant_columns(self):
        d = {k: v.copy() for k, v in self.d.items()}
        d["X9"][:] = 1
        d["X16"][:] = 1
        d["MEAS_CD"] = d["BASE_CD"].copy()
        for family in sm.FAMILIES:
            model = sm.fit(family, d, np.arange(100))
            np.testing.assert_allclose(sm.predict(model, d, np.arange(100)), d["BASE_CD"])


if __name__ == "__main__":
    unittest.main()
