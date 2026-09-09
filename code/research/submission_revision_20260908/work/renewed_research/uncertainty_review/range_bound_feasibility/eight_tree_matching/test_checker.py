"""Manufactured arrays and small streams only; no real models or full-size gate.

Candidate arithmetic comes from the producer prototype; expected answers come
from this separately authored checker and direct enumeration of simple stumps.
The shared prior tree primitive is disclosed rather than retested as new code.
"""
import copy
from fractions import Fraction as F
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import unittest
import numpy as np
import checker as c

DT = np.dtype([(name, 'f8' if name in ('value', 'num_threshold') else 'i8')
               for name in ('value', 'num_threshold', 'is_leaf', 'feature_idx',
                            'left', 'right', 'missing_go_to_left', 'is_categorical')])
SYNTHETIC = 'f'*64
PLAN = Path(__file__).resolve().parents[3]/'model_proposal'


def load(name, path, pin):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('synthetic candidate source changed')
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def arrays(signs):
    trees = []
    for sign in signs:
        tree = np.zeros(3, dtype=DT)
        tree[0]['left'], tree[0]['right'] = 1, 2
        tree[1:]['is_leaf'] = 1
        tree[1:]['value'] = [-float(sign), float(sign)]
        trees.append(tree)
    for _ in range(400-len(trees)):
        tree = np.zeros(1, dtype=DT)
        tree['is_leaf'] = 1
        trees.append(tree)
    result = {'initial': np.array([0.], dtype='f8'), 'nodes': np.concatenate(trees),
              'nodes_offsets': np.cumsum([0]+[len(t) for t in trees], dtype='i8')}
    for name in ('raw_left_cat_bitsets', 'binned_left_cat_bitsets'):
        result[name] = np.array([], dtype='u4')
        result[name+'_offsets'] = np.zeros(401, dtype='i8')
    return result


def old_candidate(a):
    old = load('synthetic_old4_producer', PLAN/'four_tree_matching_plan/producer.py',
               'a445462d5faf314ecbd7ea06cb45feb8c26cf99de8d05d246d026b4bbea4b40e')
    return old.construct(a, old.Budget(), model_sha=SYNTHETIC)


def candidate(a):
    prototype = load('synthetic_eight_candidate', PLAN/'eight_tree_matching_plan/prototype.py',
                     '127e8de6cfed33f426eb77b5cb3b80d129653b6f3443de10dcb163bac358fc8b')
    old = old_candidate(a)
    raw = json.dumps(old, sort_keys=True, separators=(',', ':')).encode()
    expected = {'model_sha256': SYNTHETIC,
                'old4_certificate_sha256': hashlib.sha256(raw).hexdigest(),
                'old4_replay_complete_sha256': 'e'*64}
    records = [{'kind': 'header', 'schema': 'EIGHT_TREE_MATCHING_JSONL_V1',
                'domain': 'FINITE_X62_V1', **expected, 'initial': float(a['initial'][0]).hex(),
                'stages': 400, 'blocks': 50}]
    paths = copy.deepcopy(old['paths'])
    records.extend(dict(kind='paths', **row) for row in paths)
    p = c.prior_checker().primitives()
    current = F(0), F(0)
    classified = feasible = 0
    budget = prototype.Budget()
    for j in range(50):
        endpoint = tuple(p.rational(v) for v in old['blocks'][2*j+1]['outgoing'])
        block, current = prototype.block(paths[8*j:8*j+8], current, 8*(j+1), endpoint, budget)
        records.append(block)
        classified += sum(x['shape'][0]*x['shape'][1] for x in block['pairs'])
        feasible += sum(x['feasible'] for x in block['pairs'])
    counts = {'stages': 400, 'blocks': 50,
              'paths': sum(len(x['leaves']) for x in paths),
              'path_edges': sum(len(v['edges']) for x in paths for v in x['leaves']),
              'pair_classifications': classified, 'feasible_pairs': feasible}
    records.append({'kind': 'footer', 'counts': counts,
                    'original_four': old['final'], 'final': c.summary(p, current)})
    return records, raw, expected


