"""Final source-only test/accounting evidence, exclusive output, preserve failures."""
import hashlib
import io
from pathlib import Path
import sys
import time
import traceback
import unittest
from test_producer import fixture,ORACLE,Q,CHECKER,RESEARCH
import engine
from runner import exclusive_json


def main():
    root=Path(__file__).resolve().parent;output=root/'FINAL_SYNTHETIC.json'
    if output.exists():raise FileExistsError(output)
    sys.path.insert(0,str(RESEARCH/'uncertainty_review/range_bound_feasibility'))
    sys.path.insert(0,str(RESEARCH/'feature_relation_certification'))
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames([
        'test_producer','test_runner','test_cache_v3','test_pilot_v2','test_prototype',
        'test_relation_checker','test_checker_additional'])
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    checks=0;minimum=None;error=None;receipt=None;start=time.perf_counter()
    def audit(new,original,*_):
        nonlocal checks,minimum
        if new<original:raise AssertionError('new estimate below full equivalent graph')
        checks+=1;delta=new-original;minimum=delta if minimum is None else min(minimum,delta)
    model=fixture(400);limits=engine.Limits(model.stages,audit=audit);states=[]
    try:
        state,reason=engine.refine(model.stages,0.,Q.sequential_range,limits,states.append,splits=1,oracle=ORACLE.feasible_witness)
        receipt=CHECKER.replay(state,model.stages,0.,Q.sequential_range,deadline=time.monotonic()+60)
    except BaseException:error=traceback.format_exc();reason='preserved_failure'
    names=('engine.py','domain.py','schema.py','runner.py','test_producer.py','test_runner.py','verify_final_synthetic.py')
    value={'status':'PASS_SOURCE_SYNTHETIC_ONLY' if result.wasSuccessful() and error is None else 'FAIL_PRESERVED',
        'tests':result.testsRun,'transcript':stream.getvalue(),'instrumented_checks':checks,
        'minimum_estimate_surplus_bytes':minimum,'large_fixture_nodes_visited':limits.visits,
        'large_fixture_oracle_calls':limits.oracle_calls,'large_fixture_reason':reason,
        'large_fixture_seconds_unprofiled_with_audit':time.perf_counter()-start,
        'large_fixture_checker':receipt,'failure':error,'actual_model_arrays_opened':False,
        'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}}
    if value['status']!='PASS_SOURCE_SYNTHETIC_ONLY':value['failed_source_snapshot']={n:(root/n).read_text() for n in names}
    exclusive_json(output,value);print({k:value[k] for k in ('status','tests','instrumented_checks','minimum_estimate_surplus_bytes','large_fixture_seconds_unprofiled_with_audit')})


if __name__=='__main__':main()
