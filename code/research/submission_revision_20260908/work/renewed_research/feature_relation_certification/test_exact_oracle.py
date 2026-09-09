import copy
import itertools
import math
import random
import sys
import unittest

from exact_oracle import feasible, feasible_witness
from relations import relation_guard


def blank():
    return [(0.0, 0.0)] * 62


def intervals(values):
    return [(a, b) for a in values for b in values if a <= b]


class ExactOracleTests(unittest.TestCase):
    def valid(self, box, point):
        self.assertTrue(relation_guard(point))
        self.assertEqual(len(point), 62)
        self.assertTrue(all(lo <= x <= hi for (lo, hi), x in zip(box, point)))

    def test_invalid_boxes(self):
        for malformed in [None, [], [(0.0, 0.0)] * 61, [(0.0, 0.0)] * 63]:
            with self.assertRaises(ValueError):
                feasible(malformed)
        for bad in [(0, 1.0), (False, 1.0), (0.0,), (2.0, 1.0),
                    (0.0, float("inf")), (float("nan"), 1.0)]:
            box = blank()
            box[37] = bad
            with self.assertRaises(ValueError):
                feasible(box)

    def test_deterministic_and_immutable(self):
        box = [[-1.0, 1.0] for _ in range(62)]
        before = copy.deepcopy(box)
        one = feasible_witness(box)
        self.assertEqual(box, before)
        self.assertEqual(one, feasible_witness(box))
        self.valid(box, one)

    def test_absolute_exhaustive_fixed_endpoint_grid(self):
        values = [-2.0, -1.0, -0.0, 0.0, 1.0, 2.0]
        choices = intervals(values)
        for alpha, absolute in itertools.product(choices, repeat=2):
            box = blank()
            box[0], box[16] = alpha, absolute
            expected = any(alpha[0] <= x <= alpha[1]
                           and absolute[0] <= abs(x) <= absolute[1] for x in values)
            point = feasible_witness(box)
            self.assertEqual(point is not None, expected)
            if point is not None:
                self.valid(box, point)

    def test_minmax_exhaustive_fixed_endpoint_grid(self):
        values = [-1.0, 0.0, 1.0]
        choices = intervals(values)
        for top, bottom, minimum, maximum in itertools.product(choices, repeat=4):
            box = blank()
            for index, interval in zip((12, 13, 18, 19), (top, bottom, minimum, maximum)):
                box[index] = interval
            expected = any(top[0] <= a <= top[1] and bottom[0] <= b <= bottom[1]
                           and minimum[0] <= min(a, b) <= minimum[1]
                           and maximum[0] <= max(a, b) <= maximum[1]
                           for a, b in itertools.product(values, repeat=2))
            point = feasible_witness(box)
            self.assertEqual(point is not None, expected)
            if point is not None:
                self.valid(box, point)

    def test_extreme_point_boxes(self):
        tiny = math.nextafter(0.0, 1.0)
        maximum = sys.float_info.max
        values = [-maximum, -1.0, -tiny, -0.0, 0.0, tiny, 1.0, maximum]
        for alpha, top, bottom in itertools.product(values, repeat=3):
            point = [-0.0] * 62
            point[0], point[16] = alpha, abs(alpha)
            point[12], point[13] = top, bottom
            point[18], point[19] = min(top, bottom), max(top, bottom)
            box = [(x, x) for x in point]
            self.valid(box, feasible_witness(box))

    def test_planted_full_boxes(self):
        rng = random.Random(202609081601)
        for _ in range(2048):
            point = [float(rng.randrange(-32, 33)) for _ in range(62)]
            point[16] = abs(point[0])
            point[18], point[19] = min(point[12], point[13]), max(point[12], point[13])
            box = [(x - float(rng.randrange(8)), x + float(rng.randrange(8))) for x in point]
            self.valid(box, feasible_witness(box))

    def test_arbitrary_boxes_endpoint_enumeration(self):
        rng = random.Random(202609081602)
        grid = [-4.0, -1.0, -0.0, 0.0, 1.0, 4.0]
        for _ in range(2048):
            box = [tuple(sorted(rng.choices(grid, k=2))) for _ in range(62)]
            expected_abs = any(box[0][0] <= a <= box[0][1]
                               and box[16][0] <= abs(a) <= box[16][1] for a in grid)
            expected_order = any(box[12][0] <= a <= box[12][1]
                                 and box[13][0] <= b <= box[13][1]
                                 and box[18][0] <= min(a, b) <= box[18][1]
                                 and box[19][0] <= max(a, b) <= box[19][1]
                                 for a, b in itertools.product(grid, repeat=2))
            point = feasible_witness(box)
            self.assertEqual(point is not None, expected_abs and expected_order)
            if point is not None:
                self.valid(box, point)

    def test_equality_boundary_and_both_orientations(self):
        box = blank()
        box[12], box[13], box[18], box[19] = (1.0, 2.0), (1.0, 1.0), (1.0, 1.0), (2.0, 2.0)
        point = feasible_witness(box)
        self.valid(box, point)
        self.assertEqual((point[12], point[13]), (2.0, 1.0))
        box[19] = (1.0, 1.0)
        self.valid(box, feasible_witness(box))

    def test_impossible_relations(self):
        for index, interval in [(16, (-2.0, -1.0)), (18, (1.0, 2.0)), (19, (-2.0, -1.0))]:
            box = blank()
            box[index] = interval
            self.assertIsNone(feasible_witness(box))
        box = blank()
        box[0], box[16] = (-1.0, 1.0), (2.0, 3.0)
        self.assertIsNone(feasible_witness(box))


if __name__ == "__main__":
    unittest.main()
