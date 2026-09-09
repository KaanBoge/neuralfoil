"""One bounded full-size wrapper gate, with fixed failure preservation."""
import io,json,time,unittest
import numpy as np
import fixtures,runner,replay_wrapper as w,support as s,test_producer,test_wrapper

FILES=('support.py','producer.py','runner.py','fixtures.py','test_producer.py','replay_wrapper.py','test_wrapper.py','verify_wrapper_synthetic.py')

def main():
    pins={name:s.digest((s.HERE/name).read_bytes()) for name in FILES}
    amendment='6994856bb7ee362c4db488f67324d40cebc8fcf23a0bd7573aec5a212fee54fc'
    metadata={'phase':'full_size_wrapper_synthetic_v3_only','actual_model_arrays_opened':False,'sources':pins,'checker_sha256':w.CHECKER_SHA,'amendment_sha256':amendment,'wrapper_cap_bytes':w.LIMIT,'original_failed_attempt_preserved':'wrapper_synthetic_attempt_1'}
    def work(out,ledger,outputs):
        for name,pin in pins.items():s.read_pinned(s.HERE/name,pin,ledger,'start_source_auth')
        s.read_pinned(s.HERE/'ROOT_MEMORY_AMENDMENT.md',amendment,ledger,'amendment_auth')
        s.read_pinned(s.HERE/'wrapper_synthetic_attempt_1/FAILURE.json','27f03e28a9932ad21aaad574438f363d44a0b9bc8557e1503c404c1d9af54f54',ledger,'original_failure_auth')
        stream=io.StringIO();suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (test_producer,test_wrapper))
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        outputs['TESTS.json']=s.exclusive(out/'TESTS.json',{'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'stdout':stream.getvalue()})
        if not result.wasSuccessful():raise ValueError('wrapper synthetic tests fail; stop')
        raw=s.read_pinned(s.HERE/'synthetic_attempt_1/certificate.json','ce8c2e1fade37918e169941fcaaf2acd63fb5f9e903cfef87c32d3709101ad60',ledger,'synthetic_certificate_bytes')
        arrays=fixtures.performance_arrays();buf=io.BytesIO();np.savez(buf,**arrays);del arrays
        cr=s.read_pinned(s.ROOT/w.CHECKER,w.CHECKER_SHA,ledger,'checker_source_bytes')
        pin='e9c94a3105ab4305c430ec8e3c14bfbc880eebe1df2cbef9ba15a5ac0dcf0a11'
        oracle=s.read_pinned(s.ROOT/w.ORACLE,pin,ledger,'oracle_source_bytes')
        start=time.monotonic()
        try:
            cert,replayed,plan=w.replay_buffers(raw,buf.getvalue(),cr,oracle,pin,ledger,outputs,out,s.digest(b'fixed-400x15-chain-fixture-v1'),start+120)
            elapsed=time.monotonic()-start
            if elapsed>120:raise TimeoutError('fixed wrapper120second gate')
            outputs['REPLAY.json']=s.exclusive(out/'REPLAY.json',replayed)
            return {'seconds':elapsed,'memory':plan,'status':'PASS_FULL_WRAPPER_GATE'}
        finally:
            for name,pin in pins.items():s.read_pinned(s.HERE/name,pin,ledger,'end_source_auth')
            s.read_pinned(s.ROOT/w.CHECKER,w.CHECKER_SHA,ledger,'end_checker_auth')
            s.read_pinned(s.HERE/'ROOT_MEMORY_AMENDMENT.md',amendment,ledger,'end_amendment_auth')
    print(json.dumps(runner.protected_attempt(s.HERE/'wrapper_synthetic_attempt_2_v3',metadata,work),sort_keys=True))

if __name__=='__main__':main()
