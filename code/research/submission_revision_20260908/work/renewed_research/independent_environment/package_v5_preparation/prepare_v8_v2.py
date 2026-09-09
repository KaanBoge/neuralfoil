"""Explicitly authorized metadata inventory only; unchanged V4 wire-format helper.

No default discovery, assembly, extraction, code fitting or scientific replay.
"""
from pathlib import Path
import argparse,hashlib,json,types,re

EDITION='submission_revision_20260908/renewed_manuscript_v8'
OLD='submission_revision_20260908/renewed_manuscript_v7/deliverables/NeuralFoil_Private_Submission_Package_v4'
OLD_MANIFEST='a14fcee7c9ea63629395d150baa3e1006e841c3de321dc94834c6acde3f95854'
OLD_INPUT='657f465632d82ea10aba4bee71e97593b8023a6789bb44958ee6b642ed121994'
TOOL='submission_revision_20260908/work/renewed_research/package_v4_tools/package_v4.py'
TOOL_SHA='d3ce20b1d959487cc2c4f5c7b35a3d2ca36ab11a3e6f6434d654e664f601f141'
FIGURES=['method_roles','accuracy_harm','calibration_utility','external_complete_eligible','measurement_label_sensitivity','confidence_rule_illustration']
ARCHIVES={'feature','correction','bounds','references','incremental_harm','label_sensitivity'}
GUIDES={'README.md':'readme','NAVIGATION.md':'navigation','PERMISSIONS.md':'permissions','REPLAY_GUIDE.md':'replay_guide','AUTHOR_CHECKLIST.md':'author_checklist'}
COUNTS={'main':[17,133,4,4],'supplement':[39,298,35,2],'references':21}
NEW_ROLES={'qualified_displays','qualified_display_review','qualified_arithmetic_review','qualified_h_report','qualified_kl_report','qualified_h_portable','qualified_kl_portable','qualified_h_replay','qualified_kl_default_replay','qualified_kl_isolated_replay','paired_sole_model_producer','paired_sole_model_replay','paired_sole_model_review'}
CAP=512*1024**2
def digest(b):return hashlib.sha256(b).hexdigest()
def parse(b):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    return json.loads(b,object_pairs_hook=pairs)
def pin(h):
    if not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('explicit SHA256 required')
def relative(root,path):
    p=Path(path);p=p if p.is_absolute() else root/p
    if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('symlink')
    p=p.resolve()
    if not p.is_relative_to(root):raise ValueError('outside project')
    return p
def checked(root,path,h):
    pin(h);p=relative(root,path);b=p.read_bytes()
    if digest(b)!=h:raise ValueError('hash mismatch '+str(p))
    return b
def permitted(name):
    s=name.lower();parts=Path(s).parts
    if any(x in s for x in ['all_context','downstream','inference_benchmark','volume4','volume_4','sealed']):raise ValueError('excluded scientific scope')
    if any(x.startswith(('venv','conda')) or x in {'.venv','.git','__pycache__','site-packages','pkgs','envs','.cache','cache'} for x in parts[:-1]):raise ValueError('environment/cache scope')
def authorization(root,path,h,output):
    # This barrier precedes any package metadata or scientific payload enumeration.
    raw=checked(root,path,h);a=parse(raw)
    keys={'authorized_phase','qa','qa_sha256','builder_sha256','packager_sha256','selection','selection_sha256','guide_sha256','output','max_payload_bytes'}
    if set(a)!=keys or a['authorized_phase']!='prepare_private_package_v5_inventory_for_v8':raise ValueError('root inventory authorization required')
    if a['builder_sha256']!=digest(Path(__file__).read_bytes()) or a['packager_sha256']!=TOOL_SHA:raise ValueError('authorized source identity')
    if type(a['max_payload_bytes'])!=int or a['max_payload_bytes']!=CAP:raise ValueError('fixed payload cap')
    if relative(root,a['output'])!=relative(root,output):raise ValueError('output authorization')
    if set(a['guide_sha256'])!=set(GUIDES):raise ValueError('explicit root guide pins')
    for v in a['guide_sha256'].values():pin(v)
    return a,raw
