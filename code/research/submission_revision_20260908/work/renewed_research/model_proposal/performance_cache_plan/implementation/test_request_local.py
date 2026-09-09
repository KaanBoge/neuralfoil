"""Source-only tests with manufactured arrays and counted mock foil calls."""
from pathlib import Path
import ast,gc,hashlib,types,unittest,weakref
import numpy as np
import feature_adapter as a
import serving_optimized as s
from response_snapshot import ResponseSnapshot

PROJECT=next(p for p in Path(__file__).parents if p.name=='NeuralFoil_Research_Paper')
F=PROJECT/'submission_revision_20260908/work/feature_reproduction/addon/feature_math.py'
OLD=PROJECT/'submission_revision_20260908/work/renewed_research/independent_environment/inference_benchmark_plan/serving.py'
def math_module():
    m=types.ModuleType('synthetic_frozen_math');exec(compile(F.read_bytes(),str(F),'exec'),m.__dict__);return m
class Foil:
    def __init__(self,owner,name,coordinates):
        self.owner=owner;self.name=name
        self.kulfan_parameters={'upper_weights':np.arange(8.)+coordinates[0,1],'lower_weights':np.arange(8.),'leading_edge_weight':.1,'TE_thickness':.001}
    def get_aero_from_neuralfoil(self,alpha,Re,mach,n_crit,model_size,xtr_upper=1.,xtr_lower=1.):
        alpha=np.asarray(alpha);re=np.asarray(Re)
        self.owner.calls.append((model_size,n_crit,alpha.copy(),re.copy(),xtr_upper,xtr_lower))
        v=.01+alpha*.0001+self.owner.sizes.index(model_size)*.00001+n_crit*.0000012345
        return {'CD':v,'CL':v*3.123456,'CM':v*.2,'Top_Xtr':v*4,'Bot_Xtr':v*5,'analysis_confidence':v*6,'extra_unquantized':v*7.123456789}
class Asb:
    def __init__(self,sizes):self.sizes=sizes;self.calls=[];self.fits=0;self.live=[]
    def Airfoil(self,name,coordinates):
        owner=self
        class Shape:
            def to_kulfan_airfoil(self):
                owner.fits+=1;f=Foil(owner,name,coordinates);owner.live.append(weakref.ref(f));return f
        return Shape()
def workload():return {'alpha':np.array([0.,2.]),'Re':np.array([1e5,2e5]),'airfoil':np.array(['test','test']),'gate':np.array([True,False]),'coordinates':{'test':'synthetic\n1 0\n.5 .1\n0 0\n.5 -.1\n1 0'}}
def service():
    f=math_module();asb=Asb(f.SIZES);return s.Serving(f,asb,None,None,None,None,{},{}),asb
