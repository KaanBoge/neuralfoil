"""Only source and manufactured/mock values. No real input materialization."""
from pathlib import Path
import ast,copy,sys,types,unittest,json
from unittest.mock import patch
H=Path(__file__).resolve().parent;B=H.parents[3]/'independent_environment/inference_benchmark_plan'
sys.path[:0]=[str(H.parent),str(B)]
import runner_cache as runner
import loader_cache as loader
import preflight_cache as barrier
import prepare_registry as prepare
import test_preflight as earlier
import numpy as np

class Tests(unittest.TestCase):
    def test_loader_separates_complete_workload(self):
        a,b,refs=earlier.Tests().full_services()
        for k in ['original','qualified','policy','q']:setattr(a,k,None)
        a.scalars={}
        with patch.object(loader.loader_v5,'load',return_value=(a,refs,{},object(),{})):
            opt,*_=loader.load('synthetic',{})
        opt.workload[barrier.COHORTS[0]]['coordinates']['a']='changed'
        opt.workload[barrier.COHORTS[0]]['alpha'][0]=1
        self.assertEqual(a.workload[barrier.COHORTS[0]]['coordinates']['a'],'a')
        self.assertEqual(a.workload[barrier.COHORTS[0]]['alpha'][0],0)
    def test_nested_mutation_during_inherited_preflight_rejected(self):
        a,b,refs=earlier.Tests().full_services()
        def corrupt(*unused):a.workload[barrier.COHORTS[0]]['coordinates']['a']='mutated';return refs,{}
        with patch.object(barrier.frozen_measurement,'preflight',side_effect=corrupt),patch.object(barrier,'audit_geometry_block',return_value={}):
            with self.assertRaisesRegex(ValueError,'complete caller workload mutation'):barrier.preflight(a,b,refs,{})
    def test_fixed_reference_members_pass_through_only(self):
        registry={'v6_reference_files':{'route':{'path':'old.npz','members':['SG/CD']}}};calls=[]
        class Access:
            def file(self,path):calls.append(('file',path));return b'fake'
            def arrays(self,b,path,keys):calls.append(('arrays',b,path,keys));return {'SG/CD':np.ones(2)}
        result=loader.references(registry,Access())
        self.assertEqual(list(result),['route']);self.assertEqual(calls,[('file','old.npz'),('arrays',b'fake','old.npz',['SG/CD'])])
    def test_native_legacy_auth_is_metadata_only(self):
        calls=[];loader.authenticate_legacy({'legacy_metadata_paths':['old_registry.json'],'v6_receipts':{'unrelated_reference.npz':'hash'}},types.SimpleNamespace(file=lambda p:calls.append(p)))
        self.assertEqual(calls,['old_registry.json'])
    def test_scoped_source_buffer_execution_and_restoration(self):
        names=['provenance_v2','serving','timing','oracle_v5','loader_v5','measurement_v5','watchdog_v6','response_snapshot','feature_adapter','serving_optimized','preflight','loader_cache']
        files=[n+'.py' for n in names];files[-2]='preflight_cache.py'
        sources={f:b'VALUE=42\n' for f in files};r={'source_paths':{f:f for f in files}}
        before={n:sys.modules.get(n) for n in names}
        saved,events=runner.execute_sources(sources,r)
        self.assertEqual(len(events),12)
        for n in names:self.assertEqual(sys.modules[n].VALUE,42)
        runner.restore(saved)
        for n in names:self.assertIs(sys.modules.get(n),before[n])
        sources['preflight_cache.py']=b'raise ValueError("synthetic")'
        with self.assertRaisesRegex(ValueError,'synthetic'):runner.execute_sources(sources,r)
        for n in names:self.assertIs(sys.modules.get(n),before[n])
    def test_child_identity_and_positive_self_peak(self):
        r={'reference_contract':'original','optimization_contract':'cache','max_rss_bytes':100}
        c={'status':'PASS','phase':'cold','route':'r','predecessor_sha256':'p','approval_sha256':'a','registry_sha256':'g','reference_contract':'original','optimization_contract':'cache','self_ru_maxrss_bytes':50,'ru_maxrss_units':'bytes on explicitly required macOS'}
        runner.validate_child_receipt(c,'cold','r','p','a','g',r)
        for value in [0,-1,float('nan'),float('inf'),101]:
            with self.assertRaises(ValueError):runner.validate_child_receipt(dict(c,self_ru_maxrss_bytes=value),'cold','r','p','a','g',r)
        with self.assertRaises(ValueError):runner.validate_child_receipt(dict(c,optimization_contract='other'),'cold','r','p','a','g',r)
    def test_preflight_phase_alarm_not_reset_by_requests(self):
        source=(H/'runner_cache.py').read_text()
        self.assertLess(source.index("if args.phase=='preflight':signal.alarm"),source.index('saved,events=execute_sources'))
        section=source[source.index("        if args.phase=='preflight':"):source.index("        else:\n            routes=")]
        self.assertIn('serv.request=original',section)
        self.assertNotIn('signal.alarm(',section)
        self.assertIn('values=old_references(r,access)',section)
        self.assertIn('full_preflight(original_service,serv,values,refs)',section)
    def test_monitor_is_unchanged_import_not_reimplementation(self):
        text=(H/'runner_cache.py').read_text();self.assertIn('from watchdog_v6 import monitor,budget',text)
        # Timed measurement and warm loops are still the original functions.
        self.assertIn('from measurement_v5 import measured,warm',text)
        self.assertIn('elapsed=measured(serv,route,references[route])',text)
        self.assertIn('counts=warm(serv,references,emit)',text)
    def test_registry_build_uses_metadata_without_opening_reference(self):
        routes=['native_a','native_b','original'];scopes={r:{'files':{},'archives':{},'arrays':{}} for r in ['all',*routes]}
        old={'sources':{},'routes':routes,'scopes':scopes,'workload_rows':{'SG_exposed':242,'W_new_challenge':255},'max_seconds':600}
        encoded=lambda x:json.dumps(x).encode()
        rb=encoded(old);rh=prepare.sha(rb);ab=encoded({'registry_sha256':rh});ah=prepare.sha(ab)
        outputs={'reference_'+r+'.npz':'synthetic_digest_'+r for r in routes}
        pb=encoded({'status':'PASS','registry_sha256':rh,'approval_sha256':ah,'outputs':outputs});ph=prepare.sha(pb)
        cb=encoded({'status':'COMPLETE_REQUIRES_INDEPENDENT_REVIEW','registry_sha256':rh,'approval_sha256':ah,'preflight_sha256':ph,'outputs':outputs})
        raw={'REGISTRY_v6.json':rb,'ROOT_ACTUAL_APPROVAL_V6.json':ab,'actual_v6_attempt_1/preflight_COMPLETE.json':pb,'actual_v6_attempt_1/COMPLETE.json':cb};opened=[]
        def read(path):
            opened.append(path)
            if path.suffix=='.npz':raise AssertionError('source-only preparation opened array')
            return raw.get(str(path.relative_to(prepare.B)) if path.is_relative_to(prepare.B) else '',b'# synthetic source')
        with patch.object(prepare,'PINS',{k:prepare.sha(v) for k,v in raw.items()}),patch.object(prepare,'read',side_effect=read):d=prepare.build()
        self.assertEqual(d['max_seconds'],600)
        self.assertEqual(len(d['v6_reference_files']),3)
        for r in routes:self.assertFalse(any(n.endswith('.npz') for n in d['scopes'][r]['files']))
        self.assertEqual(len(d['scopes']['all']['arrays']),3)

if __name__=='__main__':unittest.main()
