"""Fresh-process inference dependency and saved-array check, NumPy plus stdlib only."""
from pathlib import Path
import hashlib,importlib.util,json,sys
import numpy as np
HERE=Path(__file__).resolve().parent;BUNDLE=HERE.parents[1]/'union_deployment'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=json.loads((BUNDLE/'manifest.json').read_text())
assert sha(BUNDLE/'predictor.py')==manifest['predictor_sha256']
assert sha(BUNDLE/'retrospective_union.json')==manifest['artifact_sha256']
assert sha(BUNDLE/'inference_references.npz')==manifest['inference_references_sha256']
spec=importlib.util.spec_from_file_location('numpy_union_only',BUNDLE/'predictor.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
artifact=json.loads((BUNDLE/'retrospective_union.json').read_text());rows=0
with np.load(BUNDLE/'inference_references.npz',allow_pickle=False) as refs:
    for name in ['historical','SG_exposed','W_new_challenge']:
        d={k:refs[name+'_'+k] for k in ['BASE_CD','X62','all_model_CD','Re']}
        pred=m.predict(artifact,d,refs[name+'_gate']);np.testing.assert_array_equal(pred,refs[name+'_expected_CD']);rows+=len(pred)
assert rows==8868
assert not any(k=='sklearn' or k.startswith('sklearn.') or k=='scipy' or k.startswith('scipy.') for k in sys.modules)
result={'status':'PASS fresh NumPy-only independent replay','rows':rows,'bit_identical_reference_predictions':True,'sklearn_or_scipy_imported':False,'source_sha256':sha(Path(__file__))}
(HERE/'numpy_only_replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
