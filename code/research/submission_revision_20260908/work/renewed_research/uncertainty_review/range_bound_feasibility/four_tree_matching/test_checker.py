"""Independent arrays and adversarial tests; only synthetic producer integration.

No real model or outcomes are read. The producer supplies candidate certificates,
never expected arithmetic/path answers to the checker.
"""
import copy
from fractions import Fraction as F
import importlib.util
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
SYNTHETIC = 'f' * 64


def constant(v):
    a = np.zeros(1, dtype=DT)
    a['is_leaf'] = 1
    a['value'] = v
    return a


def stump(lo, hi, feature=0, threshold=0.):
    a = np.zeros(3, dtype=DT)
    a[0]['left'], a[0]['right'] = 1, 2
    a[0]['feature_idx'], a[0]['num_threshold'] = feature, threshold
    a[1:]['is_leaf'] = 1
    a[1:]['value'] = [lo, hi]
    return a


def pack(trees, initial=0.):
    trees = list(trees) + [constant(0.) for _ in range(400-len(trees))]
    arrays = {'initial': np.array([initial], dtype='f8'),
              'nodes': np.concatenate(trees),
              'nodes_offsets': np.cumsum([0] + [len(t) for t in trees], dtype='i8')}
    for name in ('raw_left_cat_bitsets', 'binned_left_cat_bitsets'):
        arrays[name] = np.array([], dtype='u4')
        arrays[name+'_offsets'] = np.zeros(401, dtype='i8')
    return arrays


