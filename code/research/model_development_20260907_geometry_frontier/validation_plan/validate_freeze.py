"""Fail-closed structural release checklist. Never reads experimental label files.

No network, fitting, writes, or automatic label release. JSON output to stdout.
Passing is not proof of truthful attestations, power, registration, or validity.
Never supply an unreviewed manifest: artifact content classes are attested,
not independently identified by this validator. No automatic label release.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,re,sys

UNRESOLVED={'','unknown','unresolved','todo','tbd','none','n/a','pending','draft'}
HEX=re.compile(r'^[0-9a-f]{64}$')
ALLOWED_ROLES={'model_weights','feature_code','inference_code','environment','protocol','analysis_code','cohort_metadata','identity_overlap','training_identity_inventory','candidate_predictions','baseline_predictions','exposure_attestation','license_evidence','timestamp_receipt','sample_size_justification'}
REQUIRED_ROLES=ALLOWED_ROLES-{'license_evidence'}


def validate(m):
    if not isinstance(m,dict):return {'status':'REFUSED_INVALID_MANIFEST','errors':['Manifest must be an object'],'designated_sealed_label_files_opened':False,'artifact_contents_classified_by_attestation':True}
    errors=[]
    def require(ok,msg):
        if not ok:errors.append(msg)
    def value(path):
        x=m
        for key in path.split('.'):
            if not isinstance(x,dict) or key not in x:return None
            x=x[key]
        return x
    def text(path):
        x=value(path);require(isinstance(x,str) and x.strip().lower() not in UNRESOLVED,path+' must be resolved text')
    require(m.get('schema')=='prospective_drag_freeze_v1','Unsupported schema')
    require(m.get('status')=='ready_for_custodian_review','Status must explicitly be ready_for_custodian_review')
    for path in ['claim','model.candidate_id','model.development_exposure_disclosure','cohort.population','cohort.cluster_unit','cohort.eligibility_rule','cohort.exclusion_and_failure_rule','cohort.independence_scope','custody.custodian','custody.candidate_selector','custody.independent_reviewer','custody.exposure_attestation','analysis.baseline_version','analysis.success_rule','analysis.cluster_resampling_method','analysis.multiplicity_plan','analysis.secondary_endpoints','analysis.sample_size_justification','freeze.external_timestamp_receipt']:
        text(path)
    for path in ['cohort.identity_overlap_resolved','cohort.measurement_republication_ruled_out','custody.role_separation','custody.labels_withheld','custody.sealed_label_path_not_permitted','analysis.sample_size_reviewed','freeze.protocol_review_approved','freeze.model_and_analysis_locked']:
        require(value(path) is True,path+' must be true')
    require(value('custody.developer_target_exposure')=='none_attested','Target exposure must be none_attested; known/uncertain exposure is not independent')
    require(value('custody.custodian')!=value('custody.candidate_selector'),'Custodian must be distinct from candidate selector')
    require(value('custody.independent_reviewer')!=value('custody.candidate_selector'),'Independent reviewer must be distinct from candidate selector')
    require(isinstance(value('custody.sealed_labels_sha256'),str) and bool(HEX.fullmatch(value('custody.sealed_labels_sha256') or '')),'Sealed label SHA256 commitment required, without a label path')
    require(value('analysis.primary_baseline')=='raw_neuralfoil_xlarge','Primary baseline must match this plan')
    require(value('analysis.secondary_baseline')=='native_mean8','Mean8 secondary comparison required')
    require(value('analysis.primary_metric')=='paired_point_weighted_CD_MAE_reduction','Primary metric must match this plan')
    for path in ['cohort.complete_rows','cohort.independent_units','analysis.bootstrap_draws','analysis.bootstrap_seed']:
        x=value(path);require(type(x) is int and x>0,path+' must be a positive integer')
    if type(value('cohort.complete_rows')) is int and type(value('cohort.independent_units')) is int:
        require(value('cohort.independent_units')<=value('cohort.complete_rows'),'Independent units cannot exceed complete rows')
    for path in ['analysis.minimum_useful_reduction_percent','analysis.maximum_group_harm_percent','analysis.row_equality_tolerance_CD']:
        x=value(path);require(type(x) in [int,float] and 0<=x<float('inf'),path+' must be finite nonnegative')
    conf=value('analysis.confidence_level');require(type(conf) in [float,int] and 0<conf<1,'Confidence level must be between zero and one')
    target=value('analysis.minimum_useful_reduction_percent')
    require(type(target) in [float,int] and target<=100,'MAE reduction target cannot exceed 100 percent')
    require(value('freeze.registration_status') in ['externally_registered','independently_timestamped_not_registered'],'Explicit external registration or independent timestamp status required')
    times=[]
    for path in ['freeze.protocol_frozen_utc','freeze.predictions_frozen_utc']:
        try:
            raw=value(path);t=datetime.fromisoformat(raw.replace('Z','+00:00'))
            require(t.tzinfo is not None,path+' must have timezone');require(t<=datetime.now(timezone.utc),path+' cannot be in the future');times.append(t)
        except (ValueError,TypeError,AttributeError):errors.append(path+' requires ISO8601 timezone date')
    if len(times)==2:require(times[0]<=times[1],'Protocol freeze must precede prediction freeze')
    licenses=m.get('licenses');require(isinstance(licenses,list) and bool(licenses),'At least one source-license record required')
    source_ids=value('cohort.source_ids')
    require(isinstance(source_ids,list) and bool(source_ids) and all(isinstance(v,str) and v.strip().lower() not in UNRESOLVED for v in source_ids),'Cohort source IDs must be resolved')
    licensed=[]
    if isinstance(licenses,list):
        for i,item in enumerate(licenses):
            require(isinstance(item,dict),f'License {i} must be object')
            if not isinstance(item,dict):continue
            licensed.append(item.get('source_id'))
            for k in ['source_id','terms_reference','access_basis','reproducibility_access_route']:
                x=item.get(k);require(isinstance(x,str) and x.strip().lower() not in UNRESOLVED,f'License {i}: {k} unresolved')
            require(item.get('analysis_permitted') is True,f'License {i}: analysis permission unresolved')
            require(item.get('redistribution_status') in ['permitted_with_recorded_conditions','not_permitted_no_raw_release'],f'License {i}: redistribution disposition unresolved')
    if isinstance(source_ids,list) and all(isinstance(v,str) for v in source_ids):
        require(len(set(source_ids))==len(source_ids),'Duplicate source IDs')
        require(all(licensed.count(v)==1 for v in source_ids),'Every cohort source requires exactly one license record')
    artifacts=m.get('public_artifacts');require(isinstance(artifacts,list) and bool(artifacts),'Public artifact inventory required')
    roles=set()
    if isinstance(artifacts,list):
        for i,a in enumerate(artifacts):
            if not isinstance(a,dict):errors.append(f'Artifact {i} must be object');continue
            role=a.get('role');require(role in ALLOWED_ROLES,f'Artifact {i}: unapproved role; never list sealed labels')
            if role not in ALLOWED_ROLES:continue
            roles.add(role)
            if a.get('contains_experimental_targets') is not False:
                errors.append(f'Artifact {i}: must explicitly attest no experimental targets; not opened');continue
            if a.get('approved_public_read') is not True:
                errors.append(f'Artifact {i}: public-read authorization missing; not opened');continue
            p=a.get('path');digest=a.get('sha256')
            if not isinstance(p,str) or not Path(p).is_absolute():errors.append(f'Artifact {i}: absolute path required');continue
            if not isinstance(digest,str) or not HEX.fullmatch(digest):errors.append(f'Artifact {i}: SHA256 required');continue
            if digest==value('custody.sealed_labels_sha256'):
                errors.append(f'Artifact {i}: declared digest is sealed-label commitment; not opened');continue
            if not Path(p).is_file():errors.append(f'Artifact {i}: file missing');continue
            require(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest,f'Artifact {i}: hash mismatch')
    require(REQUIRED_ROLES<=roles,'Missing required artifact roles: '+','.join(sorted(REQUIRED_ROLES-roles)))
    return {'status':'STRUCTURALLY_READY_FOR_CUSTODIAN_REVIEW' if not errors else 'REFUSED_UNRESOLVED_OR_INVALID','errors':errors,'designated_sealed_label_files_opened':False,'artifact_contents_classified_by_attestation':True,'caveat':'Never supply an unreviewed manifest. Public-file roles and target-free contents are attestations, not content detection. No proof of exposure history, licenses, external timestamp, power or statistical validity; no automatic label release.'}


if __name__=='__main__':
    try:
        result=validate(json.loads(Path(sys.argv[1]).read_text()))
    except (OSError,ValueError,IndexError) as e:result={'status':'REFUSED_INVALID_MANIFEST','errors':[str(e)],'designated_sealed_label_files_opened':False,'artifact_contents_classified_by_attestation':True}
    print(json.dumps(result,indent=2));sys.exit(0 if result['status']=='STRUCTURALLY_READY_FOR_CUSTODIAN_REVIEW' else 2)
