"""Preserved source successor; metadata/source reads only, no model NPZ."""
import ast,json
import support as s
import replay_wrapper as w

OLD=('PLAN.md','SCHEMA.md','support.py','producer.py','runner.py','fixtures.py','test_producer.py','verify_synthetic.py','freeze_sources.py','IMPLEMENTATION.md')
NEW=('replay_wrapper.py','test_wrapper.py','verify_wrapper_synthetic.py','WRAPPER_SUCCESSOR.md','freeze_sources_v2.py')

def main():
    oldraw=(s.HERE/'REGISTRY.json').read_bytes()
    if s.digest(oldraw)!='63575af74d960eb8e3cbb2f999700db9643e6a2d1c5c5bb719af27e36410fd8c':raise ValueError('original registry changed')
    old=json.loads(oldraw);delta={}
    for name in OLD:
        before=(s.HERE/'v1_snapshot'/name).read_bytes();after=(s.HERE/name).read_bytes()
        if s.digest(before)!=old['sources'][name]:raise ValueError('V1 snapshot identity '+name)
        delta[name]={'before_sha256':s.digest(before),'after_sha256':s.digest(after),'byte_identical':before==after}
        if name!='runner.py' and before!=after:raise ValueError('unexpected old source change')
    # Retain exact scientific-function ASTs in the only modified old module.
    def bodies(raw):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
    a=bodies((s.HERE/'v1_snapshot/runner.py').read_bytes());b=bodies((s.HERE/'runner.py').read_bytes())
    unchanged=('large_exclusive','load_arrays','check_approval','authenticate','same_stage0','utc')
    if any(a[k]!=b[k] for k in unchanged):raise ValueError('unexpected inherited function AST change')
    diff={'original_registry_sha256':s.digest(oldraw),'sources':delta,'unchanged_runner_function_AST':list(unchanged),'changed_runner_functions':['protected_attempt','execute'],'added_runner_functions':['named_manifest'],'pair_math_producer_byte_identical':delta['producer.py']['byte_identical']}
    diffsha=s.exclusive(s.HERE/'SOURCE_DIFF_v2.json',diff)
    deps=dict(old['dependencies']);deps[w.CHECKER]=w.CHECKER_SHA
    # Historical review reports are still pinned; current independent test file
    # is a reviewed probe-only successor, recorded separately by its owner.
    test='uncertainty_review/range_bound_feasibility/test_paired_checker.py'
    deps[test]=s.digest((s.ROOT/test).read_bytes())
    ledger=[]
    for rel,pin in deps.items():s.read_pinned(s.ROOT/rel,pin,ledger,'source_or_metadata_freeze')
    sources={name:s.digest((s.HERE/name).read_bytes()) for name in OLD+NEW}
    sources['SOURCE_DIFF_v2.json']=diffsha
    evidence={str(p.relative_to(s.HERE)):s.digest(p.read_bytes()) for p in sorted((s.HERE/'wrapper_synthetic_attempt_1').iterdir())}
    reg={'schema':'PAIRED_TREE_SOURCE_REGISTRY_V2','sources':sources,'dependencies':deps,'input':old['input'],'scope':old['scope'],'original_registry_sha256':s.digest(oldraw),'wrapper_synthetic_evidence':evidence,'synthetic_wrapper_gate':'FAILED_CONSERVATIVE_MEMORY_BUDGET','real_execution_authorized':False,'model_members_materialized_by_freezer':0,'read_ledger':ledger}
    print(s.exclusive(s.HERE/'REGISTRY_v2.json',reg))

if __name__=='__main__':main()
