"""Fresh real-input registry from frozen metadata only, no actual array access."""
import copy
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from pilot_adapter import authenticate,sha
from pilot_runner_v3 import exclusive_json


def main():
    root=Path(__file__).resolve().parent
    r,oldroot=authenticate(root.parent/'PILOT_REGISTRY_V2.json','5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a')
    cache=root/'CACHE_SOURCE_REGISTRY_V3.json'
    if sha(cache)!='ba110ac63b78f44d9dc8e3a3f277ab96245a8edfefa63fe15048569c979a3a5e':raise ValueError('cache registry pin')
    c=json.loads(cache.read_text())
    for key,item in c['sources'].items():
        if sha(root/item['path'])!=item['sha256']:raise ValueError('cache source mutation: '+key)
    out=copy.deepcopy(r)
    out['successor']='V3 minimal adapter preparation; separate real execution approval required'
    out['input']['path']=os.path.relpath(oldroot/r['input']['path'],root)
    out['sources']={k:{'path':os.path.relpath(oldroot/v['path'],root),'sha256':v['sha256']} for k,v in r['sources'].items()}
    for k,v in c['sources'].items():out['sources']['cache/'+k]=copy.deepcopy(v)
    for name in ('CACHE_SOURCE_REGISTRY_V3.json','pilot_runner_v3.py','test_adapter_v3.py',
                 'ADAPTER_V3_PROTOCOL.md','ADAPTER_V3_SOURCE.diff','ADAPTER_V3_SYNTHETIC_WITNESS.json','prepare_adapter_v3.py'):
        out['sources']['adapter/'+name]={'path':name,'sha256':sha(root/name)}
    exclusive_json(root/'PILOT_REGISTRY_V3.json',out)
    print({'registry_sha256':sha(root/'PILOT_REGISTRY_V3.json'),'source_count':len(out['sources']),'actual_model_arrays_opened':False})


if __name__=='__main__':main()
