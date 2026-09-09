"""Fixed synthetic-only properties. No actual features/models/targets loaded."""
import copy
import itertools
import math
import random
import sys
import unittest

from relations import DIMENSIONS, RELEVANT, contract, relation_guard

MAX = sys.float_info.max
TINY = math.nextafter(0., 1.)


def box(**overrides):
    value = [(-MAX, MAX)] * DIMENSIONS
    for key, interval in overrides.items():
        value[int(key)] = interval
    return value


def point(alpha, top, bottom):
    value = [0.] * DIMENSIONS
    value[0], value[12], value[13] = alpha, top, bottom
    value[16], value[18], value[19] = abs(alpha), min(top, bottom), max(top, bottom)
    return tuple(value)


def contains(intervals, value):
    return intervals is not None and all(intervals[i][0] <= value[i] <= intervals[i][1]
                                         for i in RELEVANT)


class Relations(unittest.TestCase):
    def test_guard_extreme_signed_zero_and_subnormal_points(self):
        values = [-MAX, -2., -TINY, -0., 0., TINY, 2., MAX]
        for x in itertools.product(values, repeat=3):
            p = point(*x)
            self.assertTrue(relation_guard(p))
            intervals = [(v, v) for v in p]
            self.assertTrue(contains(contract(intervals), p))

    def test_impossible_absolute_value(self):
        self.assertIsNone(contract(box(**{'16': (-2., -1.)})))

    def test_impossible_minimum_maximum_order(self):
        self.assertIsNone(contract(box(**{'18': (2., 3.), '19': (-2., 1.)})))

    def test_absolute_straddling_keeps_both_branches(self):
        result = contract(box(**{'0': (-2., 2.), '16': (1., 2.)}))
        self.assertEqual(result[0], (-2., 2.))
        self.assertTrue(contains(result, point(-1., 0., 0.)))
        self.assertTrue(contains(result, point(1., 0., 0.)))

    def test_minimum_equality_does_not_force_other_operand(self):
        intervals = box(**{'12': (0., 0.), '13': (5., 5.), '18': (0., 0.)})
        self.assertTrue(contains(contract(intervals), point(0., 0., 5.)))

    def test_maximum_equality_does_not_force_other_operand(self):
        intervals = box(**{'12': (0., 0.), '13': (-5., -5.), '19': (0., 0.)})
        self.assertTrue(contains(contract(intervals), point(0., 0., -5.)))

    def test_minimum_strict_implication(self):
        result = contract(box(**{'12': (2., 3.), '13': (-5., 5.), '18': (0., 1.)}))
        self.assertEqual(result[13], (0., 1.))

    def test_maximum_strict_implication(self):
        result = contract(box(**{'12': (-3., 1.), '13': (-5., 5.), '19': (2., 3.)}))
        self.assertEqual(result[13], (2., 3.))

    def test_input_immutability_and_zero_pass_identity(self):
        original = box(**{'16': (-2., 2.)})
        before = copy.deepcopy(original)
        self.assertEqual(contract(original, passes=0), tuple(before))
        contract(original)
        self.assertEqual(original, before)

    def test_fixed_random_box_containment_and_iteration_nesting(self):
        rng = random.Random(2026090837)
        endpoints = [-MAX, -2., -1., -TINY, 0., TINY, 1., 2., MAX]
        points = [point(*x) for x in itertools.product([-2., -TINY, 0., TINY, 2.], repeat=3)]
        for _ in range(768):
            original = box()
            for i in RELEVANT:
                original[i] = tuple(sorted(rng.choices(endpoints, k=2)))
            prior = tuple(original)
            for passes in (0, 1, 2, 16):
                result = contract(original, passes=passes)
                if result is not None:
                    self.assertIsNotNone(prior)
                    for old, new in zip(prior, result):
                        self.assertLessEqual(old[0], new[0])
                        self.assertLessEqual(new[1], old[1])
                for p in points:
                    if contains(original, p):
                        self.assertTrue(contains(result, p))
                prior = result

    def test_fixed_planted_feasible_boxes(self):
        rng = random.Random(2026090838)
        endpoints = [-MAX, -2., -1., -TINY, -0., 0., TINY, 1., 2., MAX]
        for _ in range(256):
            p = point(*(rng.choice(endpoints) for _ in range(3)))
            original = box()
            for i in RELEVANT:
                original[i] = (rng.choice([x for x in endpoints if x <= p[i]]),
                               rng.choice([x for x in endpoints if x >= p[i]]))
            self.assertTrue(contains(original, p))
            for passes in (0, 1, 2, 16):
                self.assertTrue(contains(contract(original, passes=passes), p))

    def test_invalid_schema_and_nonfinite(self):
        for bad in ([], [(0., 1.)] * 61, box(**{'0': (1., -1.)}),
                    box(**{'0': (0., float('inf'))}), box(**{'0': (False, 1.)}),
                    box(**{'0': (float('nan'), 1.)})):
            with self.assertRaises(ValueError):
                contract(bad)
        for passes in (-1, 17, True, 1.):
            with self.assertRaises(ValueError):
                contract(box(), passes=passes)
        self.assertFalse(relation_guard([0.] * 61))
        self.assertFalse(relation_guard([float('nan')] * 62))
        self.assertFalse(relation_guard([0] * 62))
        invalid = list(point(1., 2., 3.)); invalid[16] = 2.
        self.assertFalse(relation_guard(invalid))


if __name__ == '__main__':
    unittest.main(verbosity=2)
