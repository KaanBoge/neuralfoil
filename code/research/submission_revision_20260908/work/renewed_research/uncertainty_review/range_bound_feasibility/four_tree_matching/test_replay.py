"""Independent wrapper mocks, no real model intake or phase execution."""
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import replay as r
from test_checker import pack, stump


class Tests(unittest.TestCase):
    def test_exact_approval_contract(self):
        ap = {'phase': r.PHASE, 'checker_registry_sha256': 'a'*64,
              'producer_registry_sha256': 'b'*64, 'model_sha256': r.MODEL_SHA,
              'domain': 'FINITE_X62_V1', 'seconds': 900, 'workers': 1,
              'owned_cap': 256*2**20, 'output_cap': 64*2**20,
              'real_execution_authorized': True, 'output': 'attempt_1',
              'producer_complete_sha256': 'c'*64, 'producer_approval_sha256': 'd'*64,
              'certificate_sha256': 'e'*64, 'source_review_sha256': 'f'*64,
              'synthetic_gate_sha256': '0'*64}
        r.strict_approval(ap, 'a'*64, 'b'*64)
        for key, value in (('phase', 'score'), ('workers', True), ('seconds', 901),
                           ('real_execution_authorized', False), ('domain', 'R'),
                           ('output', '../elsewhere'), ('certificate_sha256', 'bad')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                r.strict_approval(dict(ap, **{key: value}), 'a'*64, 'b'*64)
        with self.assertRaises(ValueError):
            r.strict_approval(dict(ap, extra=1), 'a'*64, 'b'*64)

    def test_cold_resource_limits_not_loosened(self):
        gate = {'producer': {'seconds': 1., 'owned_estimate': 128*2**20,
                             'logical_output_bytes': 64*2**20},
                'checker': {'seconds': 120., 'owned_estimate': 256*2**20,
                            'logical_output_bytes': 64*2**20}}
        r.resource_gate(gate)
        for phase in ('producer', 'checker'):
            for key, value in (('seconds', float('nan')), ('seconds', 120.01),
                               ('seconds', True), ('owned_estimate', 257*2**20),
                               ('logical_output_bytes', 64*2**20+1)):
                bad = copy.deepcopy(gate)
                bad[phase][key] = value
                with self.subTest(phase=phase, key=key), self.assertRaises(ValueError):
                    r.resource_gate(bad)

    def test_independent_safe_member_intake(self):
        arrays = pack([stump(-.125, .125)])
        output = io.BytesIO()
        np.savez_compressed(output, **arrays)
        ledger = []
        reconstructed = r.independent_arrays(output.getvalue(), ledger)
        self.assertEqual(len(ledger), 7)
        for key in arrays:
            np.testing.assert_array_equal(arrays[key], reconstructed[key])
        output = io.BytesIO()
        np.savez_compressed(output, **arrays, extra=np.zeros(1))
        with self.assertRaises(ValueError):
            r.independent_arrays(output.getvalue(), [])

    def test_failed_bootstrap_cannot_load_arrays(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path).resolve()
            (root/'CHECKER_SOURCE_REGISTRY_V1.json').write_bytes(b'{}')
            with patch.object(r, 'HERE', root), patch.object(r, 'independent_arrays') as intake:
                with self.assertRaises(ValueError):
                    r.execute(SimpleNamespace(registry_sha256='0'*64, approval_sha256='1'*64))
                intake.assert_not_called()

    def test_bad_registry_schema_cannot_load_arrays(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path).resolve()
            raw = b'{}'
            (root/'CHECKER_SOURCE_REGISTRY_V1.json').write_bytes(raw)
            with patch.object(r, 'HERE', root), patch.object(r, 'independent_arrays') as intake:
                with self.assertRaises(ValueError):
                    r.execute(SimpleNamespace(registry_sha256=hashlib.sha256(raw).hexdigest(), approval_sha256='1'*64))
                intake.assert_not_called()

    def test_completion_reauthentication_streams_and_rejects_mutation(self):
        with tempfile.TemporaryDirectory() as path:
            payload = Path(path).resolve()/'synthetic.bin'
            raw = b'abcd'*40000
            payload.write_bytes(raw)
            pin = hashlib.sha256(raw).hexdigest()
            ledger = []
            r.reauthenticate(payload, pin, len(raw), ledger, time.monotonic()+5)
            self.assertEqual(ledger[0]['maximum_chunk_bytes'], 65536)
            self.assertEqual(ledger[0]['bytes'], len(raw))
            for bad_pin, limit, deadline in ((pin, len(raw)-1, time.monotonic()+5),
                                             ('0'*64, len(raw), time.monotonic()+5)):
                with self.assertRaises(ValueError):
                    r.reauthenticate(payload, bad_pin, limit, [], deadline)
            with self.assertRaises(TimeoutError):
                r.reauthenticate(payload, pin, len(raw), [], 0)


if __name__ == '__main__':
    unittest.main()
