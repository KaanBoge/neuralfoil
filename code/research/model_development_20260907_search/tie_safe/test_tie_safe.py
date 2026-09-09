"""Geometry-only numerical edge cases independent of experimental labels."""
import unittest
from unittest.mock import patch
import aerosandbox as asb
import numpy as np
from tie_safe_normalization import normalize_tie_safe, to_kulfan_tie_safe


class TieSafeTests(unittest.TestCase):
    def test_symmetric_two_vertex_le(self):
        points = np.array([[1., .002], [.5, .1], [0., .001], [0., -.001], [.5, -.1], [1., -.002]])
        foil = asb.Airfoil(name="two-vertex", coordinates=points)
        result = normalize_tie_safe(foil, return_dict=True)
        self.assertEqual(result["le_tie_count"], 2)
        np.testing.assert_array_equal(result["airfoil"].coordinates, points)
        # Translation/rotation/positive scaling retain the centered convention.
        transformed = foil.rotate(.3).scale(scale_x=2, scale_y=2).translate(translate_x=3, translate_y=-2)
        got = normalize_tie_safe(transformed, return_dict=True)
        self.assertEqual(got["le_tie_count"], 2)
        np.testing.assert_allclose(got["airfoil"].coordinates, points, atol=2e-15, rtol=0)

    def test_unique_le_exact_legacy_and_no_second_normalization(self):
        foil = asb.Airfoil(name="unique", coordinates=np.array([[1., 0], [.5, .1], [0., 0], [.5, -.1], [1., 0]]))
        np.testing.assert_array_equal(normalize_tie_safe(foil).coordinates, foil.normalize().coordinates)
        with patch.object(asb.Airfoil, "to_kulfan_airfoil", return_value="sentinel") as mocked:
            self.assertEqual(to_kulfan_tie_safe(foil), "sentinel")
            self.assertIs(mocked.call_args.kwargs["normalize_coordinates"], False)
        with self.assertRaises(ValueError):
            to_kulfan_tie_safe(foil, normalize_coordinates=True)

    def test_invalid_geometry(self):
        for points in [np.zeros((3, 2)), np.array([[1., 0], [np.nan, 0], [1., 0]])]:
            foil = asb.Airfoil(name="bad", coordinates=points)
            with self.assertRaises(ValueError):
                normalize_tie_safe(foil)


if __name__ == "__main__":
    unittest.main()
