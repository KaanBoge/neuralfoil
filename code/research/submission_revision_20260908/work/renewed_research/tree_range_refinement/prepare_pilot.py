"""Freeze metadata and source pins only. NEVER opens model arrays."""
import json
import os
from pathlib import Path
from pilot_adapter import sha
from pilot_runner import exclusive_json


def main():
    root = Path(__file__).resolve().parent
    prior = root.parent/'model_proposal/range_bound_feasibility'
    inputs = root.parent/'independent_environment/bounds_extraction'
    expected = {
        'qualified_numerics': (prior/'qualified_numerics.py', '76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a'),
        'evaluator': (prior/'stage1_v2/evaluator.py', '562279b3b636910098bf6f5e1bf2af790998a085d4233fa90975fdbdfcbf4705'),
        'stage0_certificate': (prior/'STAGE0_CERTIFICATE.json', '8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782'),
        'stage0_certifier': (prior/'certify_stage0.py', '54d3d84a4f5fed5f837e851ee9b84828f24f6bccfe6d5592bb44e082970882af'),
        'input_manifest': (inputs/'manifest.json', '210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea')}
    for key, (path, pin) in expected.items():
        if sha(path) != pin:
            raise ValueError('prior witness mismatch: '+key)
    manifest = json.loads((inputs/'manifest.json').read_text())
    certificate = json.loads((prior/'STAGE0_CERTIFICATE.json').read_text())
    key = 'arrays/tree_31_capped.npz'
    pin = 'ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
    if manifest['files'][key] != pin or certificate['accessed_tree_sha256'][key] != pin:
        raise ValueError('prior input hash witnesses disagree')
    registry = {'scope': {'context': 'final', 'branch': 'proper', 'family': 'capped', 'dimensions': 62, 'stages': 400},
                'real_execution_not_yet_authorized': True,
                'input': {'path': os.path.relpath(inputs/key, root), 'sha256': pin},
                'sources': {k: {'path': os.path.relpath(p, root), 'sha256': h} for k, (p,h) in expected.items()},
                'inherited_range': next(v['range'] for v in certificate['records'] if v['context']=='final'),
                'budgets': {'splits':128, 'search_node_visits':4000000, 'search_seconds':120,
                            'replay_seconds':60, 'algorithm_owned_estimate_bytes':128*1024*1024}}
    for name in ('PLAN.md','prototype.py','test_prototype.py','PILOT_PROTOCOL.md', 'pilot_adapter.py',
                 'pilot_engine.py','pilot_checker.py','pilot_runner.py','test_pilot.py','prepare_pilot.py'):
        registry['sources'][name] = {'path': name, 'sha256': sha(root/name)}
    exclusive_json(root/'PILOT_REGISTRY.json', registry)
    print(json.dumps({'registry_sha256':sha(root/'PILOT_REGISTRY.json'), 'model_arrays_opened':False}))


if __name__ == '__main__':
    main()
