"""Source-only V9/V6 inventory preparer. Future explicit root authorization required.

No archive creation, discovery, fitting, inference, or execution of evidence code.
Only the unchanged, explicitly pinned package_v4 role validator is executed.
"""
import argparse,hashlib,json,re,stat,types
from pathlib import Path,PurePosixPath

EDITION='submission_revision_20260908/renewed_manuscript_v9'
OLD='submission_revision_20260908/renewed_manuscript_v8/deliverables/NeuralFoil_Private_Submission_Package_v5'
OLD_SHA='9158ec51bbc5414f42b338b13ca722c4d58ac93c2f5c9434312ac7842f344ba9'
TOOL='submission_revision_20260908/work/renewed_research/package_v4_tools/package_v4.py'
TOOL_SHA='d3ce20b1d959487cc2c4f5c7b35a3d2ca36ab11a3e6f6434d654e664f601f141'
COUNTS={'main':[17,133,4,4],'supplement':[43,343,44,2],'references':23}
CAP=512*1024**2
PAYLOAD_CAP=CAP-16*1024**2 # Reserve outer INPUT_MANIFEST and MANIFEST expansion.
ARCHIVES={'feature','correction','bounds','references','incremental_harm','label_sensitivity','qualified_harm','qualified_kl_harm'}
GUIDES={'README.md','NAVIGATION.md','PERMISSIONS.md','REPLAY_GUIDE.md','AUTHOR_CHECKLIST.md'}
FINALIZER_DIR='submission_revision_20260908/work/renewed_research/independent_environment/final_qa_tools/'
REQUIRED_SOURCES={FINALIZER_DIR+n for n in ['finalize_v9.py','test_finalize_v9.py','prepare_v9_final_config.py','test_prepare_v9_final_config.py']}|{EDITION+'/'+n for n in ['assemble_submission.py','test_assemble_submission.py','build_documents.py','render_version.py','audit_layout.py']}
def digest(b):return hashlib.sha256(b).hexdigest()
def pin(h):
    if not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('explicit SHA256')
