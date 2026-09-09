"""Freeze the consolidated successor from authenticated v1 metadata, no arrays."""
import copy
from pathlib import Path
from pilot_adapter import authenticate,sha
from pilot_runner_v2 import exclusive_json


def main():
    root=Path(__file__).resolve().parent
    r,_=authenticate(root/'PILOT_REGISTRY.json','6062c7fe6ce3723901a8437ddc89cd9095d4f8d1bf02c22b09ad3be15cb27d06')
    r=copy.deepcopy(r)
    r['successor']='v2 consolidated source-only correction; separate approval required'
    for name in ('PILOT_REGISTRY.json','PILOT_SYNTHETIC_WITNESS.json','PILOT_IMPLEMENTATION_REVIEW.md',
                 'pilot_engine_v2.py','pilot_runner_v2.py','test_pilot_v2.py',
                 'PILOT_V2_PROTOCOL.md','SUCCESSOR_FIRST_TEST_FAILURE.md',
                 'STATIC_ACCOUNTING_V1_BENCHMARK.json','benchmark_static_v2.py',
                 'STATIC_ACCOUNTING_V2_BENCHMARK.json','prepare_pilot_v2.py'):
        r['sources'][name]={'path':name,'sha256':sha(root/name)}
    exclusive_json(root/'PILOT_REGISTRY_V2.json',r)
    print({'registry_sha256':sha(root/'PILOT_REGISTRY_V2.json'),'real_model_arrays_opened':False})


if __name__=='__main__':main()
