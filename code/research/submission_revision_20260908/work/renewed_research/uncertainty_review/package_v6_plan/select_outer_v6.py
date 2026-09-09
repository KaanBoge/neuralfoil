"""Finite metadata-only outer selection. No scientific payload hash/read or ZIP run."""
import argparse,json,stat
from pathlib import Path
import prepare_v6 as p
import stream_common as c

HERE=Path(__file__).resolve().parent
OLD_INPUT_SHA='0f7f6ae7ac18a61cebbeab3a7c0e25a105af5cad55e72c6c058f8962e3fc82d8'
FIGURES=['method_roles','accuracy_harm','calibration_utility','external_complete_eligible','measurement_label_sensitivity','confidence_rule_illustration']
GUIDE_ROLES={'README.md':'readme','NAVIGATION.md':'navigation','PERMISSIONS.md':'permissions','REPLAY_GUIDE.md':'replay_guide','AUTHOR_CHECKLIST.md':'author_checklist'}
HELPERS={'verify_saved_evidence.py','test_verify_saved_evidence.py'}
AUTH_SOURCES={'select_outer_v6.py','test_select_outer_v6.py','prepare_v6.py','package_v6.py','stream_common.py'}
INPUTS={'qa','config','archive','extraction_receipt','writer_receipt','create_approval','verify_approval','addon_selection','addon_manifest','standalone_reader_receipt'}
SKIP={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','figure','source_image_alias','readme','navigation','permissions','replay_guide','author_checklist'}

def local(root,name):
    q=Path(name);q=q if q.is_absolute() else root/q
    if any(x.is_symlink() for x in [q,*q.parents]):raise ValueError('source ancestor symlink')
    return q.resolve().relative_to(root.resolve()).as_posix()

def legacy_rows(old_input,old_manifest):
    """Reuse immutable packaged V5 payloads, not mutable original source aliases."""
    if len(old_input['files'])!=432 or len(old_manifest['files'])!=433:raise ValueError('fixed V5 inventories')
    result=[]
    for r in old_input['files']:
        n=r['target'];f=old_manifest['files'][n]
        if f!={'sha256':r['sha256'],'bytes':r['bytes']}:raise ValueError('V5 input/member disagreement')
        if r['role'] in SKIP:continue
        target=n if n.startswith(('reproduction/','historical/v4/')) else 'historical/v5/'+n
        role='private_archive' if r['role']=='private_archive' else ('environment_receipt' if r['role']=='environment_receipt' else 'legacy_evidence')
        row={'source':p.OLD+'/'+n,'target':target,'role':role,'sha256':f['sha256'],'bytes':f['bytes']}
        if role=='private_archive':row.update(id=r['id'],legacy_member=n)
        result.append(row)
    if len(result)!=397 or {r['id'] for r in result if r['role']=='private_archive'}!=p.ARCHIVES:raise ValueError('397 retained roles/eight archives')
    return result

def receipt_chain(a,d):
    """Saved immutable evidence receipts; no calibration/model execution."""
    archive=a['inputs']['archive'];ex=d['extraction_receipt'];wr=d['writer_receipt'];ca=d['create_approval'];va=d['verify_approval']
    if ex.get('status')!='VERIFIED_STREAMED_EVIDENCE' or wr.get('status')!='CREATED_STREAMED_EVIDENCE_EXTRACTION_PENDING':raise ValueError('completed archive and extraction required')
    for obj in [ex,wr]:
        if obj.get('archive_sha256')!=archive['sha256'] or obj.get('scientific_execution') is not False or obj.get('selection_sha256')!=a['inputs']['addon_selection']['sha256']:raise ValueError('archive/selection receipt identity')
    if ex.get('archive_bytes')!=wr.get('archive_bytes') or ex.get('manifest_sha256')!=a['inputs']['addon_manifest']['sha256'] or wr.get('manifest_sha256')!=a['inputs']['addon_manifest']['sha256']:raise ValueError('archive size/manifest receipt')
    for kind,phase,receipt in [('create_approval','CREATE',wr),('verify_approval','VERIFY_EXTRACT',ex)]:
        auth=d[kind]
        if auth.get('phase')!=phase or auth.get('execution_authorized') is not True or auth.get('selection_sha256')!=a['inputs']['addon_selection']['sha256'] or receipt.get('approval_sha256')!=a['inputs'][kind]['sha256']:raise ValueError('distinct phase approval chain')
        if receipt.get('source_pins')!=auth.get('source_pins'):raise ValueError('phase implementation source pins')
    if va.get('writer_receipt_sha256')!=a['inputs']['writer_receipt']['sha256'] or ex.get('writer_receipt_sha256')!=a['inputs']['writer_receipt']['sha256'] or va.get('writer_approval_sha256')!=a['inputs']['create_approval']['sha256'] or va.get('archive_sha256')!=archive['sha256']:raise ValueError('verification original predecessor chain')
    manifest=d['addon_manifest'];selected=d['addon_selection']['files']
    expected={r['target']:{'sha256':r['sha256'],'bytes':r['bytes']} for r in selected}
    if len(expected)!=len(selected) or manifest!={'schema':'v9-saved-evidence-1','selection_sha256':a['inputs']['addon_selection']['sha256'],'claim':d['addon_selection']['claim'],'files':expected}:raise ValueError('manifest exact selected inventory')
    if ex.get('files')!=len(selected) or ex.get('verified_payload_bytes')!=sum(r['bytes'] for r in selected) or ex.get('disk_files_reopened')!=len(selected)+1:raise ValueError('extracted inventory counters')
    reader=d['standalone_reader_receipt']
    required={'status':'PASS_SAVED_FILE_INTEGRITY','archive_sha256':archive['sha256'],'manifest_sha256':a['inputs']['addon_manifest']['sha256'],'source_sha256':a['helper_pins']['verify_saved_evidence.py'],'test_sha256':a['helper_pins']['test_verify_saved_evidence.py'],'files':len(selected),'expanded_bytes':sum(r['bytes'] for r in selected)+len(c.encode(manifest)),'archive_bytes':ex['archive_bytes'],'extracted_selected_files_checked':True,'scientific_code_executed':False,'extra_extracted_files_not_checked':True}
    if any(type(reader.get(k)) is not type(v) or reader[k]!=v for k,v in required.items()):raise ValueError('standalone reader exact transport identity/status')

def build_rows(root,a,d,old_input,old_manifest):
    qa=d['qa'];config=d['config'];qmap,external=p.qa_paths(root,qa,config)
    if qa.get('status')!='PASS_TECHNICAL_PREPARATION' or qa.get('config_sha256')!=a['inputs']['config']['sha256'] or config.get('schema')!='v9-final-qa-1' or config.get('edition')!=p.EDITION or config.get('finalization_authorized') is not True or config.get('content_contract')!=p.COUNTS:raise ValueError('actual V9 final QA/config')
    cp=local(root,Path(p.EDITION)/qa['config_path'])
    if cp!=a['inputs']['config']['source'] or qmap.get(cp,('',None))[1]!=qa['config_sha256']:raise ValueError('exact QA config source')
    rows=legacy_rows(old_input,old_manifest);names={r['target'].casefold() for r in rows}
    def add(source,target,role,h,**extra):
        source=local(root,source);p.permitted(source);p.permitted(target);c.pin(h)
        if target.casefold() in names:raise ValueError('duplicate selected target')
        sp=c.path(root,source)
        if not stat.S_ISREG(sp.stat().st_mode):raise ValueError('regular selected source')
        if source in qmap:
            key,qh=qmap[source]
            if qh!=h:raise ValueError('conflicting QA selection hash')
            extra['qa_key']=key
        if role in {'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','figure','source_image_alias','review'} and 'qa_key' not in extra:raise ValueError('QA-bound role required')
        rows.append({'source':source,'target':target,'role':role,'sha256':h,'bytes':sp.stat().st_size,**extra});names.add(target.casefold())
    for kind,n in [('main',33),('supplement',101)]:
        doc=qa['documents'][kind]
        if doc['pages']!=n or doc['counts']!=p.COUNTS[kind] or len(doc['visual'])!=n or {r['page'] for r in doc['visual']}!=set(range(1,n+1)):raise ValueError('134-page actual review coverage')
        for ext,key in [('pdf','pdf'),('docx','docx'),('md','reading_source' if kind=='supplement' else 'source')]:
            art=doc['artifacts'][key];source=local(root,art['path'])
            if not source.startswith(p.EDITION+'/'):raise ValueError('current edition document only')
            add(source,'manuscript/'+kind+'.'+ext,kind+('_source' if ext=='md' else '_'+ext),art['sha256'])
        art=doc['artifacts']['source'];add(art['path'],'authoring_provenance/'+kind+'.complete.build.md','build_source_snapshot',art['sha256'])
    for stem in FIGURES:
        for ext in ['png','pdf','svg']:
            src=p.EDITION+'/figures/'+stem+'.'+ext
            add(src,'figures/'+stem+'.'+ext,'figure',qmap[src][1],id=stem,format=ext)
        src=p.EDITION+'/figures/'+stem+'.png';add(src,'manuscript/figures/'+stem+'.png','source_image_alias',qmap[src][1])
    for n,role in GUIDE_ROLES.items():add(p.EDITION+'/work/package_documents/'+n,('author_approval/' if role=='author_checklist' else '')+n,role,a['guide_pins'][n])
    for n in sorted(HELPERS):add(p.EDITION+'/work/package_documents/'+n,'reproduction/v9_evidence/'+n,'evidence_reader_source',a['helper_pins'][n])
    if len(qa['review_files'])!=len(set(qa['review_files'])):raise ValueError('duplicate QA review list')
    for key in qa['review_files']:
        src=local(root,Path(p.EDITION)/key)
        add(src,'quality/reviews/'+key.replace('../','parent/'),'review',qmap[src][1])
    targets={'qa':('quality/FINAL_TECHNICAL_QA.json','technical_qa'),'config':('quality/FINAL_AUTHORIZED_CONFIG.json','final_config'),'archive':('reproduction/v9_evidence/v9_evidence.zip','private_archive'),'addon_manifest':('reproduction/v9_evidence/MANIFEST.json','evidence_manifest'),'extraction_receipt':('reproduction/v9_evidence/EXTRACTION_COMPLETE.json','evidence_receipt'),'writer_receipt':('reproduction/v9_evidence/CREATE_COMPLETE.json','evidence_receipt'),'create_approval':('reproduction/v9_evidence/CREATE_APPROVAL.json','evidence_approval'),'verify_approval':('reproduction/v9_evidence/VERIFY_APPROVAL.json','evidence_approval'),'addon_selection':('reproduction/v9_evidence/SELECTION.json','evidence_selection'),'standalone_reader_receipt':('reproduction/v9_evidence/READER_VERIFICATION.json','evidence_reader_receipt')}
    for k,(target,role) in targets.items():
        r=a['inputs'][k];add(r['source'],target,role,r['sha256'],**({'id':'v9_evidence'} if k=='archive' else {}))
    required=[]
    for source in sorted(p.REQUIRED_SOURCES):
        h=a['required_source_pins'][source];add(source,'authoring_provenance/current/'+source,'authoring_source',h);required.append({'source':source,'sha256':h})
    for source,h in sorted(a['source_pins'].items()):
        target='tools/package_v6.py' if source==p.TOOL else 'authoring_provenance/package/'+Path(source).name
        add(source,target,'package_tool' if source==p.TOOL else 'package_source',h)
    for spec in a['provenance']:
        if set(spec)!={'source','target','sha256'}:raise ValueError('explicit finite provenance spec')
        add(spec['source'],spec['target'],'package_provenance',spec['sha256'])
    # Optional public/private approvals are never inferred from technical completion.
    p.validate_records(rows)
    return {'schema':'v6-resolved-selection-1','claim':'SAVED_EVIDENCE_AND_UNCHANGED_LEGACY_REPLAYS_NOT_NEW_PORTABLE_PIPELINE','unresolved':[],'files':sorted(rows,key=lambda r:r['target']),'required_source_pins':required,'addon_receipt':a['inputs']['extraction_receipt'],'requirements':{'figure_ids':FIGURES,'figure_formats':['png','pdf','svg'],'archive_ids':sorted(p.ARCHIVES|{'v9_evidence'}),'legacy_archive_ids':sorted(p.ARCHIVES)}}

def run(root,approval,approval_sha,output):
    with c.deadline() as clock:
        rd=c.Reader(root,clock);out=c.path(rd.root,output)
        if out.exists():raise FileExistsError('preserve prior selection')
        a=c.parse(rd.check(approval,approval_sha,True))
        keys={'schema','phase','source_pins','inputs','guide_pins','helper_pins','required_source_pins','provenance','output'}
        if set(a)!=keys or a['schema']!='v6-outer-selection-approval-1' or a['phase']!='METADATA_SELECTION_ONLY' or a['output']!=output:raise ValueError('explicit metadata-only selection approval')
        expected={str((HERE/n).relative_to(rd.root)) for n in AUTH_SOURCES}
        if set(a['source_pins'])!=expected or set(a['inputs'])!=INPUTS or set(a['guide_pins'])!=set(GUIDE_ROLES) or set(a['helper_pins'])!=HELPERS or set(a['required_source_pins'])!=p.REQUIRED_SOURCES:raise ValueError('fixed input/source/guide inventory')
        if a['source_pins'].get(p.TOOL)!=p.TOOL_SHA:raise ValueError('accepted packager identity')
        for src,h in a['source_pins'].items():rd.check(src,h)
        data={}
        for name,spec in a['inputs'].items():
            if set(spec)!={'source','sha256'}:raise ValueError('input spec')
            c.safe(spec['source']);c.pin(spec['sha256'])
            if name=='archive':continue # Never hash/read the opaque ZIP here.
            raw=rd.check(spec['source'],spec['sha256'],True)
            data[name]=c.parse(raw)
        receipt_chain(a,data)
        archive=c.path(rd.root,a['inputs']['archive']['source'])
        if not archive.is_file() or archive.stat().st_size!=data['extraction_receipt']['archive_bytes']:raise ValueError('actual archive stat/receipt')
        for key in ['writer_receipt','extraction_receipt']:
            if (c.path(rd.root,a['inputs'][key]['source']).parent/'FAILURE.json').exists():raise ValueError('failed transport attempt')
        for n,h in a['guide_pins'].items():rd.check(p.EDITION+'/work/package_documents/'+n,h)
        for n,h in a['helper_pins'].items():rd.check(p.EDITION+'/work/package_documents/'+n,h)
        for src,h in a['required_source_pins'].items():rd.check(src,h)
        if not isinstance(a['provenance'],list) or len(a['provenance'])>256:raise ValueError('finite provenance cap')
        for spec in a['provenance']:
            if set(spec)!={'source','target','sha256'}:raise ValueError('provenance schema')
            c.safe(spec['target']);rd.check(spec['source'],spec['sha256'])
        old=c.parse(rd.check(p.OLD+'/MANIFEST.json',p.OLD_SHA,True));old_input=c.parse(rd.check(p.OLD+'/INPUT_MANIFEST.json',OLD_INPUT_SHA,True))
        selection=build_rows(rd.root,a,data,old_input,old)
        # STAT every opaque selected payload; end hashes only consumed metadata/source.
        for r in selection['files']:
            if c.path(rd.root,r['source']).stat().st_size!=r['bytes']:raise ValueError('selected size drift')
        rd.end();c.publish(out,selection,clock)
        return {'status':'OUTER_SELECTION_ONLY_NOT_INVENTORY_OR_ASSEMBLY','files':len(selection['files']),'bytes':sum(r['bytes'] for r in selection['files']),'sha256':c.digest(out.read_bytes()),'scientific_payloads_read':False}
if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for n in ['root','approval','approval-sha256','output']:ap.add_argument('--'+n,required=True)
    a=ap.parse_args();print(run(a.root,a.approval,a.approval_sha256,a.output))
