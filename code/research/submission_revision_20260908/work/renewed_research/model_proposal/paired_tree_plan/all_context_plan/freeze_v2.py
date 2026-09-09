"""Metadata/source-only successor freezer; no scientific array materialization."""
import ast,json,unittest,io,time
import adapter as a

OLD='07bbe24cb82430619a490f32a07a406232b910999fae86e7bf7170062aa25f49'
FILES=['adapter.py','certificates.py','study.py','test_adapter.py']
def main():
    ledger=[];old=a.json_read(a.HERE/'REGISTRY.json',OLD,ledger)
    snapshots={}
    for name,pin in old['sources'].items():
        if name.endswith(('.py','.md')):
            a.read(a.HERE/'v1_snapshot'/name,pin,ledger,'preserved V1 exact source')
            snapshots[name]=pin
    for name,pin in old['external_sources'].items():a.read(a.ROOT/name,pin,ledger,'unchanged external source')
    changes={name:{'v1':old['sources'][name],'v2':a.sha((a.HERE/name).read_bytes())} for name in FILES}
    def bodies(path):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_bytes()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    before=bodies(a.HERE/'v1_snapshot/study.py');after=bodies(a.HERE/'study.py')
    scientific=['preflight','calibrate','score','assess','scalar_match','exact_key_parity']
    if any(before[n]!=after[n] for n in scientific):raise ValueError('scientific AST changed')
    out=a.HERE/'synthetic_v2_attempt_1';out.mkdir(exist_ok=False)
    stream=io.StringIO();start=time.monotonic()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in ['test_adapter','test_context_numeric','test_successor'])
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    evidence={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'seconds':time.monotonic()-start,'stdout':stream.getvalue(),'actual_arrays':0}
    a.save(out/'RESULT.json',evidence)
    if not result.wasSuccessful():raise RuntimeError('preserved synthetic failure')
    delta={'v1_registry_sha256':OLD,'preserved_sources':snapshots,'changes':changes,'scientific_AST_unchanged':scientific,'original_JSON_and_test_receipts_retained_in_place':True}
    a.save(a.HERE/'V2_SOURCE_DIFF.json',delta)
    reg=dict(old);reg['schema']='ALL_CONTEXT_SOURCE_REGISTRY_V2'
    names=list(old['sources'])+['test_successor.py','V2_HANDOFF.md','freeze_v2.py','V2_SOURCE_DIFF.json']
    reg['sources']={name:a.sha((a.HERE/name).read_bytes()) for name in names}
    reg['v1_registry_sha256']=OLD;reg['synthetic_evidence']=dict(old['synthetic_evidence'],**{'synthetic_v2_attempt_1/RESULT.json':a.sha((out/'RESULT.json').read_bytes())})
    reg['source_metadata_reads']=ledger;reg['storage_child_caps']=a.CHILD_CAPS
    print(a.save(a.HERE/a.REGISTRY_NAME,reg))

if __name__=='__main__':main()
