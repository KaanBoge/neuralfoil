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
BOUND_ROLES={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','figure','source_image_alias','review'}
ENVIRONMENT_ADDITIONAL_PINS={
    'reference_attempt_1/complete.json':'add38cc0a0a9cb7659bf5bcd29acf7104e35a9e34b28bef14d92bbef5415b5f9',
    'matched_feature_results/complete.json':'bf98720d4f6bc16ce875c6b7ea0d85e48e66b6a25f5926b73359bf92701022a0',
    'connected_attempt_1/failure.json':'4029acbd173a7df9a2045e596a5b7fd474ee5e858837da91e1e0981d12beb6ed',
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

# Finite reviewed registry: historical audit aliases resolve only to authenticated
# V3 snapshots; no discovery, recursive capture, or substitution of new sources.
ASSEMBLY_AUDIT_FILES=json.loads(r'''[
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/FINAL.json",
    "target": "evidence/assembly_audit/v1/FINAL.json",
    "sha256": "554cc108009a0245ced44b29c97cb545b2e912217bb8caa87de94dbcb5fbd909"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/NATIVE_MATH.json",
    "target": "evidence/assembly_audit/v1/NATIVE_MATH.json",
    "sha256": "07b0a9d7e6ec98675a2417a356344449bf67d3115d1573d764750faaa01811a7"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/math_structure.py",
    "target": "evidence/assembly_audit/v1/math_structure.py",
    "sha256": "915b01d111a2edd32090eec56023301c460cc2df4ae7709191620c5af372942e"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/audit.py",
    "target": "evidence/assembly_audit/v1/audit.py",
    "sha256": "4b61e26d488a9a1f10540102ac52a158fd31ea189508c72abca25462850049fb"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/REPORT.md",
    "target": "evidence/assembly_audit/v1/REPORT.md",
    "sha256": "2c95a061056b3b47d657fe17f2e7fc3b6a7999c22553096ac0003b169bf408b0"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/MATH_STRUCTURE.json",
    "target": "evidence/assembly_audit/v1/MATH_STRUCTURE.json",
    "sha256": "6eed879e2f0e6b26c2b96dd5deab4097eae357baa2fd0da0c6a39bfc9116093c"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/finalize.py",
    "target": "evidence/assembly_audit/v1/finalize.py",
    "sha256": "1ef395d40f678257c4e43db8b7d01f53aca68c8739f8f43d95d32cdd166f790b"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7/CHECKS.json",
    "target": "evidence/assembly_audit/v1/CHECKS.json",
    "sha256": "45378c2ac04f5ea39bee010f98d5e23e1058cc0783cdbbdae1ae87ded6d76b10"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7_v2/DELTA.json",
    "target": "evidence/assembly_audit/v2/DELTA.json",
    "sha256": "309c910976b6c381ac2f3109f9ace47bb36bb117dd4d2298ef604b1b6f0891a3"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7_v2/REPORT.md",
    "target": "evidence/assembly_audit/v2/REPORT.md",
    "sha256": "70aaf2a9827e9193f37eec8a18fd034b81bd19100f24e3d5f81a1d1ed432e929"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7_v2/audit_delta.py",
    "target": "evidence/assembly_audit/v2/audit_delta.py",
    "sha256": "a3b470a0caaadd5998018a12ef2b489412b6fa3c0a68796de0b548e2b63e425d"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/independent_environment/final_assembly_v7_v2/SOURCE.diff",
    "target": "evidence/assembly_audit/v2/SOURCE.diff",
    "sha256": "31b0ed041dc15167a56719a2966bd2aff193c3b12fe416a9c4ce26fd5d0814ea"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/render_main/v3/ASSEMBLY.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/renewed_manuscript_v7/work/render_main/v3/ASSEMBLY.json",
    "sha256": "e5ddae8156557362e209c3944b291e299dae3df838e419faa3c5e173e4718c75",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/work/ASSEMBLY.json"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/displays/DISPLAY_MANIFEST.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/renewed_manuscript_v7/work/displays/DISPLAY_MANIFEST.json",
    "sha256": "598a9acc5680196796a8bbd6da09c6a6e6cb6f2b4f8b82b8f48b976511748d58",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/work/displays/DISPLAY_MANIFEST.json"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/displays/METHOD_DIAGRAM.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/renewed_manuscript_v7/work/displays/METHOD_DIAGRAM.json",
    "sha256": "453a1e844bc21ea5e8684ed155a4ef469389210e31b040b331bc5ec86ffacf47",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/work/displays/METHOD_DIAGRAM.json"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/measurement_displays/MANIFEST.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/renewed_manuscript_v7/work/measurement_displays/MANIFEST.json",
    "sha256": "24aeb9dff405eb039a99352653fec64ac125d66b926b6b72fec2ee77ce41b574",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/work/measurement_displays/MANIFEST.json"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/measurement_sensitivity/attempt_1/manifest.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/work/renewed_research/measurement_sensitivity/attempt_1/manifest.json",
    "sha256": "5afa8ac4d181ec654c7802c917e6098039e533914a8ca533d167b81177cb934f",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/work/renewed_research/measurement_sensitivity/attempt_1/manifest.json"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/uncertainty_review/EMPIRICAL_QA.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/work/renewed_research/uncertainty_review/EMPIRICAL_QA.json",
    "sha256": "feb314bdd45ae7f1935d197859f78f7eef13bc31b7f4f4e8629c135ecc5f30bb",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/work/renewed_research/uncertainty_review/EMPIRICAL_QA.json"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/risk_displays/MANIFEST.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/renewed_manuscript_v7/work/risk_displays/MANIFEST.json",
    "sha256": "3742e3839625fa51702ab4cf666adc50efdd11ec9c0e04ccefbf0a5bf42db531",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/work/risk_displays/MANIFEST.json"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/model_proposal/assessment/report.json",
    "target": "evidence/assembly_audit/input_manifests/submission_revision_20260908/work/renewed_research/model_proposal/assessment/report.json",
    "sha256": "1c34134f311695a54a9c91c0ffa19699c7ce826eb1c8f50e671336f263cce9ff",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/work/renewed_research/model_proposal/assessment/report.json"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/render_main/v3/main.complete.md",
    "target": "evidence/assembly_audit/archived_v3_sources/main.complete.md",
    "sha256": "8e633f3a77bc759bc9daf222529f295b6ec0d45f08ab13846a0ccdd9e1ea1fd1",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/main.complete.md"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/render_main/v3/manuscript.md",
    "target": "evidence/assembly_audit/archived_v3_sources/manuscript.md",
    "sha256": "4a09e964148fdbd99c108bb8c5f092bf515ea95530d0e4b22e31ce84492be84c",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/manuscript.md"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/render_supplement/v3/supplement.complete.md",
    "target": "evidence/assembly_audit/archived_v3_sources/supplement.complete.md",
    "sha256": "f00028bb73028dd7daca3166cc2a3c843dd57205ab1d3781cc71caaab6dc4430",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/supplement.complete.md"
  },
  {
    "source": "submission_revision_20260908/renewed_manuscript_v7/work/render_supplement/v3/supplement.md",
    "target": "evidence/assembly_audit/archived_v3_sources/supplement.md",
    "sha256": "cc5cbf67795d46b95ad1d64e3ec942e1ab654c7b20cc95f2613ab3cc8754e458",
    "original_witness_path": "/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper/submission_revision_20260908/renewed_manuscript_v7/supplement.md"
  },
  {
    "source": "submission_revision_20260908/work/renewed_research/uncertainty_review/range_bound_feasibility/V7_ARITHMETIC_SCOPE_REVIEW.md",
    "target": "evidence/assembly_audit/independent_arithmetic_scope_review.md",
    "sha256": "b7aae6e4c602ee33d30eaf311b14bc37a9284dc82e3f11e8665c3a0e2ef2d5b0"
  }
]''')

def authenticated_config(qa,qa_paths,edition):
    """Require the finalizer's actual authorized input, not a current draft."""
    source=(edition/qa['config_path']).resolve()
    bound=qa_paths.get(source)
    if bound is None or bound[1]!=qa['config_sha256']:
        raise ValueError('Missing final config QA pin')
    if sha(source)!=bound[1]:raise ValueError('Changed final config')
    config=json.loads(source.read_text())
    if config.get('finalization_authorized') is not True:
        raise ValueError('Final config was not authorized')
    return source,bound[1]

def authenticated_helper(qa,qa_paths,config,project):
    """Select only the helper explicitly pinned in the authorized config."""
    matches=[]
    for item in config['evidence']:
        if item['sha256']!=qa['helper_sha256']:continue
        source=Path(item['path'])
        if not source.is_absolute():source=project/source
        source=source.resolve()
        bound=qa_paths.get(source)
        if source.suffix!='.py' or bound is None or bound[1]!=qa['helper_sha256']:
            raise ValueError('Helper evidence is not QA pinned Python')
        if sha(source)!=bound[1]:raise ValueError('Changed finalizer helper')
        matches.append(source)
    if len(matches)!=1:raise ValueError('Explicit unique helper evidence required')
    return matches[0]

def qa_bound_source(qa,qa_paths,source,role):
    """Document aliases must equal the artifact reviewed for that exact role."""
    bound=qa_paths.get(source.resolve())
    if role in {'main_pdf','main_docx','main_source','supplement_pdf','supplement_docx','supplement_source'}:
        kind,artifact=role.split('_',1)
        if kind=='supplement' and artifact=='source':artifact='reading_source'
        witnessed=qa['documents'][kind]['artifacts'][artifact]
        bound=qa_paths.get(Path(witnessed['path']).resolve())
        if bound is None or bound[1]!=witnessed['sha256']:raise ValueError('Missing document artifact QA binding')
    if bound is not None and sha(source)!=bound[1]:raise ValueError('Post-QA source mutation: '+str(source))
    if bound is None and role in BOUND_ROLES:raise ValueError('Required source not covered by final QA: '+str(source))
    return bound

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
    qa_paths={}
    for name,digest in qa['files'].items():
        path=(HERE/name).resolve()
        if not path.is_relative_to(PROJECT):raise ValueError('QA path escapes project')
        if path in qa_paths and qa_paths[path][1]!=digest:raise ValueError('Conflicting QA pin')
        qa_paths[path]=(name,digest)

    def add(source,target,role='evidence',expected=None,**extra):
        source=Path(source)
        if any(p.is_symlink() for p in [source,*source.parents]) or not source.is_file():raise ValueError(source)
        source=source.resolve()
        relative=source.relative_to(PROJECT).as_posix()
        digest=sha(source)
        bound=qa_bound_source(qa,qa_paths,source,role)
        if bound is not None:
            if digest!=bound[1]:raise ValueError('Post-QA source mutation: '+relative)
            extra['qa_key']=bound[0]
        elif role in BOUND_ROLES:raise ValueError('Required source not covered by final QA: '+relative)
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
        source=HERE/(kind+'.complete.md')
        if kind=='supplement':
            source=Path(qa['documents'][kind]['artifacts']['reading_source']['path'])
            original=qa['documents'][kind]['artifacts']['source']
            add(Path(original['path']),'authoring_provenance/supplement.complete.build.md',
                'build_template',original['sha256'])
        add(source,f'manuscript/{kind}.md',kind+'_source')
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
    for record in ASSEMBLY_AUDIT_FILES:
        extra={key:record[key] for key in ['original_witness_path'] if key in record}
        add(PROJECT/record['source'],record['target'],'scientific_assembly_evidence',record['sha256'],**extra)
    config_source,config_digest=authenticated_config(qa,qa_paths,HERE)
    add(config_source,'quality/FINAL_AUTHORIZED_CONFIG.json','final_config',config_digest)
    helper=authenticated_helper(qa,qa_paths,json.loads(config_source.read_text()),PROJECT)
    for source in [helper,helper.with_name('test_'+helper.name),helper.parent/'README.md']:
        bound=qa_paths.get(source.resolve())
        if bound is None:raise ValueError('Finalizer provenance absent from QA: '+str(source))
        add(source,'authoring_provenance/final_qa_tools/'+source.name,
            'qa_tool_provenance',bound[1])
    receipt=environment/'DELIVERY.json'
    if sha(receipt)!='f1d00c395634c969a0c7463b62c120b2324501f2a6b47366ac16a20bb1e0bcca':
        raise ValueError('Changed environment delivery witness')
    add(receipt,'evidence/environment/DELIVERY.json','environment_receipt')
    for name,digest in json.loads(receipt.read_text())['root_files'].items():
        add(environment/name,'evidence/environment/'+name,'environment_receipt',digest)
    declared=json.loads(receipt.read_text())
    additional=set(declared['scientific_output_manifests'])|{declared['preserved_failure']}
    for name in sorted(additional):
        if name in declared['root_files']:continue
        if name not in ENVIRONMENT_ADDITIONAL_PINS:raise ValueError('Unpinned additional environment receipt: '+name)
        add(environment/name,'evidence/environment/'+name,'environment_receipt',ENVIRONMENT_ADDITIONAL_PINS[name])
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
            'qa_binding':{'edition':HERE.relative_to(PROJECT).as_posix(),'source':args.qa.resolve().relative_to(PROJECT).as_posix(),'sha256':args.qa_sha256},
            'technical_approval':'APPROVED_FOR_PRIVATE_ASSEMBLY','human_author_approval':False,'public_release':False,
            'max_payload_bytes':512*1024*1024,
            'requirements':{'figure_ids':FIGURES,'figure_formats':['png','svg','pdf'],
                            'archive_ids':list(ARCHIVES.values())+['incremental_harm','label_sensitivity'],
                            'legacy_archive_ids':list(ARCHIVES.values())},
            'legacy_witness':{'source':V3.relative_to(PROJECT).as_posix(),'sha256':V3_PIN},
            'files':[records[k] for k in sorted(records)]}
    # Reject any changed source during inventory preparation, including the QA.
    if sha(args.qa)!=args.qa_sha256:raise ValueError('Concurrent QA mutation')
    for record in records.values():
        if sha(PROJECT/record['source'])!=record['sha256']:raise ValueError('Concurrent source mutation')
    with args.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'INVENTORY_PREPARED_NOT_ASSEMBLED','files':len(records),
                      'bytes':sum(r['bytes'] for r in records.values()),'sha256':sha(args.output)}))

if __name__=='__main__':main()
