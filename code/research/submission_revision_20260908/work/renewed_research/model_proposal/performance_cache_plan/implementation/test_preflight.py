"""Manufactured data only; never loads model, geometry archive or real arrays."""
import sys,unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from test_request_local import OLD,math_module,Asb,Foil,workload
sys.path.insert(0,str(OLD.parent))
import preflight as p

class Tests(unittest.TestCase):
    def test_binary_equality_includes_signed_zero_shape_dtype(self):
        p.same({'x':np.array([1.])},{'x':np.array([1.])})
        for x,y in [(np.array([0.]),np.array([-0.])),(np.array([1.]),np.array([1.],dtype='f4')),(np.array([1.]),np.array([[1.]]))]:
            with self.assertRaises(ValueError):p.same(x,y)
    def test_independent_fit_and_response_checks(self):
        f=math_module();asb=Asb(f.SIZES);w=workload()
        result=p.audit_geometry_block(f,asb,f.load_pts(w['coordinates']['test']),w['alpha'],w['Re'])
        self.assertEqual(result['complete_response_comparisons'],2)
        self.assertEqual(asb.fits,4);self.assertEqual(len(asb.calls),25)
    def test_unmodeled_response_field_difference_rejected(self):
        f=math_module();asb=Asb(f.SIZES);w=workload();old=Foil.get_aero_from_neuralfoil
        def changed(foil,*args,**kwargs):
            out=old(foil,*args,**kwargs)
            if foil.name=='external_evaluation':out['extra_unquantized']=out['extra_unquantized']+1
            return out
        with patch.object(Foil,'get_aero_from_neuralfoil',changed):
            with self.assertRaisesRegex(ValueError,'extra_unquantized'):p.audit_geometry_block(f,asb,f.load_pts(w['coordinates']['test']),w['alpha'],w['Re'])
    def test_parameter_mutation_rejected(self):
        f=math_module();asb=Asb(f.SIZES);w=workload();old=Foil.get_aero_from_neuralfoil
        def changed(foil,*args,**kwargs):
            out=old(foil,*args,**kwargs);foil.kulfan_parameters['TE_thickness']+=1;return out
        with patch.object(Foil,'get_aero_from_neuralfoil',changed):
            with self.assertRaisesRegex(ValueError,'foil mutation'):p.audit_geometry_block(f,asb,f.load_pts(w['coordinates']['test']),w['alpha'],w['Re'])
    def test_missing_route_rejected_before_calls(self):
        with self.assertRaisesRegex(ValueError,'all frozen V6 routes'):p.preflight(None,None,{},None)
    def full_services(self):
        class Service:
            def __init__(self):
                self.workload={};self.f=SimpleNamespace(load_pts=lambda text:np.zeros((2,2)));self.asb=None;self.corrupt=False
                for c,n in zip(p.COHORTS,[242,255]):
                    gate=np.ones(n,dtype=bool)
                    if n==255:gate[:25]=False
                    self.workload[c]={'alpha':np.zeros(n),'Re':np.full(n,1e5),'airfoil':np.array(['a']*(n//2)+['b']*(n-n//2)),'coordinates':{'a':'a','b':'b'},'gate':gate}
            def request(self,route,diagnostics=False):
                out={c+'/CD':np.ones(len(w['alpha'])) for c,w in self.workload.items()}
                if diagnostics:
                    for c,w in self.workload.items():
                        out[c+'/BASE_CD']=np.ones(len(w['alpha']));out[c+'/X62']=np.zeros((len(w['alpha']),62))
                    if self.corrupt:out[p.COHORTS[0]+'/X62'][0,0]=1
                return out
        a=Service();b=Service();refs={r:a.request(r) for r in p.ROUTES};return a,b,refs
    def test_full_mock_barrier_and_diagnostic_rejection(self):
        a,b,refs=self.full_services()
        with patch.object(p.frozen_measurement,'preflight',return_value=(refs,{'retained':'archive differences'})),patch.object(p,'audit_geometry_block',return_value={}):
            out=p.preflight(a,b,refs,{})
            self.assertEqual(out['routes'],7);self.assertEqual(out['archive_inventory'],{'retained':'archive differences'})
            b.corrupt=True
            with self.assertRaisesRegex(ValueError,'X62'):p.preflight(a,b,refs,{})
    def test_frozen_reference_not_adopted_from_optimized(self):
        a,b,refs=self.full_services();wrong={r:{k:v.copy() for k,v in d.items()} for r,d in refs.items()};wrong[p.ROUTES[0]][p.COHORTS[0]+'/CD'][0]=2
        with patch.object(p.frozen_measurement,'preflight',return_value=(refs,{})):
            with self.assertRaisesRegex(ValueError,'unchanged original versus frozen V6'):p.preflight(a,b,wrong,{})

if __name__=='__main__':unittest.main()
