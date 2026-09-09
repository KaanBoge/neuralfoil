import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import runner
from test_producer import relation_fixture,Q,ORACLE,CHECKER
from pilot_adapter import authenticate

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parents[1]/'performance_diagnosis/PILOT_REGISTRY_V3.json'
PIN='a989ed3215fd933650c49d15644219e678e59e001affa141091fdabb02eba2a5'


class Tests(unittest.TestCase):
    def setUp(self):self.r,self.oldroot=authenticate(OLD,PIN)
    def args(self,out):return argparse.Namespace(output=str(out),registry=str(OLD),approved_registry_sha256=PIN,candidate=None)
    def test_source_rejection_precedes_array_access(self):
        with mock.patch.object(runner.adapter,'load_model') as load:
            with self.assertRaises(ValueError):authenticate(OLD,'0'*64)
            load.assert_not_called()
    def test_domain_stamped_inherited_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'new'
            def fail(cmd,**kwargs):
                self.assertTrue((out/'checkpoint_000_inherited.json').exists())
                self.assertLessEqual(kwargs['timeout'],120)
                raise subprocess.TimeoutExpired(cmd,kwargs['timeout'])
            with mock.patch.object(runner.subprocess,'run',side_effect=fail):runner.orchestrate(self.args(out),self.r,self.oldroot)
            final=json.loads((out/'FINAL.json').read_text())
            self.assertEqual(final['status'],'INHERITED_STAGE0_ONLY');self.assertEqual(final['bound_valid_on'],'FULL_FINITE_X62')
            self.assertEqual(final['domain'],runner.stamp())
    def test_mock_worker_and_checker_use_distinct_oracles(self):
        model=relation_fixture()
        def source(r,root,key):return {'qualified_numerics':Q,'root_exact_oracle':ORACLE,'relation_checker':CHECKER}[key]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(runner.adapter,'load_model',return_value=model), mock.patch.object(runner.adapter,'source_module',side_effect=source):
            args=self.args(d);runner.worker(args,self.r,self.oldroot)
            args.candidate=str(Path(d)/'candidate_001.json');runner.check(args,self.r,self.oldroot)
            status=json.loads((Path(d)/'worker_status.json').read_text());verified=json.loads((Path(d)/'verified.json').read_text())
            self.assertGreater(status['oracle_calls'],0);self.assertEqual(status['domain'],runner.stamp())
            self.assertEqual(verified['status'],'PASS_RESTRICTED_DOMAIN_REPLAY');self.assertEqual(verified['r_empty_boxes'],1)
    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as d,mock.patch.object(runner.subprocess,'run') as run:
            with self.assertRaises(FileExistsError):runner.orchestrate(self.args(d),self.r,self.oldroot)
            run.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
