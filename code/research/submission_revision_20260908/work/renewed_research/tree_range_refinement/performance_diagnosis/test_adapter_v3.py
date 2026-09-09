"""Source-only adapter tests; every model load is mocked with synthetic arrays."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import pilot_runner_v3 as runner
from test_cache_v3 import fixture,Q
from pilot_adapter import authenticate

ROOT=Path(__file__).resolve().parent
V2_PIN='5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a'


class Tests(unittest.TestCase):
    def setUp(self):
        self.r,self.oldroot=authenticate(ROOT.parent/'PILOT_REGISTRY_V2.json',V2_PIN)

    def args(self,output):
        return argparse.Namespace(output=str(output),registry=str(ROOT.parent/'PILOT_REGISTRY_V2.json'),
                    approved_registry_sha256=V2_PIN,candidate=None)

    def test_only_reviewed_engine_and_path_import_delta(self):
        old=(ROOT.parent/'pilot_runner_v2.py').read_text()
        expected=old.replace('import pilot_adapter as adapter',
             'sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\nimport pilot_adapter as adapter').replace(
             'from pilot_engine_v2 import Limits, refine','from engine_v3 import Limits, refine')
        self.assertEqual((ROOT/'pilot_runner_v3.py').read_text(),expected)

    def test_wrong_registry_refused_before_model_access(self):
        with mock.patch.object(runner.adapter,'load_model') as load:
            with self.assertRaisesRegex(ValueError,'registry hash'):
                runner.adapter.authenticate(ROOT.parent/'PILOT_REGISTRY_V2.json','0'*64)
            load.assert_not_called()

    def test_synthetic_worker_uses_reviewed_engine_and_durable_writer(self):
        import engine_v3
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(runner.adapter,'load_model',return_value=fixture(1)) as load, \
                 mock.patch.object(runner.adapter,'source_module',return_value=Q), \
                 mock.patch.object(engine_v3,'refine',wraps=engine_v3.refine) as refine:
                runner.worker(self.args(d),self.r,self.oldroot)
            load.assert_called_once();refine.assert_called_once()
            status=json.loads((Path(d)/'worker_status.json').read_text())
            self.assertEqual(status['status'],'SEARCH_RETURNED')
            self.assertEqual(status['stop_reason'],'routing_resolved')
            self.assertTrue(status['root_initialized'])
            self.assertTrue((Path(d)/'candidate_000.json').exists())

    def test_inherited_published_before_mock_timeout_and_partial_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'new'
            calls=[]
            def timeout(command,**kwargs):
                calls.append((command,kwargs))
                self.assertTrue((out/'checkpoint_000_inherited.json').exists())
                def interrupt(chunk):raise KeyboardInterrupt()
                with self.assertRaises(KeyboardInterrupt):
                    runner.exclusive_json(out/'candidate_000.json',{'unverified':'partial'},serialization_interrupt=interrupt)
                raise subprocess.TimeoutExpired(command,kwargs['timeout'])
            with mock.patch.object(runner.subprocess,'run',side_effect=timeout),mock.patch.object(runner.adapter,'load_model') as load:
                runner.orchestrate(self.args(out),self.r,self.oldroot)
                load.assert_not_called()
            final=json.loads((out/'FINAL.json').read_text())
            self.assertEqual(final['status'],'INHERITED_STAGE0_ONLY');self.assertTrue(final['search']['timeout'])
            self.assertIsNone(final['verification']);self.assertEqual(len(calls),1)
            self.assertLessEqual(calls[0][1]['timeout'],120)
            for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
                self.assertEqual(calls[0][1]['env'][key],'1')
            self.assertTrue((out/'candidate_000.json.partial').exists())

    def test_output_collision_prevents_subprocess(self):
        with tempfile.TemporaryDirectory() as d,mock.patch.object(runner.subprocess,'run') as run:
            with self.assertRaises(FileExistsError):runner.orchestrate(self.args(d),self.r,self.oldroot)
            run.assert_not_called()

    def test_mock_loader_failure_has_inherited_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'new'
            with mock.patch.object(runner.subprocess,'run',return_value=subprocess.CompletedProcess([],1)):
                runner.orchestrate(self.args(out),self.r,self.oldroot)
            final=json.loads((out/'FINAL.json').read_text())
            self.assertEqual(final['status'],'INHERITED_STAGE0_ONLY')
            self.assertEqual(final['search']['returncode'],1)


if __name__=='__main__':unittest.main(verbosity=2)
