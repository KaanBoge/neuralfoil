"""Synthetic schema tests only. No real test data or release authorization."""
from pathlib import Path
import copy,hashlib,json
from validate_freeze import validate,REQUIRED_ROLES


def main():
    root=Path(__file__).resolve().parent
    draft=json.loads((root/'freeze_manifest.template.json').read_text())
    assert validate(draft)['status'].startswith('REFUSED')
    assert validate([])['status'].startswith('REFUSED')
    m=copy.deepcopy(draft);m['status']='ready_for_custodian_review';m['claim']='SYNTHETIC TEST ONLY'
    m['model'].update(candidate_id='synthetic',development_exposure_disclosure='synthetic test fixture')
    m['cohort'].update(population='synthetic',source_ids=['synthetic'],complete_rows=100,independent_units=20,cluster_unit='synthetic independent runs',eligibility_rule='fixed synthetic rule',exclusion_and_failure_rule='retain all with frozen fallback',identity_overlap_resolved=True,independence_scope='synthetic',measurement_republication_ruled_out=True)
    m['custody'].update(custodian='synthetic custodian',candidate_selector='synthetic developer',independent_reviewer='synthetic reviewer',role_separation=True,developer_target_exposure='none_attested',exposure_attestation='synthetic test only',sealed_labels_sha256='0'*64)
    m['analysis'].update(baseline_version='synthetic pinned version',minimum_useful_reduction_percent=1.,maximum_group_harm_percent=2.,success_rule='synthetic fixed rule',cluster_resampling_method='paired independent-unit bootstrap',bootstrap_draws=20000,bootstrap_seed=123,confidence_level=.95,multiplicity_plan='single synthetic primary',secondary_endpoints='all retained',sample_size_justification='synthetic placeholder ONLY FOR UNIT TEST',sample_size_reviewed=True,row_equality_tolerance_CD=1e-12)
    m['freeze'].update(protocol_frozen_utc='2020-01-01T00:00:00Z',predictions_frozen_utc='2020-01-02T00:00:00Z',external_timestamp_receipt='synthetic receipt',registration_status='independently_timestamped_not_registered',protocol_review_approved=True,model_and_analysis_locked=True)
    m['licenses']=[dict(source_id='synthetic',terms_reference='synthetic',access_basis='synthetic',reproducibility_access_route='synthetic',analysis_permitted=True,redistribution_status='not_permitted_no_raw_release')]
    # Reuse this public source file to test hashing, not semantic file contents.
    p=Path(__file__).resolve();digest=hashlib.sha256(p.read_bytes()).hexdigest()
    m['public_artifacts']=[dict(role=r,path=str(p),sha256=digest,contains_experimental_targets=False,approved_public_read=True) for r in REQUIRED_ROLES]
    assert validate(m)['status']=='STRUCTURALLY_READY_FOR_CUSTODIAN_REVIEW'
    failures=[('cohort','identity_overlap_resolved',False),('cohort','measurement_republication_ruled_out',False),('custody','developer_target_exposure','already_viewed'),('custody','labels_withheld',False),('analysis','sample_size_reviewed',False),('analysis','maximum_group_harm_percent',float('nan')),('analysis','primary_baseline','postselected'),('freeze','model_and_analysis_locked',False),('freeze','predictions_frozen_utc','2019-01-01T00:00:00Z'),('freeze','external_timestamp_receipt','unresolved')]
    for group,key,value in failures:
        bad=copy.deepcopy(m);bad[group][key]=value;assert validate(bad)['status'].startswith('REFUSED'),(group,key)
    bad=copy.deepcopy(m);bad['licenses']=[];assert validate(bad)['status'].startswith('REFUSED')
    bad=copy.deepcopy(m);bad['public_artifacts'][0]['sha256']='1'*64;assert validate(bad)['status'].startswith('REFUSED')
    bad=copy.deepcopy(m);bad['public_artifacts'][0].update(path='/never-open-sealed-labels.csv',contains_experimental_targets=True)
    result=validate(bad);assert result['status'].startswith('REFUSED') and any('not opened' in s for s in result['errors'])
    bad=copy.deepcopy(m);bad['analysis']['minimum_useful_reduction_percent']=100.1;assert validate(bad)['status'].startswith('REFUSED')
    bad=copy.deepcopy(m);bad['public_artifacts'][0].update(path='/never-open-sealed-commitment.csv',sha256=bad['custody']['sealed_labels_sha256'])
    result=validate(bad);assert result['status'].startswith('REFUSED') and any('sealed-label commitment; not opened' in s for s in result['errors'])
    print(json.dumps({'status':'PASS','synthetic_acceptance':1,'refusal_cases':17,'real_manifest_ready':False,'no_new_experimental_data_used_by_these_synthetic_tests':True}))


if __name__=='__main__':main()
