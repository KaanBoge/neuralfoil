"""Metadata/source freeze only; never opens archive arrays or computes losses."""
import json
from pathlib import Path
from inputs import sha,ZIP_SHA,MANIFEST_SHA
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
EXTERNAL={
 'kl_confidence_production/confidence.py':'03c41a6aa79f44bd04fe374953c560db029d2f4a98f8cd1de552ed35657d9ad9',
 'kl_confidence_production/PROTOCOL_DRAFT.md':'c3217169f84bd0bbef536e1c64f6ac1fffb0fd39b6ba20bbec366487e05b0f5f',
 'kl_confidence_production/test_confidence.py':'9d63003db58c64e28fb9b1732901d38733c65bf5ac05d614067fc2e2a6d3e9ab',
 'kl_confidence_design/exact_kl.py':'115003c1d6e8a64fc68168f1d0ab3c002e7ff5709589f08e91aa753f450844ae',
 'model_proposal/range_bound_feasibility/stage1_v2/numerics.py':'b1edf2540b1ce23f46ea882e1d049e82969709a5191c1e9e7191ca9331f5d179',
 'model_proposal/range_bound_feasibility/stage1_v2/run_stage1.py':'5cb5c4897209465f2526099aae094ddce0fc72b50446f071e955520d97568ec1',
 'model_proposal/range_bound_feasibility/qualified_numerics.py':'76f886759182be1e12dd371c270fc1bbb599911b01f92fb9e383cdacc6273c4a'}
def main():
    external={}
    for name,h in EXTERNAL.items():
        p=ROOT/name
        if sha(p.read_bytes())!=h:raise ValueError('external source pin')
        external[str(p)]=h
    names=['inputs.py','run_experiment.py','test_study.py','freeze_sources.py','IMPLEMENTATION_PLAN.md','PROTOCOL_ADDENDUM.md','SYNTHETIC_RESULTS.md']
    record={'status':'SOURCE_ONLY_AWAITING_REVIEW_AND_PHASE_APPROVALS',
        'source_sha256':{n:sha((HERE/n).read_bytes()) for n in names},'external_source_sha256':external,
        'archive_sha256':ZIP_SHA,'manifest_sha256':MANIFEST_SHA,
        'real_KL_phases_executed':False,'new_core_fits':0,'assessment_route':'authenticated exact typed portable preassessment frame only',
        'score_CSVs':'17 outcome-free prediction CSVs; targets materialized only in assessment',
        'source_only_synthetic_tests':21}
    raw=json.dumps(record,indent=2).encode()+b'\n'
    with (HERE/'IMPLEMENTATION_FREEZE.json').open('xb') as f:f.write(raw)
    print(sha(raw))
if __name__=='__main__':main()