def qa_contract(root,qa):
    if qa.get('status')!='PASS_TECHNICAL_PREPARATION':raise ValueError('actual passed QA required')
    edition=root/EDITION;qmap={}
    for key,h in qa['files'].items():
        p=relative(root,edition/key);pin(h)
        if p in qmap and qmap[p][1]!=h:raise ValueError('conflicting QA pin')
        qmap[p]=(key,h)
    cp=relative(root,edition/qa['config_path']);cb=checked(root,cp,qa['config_sha256'])
    if qmap.get(cp,('',None))[1]!=qa['config_sha256']:raise ValueError('config QA binding')
    c=parse(cb)
    if c.get('schema')!='v8-final-qa-1' or c.get('finalization_authorized') is not True or c.get('edition')!=EDITION or c.get('content_contract')!=COUNTS:raise ValueError('authorized V8 config required')
    if not NEW_ROLES<={e['role'] for e in c['evidence']}:raise ValueError('qualified/sole-paired evidence missing')
    for k,n in [('main',30),('supplement',80)]:
        d=qa['documents'][k]
        if d['pages']!=n or d['counts']!=COUNTS[k] or {r['page'] for r in d['visual']}!=set(range(1,n+1)) or len(d['visual'])!=n:raise ValueError('V8 count/visual contract')
        if c['documents'][k]['pages']!=n:raise ValueError('config page mismatch')
    helper=[e for e in c['evidence'] if e['sha256']==qa['helper_sha256'] and e['path'].endswith('.py')]
    if len(helper)!=1:raise ValueError('unique explicit finalizer helper')
    hp=relative(root,helper[0]['path'])
    if qmap.get(hp,('',None))[1]!=qa['helper_sha256']:raise ValueError('helper QA binding')
    checked(root,hp,qa['helper_sha256'])
    return qmap,c,cp,hp
def historical_records(old_input,old_manifest):
    """Resolve only immutable V4 package payloads, never old mutable sources."""
    records=[]
    if len(old_manifest['files'])!=334:raise ValueError('original 334-payload manifest required')
    for row in old_input['files']:
        name=row['target'];old=old_manifest['files'][name]
        if old['sha256']!=row['sha256'] or old['bytes']!=row['bytes']:raise ValueError('legacy input/payload disagreement')
        if row['role'] in {'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','figure','source_image_alias','readme','navigation','permissions','replay_guide','author_checklist'}:continue
        target=name if name.startswith('reproduction/') else 'historical/v4/'+name
        role='private_archive' if row['role']=='private_archive' else ('environment_receipt' if row['role']=='environment_receipt' else 'legacy_evidence')
        r={'source':OLD+'/'+name,'target':target,'role':role,'sha256':old['sha256']}
        if role=='private_archive':r.update(id=row['id'],legacy_member=name)
        records.append(r)
    if {r['id'] for r in records if r['role']=='private_archive'}!=ARCHIVES:raise ValueError('six unchanged archives required')
    return records
