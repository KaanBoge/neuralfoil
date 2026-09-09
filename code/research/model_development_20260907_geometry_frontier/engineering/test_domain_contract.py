import unittest
import numpy as np
from domain_contract import legacy_benchmark_gate


class DomainTests(unittest.TestCase):
    def test_inclusive_boundaries_and_adjacent_floats(self):
        alpha = np.array([12., -12., np.nextafter(12., np.inf), 0., 0., 0., 0., 0.])
        re = np.array([600000., 600000., 100000., np.nextafter(600000., np.inf), 0., 1., 1., 1.])
        thickness = np.array([.05, .20, .12, .12, .12, np.nextafter(.05, -np.inf), np.nextafter(.20, np.inf), .12])
        base = np.array([.02] * 7 + [0.])
        np.testing.assert_array_equal(legacy_benchmark_gate(alpha, re, thickness, base),
                                      [True, True, False, False, False, False, False, False])

    def test_empty_and_input_immutability(self):
        empty = np.array([], dtype=float)
        result = legacy_benchmark_gate(empty, empty, empty, empty)
        self.assertEqual(result.dtype, np.dtype(bool))
        self.assertEqual(result.shape, (0,))
        x = [np.array([1., 2.]), np.array([100000., 200000.]), np.array([.1, .2]), np.array([.01, .02])]
        copies = [v.copy() for v in x]
        legacy_benchmark_gate(*x)
        for before, after in zip(copies, x):
            np.testing.assert_array_equal(before, after)

    def test_invalid_types_shapes_and_nonfinite(self):
        good = [np.array([0.]), np.array([100000.]), np.array([.12]), np.array([.02])]
        for i in range(4):
            for bad in [np.array([np.nan]), np.array([np.inf]), np.array([True]),
                        np.array(["1"]), np.array([1 + 0j]), np.array([[1.]]), np.array(1.)]:
                args = list(good); args[i] = bad
                with self.assertRaises(ValueError):
                    legacy_benchmark_gate(*args)
        with self.assertRaises(ValueError):
            legacy_benchmark_gate([0., 1.], [100000.], [.12], [.02])


if __name__ == "__main__":
    unittest.main()
