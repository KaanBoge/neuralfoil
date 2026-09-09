"""One synthetic-only V2 performance profile, no real array loading."""
import cProfile
import io
from pathlib import Path
import pstats
import sys
import time
import traceback
import numpy as np

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from pilot_adapter import authenticate,sha
from pilot_runner_v2 import exclusive_json
from pilot_engine_v2 import Limits,refine
from test_pilot_v2 import DT,E,Q,arrays


def main():
    authenticate(ROOT/'PILOT_REGISTRY_V2.json','5f20c0b93fe3a7ab682a0f7ea64cedb4dad67c14ff22804dcf2a715df81cc22a')
    trees=[]
    for k in range(400):
        tree=np.zeros(15,dtype=DT)
        for j in range(15):
            if j>=7:
                tree[j]['is_leaf']=1
                tree[j]['value']=((k+j)%17-8)/1024.
            else:
                depth=(j+1).bit_length()-1
                tree[j]['feature_idx']=(k+depth)%62
                tree[j]['num_threshold']=(j%3-1)/2.
                tree[j]['left']=2*j+1;tree[j]['right']=2*j+2
        trees.append(tree)
    model=E.SequentialHist(arrays(trees),required_stages=400)
    limits=Limits(model.stages,seconds=60)
    profiler=cProfile.Profile()
    published=[];start=time.perf_counter();failure=None
    profiler.enable()
    try:
        state,reason=refine(model.stages,model.initial,Q.sequential_range,limits,
                            lambda x:published.append({'splits':x['splits'],'boxes':len(x['frontier'])}),splits=1)
    except BaseException:
        failure=traceback.format_exc();reason='preserved_exception'
    finally:profiler.disable()
    elapsed=time.perf_counter()-start
    stream=io.StringIO();stats=pstats.Stats(profiler,stream=stream).sort_stats('cumulative');stats.print_stats(30)
    functions=[]
    for (file,line,name),(cc,nc,tt,ct,callers) in stats.stats.items():
        if name in ('owned_size','check','bound','sequential_range','directed','partition'):
            functions.append({'file':file,'line':line,'name':name,'primitive_calls':cc,'calls':nc,'self_seconds':tt,'cumulative_seconds':ct})
    out={'fixture':'400 deterministic15-node synthetic trees; one attempted split','elapsed_seconds':elapsed,
         'profiler_overhead_included':True,'stop_reason':reason,'failure':failure,'published':published,
         'node_visits':limits.visits,'peak_algorithm_owned_estimate_bytes':limits.peak_estimate,
         'functions':functions,'profile':stream.getvalue(),'real_arrays_opened':False,
         'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__).resolve(),ROOT/'pilot_engine_v2.py',ROOT/'PILOT_REGISTRY_V2.json')}}
    exclusive_json(Path(__file__).resolve().parent/'PROFILE_RESULT.json',out)
    print(stream.getvalue());print({'elapsed':elapsed,'stop':reason,'visits':limits.visits})


if __name__=='__main__':main()
