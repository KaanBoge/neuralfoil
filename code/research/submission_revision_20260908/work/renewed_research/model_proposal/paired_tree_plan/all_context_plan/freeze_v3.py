"""Preserve V2 and freeze the readiness-synchronized synthetic successor."""
import io,time,unittest
import adapter as a

OLD='db0ad0d57bb37b79d6b857a56b1845e152891e4d0b2b2369cb9882f5c5b55adf'
def main():
    ledger=[];old=a.json_read(a.HERE/'REGISTRY_v2.json',OLD,ledger)
    for name,pin in old['sources'].items():
        if name.endswith(('.py','.md')):a.read(a.HERE/'v2_snapshot'/name,pin,ledger,'exact V2 snapshot')
        else:a.read(a.HERE/name,pin,ledger,'unchanged V2 metadata')
    for name,pin in old['sources'].items():
        if name not in ['adapter.py','test_successor.py']:a.read(a.HERE/name,pin,ledger,'unchanged V2 source')
    before=(a.HERE/'v2_snapshot/adapter.py').read_bytes()
    if before.replace(b"REGISTRY_NAME='REGISTRY_v2.json'",b"REGISTRY_NAME='REGISTRY_v3.json'")!=(a.HERE/'adapter.py').read_bytes():raise ValueError('unexpected production change')
    review=a.ROOT/'uncertainty_review/range_bound_feasibility/PAIRED_ALL_CONTEXT_V2_REVIEW.md'
    reviewpin=a.sha(review.read_bytes());a.read(review,reviewpin,ledger,'preserved independent failure report')
    out=a.HERE/'synthetic_v3_attempt_1';out.mkdir(exist_ok=False)
    stream=io.StringIO();start=time.monotonic()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in ['test_adapter','test_context_numeric','test_successor'])
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    receipt={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'seconds':time.monotonic()-start,'stdout':stream.getvalue(),'actual_arrays':0,'independent_V2_failure_report_sha256':reviewpin}
    a.save(out/'RESULT.json',receipt)
    if not result.wasSuccessful():raise RuntimeError('preserved V3 test failure; no retry')
    reg=dict(old);reg['schema']='ALL_CONTEXT_SOURCE_REGISTRY_V3';reg['v2_registry_sha256']=OLD
    reg['sources']={name:a.sha((a.HERE/name).read_bytes()) for name in list(old['sources'])+['V3_HANDOFF.md','freeze_v3.py']}
    reg['synthetic_evidence']=dict(old['synthetic_evidence'],**{'synthetic_v3_attempt_1/RESULT.json':a.sha((out/'RESULT.json').read_bytes())})
    reg['independent_failure_report']={'path':str(review.relative_to(a.ROOT)),'sha256':reviewpin}
    reg['source_metadata_reads']=ledger
    print(a.save(a.HERE/a.REGISTRY_NAME,reg))

if __name__=='__main__':main()
