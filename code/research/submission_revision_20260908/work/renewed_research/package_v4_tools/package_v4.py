"""Manifest-driven private successor packaging. Standard library, no science execution."""
import argparse,hashlib,io,json,re,stat,zipfile
from pathlib import Path,PurePosixPath


def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('Duplicate JSON key')
        d[k]=v
    return d
def parse(b):return json.loads(b,object_pairs_hook=unique)
def digest(b):return hashlib.sha256(b).hexdigest()
def pin(h):
    if not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('Explicit SHA256 pin required')
def safe(name):
    if not isinstance(name,str) or not name:raise ValueError('Relative name required')
    p=PurePosixPath(name)
    if p.is_absolute() or str(p)!=name or '..' in p.parts or '.' in p.parts or '\\' in name or ':' in name or any(ord(c)<32 or 127<=ord(c)<=159 for c in name):
        raise ValueError('Unsafe path')
    return p
def no_symlink_ancestors(path):
    """Inspect the lexical path before resolution, including existing ancestors."""
    path=Path(path).absolute()
    if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('Symlink output/extraction ancestor')
    return path
def source(root,name):
    p=safe(name);q=root
    for part in p.parts:
        q=q/part
        if q.is_symlink():raise ValueError('Symlink source/member')
    if not q.is_file() or not stat.S_ISREG(q.stat().st_mode):raise ValueError('Regular file required')
    if root not in q.resolve().parents:raise ValueError('Source escapes root')
    return q
def checked(path,h):
    pin(h)
    if Path(path).is_symlink():raise ValueError('Symlink input')
    b=Path(path).read_bytes()
    if digest(b)!=h:raise ValueError('Input hash mismatch: '+str(path))
    return b
def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