def prepare(root,approval,approval_sha,output):
    root=Path(root).resolve();out=relative(root,output)
    if out.exists():raise FileExistsError('inventory collision')
    a,ab=authorization(root,approval,approval_sha,out)
    qb=checked(root,a['qa'],a['qa_sha256']);qa=parse(qb);qmap,c,cp,hp=qa_contract(root,qa)
    toolraw=checked(root,TOOL,TOOL_SHA);tool=types.ModuleType('pinned_v4_packager');exec(compile(toolraw,TOOL,'exec'),tool.__dict__)
    selection_raw=checked(root,a['selection'],a['selection_sha256']);selection=parse(selection_raw)
    if selection['status']!='SOURCE_SELECTION_ONLY_NOT_AUTHORIZED_INVENTORY':raise ValueError('selection schema')
    if not NEW_ROLES<={r['evidence_role'] for r in selection['files']}:raise ValueError('finite evidence selection incomplete')
    old=parse(checked(root,OLD+'/MANIFEST.json',OLD_MANIFEST));old_input=parse(checked(root,OLD+'/INPUT_MANIFEST.json',OLD_INPUT))
    records=[];targets=set();total=0
    def add(source,target,role,expected,**extra):
        nonlocal total
        permitted(str(source));permitted(target);tool.safe(target)
        if target.casefold() in targets:raise ValueError('duplicate target')
        sp=relative(root,source);bound=qmap.get(sp)
        if role in tool.BOUND_ROLES and bound is None:raise ValueError('required QA binding')
        if bound:
            if bound[1]!=expected:raise ValueError('conflicting QA/evidence pin')
            extra['qa_key']=bound[0]
        size=sp.stat().st_size
        if total+size>CAP:raise ValueError('payload cap before read')
        checked(root,sp,expected);total+=size;targets.add(target.casefold())
        records.append({'source':sp.relative_to(root).as_posix(),'target':target,'role':role,'sha256':expected,'bytes':size,**extra})
    for r in historical_records(old_input,old):
        r=dict(r);source=r.pop('source');target=r.pop('target');role=r.pop('role');h=r.pop('sha256');add(source,target,role,h,**r)
    for kind in ['main','supplement']:
        for ext in ['pdf','docx','source']:
            key='reading_source' if kind=='supplement' and ext=='source' else ext
            art=qa['documents'][kind]['artifacts'][key];p=relative(root,art['path'])
            if not p.is_relative_to(root/EDITION):raise ValueError('publication must be current V8')
            add(p,'manuscript/'+kind+('.md' if ext=='source' else '.'+ext),kind+'_'+ext,art['sha256'])
        art=qa['documents'][kind]['artifacts']['source'];add(art['path'],'authoring_provenance/'+kind+'.complete.build.md','build_source_snapshot',art['sha256'])
    for f in FIGURES:
        for ext in ['png','pdf','svg']:
            p=root/EDITION/'figures'/f'{f}.{ext}'
            if p not in qmap:raise ValueError('final figure not QA pinned')
            add(p,f'figures/{f}.{ext}','figure',qmap[p][1],id=f,format=ext)
        p=root/EDITION/'figures'/f'{f}.png';add(p,f'manuscript/figures/{f}.png','source_image_alias',qmap[p][1])
    for name,role in GUIDES.items():add(root/EDITION/'work/package_documents'/name,('author_approval/' if role=='author_checklist' else '')+name,role,a['guide_sha256'][name])
    for r in selection['files']:
        p=relative(root,r['source'])
        if qmap.get(p,('',None))[1]!=r['sha256']:raise ValueError('selected evidence not final QA pinned')
        extra={};role='scientific_evidence'
        if r['evidence_role'] in {'qualified_h_portable','qualified_kl_portable'}:
            role='private_archive';extra['id']='qualified_harm' if r['evidence_role']=='qualified_h_portable' else 'qualified_kl_harm'
        add(p,r['target'],role,r['sha256'],evidence_role=r['evidence_role'],**extra)
    for key in qa['review_files']:
        p=relative(root,root/EDITION/key);add(p,'quality/reviews/'+key.replace('../','parent/'),'review',qmap[p][1])
    add(a['qa'],'quality/FINAL_TECHNICAL_QA.json','technical_qa',a['qa_sha256'])
    add(cp,'quality/FINAL_AUTHORIZED_CONFIG.json','final_config',qa['config_sha256'])
    add(hp,'authoring_provenance/finalizer/'+hp.name,'qa_helper',qa['helper_sha256'])
    add(TOOL,'tools/package_v4.py','package_tool',TOOL_SHA)
    add(a['selection'],'authoring_provenance/EVIDENCE_SELECTION.json','selection_source',a['selection_sha256'])
    add(approval,'quality/INVENTORY_AUTHORIZATION.json','inventory_authorization',approval_sha)
    add(Path(__file__),'authoring_provenance/prepare_v8_v2.py','inventory_builder',a['builder_sha256'])
    m={'schema':'private_submission_inputs_v4','package_name':'NeuralFoil_Private_Submission_Package_v5','manuscript_edition':'V8','package_revision':5,'wire_format_version':4,'technical_approval':'APPROVED_FOR_PRIVATE_ASSEMBLY','human_author_approval':False,'public_release':False,'max_payload_bytes':CAP,'qa_binding':{'edition':EDITION,'source':relative(root,a['qa']).relative_to(root).as_posix(),'sha256':a['qa_sha256']},'legacy_witness':{'source':OLD+'/MANIFEST.json','sha256':OLD_MANIFEST},'requirements':{'figure_ids':FIGURES,'figure_formats':['png','svg','pdf'],'archive_ids':sorted(ARCHIVES|{'qualified_harm','qualified_kl_harm'}),'legacy_archive_ids':sorted(ARCHIVES)},'files':sorted(records,key=lambda r:r['target'])}
    # Reuse exact role binding without doing archive assembly or full payload buffering.
    tool.qa_binding(root,m,{'quality/FINAL_TECHNICAL_QA.json':qb})
    names=[r['target'].casefold() for r in records]
    if set(names)&{'manifest.json','input_manifest.json'} or any(x!=y and y.startswith(x+'/') for x in names for y in names):raise ValueError('reserved target or file/directory collision')
    for r in records:checked(root,r['source'],r['sha256'])
    checked(root,a['qa'],a['qa_sha256']);checked(root,approval,approval_sha);checked(root,TOOL,TOOL_SHA)
    tool.dump(out,m)
    return {'status':'INVENTORY_PREPARED_NOT_ASSEMBLED','files':len(records),'bytes':total,'sha256':digest(out.read_bytes())}
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['project','approval','approval-sha256','output']:p.add_argument('--'+k,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.project,a.approval,a.approval_sha256,a.output),indent=2))