def stream(records):
    return io.BytesIO(b''.join(json.dumps(r, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()+b'\n' for r in records))


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = arrays((1,)*4+(-1,)*4)
        cls.records, cls.old, cls.expected = candidate(cls.a)

    def verify(self, records=None, old=None, expected=None, a=None):
        return c.check_stream(stream(self.records if records is None else records),
                              self.a if a is None else a, self.old if old is None else old,
                              expected=self.expected if expected is None else expected)

    def test_all105_matchings(self):
        m = c.matchings()
        self.assertEqual(len(set(m)), 105)
        self.assertTrue(all(sorted(v for k in row for v in c.PAIRS[k]) == list(range(8)) for row in m))

    def test_small_full_stream_and_cross_four_cancellation(self):
        report = self.verify()
        self.assertEqual(report['records'], 452)
        self.assertEqual(report['counts']['pair_classifications'], 112+49*28)
        p = c.prior_checker().primitives()
        self.assertLess(p.rational(report['final']['B']), p.rational(report['original_four']['B']))
        lo, hi = (p.rational(report['final'][k]) for k in ('lower', 'upper'))
        for x in (-2., 0., math.nextafter(0., 1.), 2.):
            value = 0.
            for sign in (1,)*4+(-1,)*4:
                value = value + (-sign if x <= 0 else sign)
            self.assertTrue(lo <= F(value) <= hi)

    def test_rejected_pair_and_missing_matching_corruption(self):
        bad = copy.deepcopy(self.records)
        bad[401]['pairs'][0]['status_hex'] = '02'*4
        with self.assertRaises(ValueError):self.verify(bad)
        bad = copy.deepcopy(self.records)
        bad[401]['matchings'].pop()
        with self.assertRaises(ValueError):self.verify(bad)

    def test_wrong_global_stage_and_false_old_endpoint(self):
        bad = copy.deepcopy(self.records)
        bad[401]['old4_stage'] = 4
        with self.assertRaises(ValueError):self.verify(bad)
        bad = copy.deepcopy(self.records)
        bad[401]['old4_global_outgoing'] = c.interval((F(0), F(0)))
        with self.assertRaises(ValueError):self.verify(bad)

    def test_old_math_replayed_not_just_hashed(self):
        old = json.loads(self.old)
        old['blocks'][1]['outgoing'] = c.interval((F(0), F(0)))
        raw = json.dumps(old, sort_keys=True, separators=(',', ':')).encode()
        expected = dict(self.expected, old4_certificate_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ValueError):self.verify(old=raw, expected=expected)

    def test_model_identity_and_topology_corruption(self):
        with self.assertRaises(ValueError):self.verify(expected=dict(self.expected, model_sha256='a'*64))
        a = {k:v.copy() for k,v in self.a.items()}
        a['nodes'][0]['left'] = 0
        with self.assertRaises(ValueError):self.verify(a=a)

    def test_stream_completeness_and_duplicate_json(self):
        with self.assertRaises(ValueError):self.verify(self.records[:-1])
        with self.assertRaises(ValueError):self.verify(self.records+[self.records[-1]])
        raw = stream(self.records).getvalue().replace(b'{', b'{"kind":"duplicate",', 1)
        with self.assertRaises(ValueError):c.check_stream(io.BytesIO(raw), self.a, self.old, expected=self.expected)

    def test_exact_half_subnormal_and_limb_cap(self):
        self.assertGreater(c.HALF_ETA, 0)
        self.assertEqual(float(c.HALF_ETA), 0.)
        self.assertEqual(2*c.HALF_ETA, F(math.nextafter(0., 1.)))
        with self.assertRaises(ValueError):c.encoded(F(2**4096))

    def test_original_order_cancellation_needs_error_allowance(self):
        a = arrays(())
        values = [2.**53, 1., -2.**53, 0., 0., 0., 0., 0.]
        a['nodes']['value'][:8] = values
        p = c.prior_checker().primitives()
        _, trees = p.inventory(a)
        record, outgoing, _ = c.expected_block(p, trees, 0, (F(0), F(0)), (F(-4), F(4)))
        self.assertEqual([p.rational(v) for v in record['real_sum']], [F(1), F(1)])
        native = 0.
        for value in values:native = native + value
        self.assertEqual(native, 0.)
        self.assertGreaterEqual(p.rational(record['error_total']), 1)
        self.assertTrue(outgoing[0] <= F(native) <= outgoing[1])

    def test_matching_extremum_need_not_be_attained(self):
        p = c.prior_checker().primitives()
        full = ((-p.MAX, p.MAX),)*62
        trees = []
        for feature in (0, 1):
            tree = []
            for leaf, branch, value in ((1, 'L', -1.), (2, 'R', 1.)):
                edge = {'node': 0, 'feature': feature, 'threshold': 0.0.hex(), 'branch': branch}
                tree.append(({'leaf': leaf, 'value': value.hex(), 'edges': [edge]}, p.restrict(full, feature, 0., branch)))
            trees.append(tree)
        third = []
        for leaf, (sx, sy) in enumerate(((-1, -1), (-1, 1), (1, -1), (1, 1)), 1):
            edges = [{'node': 0, 'feature': 0, 'threshold': 0.0.hex(), 'branch': 'L' if sx < 0 else 'R'},
                     {'node': 1 if sx < 0 else 4, 'feature': 1, 'threshold': 0.0.hex(), 'branch': 'L' if sy < 0 else 'R'}]
            box = full
            for edge in edges:box = p.restrict(box, edge['feature'], 0., edge['branch'])
            third.append(({'leaf': leaf, 'value': float(-sx*sy).hex(), 'edges': edges}, box))
        trees.append(third)
        trees.extend([[({'leaf': 0, 'value': 0.0.hex(), 'edges': []}, full)] for _ in range(5)])
        record, _, _ = c.expected_block(p, trees, 0, (F(0), F(0)), (F(-4), F(4)))
        upper = p.rational(record['real_sum'][1])
        actual = max(sx+sy-sx*sy for sx in (-1, 1) for sy in (-1, 1))
        self.assertEqual(actual, 1)
        self.assertEqual(upper, 3)
        self.assertGreater(upper, actual)

    def test_resource_admission(self):
        with self.assertRaises(MemoryError):c.owned_estimate(0, 0, 0, c.LINE_CAP+1)
        with self.assertRaises(ValueError):c.owned_estimate(True, 0, 0)
        with self.assertRaises(MemoryError):c.check_stream(stream(self.records), self.a, self.old, expected=self.expected, source_bytes=100*2**20)


if __name__ == '__main__':
    unittest.main()
