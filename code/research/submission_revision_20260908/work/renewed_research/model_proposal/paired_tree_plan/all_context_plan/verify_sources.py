"""Exclusive first synthetic test receipt; no real study execution."""
import io,unittest
import adapter as a,test_adapter

def main():
    pins={p.name:a.sha(p.read_bytes()) for p in a.HERE.glob('*.py')}
    def work(out,ledger,outputs,deadline):
        for name,pin in pins.items():a.read(a.HERE/name,pin,ledger,'start synthetic source authentication')
        stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_adapter))
        outputs['TESTS.json']=a.save(out/'TESTS.json',{'tests':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'stdout':stream.getvalue()})
        for name,pin in pins.items():a.read(a.HERE/name,pin,ledger,'end synthetic source authentication')
        if not r.wasSuccessful():raise ValueError('synthetic failure; preserve first attempt')
        return {'tests':r.testsRun,'actual_arrays_opened':0,'synthetic_bootstrap_old238_new342_exact_key_parity':True}
    print(a.attempt(a.HERE/'synthetic_attempt_1',{'phase':'source_synthetic_only','sources':pins},work)['status'])

if __name__=='__main__':main()
