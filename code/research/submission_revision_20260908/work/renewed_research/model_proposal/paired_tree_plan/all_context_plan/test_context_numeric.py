"""Two synthetic model identities through unchanged producer/checker bodies."""
import unittest
import adapter as a

class Tests(unittest.TestCase):
    def test_two_explicit_identities(self):
        ledger=[]
        with a.sole_modules(ledger) as (ms,reg):
            specs={'context_synthetic_fixture':(a.SOLE/'fixtures.py',reg['sources']['fixtures.py']),
                   'context_independent_checker':(a.ROOT/'uncertainty_review/range_bound_feasibility/paired_checker.py','33e04358f4ac925b79f5022880c128bd6b0e55016c8e45262e2db8a5ea4bf30b')}
            with a.modules(specs,ledger) as more:
                arrays=more['context_synthetic_fixture'].small_arrays()
                for identity in ['synthetic_context_a','synthetic_context_b']:
                    pin=a.sha(identity.encode())
                    cert=ms['producer'].construct(arrays,ms['support'].dependencies(ledger),ms['support'].Budget(),model_sha=pin)
                    checked=more['context_independent_checker'].check(cert,arrays,expected_model_sha=pin)
                    self.assertEqual(checked['model_sha256'],pin)
                    with self.assertRaises(ValueError):more['context_independent_checker'].check(cert,arrays,expected_model_sha=a.sha(b'wrong-context'))

if __name__=='__main__':unittest.main()
