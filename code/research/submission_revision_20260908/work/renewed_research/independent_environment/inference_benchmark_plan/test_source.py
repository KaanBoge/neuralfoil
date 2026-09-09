"""Synthetic only: no project/model/input array reads or real forward calls."""
import io,json,tempfile,unittest
from pathlib import Path
from fractions import Fraction
from unittest.mock import patch
import numpy as np
import serving,timing,loader,runner

class Tests(unittest.TestCase):
    def test_exact_rejects_single_ulp(self):
        with self.assertRaises(ValueError):serving.exact({'a':np.array([1.])},{'a':np.nextafter(np.array([1.]),2.)})
    def test_exact_rejects_dtype_shape_keys(self):
        for b in [{'a':np.array([1],int)},{'a':np.array([[1.]])},{'b':np.array([1.])}]:
            with self.assertRaises(ValueError):serving.exact({'a':np.array([1.])},b)
    def test_schedule_fixed_balanced(self):
        a=timing.schedule();self.assertEqual(a,timing.schedule());self.assertEqual(len(a),49)
        for k in serving.ROUTES:self.assertEqual(sum(k==v for _,v in a),7)
    def test_fidelity_failure_precedes_timer(self):
        ref={k:{'a':np.array([1.])} for k in serving.ROUTES}
        def clock():raise AssertionError('timer reached')
        with self.assertRaises(ValueError):timing.warm(lambda k:{'a':np.array([2.])},ref,lambda x:None,clock)
    def test_online_fraction_inside_timer_check_outside(self):
        order=[]
        def clock():order.append('clock');return float(len(order))
        def request(k):order.append('online_fraction');v=Fraction(1,3)+Fraction(1,7);return {'a':np.array([float(v)])}
        def check(a,b):order.append('fidelity')
        with patch.object(timing,'exact',check):timing.measured(request,'x',{},clock)
        self.assertEqual(order,['clock','online_fraction','clock','fidelity'])
    def test_numerical_arrays_allowlist_no_other_member(self):
        b=io.BytesIO();np.savez(b,allowed=np.array([1.]),forbidden=np.array([object()],object))
        self.assertEqual(list(loader.arrays(b.getvalue(),['allowed'])),['allowed'])
        with self.assertRaises(ValueError):loader.arrays(b.getvalue(),['forbidden'])
    def test_paths(self):
        for n in ['../x','/x','a\\b','a:b','a//b','']:
            with self.assertRaises(ValueError):loader.safe_name(n)
    def test_exclusive_writer(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json';runner.write(p,{'x':1})
            with self.assertRaises(FileExistsError):runner.write(p,{'x':2})
            self.assertEqual(json.loads(p.read_text()),{'x':1})
    def test_authenticate_failure_before_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_bytes(b'synthetic')
            with self.assertRaises(ValueError):loader.authenticate(d,{'files':{'x':'0'*64},'archives':{}})
    def test_original_label_explicit(self):
        class Original:
            def predict(self,x,b,a,g,label):
                assert label=='unpenalized_transfer';return b.copy(),np.zeros(len(b))
        w={c:{'alpha':np.array([0.]),'gate':np.array([False])} for c in serving.COHORTS}
        s=serving.Serving(None,None,Original(),None,None,None,{},w)
        s.features=lambda w:{'X62':np.zeros((1,62)),'BASE_CD':np.ones(1),'all_model_CD':np.ones((1,8))}
        v=s.request(serving.ROUTES[2]);self.assertEqual(len(v),4)
        for c in serving.COHORTS:np.testing.assert_array_equal(v[c+'/CD'],[1.])
    def test_no_confidence_fit_invoked_online(self):
        class Q:
            def guarded_core(self,b,r,g):return b*1.1,b*1.05,g
        class Policy:
            def predictions(self,s,b,c,h,g):return np.where(g,h,b),np.zeros(len(b))
        class Model:
            def predict_raw(self,x):return np.zeros(len(x))
        w={c:{'alpha':np.array([0.]),'gate':np.array([False])} for c in serving.COHORTS}
        s=serving.Serving(None,None,None,Model(),Policy(),Q(),{k:{'t':.1} for k in serving.QUALIFIED},w)
        s.features=lambda w:{'X62':np.zeros((1,62)),'BASE_CD':np.ones(1),'all_model_CD':np.ones((1,8))}
        for label in serving.QUALIFIED:
            for c in serving.COHORTS:np.testing.assert_array_equal(s.request(label)[c+'/CD'],[1.])
    def test_unknown_route(self):
        s=serving.Serving(*([None]*8))
        with self.assertRaises(ValueError):s.request('default')

if __name__=='__main__':unittest.main()
