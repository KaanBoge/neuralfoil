"""Source/metadata-only registry. Does not read actual model input arrays."""
import copy
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from pilot_adapter import authenticate,sha
from pilot_runner_v2 import exclusive_json


def main():
    root=Path(__file__).resolve().parent
    r,oldroot=authenticate(root.parent/'PILOT_REGISTRY_V2.json','5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a')
    out={'status':'SOURCE_SYNTHETIC_ONLY_REVIEW_REQUIRED','scope':r['scope'],
         'execution_authorized':False,'sources':{},'input_metadata_only':copy.deepcopy(r['input']),
         'budgets_unchanged':r['budgets']}
    out['input_metadata_only']['path']=os.path.relpath(oldroot/r['input']['path'],root)
    for k,v in r['sources'].items():
        out['sources']['v2/'+k]={'path':os.path.relpath(oldroot/v['path'],root),'sha256':v['sha256']}
    for p in [root.parent/'PILOT_REGISTRY_V2.json']+[root/n for n in (
            'PROFILE_PLAN.md','CACHE_FEASIBILITY_PLAN.md','profile_fixture.py','PROFILE_RESULT.json',
            'DIAGNOSIS_WITNESS.json','cache_v3.py','engine_v3.py','test_cache_v3.py',
            'profile_fixture_v3.py','PROFILE_V3_RESULT.json','verify_synthetic_v3.py',
            'SYNTHETIC_V3_WITNESS.json','V3_IMPLEMENTATION_REPORT.md','SOURCE_CHANGES.diff','freeze_source_v3.py')]:
        out['sources'][p.name]={'path':os.path.relpath(p,root),'sha256':sha(p)}
    exclusive_json(root/'CACHE_SOURCE_REGISTRY_V3.json',out)
    print({'registry_sha256':sha(root/'CACHE_SOURCE_REGISTRY_V3.json'),'sources':len(out['sources']),'real_model_arrays_opened':False})


if __name__=='__main__':main()
