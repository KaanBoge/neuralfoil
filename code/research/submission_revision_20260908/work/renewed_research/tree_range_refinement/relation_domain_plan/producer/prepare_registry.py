"""Finite source/model metadata freeze. No actual model array reads."""
import copy
import os
from pathlib import Path
from runner import adapter,exclusive_json
from domain import stamp


def main():
    root=Path(__file__).resolve().parent;tree=root.parents[1];research=tree.parent
    r,oldroot=adapter.authenticate(tree/'performance_diagnosis/PILOT_REGISTRY_V3.json','a989ed3215fd933650c49d15644219e678e59e001affa141091fdabb02eba2a5')
    out=copy.deepcopy(r)
    out.update(successor='restricted R producer; distinct actual approval required',domain=stamp(),entrypoint='runner.py')
    out['input']['path']=os.path.relpath(oldroot/r['input']['path'],root)
    out['sources']={k:{'path':os.path.relpath(oldroot/v['path'],root),'sha256':v['sha256']} for k,v in r['sources'].items()}
    dependencies={
      'root_exact_oracle':(research/'feature_relation_certification/exact_oracle.py','35fa867b21c5beed6521f5238560561e18eb0e55a20f443ab4a8c60d91374712'),
      'root_relation_guard':(research/'feature_relation_certification/relations.py','1f175bdfe40e0e13451963bb4752e2d5903592f0f92c07246038c96e1b8c0127'),
      'relation_checker':(research/'uncertainty_review/range_bound_feasibility/relation_checker.py','3fd1c9f810cd1562875ec2153ea81796c8456a2445287af8c6db40a142b0e8a8'),
      'independent_relation_oracle':(tree/'feature_relation_oracle_review/oracle.py','e9c94a3105ab4305c430ec8e3c14bfbc880eebe1df2cbef9ba15a5ac0dcf0a11'),
      'independent_checker_tests':(research/'uncertainty_review/range_bound_feasibility/test_relation_checker.py','d039ba3d5e3152b0f2e3ba18c9803b6307f8b42902d4a6e0bedbfcd40ece3a3f')}
    for key,(path,pin) in dependencies.items():
        if adapter.sha(path)!=pin:raise ValueError('dependency mutation: '+key)
        out['sources'][key]={'path':os.path.relpath(path,root),'sha256':pin}
    other=[research/'feature_relation_certification/test_checker_additional.py',tree/'relation_domain_plan/INTEGRATION_PROTOCOL.md',tree/'feature_relation_oracle_review/PLAN_AND_PROOF.md']
    for path in other+[root/n for n in ('engine.py','domain.py','schema.py','runner.py','test_producer.py','test_runner.py',
          'verify_tests.py','verify_tests_2.py','verify_final_synthetic.py','profile_fixed.py','TEST_ATTEMPT_1.json',
          'TEST_ATTEMPT_2.json','FIRST_TEST_FAILURE.md','FIXED_PROFILES.json','FINAL_SYNTHETIC.json',
          'IMPLEMENTATION_REPORT.md','SOURCE_CHANGES.diff','prepare_registry.py')]:
        out['sources']['R/'+path.name]={'path':os.path.relpath(path,root),'sha256':adapter.sha(path)}
    exclusive_json(root/'R_PILOT_REGISTRY.json',out)
    print({'registry_sha256':adapter.sha(root/'R_PILOT_REGISTRY.json'),'sources':len(out['sources']),'actual_model_arrays_opened':False})


if __name__=='__main__':main()
