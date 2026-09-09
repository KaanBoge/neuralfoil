"""Two prespecified synthetic fixtures, cProfile enabled; no actual model files."""
import cProfile
import hashlib
import io
import json
from pathlib import Path
import pstats
import time
import traceback
from test_producer import fixture,relation_fixture,ORACLE,Q,CHECKER
import engine
from runner import exclusive_json


def main():
    root=Path(__file__).resolve().parent
    output=root/'FIXED_PROFILES.json'
    if output.exists():raise FileExistsError(output)
    results=[]
    for name,model in [('original400x15',fixture(400)),('relation400x3',relation_fixture(400))]:
        limits=engine.Limits(model.stages,seconds=60);profile=cProfile.Profile();published=[];last=[]
        def publish(s):
            published.append({'splits':s['splits'],'product_boxes':s['product_boxes'],'r_empty_boxes':s['r_empty_boxes']})
            last[:]=[s]
        start=time.perf_counter();failure=None;profile.enable()
        try:state,reason=engine.refine(model.stages,0.,Q.sequential_range,limits,publish,splits=1,oracle=ORACLE.feasible_witness)
        except BaseException:failure=traceback.format_exc();reason='preserved_exception'
        finally:profile.disable()
        seconds=time.perf_counter()-start
        stream=io.StringIO();stats=pstats.Stats(profile,stream=stream).sort_stats('cumulative');stats.print_stats(25)
        receipt=None;checker_failure=None;checkstart=time.perf_counter()
        if last:
            try:receipt=CHECKER.replay(last[0],model.stages,0.,Q.sequential_range,deadline=time.monotonic()+60)
            except BaseException:checker_failure=traceback.format_exc()
        results.append({'fixture':name,'profile_enabled':True,'accounting_audit_enabled':False,
            'seconds':seconds,'stop':reason,'failure':failure,'published':published,'node_visits':limits.visits,
            'oracle_calls':limits.oracle_calls,'infeasible_queries':limits.infeasible_queries,
            'peak_algorithm_owned_estimate':limits.peak_estimate,'profile':stream.getvalue(),
            'checker':receipt,'checker_failure':checker_failure,'checker_seconds':time.perf_counter()-checkstart,
            'last_checkpoint':last[0] if last else None})
        print(name,seconds,reason,limits.visits,flush=True)
    exclusive_json(output,{'status':'SYNTHETIC_PROFILES_ONLY','results':results,'actual_model_arrays_opened':False,
        'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('engine.py','domain.py','schema.py','test_producer.py','profile_fixed.py')}})


if __name__=='__main__':main()
