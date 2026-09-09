"""Prepare a finite, externally pinnable inventory after final V7 technical QA.

No archive assembly, scientific execution, publication, or author approval.
"""
from pathlib import Path
import argparse
import hashlib
import json

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
PROJECT=BASE.parent
RESEARCH=BASE/'work/renewed_research'
V3=BASE/'deliverables/NeuralFoil_Private_Submission_Package_v3/MANIFEST.json'
V3_PIN='3efaf78fe936c6a5fb59cf5163442feb1121bc2d8bbc499f0feea666d78d73f6'
FIGURES=['method_roles','accuracy_harm','calibration_utility','external_complete_eligible','measurement_label_sensitivity']
ARCHIVES={
    'reproduction/connected/archives/feature_reproduction_private.zip':'feature',
    'reproduction/connected/archives/private_reproduction.zip':'correction',
    'reproduction/bounds/bounds_private.zip':'bounds',
    'reproduction/references/reference_reproduction_private.zip':'references',
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--qa',required=True,type=Path)
    parser.add_argument('--qa-sha256',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError(args.output)
    if sha(args.qa)!=args.qa_sha256:raise ValueError('Changed technical QA')
    qa=json.loads(args.qa.read_text())
    if qa['status']!='PASS_TECHNICAL_PREPARATION':raise ValueError('Final technical QA required')
    if sha(V3)!=V3_PIN:raise ValueError('Changed original V3 manifest')
    old=json.loads(V3.read_text())
    records={}

    def add(source,target,role='evidence',expected=None,**extra):
        source=Path(source)
        if source.is_symlink() or not source.is_file():raise ValueError(source)
        relative=source.relative_to(PROJECT).as_posix()
        digest=sha(source)
        if expected is not None and digest!=expected:raise ValueError('Changed source: '+relative)
        if target in records:raise ValueError('Duplicate target: '+target)
        records[target]={'source':relative,'target':target,'role':role,
                         'bytes':source.stat().st_size,'sha256':digest,**extra}

    # Explicit, authenticated historical evidence; no recursive live-folder scrape.
    for target,record in old['files'].items():
        if target.startswith('reproduction/'):
            extra={'id':ARCHIVES[target],'legacy_member':target} if target in ARCHIVES else {}
            add(PROJECT/record['source'],target,'private_archive' if extra else 'legacy_evidence',record['sha256'],**extra)
        elif target.startswith('evidence/'):
            add(PROJECT/record['source'],'evidence/prior/'+target.removeprefix('evidence/'),'legacy_evidence',record['sha256'])
        elif target in {'author_approval/ACCESS_RIGHTS_MATRIX.md','author_approval/CITATION_LEDGER.md','author_approval/VENUE_REVIEW.md'}:
            add(PROJECT/record['source'],'author_approval/historical/'+Path(target).name,'historical_author_aid',record['sha256'])

    for kind,stem in [('main','Manuscript'),('supplement','Supplement')]:
        for ext in ['pdf','docx']:
            add(HERE/'deliverables'/f'NeuralFoil_Measurement_Correction_{stem}.{ext}',f'manuscript/{kind}.{ext}',kind+'_'+ext)
        add(HERE/(kind+'.complete.md'),f'manuscript/{kind}.md',kind+'_source')
    for stem in FIGURES:
        for ext in ['png','svg','pdf']:
            add(HERE/'figures'/(stem+'.'+ext),'figures/'+stem+'.'+ext,'figure',id=stem,format=ext)
        add(HERE/'figures'/(stem+'.png'),'manuscript/figures/'+stem+'.png','source_image_alias')

    for name,role in [('README.md','readme'),('NAVIGATION.md','navigation'),('PERMISSIONS.md','permissions'),
                      ('REPLAY_GUIDE.md','replay_guide'),('AUTHOR_CHECKLIST.md','author_checklist')]:
        target='author_approval/'+name if role=='author_checklist' else name
        add(HERE/'work/package_documents'/name,target,role)
    for name in ['package_v4.py','test_package_v4.py']:
        add(RESEARCH/'package_v4_tools'/name,'tools/'+name,'package_tool')

    for name in ['manuscript.md','supplement.md','assemble_submission.py','build_documents.py',
                 'archive_build.py','audit_layout.py','prepare_package_inputs.py']:
        add(HERE/name,'authoring_provenance/'+name,'authoring_source')
    add(HERE/'work/ASSEMBLY.json','authoring_provenance/ASSEMBLY.json','assembly_receipt')
    # Authoring sources are provenance, not a claimed standalone installation.
    add(PROJECT/'modern_edition/build_document.py','authoring_provenance/preserved_design.py','authoring_source')

    risk=RESEARCH/'model_proposal'
    for name in ['PROPOSAL.md','APPROVAL.md','REPORT.md','TEST_RESULTS.md','incremental_harm.py',
                 'run_experiment.py','assess_experiment.py','test_incremental_harm.py','verify_results.py']:
        add(risk/name,'evidence/renewed/incremental_harm/'+name)
    for name in ['all_row_predictions.csv','bootstrap.csv','bundle_harm_metrics.csv','calibration_summary.csv',
                 'candidate_summary.csv','decisions.csv','expected_harm_metrics.csv','group_metrics.csv',
                 'harm_metrics.csv','intervention_metrics.csv','panel_metrics.csv','report.json']:
        add(risk/'assessment'/name,'evidence/renewed/incremental_harm/assessment/'+name)
    for name in ['EXPORT.json','FRESH_EXECUTION.json','PRIOR_REPLAY_DIFFERENCES.json','PROTOCOL.md','README.md','REPORT.md']:
        add(risk/'portable'/name,'reproduction/incremental_harm/'+name)
    add(risk/'portable/incremental_harm_private.zip','reproduction/incremental_harm/incremental_harm_private.zip',
        'private_archive','6b95849963500179f19e81915f61693c6837f53c0d294bd5f4f4a5abac135c5c',id='incremental_harm')

    sensitivity=RESEARCH/'measurement_sensitivity'
    for name in ['PROTOCOL.md','sensitivity.py','test_sensitivity.py','build_displays.py']:
        add(sensitivity/name,'evidence/renewed/label_sensitivity/'+name)
    for name in ['grid.csv','manifest.json','panels.csv','radii.csv','synthetic_tests.txt']:
        add(sensitivity/'attempt_1'/name,'evidence/renewed/label_sensitivity/results/'+name)
    portable=RESEARCH/'uncertainty_review/portable_sensitivity'
    for name in ['README.md','REPORT.md','export_verified.json','fresh_verification.json','existing_output_refusal.txt']:
        add(portable/name,'reproduction/label_sensitivity/'+name)
    add(portable/'portable_sensitivity_private.zip','reproduction/label_sensitivity/portable_sensitivity_private.zip',
        'private_archive','5bb33a1b14d9d4377d9720f7123e20d0e8b5a16e738448c6798e2f38d32be750',id='label_sensitivity')

    environment=RESEARCH/'independent_environment'
    receipt=environment/'DELIVERY.json'
    if sha(receipt)!='f1d00c395634c969a0c7463b62c120b2324501f2a6b47366ac16a20bb1e0bcca':
        raise ValueError('Changed environment delivery witness')
    add(receipt,'evidence/environment/DELIVERY.json','environment_receipt')
    for name,digest in json.loads(receipt.read_text())['root_files'].items():
        add(environment/name,'evidence/environment/'+name,'environment_receipt',digest)
    for subdir,names in [
        ('portable_replays',['REPORT.md','REPORT_PERMISSION_CORRECTION.md','COMPLETE.json','EXECUTION.json','run.py']),
        ('risk_replay',['REPORT.md','METRIC_REPLAY.json','audit.py','diagnostic_replay.py']),
    ]:
        for name in names:add(environment/subdir/name,'evidence/environment/'+subdir+'/'+name,'environment_receipt')

    # The explicit final QA witness list is finite and must already be approved.
    # Files may be local originals; all are copied to a dedicated quality namespace.
    for relative in qa['review_files']:
        add(HERE/relative,'quality/reviews/'+relative.replace('../','parent/'),'review')
    add(args.qa,'quality/FINAL_TECHNICAL_QA.json','technical_qa',args.qa_sha256)
    for name in ['work/measurement_displays/MANIFEST.json','work/risk_displays/MANIFEST.json']:
        add(HERE/name,'evidence/renewed/displays/'+Path(name).parent.name+'/'+Path(name).name)

    result={'schema':'private_submission_inputs_v4','package_name':'NeuralFoil_Private_Submission_Package_v4',
            'technical_approval':'APPROVED_FOR_PRIVATE_ASSEMBLY','human_author_approval':False,'public_release':False,
            'max_payload_bytes':512*1024*1024,
            'requirements':{'figure_ids':FIGURES,'figure_formats':['png','svg','pdf'],
                            'archive_ids':list(ARCHIVES.values())+['incremental_harm','label_sensitivity'],
                            'legacy_archive_ids':list(ARCHIVES.values())},
            'legacy_witness':{'source':V3.relative_to(PROJECT).as_posix(),'sha256':V3_PIN},
            'files':[records[k] for k in sorted(records)]}
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'INVENTORY_PREPARED_NOT_ASSEMBLED','files':len(records),
                      'bytes':sum(r['bytes'] for r in records.values()),'sha256':sha(args.output)}))

if __name__=='__main__':main()
