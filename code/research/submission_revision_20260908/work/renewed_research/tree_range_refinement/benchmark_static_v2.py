"""Fixed 400-stump accounting microbenchmark; no real input files."""
from pathlib import Path
import time
from pilot_engine import Limits as Original
from pilot_engine_v2 import Limits as Cached
from pilot_runner_v2 import exclusive_json
from pilot_adapter import sha
from test_pilot_v2 import stump


def main():
    stages=tuple(stump() for _ in range(400))
    for t in stages:t.setflags(write=False)
    results=[]
    for cls in (Original,Cached):
        timings=[]
        for _ in range(5):
            limits=cls(stages,seconds=120)
            start=time.perf_counter()
            for _ in range(2000):limits.check((),visit=True)
            timings.append(time.perf_counter()-start)
        results.append({'implementation':cls.__module__,'seconds_five_repeats':timings,
                        'peak_estimate':limits.peak_estimate})
    if results[1]['peak_estimate']<results[0]['peak_estimate']:
        raise AssertionError('weaker accounting')
    exclusive_json(Path('STATIC_ACCOUNTING_V2_BENCHMARK.json'),{
        'trees':400,'nodes_per_tree':3,'checks_per_repeat':2000,'results':results,
        'source_sha256':{s:sha(s) for s in ('pilot_engine.py','pilot_engine_v2.py',__file__)},
        'real_model_arrays_opened':False,
        'scope':'Accounting microbenchmark only; not prediction/search or actual-model runtime estimate.'})
    print(results)


if __name__=='__main__':main()
