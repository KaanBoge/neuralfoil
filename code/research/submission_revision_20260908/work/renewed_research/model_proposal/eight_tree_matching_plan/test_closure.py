"""Hostile small metadata/timer mocks; no large fixture or real payload."""
import argparse
import json
from pathlib import Path
import signal
import tempfile
import time
import unittest
from unittest.mock import patch
import production_support as s
import run_phase
import run_gate


class ClosureTests(unittest.TestCase):
    def test_aggregate_live_before_second_parse(self):
        raw=b'['+b','.join([b'0']*100)+b']'
        charge=s.metadata_charge(raw)
        budget=s.MetadataBudget(s.METADATA_CAP-charge)
        with patch.object(s,'parse',wraps=s.parse) as parser:
            self.assertEqual(len(budget.parse(raw,[],'first')),100)
            with self.assertRaises(MemoryError):budget.parse(raw,[],'second')
            self.assertEqual(parser.call_count,1)
        self.assertEqual(budget.used,s.METADATA_CAP)

    def test_hostile_metadata_depth_no_parse(self):
        raw=b'['*19+b'0'+b']'*19
        with patch.object(s,'parse') as parser:
            with self.assertRaises(ValueError):s.MetadataBudget().parse(raw,[],'deep')
            parser.assert_not_called()

    def test_quoted_braces_not_containers(self):
        raw=b'{"a":"[[[}}}"}'
        self.assertEqual(s.MetadataBudget().parse(raw,[],'quoted'),{'a':'[[[}}}'})

    def test_parent_deadline_not_extended(self):
        with patch.object(s.signal,'getsignal',return_value='old'),patch.object(s.signal,'getitimer',return_value=(5.,0.)),patch.object(s.signal,'signal'),patch.object(s.signal,'setitimer') as timer,patch.object(s.time,'monotonic',side_effect=[10.,12.]):
            with self.assertRaises(TimeoutError):
                with s.HardDeadline(120):raise TimeoutError('manufactured phase')
            self.assertEqual(timer.call_args_list[0].args,(signal.ITIMER_REAL,5.))
            self.assertEqual(timer.call_args_list[-1].args,(signal.ITIMER_REAL,3.,0.))

    def test_subphase_120_without_parent(self):
        with patch.object(s.signal,'getsignal'),patch.object(s.signal,'getitimer',return_value=(0.,0.)),patch.object(s.signal,'signal'),patch.object(s.signal,'setitimer') as timer:
            with s.HardDeadline(120):pass
            self.assertEqual(timer.call_args_list[0].args,(signal.ITIMER_REAL,120))

    def test_actual_entry900_starts_before_bootstrap(self):
        args=argparse.Namespace(phase='capsule',registry_sha256='a'*64,approval_sha256='b'*64)
        with patch.object(run_phase.signal,'getsignal'),patch.object(run_phase.signal,'signal'),patch.object(run_phase.signal,'setitimer') as timer:
            def fail(*args):
                self.assertEqual(timer.call_args_list[0].args,(signal.ITIMER_REAL,900))
                raise TimeoutError('bootstrap deadline')
            with patch.object(run_phase,'bootstrap',side_effect=fail),self.assertRaises(TimeoutError):run_phase.execute(args)
            self.assertEqual(timer.call_args_list[-1].args,(signal.ITIMER_REAL,0))

    def test_timeout_receipt_and_stream_remain(self):
        with tempfile.TemporaryDirectory() as td:
            store=s.Store(Path(td).resolve()/'attempt',time.monotonic()+10)
            store.begin();store.record({'kind':'synthetic'})
            store.deadline=time.monotonic()-1
            exc=TimeoutError('fixed subphase')
            s.retain_failure(store,{'phase':'mock'},[],time.monotonic(),exc,'synthetic')
            record=json.loads((store.path/'FAILURE.json').read_bytes())
            self.assertEqual(record['status'],'FAILED_NO_RETRY')
            self.assertIn('fixed subphase',record['error'])
            self.assertEqual((store.path/'certificate.jsonl').read_bytes(),b'{"kind":"synthetic"}\n')

    def test_gate_approval_refuses_extra_and_caps(self):
        a=dict(phase='fixed_eight_synthetic_gate',registry_sha256='a'*64,entrypoint_sha256='b'*64,
               output='synthetic_gate_attempt_1',seconds=900,subphase_seconds=120,workers=1,
               producer_owned_cap=128*2**20,checker_owned_cap=256*2**20,output_cap=64*2**20,
               python='3.13.9',synthetic_execution_authorized=True,source_review_sha256='c'*64)
        run_gate.gate_approval(a,'a'*64,'b'*64)
        for key,value in [('subphase_seconds',121),('seconds',901),('extra',True),('synthetic_execution_authorized',False)]:
            bad=dict(a);bad[key]=value
            with self.assertRaises(ValueError):run_gate.gate_approval(bad,'a'*64,'b'*64)


if __name__=='__main__':unittest.main()
