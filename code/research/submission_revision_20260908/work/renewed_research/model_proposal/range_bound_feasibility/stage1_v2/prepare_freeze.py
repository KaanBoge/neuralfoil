"""Freeze source/metadata identities only. Never reads NPZ, CSV, or models."""
from pathlib import Path
import hashlib
import json
import run_stage1 as r


def main():
    # Only manifest/QA JSON is read here; no Inputs(), evaluator or scalar call.
    a=r.json_checked(r.A/'results/freeze.json',r.PINS['a_freeze'])
    qa=r.json_checked(r.A/'DELIVERY_QA.json',r.PINS['a_qa'])
    complete_path=r.A/'results/complete.json'
    complete_hash=qa['source_and_result_sha256'][str(complete_path)]
    complete=r.json_checked(complete_path,complete_hash)
    if complete['freeze_sha256']!=r.PINS['a_freeze']:raise ValueError('metadata chain')
    tree=r.json_checked(r.BUNDLE/'manifest.json',r.PINS['trees'])
    expected={**a['artifact_sha256'],**complete['output_sha256']}
    files={}
    for context in a['contexts']:
        for name in [f'membership_{context}.json',f'calibration_{context}.npz',f'inference_{context}.npz']:
            p=r.A/'results'/name;files[str(p)]=expected[str(p)]
        if context!='final':
            p=r.A/'results'/f'predictions_{context}.csv';files[str(p)]=expected[str(p)]
    for context in r.EXTERNAL:
        for suffix in ['_inference.npz','_predictions.csv']:
            p=r.A/'exposed_results'/(context+suffix);files[str(p)]=expected[str(p)]
    for row in tree['trees']:
        if row['branch']=='proper':
            files[str(r.BUNDLE/row['capped'])]=tree['files'][row['capped']]
    record={'status':'PRE_EXECUTION_METADATA_IDENTITIES_ONLY','real_feature_arrays_read':False,
        'outcome_arrays_or_csv_read':False,'expected_input_sha256':files,
        'metadata_sha256':{str(r.A/'results/freeze.json'):r.PINS['a_freeze'],str(r.A/'DELIVERY_QA.json'):r.PINS['a_qa'],
                           str(complete_path):complete_hash,str(r.BUNDLE/'manifest.json'):r.PINS['trees']},
        'certificate_sha256':r.PINS['certificate'],
        'legacy_assessment_report_sha256':'1c34134f311695a54a9c91c0ffa19699c7ce826eb1c8f50e671336f263cce9ff'}
    r.write_json(r.HERE/'INPUT_MANIFEST.json',record)
    names=['PROTOCOL.md','INPUT_MANIFEST.json','numerics.py','evaluator.py','run_stage1.py',
           'assess_stage1.py','test_stage1.py','test_serialization.py','prepare_freeze.py','TEST_RESULTS.md',
           'SERIALIZATION_ADDENDUM.md','verify_source_delta.py','SOURCE_DELTA.json']
    r.write_json(r.HERE/'IMPLEMENTATION_FREEZE.json',{'status':'IMPLEMENTATION_ONLY_AWAITING_EXECUTION_APPROVAL',
        'source_sha256':{name:r.sha((r.HERE/name).read_bytes()) for name in names},
        'protocol_draft_sha256':r.sha((r.HERE.parent/'STAGE1_PROTOCOL_DRAFT.md').read_bytes()),
        'stage0_numerics_sha256':r.n.PIN,'production_AST':{'groups':r.n.GROUP_AST,'confidence':r.n.CONFIDENCE_AST},
        'phases_executed':[]})
    print(r.sha((r.HERE/'IMPLEMENTATION_FREEZE.json').read_bytes()))

if __name__=='__main__':main()
