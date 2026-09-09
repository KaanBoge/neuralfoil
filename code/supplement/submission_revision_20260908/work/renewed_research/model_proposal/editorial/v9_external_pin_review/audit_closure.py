"""Independently reconstruct external whitelist from selected metadata only.

No external contents or scientific payloads are read, and no finalizer runs.
"""
import ast
from collections import Counter
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[2]
PROJECT=WORK.parents[2]
TOOLS=WORK/'independent_environment/final_qa_tools'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    pins={};external={};origins={};parsed={}
    def path(raw,base=PROJECT):
        p=Path(raw)
        return p if p.is_absolute() else base/p
    def read(spec):
        p=path(spec['path']);assert p.resolve().is_relative_to(PROJECT)
        assert not any(x.is_symlink() for x in [p,*p.parents] if x.is_relative_to(PROJECT))
        raw=p.read_bytes();assert sha(raw)==spec['sha256']
        pins[str(p)]=spec['sha256'];parsed[str(p)]=spec['sha256']
        return json.loads(raw)
    def pointer(d,s):
        for k in s.strip('/').split('/') if s else []:
            k=k.replace('~1','/').replace('~0','~');d=d[int(k)] if isinstance(d,list) else d[k]
        return d
    def select(raw,h,origin,base=PROJECT):
        p=path(raw,base)
        if p.resolve().is_relative_to(PROJECT):return
        s=str(p)
        assert p.is_absolute() and s==str(Path(s)) and not any(x in {'','.','..'} for x in s.split('/')[1:])
        assert p.is_file() and not any(x.is_symlink() for x in [p,*p.parents])
        assert s not in external or external[s]==h
        external[s]=h;origins.setdefault(s,[]).append(origin)
    proposal=read(dict(path=str(TOOLS/'V9_EXTERNAL_READONLY_PROPOSAL.json'),sha256='148540058cbf4ffefaed38f197e1a939d5ffb720a29f360cb92b921571eb3728'))
    config=read(dict(path=proposal['config_path'],sha256=proposal['config_sha256']))
    assert proposal['config_sha256']=='90b6bb7459ca21285441909ecf396db92634879d85fdc8992ed1a95b3809908c'
    for e in config['evidence']:
        if not any(e.get(k) for k in ('assertions','maps','record_lists','scalar_pins')):continue
        d=read(e)
        for s in e.get('scalar_pins',[]):select(s['path'],pointer(d,s['pointer']),e['role']+':scalar')
        for s in e.get('record_lists',[]):
            for row in pointer(d,s['pointer']):select(row['path'],row['sha256'],e['role']+':list',path(s['base']))
        for s in e.get('maps',[]):
            for p,h in pointer(d,s['pointer']).items():select(p,h,e['role']+':map',path(s['base']))
    old=read(config['old_qa'])
    for p,h in old['files'].items():select(p,h,'old_qa:files',path(config['old_qa']['base']))
    assert external==proposal['external_readonly_pins'] and len(external)==360
    sources={}
    for n,h in {'finalize_v9.py':'103c77f1e2a5da1be65a124b121c08d0b0fd089a0b5c2a9484590e4795a7278a',
                'finalize_v9_v2.py':'027a192786e727344b45e7de5f7eb4e158abe85222d856e40afdab6ba8896341',
                'test_finalize_v9.py':'b9945afbb04709def69269ad818b29065df16d2f8ee092cec3eef581b0d10ede',
                'test_finalize_v9_v2.py':'cf6d2c17bebfde28da9628c960cf2e913c252158ab056e7357e827ec344be52d'}.items():
        raw=(TOOLS/n).read_bytes();assert sha(raw)==h;sources[n]=h
    def functions(n):
        return {v.name:ast.dump(v,include_attributes=False) for v in ast.parse((TOOLS/n).read_text()).body if isinstance(v,(ast.FunctionDef,ast.ClassDef))}
    oldf,newf=functions('finalize_v9.py'),functions('finalize_v9_v2.py')
    assert oldf.keys()==newf.keys()
    changed=sorted(k for k in oldf if oldf[k]!=newf[k]);assert changed==['Pins','run']
    for p,h in pins.items():assert sha(Path(p).read_bytes())==h
    result=dict(status='PASS_SOURCE_AND_METADATA_WHITELIST_CLOSURE_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                sources=sources,changed_ast_functions=changed,metadata_pins=pins,unique_metadata_count=len(parsed),
                external_readonly_pins=external,origins=origins,extensions=dict(Counter(Path(p).suffix for p in external)),
                external_payloads_read=0,finalizers_executed=0,source_sha256=sha(Path(__file__).read_bytes()))
    with (HERE/'QA.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(dict(status=result['status'],metadata_count=len(parsed),external_count=len(external),extensions=result['extensions'],qa_sha256=sha((HERE/'QA.json').read_bytes()))))

if __name__=='__main__':main()
