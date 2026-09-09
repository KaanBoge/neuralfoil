"""Measurement semantics isolated for synthetic tests; no automatic execution."""
import random,time
from serving import ROUTES,exact

def schedule():
    rng=random.Random(20260908);out=[]
    for repeat in range(7):
        routes=list(ROUTES);rng.shuffle(routes)
        out.extend((repeat,route) for route in routes)
    return out

def measured(request,route,expected,clock=time.perf_counter):
    start=clock();actual=request(route);elapsed=clock()-start
    # Includes parsing/features/tree/online Fraction interpolation, not checks.
    exact(actual,expected)
    return elapsed

def warm(request,references,emit,clock=time.perf_counter):
    # Every route passes untimed fidelity BEFORE the first measured request.
    for route in ROUTES:exact(request(route),references[route])
    for _ in range(2):
        for route in ROUTES:exact(request(route),references[route])
    for repeat,route in schedule():
        emit({'repeat':repeat,'route':route,'seconds':measured(request,route,references[route],clock),
              'output_rows':497,'scope':'warm full request; model/input bytes resident; geometry/features recomputed'})
