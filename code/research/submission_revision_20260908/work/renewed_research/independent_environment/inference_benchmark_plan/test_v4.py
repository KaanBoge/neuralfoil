"""Synthetic mocked child receipts only; no real arrays, predictor or timer."""
import json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import runner_v4 as runner
import loader_v2,measurement_v3
from serving import ROUTES
from timing import schedule

class Tests(unittest.TestCase):
    def test_preflight_cold_warm_receipt_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory).resolve();ab=b'synthetic approval';rb=b'synthetic registry'
            registry={'scopes':{'all':{'files':{},'archives':{},'arrays':{}},**{r:{'files':{},'archives':{},'arrays':{}} for r in ROUTES}},'routes':list(ROUTES),'max_request_seconds':60}
            approval={};sources={}
            def fake_load(root,r,route=None,with_references=False,access=None):
                return types.SimpleNamespace(request=lambda *a,**k:{}),{}, {'scope':'synthetic'},access,{}
            values={r:{'synthetic_CD':np.ones(1,dtype=np.float64)} for r in ROUTES}
            def fake_warm(serv,refs,emit):
                for repeat,route in schedule():emit({'repeat':repeat,'route':route,'seconds':0.,'output_rows':497})
                return {'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49}
            def args(phase,route=None,pred=None):return types.SimpleNamespace(phase=phase,route=route,project='/synthetic-not-read',output=str(out),predecessor_sha256=pred)
            with patch.object(loader_v2,'load',side_effect=fake_load) as load,patch.object(loader_v2,'finish'),patch.object(measurement_v3,'preflight',return_value=values),patch.object(measurement_v3,'measured',return_value=0.) as measured,patch.object(measurement_v3,'warm',side_effect=fake_warm),patch.object(runner,'finish_bootstrap'):
                runner.child(args('preflight'),approval,registry,sources,ab,rb,[])
                raw=(out/'preflight_COMPLETE.json').read_bytes();preflight=json.loads(raw)
                self.assertEqual(preflight['phase'],'preflight');self.assertIsNone(preflight['route'])
                self.assertEqual(set(preflight['outputs']),{'reference_'+r+'.npz' for r in ROUTES})
                self.assertEqual(load.call_args.kwargs['route'],None);self.assertTrue(load.call_args.kwargs['with_references'])
                pred=runner.sha(raw)
                for route in ROUTES:
                    runner.child(args('cold',route,pred),approval,registry,sources,ab,rb,[])
                    cold=json.loads((out/('cold_'+route+'_COMPLETE.json')).read_text())
                    self.assertEqual(cold['phase'],'cold');self.assertEqual(cold['route'],route)
                    self.assertEqual(cold['predecessor_sha256'],pred)
                    self.assertEqual(set(cold['outputs']),{'reference_'+route+'.npz','cold_'+route+'.json'})
                    self.assertEqual(load.call_args.kwargs['route'],route);self.assertFalse(load.call_args.kwargs['with_references'])
                self.assertEqual(measured.call_count,7)
                runner.child(args('warm',pred=pred),approval,registry,sources,ab,rb,[])
                warm=json.loads((out/'warm_COMPLETE.json').read_text())
                self.assertEqual(warm['phase'],'warm');self.assertIsNone(warm['route']);self.assertEqual(warm['predecessor_sha256'],pred)
                self.assertEqual(load.call_args.kwargs['route'],None)
                self.assertEqual(len([n for n in warm['outputs'] if n.startswith('warm_')]),49)
                self.assertEqual(json.loads((out/'WARM_COUNTS.json').read_text()),{'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49})
    def test_metadata_only_source_diff(self):
        p=Path(__file__).parent
        old=(p/'runner_v3.py').read_text()
        expected=old.replace('runner_v3.py','runner_v4.py').replace('REGISTRY_v3.json','REGISTRY_v4.json').replace('one_fixed_inference_benchmark_v3','one_fixed_inference_benchmark_v4').replace("for route,v in values.items():\n                p=out/('reference_'+route+'.npz')","for reference_route,v in values.items():\n                p=out/('reference_'+reference_route+'.npz')")
        self.assertEqual((p/'runner_v4.py').read_text(),expected)
if __name__=='__main__':unittest.main()
