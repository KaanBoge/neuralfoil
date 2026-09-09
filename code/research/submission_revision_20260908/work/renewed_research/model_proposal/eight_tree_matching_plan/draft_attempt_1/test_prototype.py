"""Small manufactured fixtures only: never the 400-tree performance gate."""
import math
from pathlib import Path
import tempfile
import unittest
from fractions import Fraction as F
import prototype as p


def fixture(signs=(1,)*8):
    return [dict(stage=k, leaves=[
        dict(leaf=1, value=float(-s).hex(), edges=[[0, 0, 0.0.hex(), 0]], empty=False),
        dict(leaf=2, value=float(s).hex(), edges=[[0, 0, 0.0.hex(), 1]], empty=False)])
        for k, s in enumerate(signs)]


def decode(v):
    return F(int(v['numerator'], 16), int(v['denominator'], 16))


class PrototypeTests(unittest.TestCase):
    def test_matching_complete(self):
        self.assertEqual(len(p.PAIRS), 28)
        self.assertEqual(len(set(p.MATCHINGS)), 105)
        for ids in p.MATCHINGS:
            self.assertEqual(sorted(v for i in ids for v in p.PAIRS[i]), list(range(8)))

    def test_all_statuses_retained(self):
        budget = p.Budget()
        record, out = p.block(fixture(), (F(0), F(0)), 8, (F(-8), F(8)), budget)
        self.assertEqual(budget.pairs, 112)
        self.assertEqual(len(record['pairs']), 28)
        self.assertEqual(len(record['matchings']), 105)
        self.assertTrue(all(x['status_hex'] == '02010102' for x in record['pairs']))
        self.assertEqual(out, (F(-8), F(8)))

    def test_cross_four_dependency(self):
        record, out = p.block(fixture((1,)*4+(-1,)*4), (F(0), F(0)),
                              8, (F(-8), F(8)), p.Budget())
        self.assertEqual([decode(v) for v in record['real_sum']], [0, 0])
        self.assertLess(out[1]-out[0], F(1, 10**12))
        self.assertLessEqual(out[0], 0)
        self.assertGreaterEqual(out[1], 0)

    def test_containment_original_sequential(self):
        for signs in ((1,)*8, (1,)*4+(-1,)*4, (1, -1)*4):
            _, out = p.block(fixture(signs), (F(0), F(0)), 8,
                             (F(-8), F(8)), p.Budget())
            for side in (-1., 1.):
                raw = 0.
                for sign in signs:
                    raw = raw + side*sign
                self.assertLessEqual(out[0], F(raw))
                self.assertGreaterEqual(out[1], F(raw))

    def test_wrong_old_stage(self):
        with self.assertRaises(ValueError):
            p.block(fixture(), (F(0), F(0)), 4, (F(-8), F(8)), p.Budget())

    def test_disjoint_old_chain_refused(self):
        with self.assertRaises(ValueError):
            p.block(fixture(), (F(0), F(0)), 8, (F(20), F(30)), p.Budget())

    def test_duplicate_leaf(self):
        trees = fixture()
        trees[0]['leaves'][1]['leaf'] = 1
        with self.assertRaises(ValueError):
            p.block(trees, (F(0), F(0)), 8, (F(-8), F(8)), p.Budget())

    def test_false_empty(self):
        trees = fixture()
        trees[0]['leaves'][0]['empty'] = True
        with self.assertRaises(ValueError):
            p.block(trees, (F(0), F(0)), 8, (F(-8), F(8)), p.Budget())

    def test_strict_max_and_signed_zero(self):
        self.assertIsNone(p.path_box([[0, 0, p.MAX.hex(), 1]]))
        box = p.path_box([[0, 0, (-0.0).hex(), 1]])
        self.assertEqual(box[0][0], math.nextafter(0., 1.))

    def test_half_subnormal_exact(self):
        self.assertGreater(p.HALF_ETA, 0)
        self.assertEqual(p.directed(p.HALF_ETA, False), 0)
        self.assertEqual(p.directed(p.HALF_ETA, True), F(math.nextafter(0., 1.)))
        self.assertEqual(p.directed(-p.HALF_ETA, True), 0)

    def test_overflow_and_limb_refused(self):
        with self.assertRaises(ValueError):
            p.directed(F(p.MAX)*2, True)
        with self.assertRaises(ValueError):
            p.rational(F(1, 2**4097))

    def test_resource_gate_fixed(self):
        self.assertEqual(p.memory_plan(0, 0, 0)['estimate'], 96*2**20)
        with self.assertRaises(MemoryError):
            p.memory_plan(9*2**20, 0, 0)
        with self.assertRaises(ValueError):
            p.memory_plan(True, 0, 0)

    def test_exclusive_partial_preservation(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'synthetic.jsonl'
            sink = p.SyntheticStream(path)
            sink.write({'kind': 'synthetic'})
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                sink.write({'bad': math.nan})
            sink.close()
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                p.SyntheticStream(path)

    def test_output_reserve(self):
        with tempfile.TemporaryDirectory() as td:
            sink = p.SyntheticStream(Path(td)/'synthetic.jsonl')
            sink.size = p.OUTPUT_CAP-p.FAILURE_RESERVE
            with self.assertRaises(OSError):
                sink.write({'kind': 'synthetic'})
            sink.close()


if __name__ == '__main__':
    unittest.main()