BOUND_ROLES={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source','figure','source_image_alias','review'}
DOCUMENT_ROLES={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source'}
def qa_binding(root,m,buffers):
    binding=m['qa_binding'];safe(binding['edition']);safe(binding['source'])
    qa_record=next(r for r in m['files'] if r['role']=='technical_qa')
    if qa_record['source']!=binding['source'] or qa_record['sha256']!=binding['sha256']:raise ValueError('Technical QA binding mismatch')
    qa=parse(buffers[qa_record['target']])
    if qa.get('status')!='PASS_TECHNICAL_PREPARATION':raise ValueError('Technical QA not passed')
    edition=root/binding['edition'];qmap={}
    for key,h in qa['files'].items():
        if '\\' in key:raise ValueError('Invalid QA path')
        resolved=(edition/key).resolve()
        if not resolved.is_relative_to(root):raise ValueError('QA source escapes project')
        pin(h);qmap[key]=(resolved,h)
    reviews=set(qa['review_files']);seen_reviews=set()
    for r in m['files']:
        if r['role'] in BOUND_ROLES and 'qa_key' not in r:raise ValueError('Required QA pin missing: '+r['role'])
        if 'qa_key' not in r:continue
        if r['qa_key'] not in qmap:raise ValueError('Unknown QA key')
        reviewed,h=qmap[r['qa_key']]
        if r['sha256']!=h:raise ValueError('Post-QA mutation')
        if r['role'] in DOCUMENT_ROLES:
            kind,artifact=r['role'].split('_',1)
            if kind=='supplement' and artifact=='source':artifact='reading_source'
            a=qa['documents'][kind]['artifacts'][artifact]
            if Path(a['path']).resolve()!=reviewed or a['sha256']!=h:raise ValueError('QA document role mismatch')
        elif (root/r['source']).resolve()!=reviewed:raise ValueError('QA source mapping mismatch')
        if r['role']=='review':seen_reviews.add(r['qa_key'])
    if reviews!=seen_reviews:raise ValueError('Review inventory does not match QA')


def validate_inputs(root,manifest_path,expected):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Real project root required')
    root=root.resolve();raw=checked(manifest_path,expected);m=parse(raw)
    if m.get('schema')!='private_submission_inputs_v4':raise ValueError('Unknown input schema')
    if m.get('technical_approval')!='APPROVED_FOR_PRIVATE_ASSEMBLY':raise ValueError('Final technical pin approval required')
    if m.get('human_author_approval') is not False or m.get('public_release') is not False:
        raise ValueError('No author/public approval may be inferred')
    if not re.fullmatch('[A-Za-z0-9_-]+',m['package_name']):raise ValueError('Simple package name required')
    cap=m['max_payload_bytes']
    if type(cap)!=int or not 0<cap<=512*1024*1024:raise ValueError('Approved bounded payload budget required')
    records=m['files'];names=[r['target'] for r in records]
    if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('Duplicate/case-colliding targets')
    if any(a!=b and b.startswith(a+'/') for a in names for b in names):raise ValueError('File/directory collision')
    if set(names)&{'MANIFEST.json','INPUT_MANIFEST.json'}:raise ValueError('Reserved target')
    roles={r['role'] for r in records}
    required={'main_pdf','main_docx','supplement_pdf','supplement_docx','main_source','supplement_source',
              'readme','navigation','permissions','author_checklist','technical_qa','environment_receipt'}
    if not required<=roles:raise ValueError('Missing required publication/review roles')
    for role in required-{'environment_receipt'}:
        if sum(r['role']==role for r in records)!=1:raise ValueError('Ambiguous singleton role: '+role)
    wanted=m['requirements']
    figs={(r['id'],r['format']) for r in records if r['role']=='figure'}
    if len(figs)!=sum(r['role']=='figure' for r in records):raise ValueError('Duplicate figure/format')
    if figs!={(i,f) for i in wanted['figure_ids'] for f in wanted['figure_formats']}:
        raise ValueError('Figure inventory differs from approved requirements')
    archives=[r for r in records if r['role']=='private_archive']
    if len(archives)!=len(wanted['archive_ids']) or {r['id'] for r in archives}!=set(wanted['archive_ids']):
        raise ValueError('Archive inventory mismatch')
    legacy=m['legacy_witness'];old=parse(checked(source(root,legacy['source']),legacy['sha256']))
    if {r['id'] for r in archives if 'legacy_member' in r}!=set(wanted['legacy_archive_ids']):
        raise ValueError('Legacy archive mapping incomplete')
    for r in archives:
        if 'legacy_member' in r and old['files'][r['legacy_member']]['sha256']!=r['sha256']:
            raise ValueError('Original portable archive changed')
    buffers={};total=0
    for r in records:
        safe(r['target']);sp=safe(r['source'])
        if any(part.startswith(('venv_','conda_')) or part in {'site-packages','__pycache__','.venv','.git','.cache','cache','pkgs','envs'} for part in sp.parts[:-1]):
            raise ValueError('Environment/cache trees cannot be packaged')
        p=source(root,r['source']);size=p.stat().st_size
        if type(r['bytes'])!=int or size!=r['bytes']:raise ValueError('Declared size mismatch')
        total+=size
        if total>cap:raise ValueError('Payload budget exceeded')
        buffers[r['target']]=checked(p,r['sha256'])
    qa_binding(root,m,buffers)
    # Requirements, actual source pins and role inventory travel with the package.
    return m,raw,buffers


def verify(root,expected):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Real package root required')
    root=root.resolve();m=parse(checked(source(root,'MANIFEST.json'),expected))
    if m.get('schema')!='private_submission_package_v4':raise ValueError('Unknown package schema')
    actual=set()
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('Symlink in package')
        if p.is_file():actual.add(p.relative_to(root).as_posix())
        elif not p.is_dir():raise ValueError('Nonregular entry')
    if actual!=set(m['files'])|{'MANIFEST.json'}:raise ValueError('Unlisted/missing package entry')
    for name,r in m['files'].items():
        b=checked(source(root,name),r['sha256'])
        if len(b)!=r['bytes']:raise ValueError('Payload size mismatch')
    return {'status':'PASS_INTEGRITY_ONLY','files':len(m['files']),'manifest_sha256':expected,
            'scientific_code_executed':False,'author_approval':False,'redistribution_permission':False}


def assemble(root,manifest_path,expected,out):
    out=no_symlink_ancestors(out);zip_path=out.with_name(out.name+'.zip');delivery=out.with_name(out.name+'_DELIVERY.json')
    if any(p.exists() or p.is_symlink() for p in [out,zip_path,delivery]):raise FileExistsError('Preserve prior assembly attempts')
    m,raw,buffers=validate_inputs(root,manifest_path,expected)
    if out.name!=m['package_name']:raise ValueError('Approved output name mismatch')
    out.mkdir(parents=True,exist_ok=False);buffers['INPUT_MANIFEST.json']=raw
    records={}
    for name,b in buffers.items():
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(b)
        records[name]={'sha256':digest(b),'bytes':len(b)}
    dump(out/'MANIFEST.json',{'schema':'private_submission_package_v4','input_manifest_sha256':expected,
        'private':True,'human_author_approval':False,'public_release':False,'files':records})
    mh=digest((out/'MANIFEST.json').read_bytes());verified=verify(out,mh)
    with zipfile.ZipFile(zip_path,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in sorted([*buffers,'MANIFEST.json']):
            info=zipfile.ZipInfo(out.name+'/'+name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|0o644)<<16;z.writestr(info,(out/name).read_bytes())
    result={**verified,'status':'ASSEMBLED_EXTRACTION_PENDING','archive_sha256':digest(zip_path.read_bytes()),
            'archive_bytes':zip_path.stat().st_size,'input_manifest_sha256':expected,'package_name':out.name}
    dump(delivery,result);return result


def extract(archive,archive_sha,manifest_sha,dest,max_bytes=512*1024*1024):
    dest=no_symlink_ancestors(dest)
    if dest.exists() or dest.is_symlink():raise FileExistsError('Fresh extraction directory required')
    raw=checked(archive,archive_sha)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('Duplicate ZIP entry')
        if sum(i.file_size for i in infos)>max_bytes:raise ValueError('Unexpected expansion')
        roots=set()
        for i in infos:
            p=safe(i.filename);roots.add(p.parts[0])
            if len(p.parts)<2 or i.is_dir() or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Unsafe ZIP member')
            mode=stat.S_IFMT(i.external_attr>>16)
            if mode not in [0,stat.S_IFREG]:raise ValueError('Nonregular ZIP member')
        if len(roots)!=1:raise ValueError('Single package root required')
        folded=[n.casefold() for n in names]
        if any(a!=b and b.startswith(a+'/') for a in folded for b in folded):raise ValueError('ZIP file/directory collision')
        root=roots.pop();mb=z.read(root+'/MANIFEST.json');pin(manifest_sha)
        if digest(mb)!=manifest_sha:raise ValueError('Inner manifest pin mismatch')
        m=parse(mb)
        if m.get('schema')!='private_submission_package_v4':raise ValueError('Unknown package schema')
        if set(names)!={root+'/'+n for n in m['files']}|{root+'/MANIFEST.json'}:raise ValueError('ZIP inventory mismatch')
        # Authenticate every ZIP payload before any extraction writes.
        for name,r in m['files'].items():
            safe(name);b=z.read(root+'/'+name)
            if digest(b)!=r['sha256'] or len(b)!=r['bytes']:raise ValueError('ZIP payload mismatch')
        dest.mkdir(parents=True,exist_ok=False)
        for i in infos:
            p=dest/i.filename;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(z.read(i))
    return verify(dest/root,manifest_sha)


if __name__=='__main__':
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='mode',required=True)
    for mode in ['preflight','assemble']:
        p=sub.add_parser(mode);p.add_argument('--project-root',required=True);p.add_argument('--input-manifest',required=True)
        p.add_argument('--input-sha256',required=True)
        if mode=='assemble':p.add_argument('--output',required=True)
    p=sub.add_parser('verify');p.add_argument('--root',required=True);p.add_argument('--manifest-sha256',required=True)
    p=sub.add_parser('extract');p.add_argument('--archive',required=True);p.add_argument('--archive-sha256',required=True)
    p.add_argument('--manifest-sha256',required=True);p.add_argument('--destination',required=True)
    a=ap.parse_args()
    if a.mode=='preflight':
        m,_,b=validate_inputs(a.project_root,a.input_manifest,a.input_sha256);r={'status':'READY_INPUTS_ONLY','files':len(b),'bytes':sum(map(len,b.values()))}
    elif a.mode=='assemble':r=assemble(a.project_root,a.input_manifest,a.input_sha256,a.output)
    elif a.mode=='verify':r=verify(a.root,a.manifest_sha256)
    else:r=extract(a.archive,a.archive_sha256,a.manifest_sha256,a.destination)
    print(json.dumps(r,indent=2))