def parse(b):
    def unique(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate key')
            d[k]=v
        return d
    return json.loads(b,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def safe(name):
    if not isinstance(name,str) or not name:raise ValueError('relative path required')
    p=PurePosixPath(name)
    if p.is_absolute() or str(p)!=name or '..' in p.parts or '\\' in name or ':' in name or any(ord(c)<32 or 127<=ord(c)<=159 for c in name):raise ValueError('unsafe path')
    return p
def permitted(name):
    p=safe(name);s=name.lower()
    if any(x in s for x in ['eight_tree','eight-tree','eighttree','volume4','volume_4','sealed']):raise ValueError('excluded study/data')
    if any(x.lower().startswith(('venv','conda')) or x.lower() in {'.venv','.git','__pycache__','site-packages','pkgs','envs','.cache','cache'} for x in p.parts[:-1]):raise ValueError('runtime tree excluded')
def path(root,name):
    p=root/safe(name)
    if any(q.is_symlink() for q in [p,*p.parents]):raise ValueError('symlink')
    return p
class Reads:
    def __init__(self,root):self.root=Path(root).absolute();self.pins={}
    def check(self,name,h,retain=False):
        pin(h);p=path(self.root,name)
        if not stat.S_ISREG(p.stat().st_mode):raise ValueError('regular file')
        hasher=hashlib.sha256();chunks=[]
        with p.open('rb') as f:
            while b:=f.read(1024*1024):
                hasher.update(b)
                if retain:chunks.append(b)
        if hasher.hexdigest()!=h:raise ValueError('hash mismatch '+name)
        if name in self.pins and self.pins[name]!=h:raise ValueError('conflicting input')
        self.pins[name]=h
        return b''.join(chunks) if retain else None
    def json(self,name,h):return parse(self.check(name,h,True))
    def end(self):
        for n,h in list(self.pins.items()):self.check(n,h)
def validate_records(rows):
    names=[]
    for r in rows:
        if not {'source','target','role','sha256','bytes'}<=r.keys():raise ValueError('record fields')
        permitted(r['source']);permitted(r['target']);pin(r['sha256'])
        if type(r['bytes']) is not int or r['bytes']<0:raise ValueError('size')
        names.append(r['target'].casefold())
    if len(names)!=len(set(names)) or any(a!=b and b.startswith(a+'/') for a in names for b in names):raise ValueError('target collision')
    if {'manifest.json','input_manifest.json'}&set(names):raise ValueError('reserved target')
    if sum(r['bytes'] for r in rows)>PAYLOAD_CAP:raise ValueError('payload plus manifest reserve')
def prepare(root,approval,approval_sha,output):
    rd=Reads(root);out=path(rd.root,output)
    if out.exists():raise FileExistsError('preserve previous inventory')
    a=rd.json(approval,approval_sha)
    keys={'schema','authorized_phase','preparer_sha256','packager_sha256','qa','qa_sha256','selection','selection_sha256','output','human_author_approval','public_release'}
    if set(a)!=keys or a['schema']!='v6-inventory-approval-1' or a['authorized_phase']!='PREPARE_INVENTORY_ONLY':raise ValueError('root inventory approval')
    own=Path(__file__).absolute().relative_to(rd.root).as_posix()
    if a['preparer_sha256']!=digest(Path(__file__).read_bytes()) or a['packager_sha256']!=TOOL_SHA or a['output']!=output or a['human_author_approval'] is not False or a['public_release'] is not False:raise ValueError('authority binding')
    rd.check(own,a['preparer_sha256'])
    qa=rd.json(a['qa'],a['qa_sha256'])
    if qa.get('status')!='PASS_TECHNICAL_PREPARATION':raise ValueError('final QA missing')
    qmap={}
    for n,h in qa['files'].items():
        q=(rd.root/EDITION/n)
        if any(x.is_symlink() for x in [q,*q.parents]):raise ValueError('QA symlink')
        key=q.resolve().relative_to(rd.root.resolve()).as_posix();pin(h);qmap[key]=(n,h)
    config=(Path(EDITION)/qa['config_path']).as_posix()
    config=(rd.root/config).resolve().relative_to(rd.root.resolve()).as_posix()
    c=rd.json(config,qa['config_sha256'])
    if c.get('schema')!='v9-final-qa-1' or c.get('edition')!=EDITION or c.get('finalization_authorized') is not True or c.get('content_contract')!=COUNTS:raise ValueError('V9 authorized final config')
    if qmap.get(config,('',None))[1]!=qa['config_sha256']:raise ValueError('config QA binding')
    for kind,n in [('main',33),('supplement',101)]:
        d=qa['documents'][kind]
        if d['pages']!=n or d['counts']!=COUNTS[kind] or len(d['visual'])!=n or {r['page'] for r in d['visual']}!=set(range(1,n+1)):raise ValueError('page/content coverage')
    s=rd.json(a['selection'],a['selection_sha256'])
    if s.get('schema')!='v6-resolved-selection-1' or s.get('unresolved')!=[] or s.get('claim')!='SAVED_EVIDENCE_AND_UNCHANGED_LEGACY_REPLAYS_NOT_NEW_PORTABLE_PIPELINE':raise ValueError('resolved finite selection required')
    rows=s['files'];validate_records(rows)
    singleton={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','readme','navigation','permissions','replay_guide','author_checklist','technical_qa'}
    if any(sum(r['role']==k for r in rows)!=1 for k in singleton):raise ValueError('publication singleton roles')
    if not any(r['role']=='environment_receipt' for r in rows):raise ValueError('environment receipt')
    technical=next(r for r in rows if r['role']=='technical_qa')
    if (technical['source'],technical['sha256'])!=(a['qa'],a['qa_sha256']):raise ValueError('actual QA role binding')
    wanted=s['requirements']
    if set(wanted['archive_ids'])!=ARCHIVES|{'v9_evidence'} or len(wanted['archive_ids'])!=9 or set(wanted['legacy_archive_ids'])!=ARCHIVES or len(wanted['legacy_archive_ids'])!=8:raise ValueError('fixed archive requirements')
    if {x['source'] for x in s['required_source_pins']}!=REQUIRED_SOURCES or len(s['required_source_pins'])!=len(REQUIRED_SOURCES):raise ValueError('fixed source/test list')
    legacy=rd.json(OLD+'/MANIFEST.json',OLD_SHA)
    legacy_archives=[r for r in rows if r['role']=='private_archive' and r.get('id') in ARCHIVES]
    if len(legacy_archives)!=8 or {r['id'] for r in legacy_archives}!=ARCHIVES:raise ValueError('eight original archives')
    for r in legacy_archives:
        if r['source']!=OLD+'/'+r['legacy_member'] or legacy['files'][r['legacy_member']]!={'sha256':r['sha256'],'bytes':r['bytes']}:raise ValueError('immutable legacy bytes')
    addon=[r for r in rows if r['role']=='private_archive' and r.get('id')=='v9_evidence']
    if len(addon)!=1:raise ValueError('one evidence add-on')
    # Explicit closure receipt is mandatory; size alone is not a replay claim.
    er=rd.json(s['addon_receipt']['source'],s['addon_receipt']['sha256'])
    if er.get('status')!='VERIFIED_STREAMED_EVIDENCE' or er.get('archive_sha256')!=addon[0]['sha256'] or er.get('archive_bytes')!=addon[0]['bytes'] or er.get('scientific_execution') is not False:raise ValueError('add-on integrity receipt')
    toolraw=rd.check(TOOL,TOOL_SHA,True);tool=types.ModuleType('pinned_package_v4');exec(compile(toolraw,TOOL,'exec'),tool.__dict__)
    for r in rows:
        if path(rd.root,r['source']).stat().st_size!=r['bytes']:raise ValueError('stat mismatch')
        if r['role'] in tool.BOUND_ROLES:
            key,h=qmap.get(r['source'],(None,None))
            if h!=r['sha256'] or r.get('qa_key')!=key:raise ValueError('final QA selected role')
        rd.check(r['source'],r['sha256'])
    # Every finalizer config source/test is selected explicitly, not inferred by basename.
    for spec in s['required_source_pins']:
        if not any(r['source']==spec['source'] and r['sha256']==spec['sha256'] for r in rows):raise ValueError('source/test closure')
        rd.check(spec['source'],spec['sha256'])
    nav=next(r for r in rows if r['role']=='navigation')
    text=rd.check(nav['source'],nav['sha256'],True).decode()
    if 'historical/v4/evidence/' not in text:raise ValueError('correct historical navigation required')
    m={'schema':'private_submission_inputs_v4','package_name':'NeuralFoil_Private_Submission_Package_v6','manuscript_edition':'V9','package_revision':6,'wire_format_version':4,'technical_approval':'APPROVED_FOR_PRIVATE_ASSEMBLY','human_author_approval':False,'public_release':False,'max_payload_bytes':CAP,'qa_binding':{'edition':EDITION,'source':a['qa'],'sha256':a['qa_sha256']},'legacy_witness':{'source':OLD+'/MANIFEST.json','sha256':OLD_SHA},'requirements':s['requirements'],'files':rows}
    tool.qa_binding(rd.root,m,{r['target']:rd.check(r['source'],r['sha256'],True) for r in rows if r['role']=='technical_qa'})
    rd.end()
    raw=(json.dumps(m,indent=2,allow_nan=False)+'\n').encode()
    if len(raw)>8*1024**2:raise ValueError('input manifest reserve exceeded')
    with out.open('xb') as f:f.write(raw)
    return {'status':'INVENTORY_ONLY_NOT_ASSEMBLED','files':len(rows),'payload_bytes':sum(r['bytes'] for r in rows),'sha256':digest(raw)}
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ['root','approval','approval-sha256','output']:p.add_argument('--'+k,required=True)
    a=p.parse_args();print(json.dumps(prepare(a.root,a.approval,a.approval_sha256,a.output),indent=2))
