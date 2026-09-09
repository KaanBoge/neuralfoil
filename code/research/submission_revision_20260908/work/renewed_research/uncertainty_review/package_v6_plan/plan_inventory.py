"""Fixed metadata-only proposal. Never open a scientific payload or make a ZIP."""
import hashlib,json,collections
from pathlib import Path

PROJECT=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
SUB='submission_revision_20260908/'
RESEARCH=SUB+'work/renewed_research/'
HERE=Path(__file__).resolve().parent
V5=SUB+'renewed_manuscript_v8/deliverables/NeuralFoil_Private_Submission_Package_v5/'
FRAGMENT=RESEARCH+'independent_environment/final_qa_tools/V9_EVIDENCE_FRAGMENT_DRAFT_v4.json'
FRAGMENT_SHA='c9c14054db4972c9b5df34fb24f8bea6d030da60776a2d9265c9a9b7a4687d7b'
V5_SHA='9158ec51bbc5414f42b338b13ca722c4d58ac93c2f5c9434312ac7842f344ba9'
V5_INPUT_SHA='0f7f6ae7ac18a61cebbeab3a7c0e25a105af5cad55e72c6c058f8962e3fc82d8'
SKIP_ROLES={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','figure','source_image_alias','readme','navigation','permissions','replay_guide','author_checklist'}
def sha(b):return hashlib.sha256(b).hexdigest()
def pointer(d,s):
    for k in s.strip('/').split('/') if s else []:d=d[k.replace('~1','/').replace('~0','~')]
    return d
def main():
    records={};reads={};omissions=[]
    def add(path,h,role):
        p=Path(path);p=p if p.is_absolute() else PROJECT/p
        if any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('symlink')
        p=p.resolve()
        if not p.is_relative_to(PROJECT):
            omissions.append({'external_runtime_not_packaged':str(p),'sha256':h});return p
        key=p.relative_to(PROJECT).as_posix()
        if 'eight' in key.lower():raise ValueError('eight-tree excluded')
        if key in records and records[key]['sha256']!=h:
            omissions.append({'historical_source_needs_snapshot':key,'sha256':h,'other_sha256':records[key]['sha256']});return p
        records[key]={'source':key,'sha256':h,'bytes':p.stat().st_size,'role':role}
        return p
    def meta(path,h,role='receipt'):
        p=add(path,h,role);b=p.read_bytes()
        if sha(b)!=h:raise ValueError('metadata hash '+str(p))
        reads[p.relative_to(PROJECT).as_posix()]=h
        return json.loads(b)
    fragment=meta(FRAGMENT,FRAGMENT_SHA,'proposal_authority')
    old=meta(V5+'MANIFEST.json',V5_SHA,'legacy_manifest')
    inp=meta(V5+'INPUT_MANIFEST.json',V5_INPUT_SHA,'legacy_input')
    legacy=[]
    for row in inp['files']:
        if row['role'] in SKIP_ROLES:continue
        n=row['target'];r=old['files'][n]
        if (r['sha256'],r['bytes'])!=(row['sha256'],row['bytes']):raise ValueError('legacy disagreement')
        # Preserve historical/v4 literally; do not produce historical/v5/historical/v4.
        dest=n if n.startswith(('reproduction/','historical/v4/')) else 'historical/v5/'+n
        legacy.append({'source':V5+n,'target':dest,'sha256':r['sha256'],'bytes':r['bytes'],'role':row['role']})
    for p,h in fragment['authenticated_metadata_and_source_sha256'].items():add(p,h,'fragment_source_metadata')
    def outputs(path,h):
        d=meta(path,h);base=Path(path).parent
        for n,v in d.get('outputs',{}).items():add(base/n,v,'opaque_saved_output')
        return d
    for e in fragment['added_evidence']+fragment['history_pins']:
        add(e['path'],e['sha256'],e['role'])
        if e['role']=='v8_frozen_qa':continue # V5 retains its finite historical copy.
        if e.get('maps') or e.get('scalar_pins') or e.get('record_lists'):
            d=meta(e['path'],e['sha256'])
            for m in e.get('maps',[]):
                for n,h in pointer(d,m['pointer']).items():add(Path(m['base'])/n,h,'declared_map_payload')
            for m in e.get('scalar_pins',[]):add(m['path'],pointer(d,m['pointer']),'scalar_pin_metadata')
            for m in e.get('record_lists',[]):
                for row in pointer(d,m['pointer']):add(Path(m['base'])/row['path'],row['sha256'],'declared_input_payload')
        for phase in e.get('phase_chain',[]):
            outputs(phase['path'],phase['sha256']);add(phase['approval']['path'],phase['approval']['sha256'],'phase_approval')
        if e['role'] in {'paired_all_context_producer','paired_all_context_replay','four_tree_all_context_producer','four_tree_all_context_replay'}:
            d=meta(e['path'],e['sha256']);contexts=d.get('contexts',d.get('summary',{}).get('contexts',{}))
            if len(contexts)!=16:raise ValueError('complete sixteen contexts')
            for name,row in contexts.items():
                if name=='final':continue # Explicit inherited-final witnesses below.
                outputs(Path(e['path']).parent/name/'COMPLETE.json',row.get('complete_sha256',row.get('replay_complete_sha256')))
    # Fixed inherited final, not inferred from a new scan.
    for p,h in [
      (RESEARCH+'model_proposal/paired_tree_plan/actual_producer_attempt_1/COMPLETE.json','dce7280d67453cf120001a412d05ba6cbde4c33c05c4a0b65284ae359ddc433c'),
      (RESEARCH+'model_proposal/paired_tree_plan/actual_replay_attempt_1/COMPLETE.json','02b122ad8fb24243815bd8b016c41d91cf83f45c3f1c72f32c80a18d7102079a'),
      (RESEARCH+'model_proposal/four_tree_matching_plan/attempt_1/COMPLETE.json','dcb30c773b23f1a4dff91e5eb49058566793826aa9b699512b76390c5acc3704'),
      (RESEARCH+'uncertainty_review/range_bound_feasibility/four_tree_matching/attempt_1/COMPLETE.json','af092b5b5a7149c1156375bf784c700035d785324d23494f323aa14f5efcb4aa')]:outputs(p,h)
    # Finite registry source maps. Bodies of referenced payloads remain unopened.
    registries=[r for r in list(records.values()) if Path(r['source']).name.startswith('REGISTRY') and r['source'].endswith('.json')]
    for r in registries:
        d=meta(r['source'],r['sha256'],'source_registry');base=Path(r['source']).parent
        for key in ['sources','external_sources','metadata']:
            for n,v in d.get(key,{}).items():
                if isinstance(v,str):p=base/d['source_paths'][n] if key=='sources' and n in d.get('source_paths',{}) else (base if key=='sources' else Path(RESEARCH))/n;h=v
                elif isinstance(v,dict) and {'path','sha256'}<=v.keys():p=Path(RESEARCH)/v['path'];h=v['sha256']
                else:omissions.append({'registry':r['source'],'field':key,'key':n});continue
                add(p,h,'registry_source_or_metadata')
    # Current authoring/finalizer source witnesses only, never guessed final QA.
    tools=Path(RESEARCH)/'independent_environment/final_qa_tools'
    for n in ['finalize_v9.py','test_finalize_v9.py','prepare_v9_final_config.py','test_prepare_v9_final_config.py']:
        p=PROJECT/tools/n;b=p.read_bytes();add(tools/n,sha(b),'v9_finalizer_source_test')
    edition=SUB+'renewed_manuscript_v9/'
    for n in ['work/ROOT_ASSEMBLY_CONFIG_v2.json','work/ASSEMBLY.json','assemble_submission.py','test_assemble_submission.py','build_documents.py','render_version.py','audit_layout.py']:
        p=PROJECT/edition/n;b=p.read_bytes();add(edition+n,sha(b),'v9_authoring_metadata_source')
    for kind in ['main','supplement']:
        for n in ['BUILD.json','PAGE_MAP.json','LAYOUT_AUDIT.json']:
            p=PROJECT/edition/'work'/('render_'+kind)/'v2'/n
            if not p.exists():omissions.append({'pending_render_metadata_name':str(p)});continue
            b=p.read_bytes();add(p,sha(b),'current_render_metadata')
    # All counts here are STAT estimates, not new payload authentication.
    total=sum(r['bytes'] for r in records.values());lt=sum(r['bytes'] for r in legacy)
    result={'status':'SOURCE_ONLY_FINITE_PROPOSAL_NOT_PACKAGE_INVENTORY','scientific_payloads_opened':False,'final_qa_binding':None,
      'metadata_json_parsed':reads,'legacy_retained':legacy,'addon_files':sorted(records.values(),key=lambda r:r['source']),
      'unresolved_schema_records':omissions,'addon_stat_bytes':total,'legacy_retained_bytes':lt,
      'flat_subtotal_bytes':total+lt,'unresolved_documents_guides_qa_reserve_bytes':32*1024**2,
      'flat_conservative_planning_bytes':total+lt+32*1024**2,'unchanged_outer_payload_cap_bytes':512*1024**2,
      'addon_compressed_size_known':False,'portable_replay_claim':False}
    out=HERE/'INVENTORY_PROPOSAL.json'
    with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'metadata_json_parsed','legacy_retained','addon_files'}},indent=2))
if __name__=='__main__':main()