class Tests(unittest.TestCase):
    def test_counts_order_batch_and_lifetime(self):
        serv,asb=service();w=workload();old={k:v.copy() for k,v in w.items() if isinstance(v,np.ndarray)}
        d=serv.features(w)
        self.assertEqual(asb.fits,1);self.assertEqual(len(asb.calls),12)
        self.assertEqual([(x[0],x[1]) for x in asb.calls],[('xlarge',n) for n in [5,7,9,11,13]]+[(n,9) for n in serv.f.SIZES if n!='xlarge'])
        for row in asb.calls:np.testing.assert_array_equal(row[2],w['alpha']);np.testing.assert_array_equal(row[3],w['Re'])
        for k,v in old.items():np.testing.assert_array_equal(w[k],v)
        self.assertEqual(d['X62'].shape,(2,62));gc.collect();self.assertTrue(all(r() is None for r in asb.live))
    def test_no_cross_request_hit_changed_input(self):
        serv,asb=service();w=workload();first=serv.features(w)
        w['alpha']=w['alpha']+1;second=serv.features(w)
        self.assertEqual((asb.fits,len(asb.calls)),(2,24));self.assertFalse(np.array_equal(first['BASE_CD'],second['BASE_CD']))
        w['coordinates']['test']=w['coordinates']['test'].replace('.5 .1','.5 .2');serv.features(w)
        self.assertEqual((asb.fits,len(asb.calls)),(3,36))
    def test_native_routes_unchanged_counts(self):
        for mean,count in [(False,1),(True,8)]:
            serv,asb=service();serv.native(workload(),mean)
            self.assertEqual(asb.fits,1);self.assertEqual(len(asb.calls),count)
    def test_snapshot_copies_full_response_and_mutations(self):
        src={'CD':np.array([.0123456789]),'extra':{'a':np.array([2.])},'tuple':(np.array([3.]),),'list':[4.]}
        saved=ResponseSnapshot(src);src['CD'][0]=99;one=saved.copy();one['CD'][0]=88;one['extra']['a'][0]=77
        self.assertEqual(saved.copy()['CD'][0],.0123456789);self.assertEqual(saved.copy()['extra']['a'][0],2.)
        self.assertEqual(saved.copy()['tuple'][0][0],3.);self.assertIsInstance(saved.copy()['list'],list)
    def test_full_unquantized_reuse_and_no_extra_call(self):
        f=math_module();asb=Asb(f.SIZES);coords=f.load_pts(workload()['coordinates']['test']);foil=asb.Airfoil('x',coords).to_kulfan_airfoil();w=workload()
        mats,saved=a.calc_with_foil(coords,w['alpha'],w['Re'],foil,f)
        raw=saved.copy();self.assertIn('extra_unquantized',raw);self.assertFalse(np.array_equal(raw['CD'],mats['CD'][:,2]))
        base=a.predict_base_with_foil(coords,w['alpha'],w['Re'],foil,saved,f)
        np.testing.assert_array_equal(base['XLARGE_CD'],mats['CD'][:,2]);self.assertEqual(len(asb.calls),12)
        np.testing.assert_array_equal(saved.copy()['CD'],raw['CD'])
    def test_helper_ast_only_approved_injections(self):
        old=ast.parse(F.read_text());new=ast.parse(Path(a.__file__).read_text())
        for old_name,new_name in [('calc','calc_with_foil'),('predict_base','predict_base_with_foil')]:
            x=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==old_name)
            y=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==new_name)
            # Compare literal source after exact, declared injections are reversed.
            actual=ast.get_source_segment(Path(a.__file__).read_text(),y)
            if old_name=='calc':
                actual=actual.replace('def calc_with_foil(coordinates, alpha, reynolds, foil, math):','def calc(coordinates, alpha, reynolds):')
                actual=actual.replace('    GRID=math.GRID;FIELDS=math.FIELDS;retained=None\n','    import aerosandbox as asb\n    foil = asb.Airfoil(name="transition_sensitivity", coordinates=coordinates).to_kulfan_airfoil()\n')
                actual=actual.replace('        if ncrit==9:retained=ResponseSnapshot(results)\n','').replace('    if retained is None:raise ValueError("missing fixed ncrit9 response")\n    return matrices,retained','    return matrices')
            else:
                actual=actual.replace('def predict_base_with_foil(coordinates, alpha, re, foil, retained, math):','def predict_base(coordinates, alpha, re):')
                actual=actual.replace('    SIZES=math.SIZES;foil_stats2=math.foil_stats2\n','    import aerosandbox as asb\n    foil = asb.Airfoil(name="external_evaluation", coordinates=coordinates).to_kulfan_airfoil()\n').replace('retained.copy() if size=="xlarge" else ','')
            self.assertEqual(ast.dump(ast.parse(actual).body[0]),ast.dump(x))
    def test_native_and_request_ast_identical(self):
        old=next(n for n in ast.parse(OLD.read_text()).body if isinstance(n,ast.ClassDef))
        new=next(n for n in ast.parse(Path(s.__file__).read_text()).body if isinstance(n,ast.ClassDef))
        for name in ['__init__','native','request']:
            self.assertEqual(ast.dump(next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)),ast.dump(next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)))
    def test_no_module_cache(self):
        self.assertEqual(ResponseSnapshot.__slots__,('_payload',))
        for module in [a,s]:self.assertFalse(any(isinstance(v,ResponseSnapshot) for v in vars(module).values()))

if __name__=='__main__':unittest.main()
