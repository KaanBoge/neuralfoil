"""Source/metadata-only freeze. Never opens an NPZ or runs a producer/gate."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
MODEL_SHA='ff9c030097f307be0b30627e79f05daf8da7c7176b5621039ff2e3485a9cf327'
SOURCES=['producer.py','fixtures.py','run.py','io_support.py','cold_gate.py','test_producer.py','test_wrapper.py','test_accounting.py','test_cold_gate.py','prepare_source_freeze.py','SCHEMA.md','PROTOCOL.md','MEMORY_PLAN.md','COLD_GATE_PLAN.md','TEST_RESULTS.md']
CHECKER_SOURCES={'checker':'uncertainty_review/range_bound_feasibility/four_tree_matching/checker.py','entry':'uncertainty_review/range_bound_feasibility/four_tree_matching/replay.py','primitive':'uncertainty_review/range_bound_feasibility/paired_checker.py','io':'model_proposal/four_tree_matching_plan/io_support.py'}
PREDS={'manifest':'independent_environment/bounds_extraction/manifest.json','stage0':'model_proposal/range_bound_feasibility/STAGE0_CERTIFICATE.json','adjacent_replay':'model_proposal/paired_tree_plan/actual_replay_attempt_1/REPLAY.json','adjacent_complete':'model_proposal/paired_tree_plan/actual_replay_attempt_1/COMPLETE.json','adjacent_producer_complete':'model_proposal/paired_tree_plan/actual_producer_attempt_1/COMPLETE.json','adjacent_producer_approval':'model_proposal/paired_tree_plan/ROOT_ACTUAL_PRODUCER_APPROVAL.json','adjacent_replay_approval':'model_proposal/paired_tree_plan/ROOT_ACTUAL_REPLAY_APPROVAL.json','adjacent_registry':'model_proposal/paired_tree_plan/REGISTRY_v3.json'}
EXPECTED={'manifest':'210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea','stage0':'8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782','adjacent_replay':'d4c47766c41c61814049ab42c973efdca621e0aade8dcf0b4087d74bbbe4827b','adjacent_complete':'02b122ad8fb24243815bd8b016c41d91cf83f45c3f1c72f32c80a18d7102079a','adjacent_producer_complete':'dce7280d67453cf120001a412d05ba6cbde4c33c05c4a0b65284ae359ddc433c','adjacent_registry':'7c53d7c0385d9df5222e901ec9a7b971b72c96ea72301a3d5e398089600061a2'}
def sha(path):
    if path.is_symlink() or any(x.is_symlink() for x in path.parents) or path.suffix!='.json' and path.parent!=HERE and path not in [ROOT/v for v in CHECKER_SOURCES.values()]:raise ValueError('metadata/source scope')
    if path.stat().st_size>2**20:raise ValueError('source/metadata byte cap')
    return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    out=HERE/'REGISTRY_SOURCE_V1.json'
    if out.exists():raise FileExistsError('preserve source freeze')
    deps={k:{'path':v,'sha256':sha(ROOT/v)} for k,v in PREDS.items()}
    for k,v in EXPECTED.items():
        if deps[k]['sha256']!=v:raise ValueError('expected inherited pin '+k)
    r={'schema':'FOUR_TREE_SOURCE_REGISTRY_V1','actual_execution_authorized':False,'cold_gate_executed':False,'model_sha256':MODEL_SHA,'sources':{n:sha(HERE/n) for n in SOURCES},'predecessors':deps,'checker_sources':{k:{'path':v,'sha256':sha(ROOT/v)} for k,v in CHECKER_SOURCES.items()}}
    with out.open('x') as f:json.dump(r,f,sort_keys=True,indent=2)
    print(json.dumps({'registry_sha256':sha(out),'source_pins':len(SOURCES),'metadata_pins':len(deps),'model_materializations':0,'cold_gate_runs':0}))
if __name__=='__main__':main()
