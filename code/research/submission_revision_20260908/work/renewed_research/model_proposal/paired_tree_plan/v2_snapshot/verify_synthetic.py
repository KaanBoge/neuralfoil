"""One fixed producer gate; exclusively preserves first synthetic attempt."""
import io,json,time,unittest,platform
from pathlib import Path
import fixtures,producer,runner,support as s,test_producer

def main():
    out=s.HERE/'synthetic_attempt_1'
    def work(path,ledger,outputs):
        stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromModule(test_producer)
        tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        outputs['TESTS.json']=s.exclusive(path/'TESTS.json',{'tests':tests.testsRun,'failures':len(tests.failures),'errors':len(tests.errors),'stdout':stream.getvalue()})
        if not tests.wasSuccessful():raise ValueError('synthetic tests failed; preserve and stop')
        a=fixtures.performance_arrays();deps=s.dependencies(ledger);b=s.Budget(120)
        start=time.monotonic()
        cert=producer.construct(a,deps,b,model_sha=s.digest(b'fixed-400x15-chain-fixture-v1'))
        if cert['counts']['attempted_pairs']!=90000 or any(cert['summary'][d]['feasible_pairs']!=45000 for d in ('D','R')):raise ValueError('fixed performance inventory')
        sha,n=runner.large_exclusive(path/'certificate.json',cert);outputs['certificate.json']=sha;outputs['certificate.json.partial']=sha
        elapsed=time.monotonic()-start;b.check()
        record={'producer_elapsed_seconds':elapsed,'gate_seconds':120,'estimated_owned_peak_bytes':b.peak,'memory_measure':'estimate NOT RSS','certificate_bytes':n,'counts':cert['counts'],'independent_checker_status':'pending separate independent implementation/run','python':platform.python_version()}
        outputs['PERFORMANCE.json']=s.exclusive(path/'PERFORMANCE.json',record)
        return record
    print(json.dumps(runner.protected_attempt(out,{'phase':'synthetic_only','real_arrays_opened':0},work),sort_keys=True))

if __name__=='__main__':main()
