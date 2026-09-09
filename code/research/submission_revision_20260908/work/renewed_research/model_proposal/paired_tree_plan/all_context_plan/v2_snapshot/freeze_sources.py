"""Source/metadata-only freeze; never opens model or private archive arrays."""
import json
import adapter as a,study_inputs as si

FILES=('PROTOCOL_DRAFT.md','CONTEXTS.json','CONTEXT_METADATA_RECEIPT.json','IMPLEMENTATION_HANDOFF.md','adapter.py','certificates.py','study_inputs.py','study.py','prepare_contexts.py','test_adapter.py','verify_sources.py','test_context_numeric.py','verify_context_numeric.py','freeze_sources.py')

def main():
    ledger=[]
    sole=a.json_read(a.SOLE/'REGISTRY_v3.json',a.SOLE_REGISTRY_SHA,ledger)
    external={str((a.SOLE/name).relative_to(a.ROOT)):pin for name,pin in sole['sources'].items()}
    external.update(sole['dependencies'])
    external[str((a.SOLE/'REGISTRY_v3.json').relative_to(a.ROOT))]=a.SOLE_REGISTRY_SHA
    path=a.ROOT/'model_proposal/kl_bound_study/portable_plan/REGISTRY_v3.json'
    kl=a.json_read(path,'227aa87d058747052b09e5c907691e0c846697dfe2c61e85437f4e161f7095fd',ledger)
    for name in ['integrity.py','shared.py']:
        external['model_proposal/kl_bound_study/portable_plan/'+name]=kl['sources'][name]
    external['model_proposal/range_bound_feasibility/stage1_v2/portable_plan/fresh_extraction_v1/code/metrics.py']='f029c9e61e29a20b6232dd21f2b891b5e4a01c3351cf5c92e1a7518eaa1c1fb4'
    for name,pin in external.items():a.read(a.ROOT/name,pin,ledger,'source/metadata freeze')
    contexts=a.json_read(a.HERE/'CONTEXTS.json','186df022fe2d891488aaeb5cec5d650e34e2a4904f13faa4a1b64f38f55c8c9a',ledger)
    sources={name:a.sha((a.HERE/name).read_bytes()) for name in FILES}
    evidence={str(p.relative_to(a.HERE)):a.sha(p.read_bytes()) for folder in ['synthetic_attempt_1','synthetic_context_attempt_1'] for p in sorted((a.HERE/folder).iterdir())}
    reg={'schema':'ALL_CONTEXT_SOURCE_REGISTRY_V1','sources':sources,'external_sources':external,'contexts':contexts,
         'inputs':{'parent_archive':{'path':si.PARENT,'sha256':si.PARENT_SHA,'manifest_sha256':si.PARENT_MANIFEST},'KL_archive':{'path':si.ADDON,'sha256':si.ADDON_SHA,'manifest_sha256':si.ADDON_MANIFEST}},
         'final_inherited':{'producer_complete_sha256':a.FINAL_PRODUCER_SHA,'certificate_sha256':a.FINAL_CERT_SHA,'replay_complete_sha256':a.FINAL_REPLAY_SHA},
         'new_labels':si.LABELS,'bootstrap_references':si.REFS,'harm_reference_count':11,'new_scalar_count':32,'panel_record_count':589,'bootstrap_record_count':342,'harm_record_count':6479,
         'synthetic_evidence':evidence,'source_metadata_reads':ledger,'actual_array_materializations':0,'actual_phase_authorized':False}
    print(a.save(a.HERE/'REGISTRY.json',reg))

if __name__=='__main__':main()