def producer():
    path = Path(__file__).resolve().parents[3] / 'model_proposal/four_tree_matching_plan/producer.py'
    spec = importlib.util.spec_from_file_location('synthetic_candidate_producer', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def candidate(arrays):
    p = producer()
    return p.construct(arrays, p.Budget(), model_sha=SYNTHETIC)


def verify(cert, arrays, **kw):
    return c.check(cert, arrays, expected_model_sha=SYNTHETIC, **kw)


class PrimitiveTests(unittest.TestCase):
    def test_exact_half_subnormal(self):
        self.assertGreater(c.HALF_ETA, 0)
        self.assertEqual(float(c.HALF_ETA), 0.)
        self.assertEqual(c.HALF_ETA * 2, F(math.nextafter(0., 1.)))

    def test_rational_codec_and_resource_rejection(self):
        for value in (F(0), F(-7, 8), c.HALF_ETA, F(2**4095)):
            c.safe_json(c.encoded(value))
        for value in (F(2**4096), F(1, 2**4096)):
            with self.assertRaises(ValueError):
                c.encoded(value)
        for value in ({'encoding': 'signed_hex_fraction_v1', 'numerator': '0x2', 'denominator': '0x2'},
                      {'encoding': 'signed_hex_fraction_v1', 'numerator': '0x1', 'denominator': '-0x2'},
                      {'encoding': 'signed_hex_fraction_v1', 'numerator': '0X1', 'denominator': '0x2'},
                      1.0, None):
            with self.assertRaises(ValueError):
                c.safe_json(value)

    def test_owned_accounting_admission(self):
        self.assertLess(c.owned_estimate(2**20, 2**20, 2**20), c.MEMORY_CAP)
        for value in (-1, True, 1.):
            with self.assertRaises(ValueError):
                c.owned_estimate(value, 0, 0)
        with self.assertRaises(MemoryError):
            c.owned_estimate(0, 0, c.INPUT_CAP+1)

    def test_primitive_outward_overflow(self):
        p = c.primitives()
        with self.assertRaises(ValueError):
            p.directed(F(sys.float_info.max)*2, True)

    def test_preparse_structural_and_scalar_rejection(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}',
                    b'['*17+b']'*17, b'{"x":'+b'9'*100+b'}',
                    b'{"x":"'+b'a'*7000+b'"}', b'{"x":"unfinished'):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                c.parse_certificate(raw)
        # Container inflation is charged before constructing nested objects.
        raw = b'[' + b','.join([b'[]']*6000) + b']'
        _, allocation = c.parse_certificate(raw)
        self.assertGreater(allocation, 5*len(raw))


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arrays = pack([stump(-.125, .125), stump(-.125, .125),
                           stump(.125, -.125), stump(.125, -.125)])
        cls.cert = candidate(cls.arrays)

    def test_cross_cancellation_and_original_chain_separate(self):
        result = verify(self.cert, self.arrays)
        q = lambda x: F(int(x['numerator'], 16), int(x['denominator'], 16))
        self.assertEqual(list(map(q, self.cert['blocks'][0]['real_sum'])), [0, 0])
        self.assertGreater(q(result['final']['lower']), q(result['original_adjacent']['lower']))
        self.assertLess(q(result['final']['upper']), q(result['original_adjacent']['upper']))
        self.assertNotEqual(self.cert['blocks'][1]['incoming'], self.cert['blocks'][1]['original_incoming'])
        self.assertGreater(result['branch_witness_checks'], 0)

    def test_native_reassociation_counterexample(self):
        arrays = pack([constant(2.**53), constant(1.), constant(-2.**53), constant(0.)])
        cert = candidate(arrays)
        verify(cert, arrays)
        q = lambda x: F(int(x['numerator'], 16), int(x['denominator'], 16))
        self.assertEqual(list(map(q, cert['blocks'][0]['real_sum'])), [1, 1])
        native = ((2.**53 + 1.) - 2.**53) + 0.
        self.assertEqual(native, 0.)
        self.assertLessEqual(q(cert['final']['lower']), F(native))
        self.assertGreaterEqual(q(cert['final']['upper']), F(native))

    def test_signed_zero_subnormal_and_empty_max_right(self):
        eta = math.nextafter(0., 1.)
        arrays = pack([stump(-eta, eta, threshold=-0.),
                       stump(eta, -eta, threshold=0.),
                       stump(0., 1., threshold=sys.float_info.max)], initial=-0.)
        cert = candidate(arrays)
        verify(cert, arrays)
        self.assertEqual(cert['initial'], '-0x0.0p+0')
        self.assertTrue(cert['paths'][2]['leaves'][1]['empty'])

    def test_mutated_status_missing_duplicate_pair(self):
        for mode in ('status', 'omit', 'duplicate', 'swap', 'uppercase', 'shape', 'feasible'):
            cert = copy.deepcopy(self.cert)
            pairs = cert['blocks'][0]['pairs']
            if mode == 'status': pairs[0]['status_hex'] = '02' * 4
            if mode == 'omit': pairs.pop()
            if mode == 'duplicate': pairs[1] = copy.deepcopy(pairs[0])
            if mode == 'swap': pairs[0], pairs[1] = pairs[1], pairs[0]
            if mode == 'uppercase': pairs[0]['status_hex'] = '020A0202'
            if mode == 'shape': pairs[0]['shape'][0] = 2.0
            if mode == 'feasible': pairs[0]['feasible'] = True
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify(cert, self.arrays)

    def test_mutated_path_leaf_branch_empty_or_order(self):
        for mode in ('branch', 'leaf', 'empty', 'stage', 'value', 'unknown', 'order'):
            cert = copy.deepcopy(self.cert)
            stage = cert['paths'][0]
            leaf = stage['leaves'][0]
            if mode == 'branch': leaf['edges'][0][3] = True
            if mode == 'leaf': leaf['leaf'] = 2
            if mode == 'empty': leaf['empty'] = True
            if mode == 'stage': stage['stage'] = False
            if mode == 'value': leaf['value'] = '0x1.0000000000000p+0'
            if mode == 'unknown': leaf['unknown'] = 0
            if mode == 'order': stage['leaves'].reverse()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify(cert, self.arrays)

    def test_mutated_bound_error_matching_or_old_chain(self):
        for mode in ('delta', 'total', 'matching', 'range', 'round', 'adjacent', 'old', 'out'):
            cert = copy.deepcopy(self.cert)
            b = cert['blocks'][0]
            if mode == 'delta': b['error_steps'][0]['delta'] = c.encoded(0)
            if mode == 'total': b['error_total'] = c.encoded(0)
            if mode == 'matching': b['matchings'][0]['pair_indices'] = [0, 4]
            if mode == 'range': b['real_sum'][0] = c.encoded(1)
            if mode == 'round': b['rounding_branch'][0] = c.encoded(0)
            if mode == 'adjacent': b['adjacent_transfer'][0][0] = c.encoded(0)
            if mode == 'old': cert['blocks'][1]['original_incoming'] = cert['blocks'][1]['incoming']
            if mode == 'out': b['outgoing'][1] = c.encoded(-1)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify(cert, self.arrays)

    def test_mutated_identity_counts_accounting_summary(self):
        for mode in ('hash', 'domain', 'count', 'account', 'extra', 'summary', 'stage'):
            cert = copy.deepcopy(self.cert)
            if mode == 'hash': cert['model_sha256'] = '0'*64
            if mode == 'domain': cert['domain'] = 'R'
            if mode == 'count': cert['counts']['stages'] = 400.
            if mode == 'account': cert['accounting']['array_bytes'] += 1
            if mode == 'extra': cert['extra'] = 1
            if mode == 'summary': cert['stage0']['B'] = c.encoded(0)
            if mode == 'stage': cert['blocks'].pop()
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify(cert, self.arrays)

    def test_model_mutation_and_readonly_preservation(self):
        arrays = copy.deepcopy(self.arrays)
        arrays['nodes'][1]['value'] += .01
        with self.assertRaises(ValueError):
            verify(self.cert, arrays)
        before = {k: a.tobytes() for k, a in self.arrays.items()}
        for a in self.arrays.values(): a.setflags(write=False)
        verify(self.cert, self.arrays)
        self.assertEqual(before, {k: a.tobytes() for k, a in self.arrays.items()})

    def test_deadline_wrong_stage_count_and_memory(self):
        with self.assertRaises(TimeoutError): verify(self.cert, self.arrays, deadline=0)
        with self.assertRaises(MemoryError): verify(self.cert, self.arrays, input_bytes=c.INPUT_CAP)
        arrays = copy.deepcopy(self.arrays)
        arrays['nodes_offsets'] = arrays['nodes_offsets'][:-1]
        with self.assertRaises(ValueError): verify(self.cert, arrays)

    def test_json_roundtrip(self):
        raw = json.dumps(self.cert, allow_nan=False).encode()
        parsed, allocation = c.parse_certificate(raw, array_bytes=sum(a.nbytes for a in self.arrays.values()))
        verify(parsed, self.arrays, input_bytes=len(raw), parsed_bytes=allocation)


if __name__ == '__main__':
    unittest.main()
