from fractions import Fraction as F
import itertools
import math
import random
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import paired_enclosure as p


def outward(value, up):
    # Independent test reference; choose adjacent representable values directly.
    value = F(value)
    nearest = float(value)
    if (F.from_float(nearest) < value) if up else (F.from_float(nearest) > value):
        nearest = math.nextafter(nearest, math.inf if up else -math.inf)
    return F.from_float(nearest)


def stage_reference(initial, stages):
    lo = hi = F.from_float(initial)
    for values in stages:
        lo = outward(lo + min(F.from_float(v) for v in values), False)
        hi = outward(hi + max(F.from_float(v) for v in values), True)
    return lo, hi


class PairedEnclosureTests(unittest.TestCase):
    def test_cartesian_exact_equivalence(self):
        rng = random.Random(202609081613)
        for _ in range(256):
            initial = rng.uniform(-1, 1)
            stages = [tuple(rng.uniform(-0.25, 0.25) for _ in range(3)) for _ in range(6)]
            blocks = [list(itertools.product(stages[i], stages[i+1])) for i in range(0, 6, 2)]
            actual = p.enclose(initial, blocks)
            self.assertEqual((actual['lower'], actual['upper']), stage_reference(initial, stages))

    def test_singleton_blocks(self):
        stages = [(-1.0, 0.0, 1.0), (-0.1, 0.2), (2.0,)]
        actual = p.enclose(0.3, [[(v,) for v in stage] for stage in stages])
        self.assertEqual((actual['lower'], actual['upper']), stage_reference(0.3, stages))

    def test_compatible_cancellation_strictly_tighter(self):
        actual = p.enclose(0.0, [[(1.0, -1.0), (-1.0, 1.0)]])
        self.assertEqual((actual['lower'], actual['upper']), (F(0), F(0)))
        self.assertEqual(stage_reference(0.0, [(-1.0, 1.0)] * 2), (F(-2), F(2)))

    def test_subset_nested_and_all_native_paths_contained(self):
        rng = random.Random(202609081614)
        for _ in range(256):
            blocks = [tuple((rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(3)) for _ in range(3)]
            initial = rng.uniform(-1, 1)
            actual = p.enclose(initial, blocks)
            independent = stage_reference(initial, [tuple(row[j] for row in block) for block in blocks for j in (0, 1)])
            self.assertLessEqual(independent[0], actual['lower'])
            self.assertLessEqual(actual['upper'], independent[1])
            for path in itertools.product(*blocks):
                accumulator = initial
                for sequence in path:
                    for value in sequence:
                        accumulator += value
                exact = F.from_float(accumulator)
                self.assertLessEqual(actual['lower'], exact)
                self.assertLessEqual(exact, actual['upper'])

    def test_extreme_subnormal_zero_and_adjacency(self):
        tiny = math.nextafter(0.0, 1.0)
        maximum = sys.float_info.max
        fixtures = [(0.0, [(tiny, -tiny), (-tiny, tiny)]),
                    (-0.0, [(-0.0, 0.0), (0.0, -0.0)]),
                    (0.0, [(maximum, -maximum), (-maximum, maximum)]),
                    (1.0, [(2.0**-53, -2.0**-53), (-2.0**-53, 2.0**-53)])]
        for initial, block in fixtures:
            result = p.enclose(initial, [block])
            for first, second in block:
                value = (initial + first) + second
                self.assertLessEqual(result['lower'], F.from_float(value))
                self.assertLessEqual(F.from_float(value), result['upper'])

    def test_overflow_refused(self):
        with self.assertRaises(ValueError):
            p.enclose(sys.float_info.max, [[(sys.float_info.max, 0.0)]])

    def test_invalid_schema(self):
        for blocks in [None, [], [[]], [[()]], [[(0.0, 1.0, 2.0)]], [[(0.0,), (0.0, 1.0)]],
                       [[(1,)]], [[(True,)]], [[(float('nan'),)]], [[(float('inf'),)]],
                       [[(0.0,)] * 226], [[(0.0,)]] * 201]:
            with self.assertRaises(ValueError):
                p.enclose(0.0, blocks)
        for initial in [0, True, float('inf'), float('nan')]:
            with self.assertRaises(ValueError):
                p.enclose(initial, [[(0.0,)]])

    def test_runtime_format_guard(self):
        fake = SimpleNamespace(radix=2, mant_dig=24, min_exp=-125, max_exp=128)
        with patch.object(p.sys, 'float_info', fake):
            with self.assertRaises(RuntimeError):
                p.enclose(0.0, [[(0.0,)]])

    def test_input_preservation(self):
        block = [[(0.1, -0.1), (0.2, -0.2)]]
        before = repr(block)
        p.enclose(0.0, block)
        self.assertEqual(before, repr(block))


if __name__ == '__main__':
    unittest.main()
