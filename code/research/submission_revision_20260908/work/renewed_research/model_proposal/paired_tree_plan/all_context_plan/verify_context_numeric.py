import io,unittest
import adapter as a,test_context_numeric

def main():
    def work(out,ledger,outputs,deadline):
        stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_context_numeric))
        outputs['TESTS.json']=a.save(out/'TESTS.json',{'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'stdout':stream.getvalue()})
        if not r.wasSuccessful():raise ValueError('synthetic context identity test failed')
        return {'two_synthetic_context_identities_verified':True,'actual_arrays_opened':0}
    pins={p.name:a.sha(p.read_bytes()) for p in a.HERE.glob('*.py')}
    print(a.attempt(a.HERE/'synthetic_context_attempt_1',{'phase':'additional_synthetic_context_test','sources':pins},work)['status'])

if __name__=='__main__':main()
