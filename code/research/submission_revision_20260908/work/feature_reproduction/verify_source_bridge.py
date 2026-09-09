"""Record AST identity and bridge to the completed private model-study inputs."""
import ast,hashlib,json
from pathlib import Path
import numpy as np
here=Path(__file__).resolve().parent;root=here.parents[2]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def funcs(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)}
actual=funcs(here/'addon/feature_math.py');checks=[]
for path,names in [('model_development_20260906/reproduction/reproduce_doubleclean.py',['load_pts','foil_stats2']),('model_development_20260906/score_external.py',['predict_base']),('model_development_20260906_v2/develop_v2.py',['add_features']),('model_development_20260907_transition/generate_inputs.py',['calc','supplement'])]:
    source=root/path;original=funcs(source)
    for name in names:
        assert actual[name]==original[name];checks.append({'function':name,'source':path,'source_sha256':sha(source),'ast_identical':True})
bridge=[]
for name in ['historical','SG_exposed','W_new_challenge']:
    source=root/'reproduction_20260908_private/bundle/data'/f'{name}.npz';fresh=here/'results'/f'{name}.npz'
    with np.load(source,allow_pickle=False) as s,np.load(fresh,allow_pickle=False) as d:
        keys=['X62','BASE_CD','XLARGE_CD','all_model_CD','alpha','Re']
        for key in keys:
            assert np.array_equal(s[key],d[key]),(name,key)
        bridge.append({'cohort':name,'rows':len(d['alpha']),'keys_exact':keys,'source_sha256':sha(source),'regenerated_sha256':sha(fresh)})
result={'function_checks':checks,'private_A_B_package_bridge':bridge}
(here/'source_bridge_verified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
