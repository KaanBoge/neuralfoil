"""Prepare explicitly selected v5 main/v7 supplement config, never final QA."""
from pathlib import Path
import json,hashlib,ast
HERE=Path(__file__).resolve().parent;ENV=HERE.parent;R=ENV.parent;REV=R.parents[1];ROOT=REV.parent;E=REV/'renewed_manuscript_v7'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p,expected=None):
    h=sha(p)
    if expected:assert h==expected,str(p)
    return {'path':str(p.relative_to(ROOT)),'sha256':h}
def evidence(role,p,status=None,maps=(),expected=None,assertions=()):
    x={**pin(p,expected),'role':role}
    x['assertions']=([{'pointer':'/status','equals':status}] if status is not None else [])+list(assertions)
    if maps:x['maps']=[{'pointer':key,'base':str(base.relative_to(ROOT))} for key,base in maps]
    d=json.loads(p.read_text()) if status is not None or maps else None
    if status is not None:assert d['status']==status
    for key,base in maps:
        z=d
        for part in key.strip('/').split('/'):z=z[int(part)] if isinstance(z,list) else z[part]
        for name,h in z.items():pin(Path(name) if Path(name).is_absolute() else base/name,h)
    return x
items=[]
items.append(evidence('assembly',E/'work/ASSEMBLY.json','PASS',[('/source_sha256',ROOT)]))
items.append(evidence('legacy_displays',E/'work/displays/DISPLAY_MANIFEST.json','PASS',[('/source_sha256',ROOT),('/outputs',E)]))
items.append(evidence('method_diagram',E/'work/displays/METHOD_DIAGRAM.json','BUILT_REQUIRES_VISUAL_REVIEW',[('/outputs',E)]))
for role,folder,status in [('risk_displays','risk_displays','EXACT_SOURCE_DERIVED_TABLES_NOT_YET_LAYOUT_REVIEWED'),('sensitivity_displays','measurement_displays','BUILT_REQUIRES_VISUAL_REVIEW')]:
    items.append(evidence(role,E/f'work/{folder}/MANIFEST.json',status,[('/input_sha256',ROOT),('/output_sha256',E)]))
items.append(evidence('risk_report',R/'model_proposal/assessment/report.json','complete_exploratory_not_certified',[('/output_sha256',R/'model_proposal/assessment')],expected='1c34134f311695a54a9c91c0ffa19699c7ce826eb1c8f50e671336f263cce9ff'))
items.append(evidence('sensitivity_report',R/'measurement_sensitivity/attempt_1/manifest.json','complete_retrospective_sensitivity_not_prediction_improvement',[('/output_sha256',R/'measurement_sensitivity/attempt_1')],expected='5afa8ac4d181ec654c7802c917e6098039e533914a8ca533d167b81177cb934f'))
items.append(evidence('risk_portable',R/'model_proposal/portable/incremental_harm_private.zip',expected='6b95849963500179f19e81915f61693c6837f53c0d294bd5f4f4a5abac135c5c'))
items.append(evidence('sensitivity_portable',R/'uncertainty_review/portable_sensitivity/portable_sensitivity_private.zip',expected='5bb33a1b14d9d4377d9720f7123e20d0e8b5a16e738448c6798e2f38d32be750'))
items.append(evidence('environment_receipts',ENV/'DELIVERY.json','COMPLETE',[('/root_files',ENV)],expected='f1d00c395634c969a0c7463b62c120b2324501f2a6b47366ac16a20bb1e0bcca'))
items.append(evidence('environment_receipts',ENV/'VERIFIED.json','PASS_STAGED_MATCHED_BUILD_CHAIN_WITH_PRESERVED_PYPI_FAILURE',expected='12d3cf0ca398fc1a30d65023b30d17c6e13ba987193dc45faab1eb830d952e8f'))
items.append(evidence('portable_replay_receipts',ENV/'portable_replays/COMPLETE.json',maps=[('/records/5/output_sha256',ENV/'portable_replays/sensitivity_output'),('/records/9/output_sha256',ENV/'portable_replays/incremental_output')],expected='8bd70d6e29e092f5f2de6e17e374eb77321108b10caa5636f14b00e7238d767e',assertions=[{'pointer':'/new_core_fits','equals':0},{'pointer':'/isolated_third_party_environment','equals':True}]+[{'pointer':f'/records/{i}/exit_code','equals':0} for i in [0,2,3,4,7,8]]))
items.append(evidence('assembly_audit',ENV/'final_assembly_v7/FINAL.json','PASS_REAUTHENTICATED',[('/additional_display_pins',ROOT),('/owned_evidence_sha256',ENV/'final_assembly_v7')],expected='554cc108009a0245ced44b29c97cb545b2e912217bb8caa87de94dbcb5fbd909'))
for p in [ENV/'portable_replays/REPORT.md',ENV/'portable_replays/REPORT_PERMISSION_CORRECTION.md',ENV/'portable_replays/EXECUTION.json',HERE/'finalize_v7.py',HERE/'test_finalize_v7.py',HERE/'README.md',ENV/'reference_attempt_1/complete.json',ENV/'matched_feature_results/complete.json',ENV/'connected_attempt_1/failure.json']:
    items.append(evidence('ancillary',p))
