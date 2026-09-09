"""Public NumPy-only checks on artificial inputs; no study data/model loading."""
import copy
import importlib.util
from pathlib import Path
import unittest

import numpy as np

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/synthetic_policy.py'
SPEC = importlib.util.spec_from_file_location('synthetic_policy_example', EXAMPLE)
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)


class PublicSmoke(unittest.TestCase):
    def setUp(self):
        self.predictor = example.load_predictor()
        self.artifact = example.artificial_artifact()
        self.x, self.base, self.sizes, self.gate = example.artificial_inputs()

    def predict(self, **changes):
        args = dict(artifact=self.artifact, X62=self.x, BASE_CD=self.base,
                    all_model_CD=self.sizes, gate=self.gate,
                    label='unpenalized_transfer')
        args.update(changes)
        return self.predictor.predict(**args)

    def test_prediction_and_exact_fallback(self):
        cd, strength = self.predict()
        expected_core = self.base * 1.5
        expected = 0.5 * self.base + 0.5 * expected_core
        np.testing.assert_array_equal(cd[self.gate], expected[self.gate])
        np.testing.assert_array_equal(cd[~self.gate], self.base[~self.gate])
        np.testing.assert_array_equal(strength, [0.5, 0.0])

    def test_all_false_gate(self):
        cd, strength = self.predict(gate=np.zeros(2, dtype=bool))
        np.testing.assert_array_equal(cd, self.base)
        np.testing.assert_array_equal(strength, np.zeros(2))

    def test_malformed_schema(self):
        broken = copy.deepcopy(self.artifact)
        broken['schema'] = 'unknown'
        with self.assertRaises(ValueError):
            self.predict(artifact=broken, gate=np.zeros(2, dtype=bool))

    def test_invalid_dimensions(self):
        for kwargs in [{'X62': np.zeros((2, 61))},
                       {'all_model_CD': np.ones((2, 7))},
                       {'BASE_CD': self.base[:, None]}]:
            with self.assertRaises(ValueError):
                self.predict(**kwargs)

    def test_invalid_gate(self):
        for gate in [np.array([1, 0]), np.array([True]), None]:
            with self.assertRaises(ValueError):
                self.predict(gate=gate)

    def test_inputs_not_mutated(self):
        before = [a.copy() for a in (self.x, self.base, self.sizes, self.gate)]
        artifact = copy.deepcopy(self.artifact)
        self.predict()
        for actual, saved in zip((self.x, self.base, self.sizes, self.gate), before):
            np.testing.assert_array_equal(actual, saved)
        self.assertEqual(self.artifact, artifact)


if __name__ == '__main__':
    unittest.main()
