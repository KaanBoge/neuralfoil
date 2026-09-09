"""Frozen-scope synthetic validation including every-check 400-tree comparison."""
import io
import platform
from pathlib import Path
import sys
import time
import unittest
from test_cache_v3 import fixture,new,Q
from pilot_adapter import authenticate,sha
from pilot_runner_v2 import exclusive_json


def main():
    root=Path(__file__).resolve().parent
    authenticate(root.parent/'PILOT_REGISTRY_V2.json','5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a')
    out=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromNames(['test_cache_v3','test_pilot_v2','test_prototype'])
    result=unittest.TextTestRunner(stream=out,verbosity=2).run(suite)
    if not result.wasSuccessful():raise AssertionError(out.getvalue())
    checks=0;minimum_margin=None
    def audit(estimate,reference,*_):
        nonlocal checks,minimum_margin
        if estimate<reference:raise AssertionError('weaker than unchanged V2 equivalent graph')
        checks+=1;delta=estimate-reference
        minimum_margin=delta if minimum_margin is None else min(minimum_margin,delta)
    model=fixture(400);limits=new.Limits(model.stages,audit=audit)
    checkpoints=[];start=time.perf_counter()
    state,reason=new.refine(model.stages,model.initial,Q.sequential_range,limits,checkpoints.append,splits=1)
    large_seconds=time.perf_counter()-start
    exclusive_json(root/'SYNTHETIC_V3_WITNESS.json',{
        'status':'PASS_SYNTHETIC_ONLY','tests':result.testsRun,'transcript':out.getvalue(),
        'python':sys.version,'platform':platform.platform(),'large_fixture_trees':400,
        'large_fixture_nodes_per_tree':15,'instrumented_checks':checks,
        'minimum_new_minus_V2_estimate_bytes':minimum_margin,'large_fixture_visits':limits.visits,
        'large_fixture_stop':reason,'large_fixture_seconds_unprofiled_with_audit':large_seconds,
        'large_fixture_splits':state['splits'],'real_model_arrays_opened':False,
        'source_sha256':{p.name:sha(p) for p in [root/'engine_v3.py',root/'cache_v3.py',root/'test_cache_v3.py',Path(__file__).resolve()]}})
    print({'tests':result.testsRun,'instrumented_checks':checks,'minimum_margin':minimum_margin,'seconds':large_seconds})


if __name__=='__main__':main()
