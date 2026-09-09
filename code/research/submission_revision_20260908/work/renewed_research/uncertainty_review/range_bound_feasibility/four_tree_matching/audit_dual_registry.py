"""Metadata/source-byte audit only: no imports of scientific modules or arrays."""
from pathlib import Path
import hashlib,json,ast
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
P=ROOT/'model_proposal/four_tree_matching_plan'
EXPECTED_P='6bdc54d1097e45da552831e52548fe80a38d245e58b9baf399ab0efd48eb59bc'
EXPECTED_C='2620c070f12bb945df6e35063fa347aa7dad39e07f852f5ce39dcce7b6198b26'
ledger=[]
def read(path,pin):
    if any(x.is_symlink() for x in (path,*path.parents)) or path.suffix not in {'.json','.py','.md'} or path.stat().st_size>2**20:raise ValueError('bounded source/metadata path')
    raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
    assert actual==pin,(path,actual,pin)
    ledger.append({'path':str(path.relative_to(ROOT)),'sha256':pin,'bytes':len(raw)})
    return raw
def main():
    out=HERE/'DUAL_REGISTRY_QA.json'
    if out.exists():raise FileExistsError('preserve audit')
    p=json.loads(read(P/'REGISTRY_SOURCE_V1.json',EXPECTED_P));c=json.loads(read(HERE/'CHECKER_SOURCE_REGISTRY_V1.json',EXPECTED_C))
    assert set(p)=={'schema','actual_execution_authorized','cold_gate_executed','model_sha256','sources','predecessors','checker_sources'}
    assert p['schema']=='FOUR_TREE_SOURCE_REGISTRY_V1' and p['actual_execution_authorized'] is False and p['cold_gate_executed'] is False
    assert set(c)=={'schema','model_sha256','sources','producer_registry_sha256'} and c['schema']=='FOUR_TREE_CHECKER_SOURCE_REGISTRY_V1'
    assert c['producer_registry_sha256']==EXPECTED_P and c['model_sha256']==p['model_sha256']
    assert c['sources']==p['checker_sources'] and set(c['sources'])=={'checker','entry','primitive','io'}
    assert len(p['sources'])==15 and len(p['predecessors'])==8
    for name,pin in p['sources'].items():
        assert Path(name).name==name
        read(P/name,pin)
    refs={}
    for role,entry in p['predecessors'].items():refs[role]=json.loads(read(ROOT/entry['path'],entry['sha256']))
    source={}
    for role,entry in p['checker_sources'].items():source[role]=read(ROOT/entry['path'],entry['sha256'])
    for entry in c['sources'].values():read(ROOT/entry['path'],entry['sha256'])
    assert refs['adjacent_complete']['outputs']['REPLAY.json']==p['predecessors']['adjacent_replay']['sha256']
    assert refs['adjacent_replay_approval']['producer_complete_sha256']==p['predecessors']['adjacent_producer_complete']['sha256']
    assert refs['adjacent_replay_approval']['certificate_sha256']==refs['adjacent_producer_complete']['outputs']['certificate.json']
    for key,app in [('adjacent_complete','adjacent_replay_approval'),('adjacent_producer_complete','adjacent_producer_approval')]:
        assert refs[key]['approval_sha256']==p['predecessors'][app]['sha256'] and refs[key]['model_sha256']==p['model_sha256']
        assert refs[key]['registry_sha256']==p['predecessors']['adjacent_registry']['sha256'] and refs[app]['real_execution_authorized'] is True
    tree=ast.parse(source['entry']);f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='reauthenticate')
    assert not any(isinstance(x,ast.Attribute) and x.attr in {'read_bytes','pinned'} for x in ast.walk(f))
    assert any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='read' for x in ast.walk(f))
    read(HERE/'ROOT_SOURCE_REVIEW.md','474376621e01f530793baab0541f41a088dc5f4c006033ffc0760ec50a1a1058')
    result={'status':'PASS_SOURCE_METADATA_ONLY','producer_registry_sha256':EXPECTED_P,'checker_registry_sha256':EXPECTED_C,'producer_total_pins':27,'producer_local_source_pins':15,'shared_checker_source_pins':4,'predecessor_pins':8,'checker_registry_repeated_pins':4,'ledger':ledger,'scientific_module_executions':0,'array_materializations':0,'cold_gate_runs':0,'clearance':'Separate fixed synthetic cold-gate approval may be considered; no actual model clearance.'}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps({'status':result['status'],'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'pin_checks':len(ledger)}))
if __name__=='__main__':main()