candidates={}
for kind,version,ledger,report in [
 ('supplement','v1',HERE/'canonical_reviews/v1_PAGE_LEDGER.json',ENV/'visual_v7_v1/REVIEW.md'),
 ('supplement','v3',HERE/'canonical_reviews/v3_PAGE_LEDGER.json',ENV/'visual_v7_v3/REVIEW.md'),
 ('main','v1',R/'uncertainty_review/visual_main_v7_v1/PAGE_LEDGER.json',R/'uncertainty_review/visual_main_v7_v1/REVIEW.md'),
 ('supplement','v3',R/'uncertainty_review/visual_v7_v3/PAGE_LEDGER.json',R/'uncertainty_review/visual_v7_v3/REVIEW.md')]:
    d=json.loads(ledger.read_text());folder=E/f'work/render_{kind}/{version}';stem='Manuscript' if kind=='main' else 'Supplement';pdf=folder/f'NeuralFoil_Measurement_Correction_{stem}.pdf';pin(pdf,d['pdf_sha256'])
    for i,row in enumerate(d['pages']):
        if row['result']!='PASS' or row['individually_viewed_original_resolution'] is not True:continue
        png=folder/f"page-{row['page']}.png";pin(png,row['png_sha256'])
        candidates[(kind,row['png_sha256'])]={'ledger':pin(ledger),'report':pin(report),'record_pointer':f'/pages/{i}','reviewed_page':row['page'],'reviewed_png':pin(png),'reviewed_pdf':pin(pdf)}
docs={};missing={}
for kind,version,pages,expected in [('main','v5',27,'8e633f3a77bc759bc9daf222529f295b6ec0d45f08ab13846a0ccdd9e1ea1fd1'),('supplement','v7',67,'f00028bb73028dd7daca3166cc2a3c843dd57205ab1d3781cc71caaab6dc4430')]:
    folder=E/f'work/render_{kind}/{version}';stem='Manuscript' if kind=='main' else 'Supplement';base=f'NeuralFoil_Measurement_Correction_{stem}'
    doc={'version':version,'pages':pages,'source':pin(E/f'{kind}.complete.md',expected),'builder':pin(folder/'build_documents.py'),'build':pin(folder/'BUILD.json'),'layout':pin(folder/'LAYOUT_AUDIT.json'),'page_map':pin(folder/'PAGE_MAP.json'),'docx':pin(folder/f'{base}.docx'),'pdf':pin(folder/f'{base}.pdf'),'deliverable_pdf':str((E/'deliverables'/f'{base}.pdf').relative_to(ROOT)),'deliverable_docx':str((E/'deliverables'/f'{base}.docx').relative_to(ROOT)),'visual':{}}
    for page in range(1,pages+1):
        found=candidates.get((kind,sha(folder/f'page-{page}.png')))
        if found:doc['visual'][str(page)]=found
    if kind=='supplement':
        tree=ast.parse((folder/'build_documents.py').read_text());labels=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TOC_LABELS' for t in n.targets))
        headings=json.loads((folder/'BUILD.json').read_text())['headings'];doc['toc_labels']={h['text']:labels.get(h['text'].split()[0],h['text']) for h in headings if h['level']==1 and (h['text'].startswith('S') or h['text']=='References')}
    docs[kind]=doc;missing[kind]=[n for n in range(1,pages+1) if str(n) not in doc['visual']]
old=REV/'work/FINAL_TECHNICAL_QA_v3.json'
cfg={'schema':'v7-final-qa-1','finalization_authorized':False,'project_root':str(ROOT),'edition':str(E.relative_to(ROOT)),
     'old_qa':{**pin(old),'base':str(REV.relative_to(ROOT)),'file_count':754},'evidence':items,'documents':docs,
     '_draft_missing_actual_visual_witness_pages':missing,'_draft_scope':'Explicit root-selected versions; pending root review and visual evidence. Not executable authorization.'}
target=HERE/'DRAFT_SELECTED_CONFIG.json'
with target.open('x') as f:json.dump(cfg,f,indent=2);f.write('\n')
print(json.dumps({'draft_sha256':sha(target),'missing':missing,'no_finalizer_executed':True},indent=2))
