"""Finite V9 source assembly; no discovery, scientific calculation or rendering.

Root supplies and authorizes the exact config pin. Draft preparation alone does
not invoke this module. Every successful version has an immutable full snapshot.

Publication of three current aliases is ordered, not a filesystem transaction.
If interrupted, preserve snapshots and partial aliases; do not rerun automatically.
A reviewer must authenticate the snapshot and each alias, then separately authorize
manual restoration or completion. Ordinary execution rejects mixed predecessors.
"""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,os,re

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
TOKENS={'@@PAIRED_TABLES@@':['S36','S37','S38'],
        '@@FOUR_TREE_DOWNSTREAM@@':['S39','S40','S41'],
        '@@TIMING_TABLES@@':['S42','S43','S44']}
LABEL_MAP={('A: ','A '),('B: ','B '),('SG exposed','SG'),('W new challenge','W'),
           ('eligible only/','Eligible '),('/',' '),('Leave out all uiuc','Holdout all UIUC'),
           ('Leave outall uiuc','Holdout allUIUC')}
EVIDENCE={'v8_staging_chain','paired_display_chain','four_tree_display_chain','runtime_display_chain'}
CAPTION=re.compile(r'^Table ([A-Z]*\d+)\..*$',re.M)
TABLE=re.compile(r'^\|.*(?:\n\|.*)*',re.M)
RESERVED='NAVIGATION_PLACEHOLDER'
MAX_BYTES=256*2**20

def sha(raw):return hashlib.sha256(raw).hexdigest()
def pin(value):
    return type(value) is str and len(value)==64 and all(x in '0123456789abcdef' for x in value)
def unique(items):
    result={}
    for k,v in items:
        if k in result:raise ValueError('duplicate JSON key')
        result[k]=v
    return result
def parse(raw):
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def path(root,value):
    p=PurePosixPath(value)
    if not value or p.is_absolute() or str(p)!=value or '..' in p.parts or '\\' in value or any(ord(c)<32 for c in value):raise ValueError('noncanonical relative path')
    result=Path(root)/value
    if any(p.is_symlink() for p in [result,*result.parents]):raise ValueError('symlink input/output')
    return result
def raw_file(p):
    if any(x.is_symlink() for x in [p,*p.parents]) or not p.is_file() or p.stat().st_size>MAX_BYTES:raise ValueError('bounded nonsymlink regular input')
    return p.read_bytes()
def references(text):
    if text.count('# References')!=1 or not re.search(r'^# References$',text,re.M):raise ValueError('one exact References heading')
    section=text[text.index('# References'):]
    ids=[int(v) for v in re.findall(r'^\[(\d+)\]',section,re.M)]
    if ids!=list(range(1,22)):raise ValueError('exact21 ordered references')
    return section
def tables(text):return TABLE.findall(text)
def captions(text):return [m.group(0) for m in CAPTION.finditer(text)]
def preserved(old,new,expected_tables,expected_captions):
    blocks=tables(old);caps=captions(old)
    if len(blocks)!=expected_tables or len(caps)!=expected_captions:raise ValueError('old table/caption scope')
    # Exact ordered subsequence, retaining duplicate blocks as distinct occurrences.
    for source,output,kind in [(blocks,tables(new),'table'),(caps,captions(new),'caption')]:
        pos=0
        for value in source:
            try:pos=output.index(value,pos)+1
            except ValueError:raise ValueError('old '+kind+' bytes/order changed') from None
    if references(old)!=references(new):raise ValueError('old reference bytes changed')
    return {'pipe_tables':len(blocks),'captions':len(caps),'table_sha256':[sha(v.encode()) for v in blocks],'caption_sha256':[sha(v.encode()) for v in caps],'references_sha256':sha(references(old).encode())}
def clean(text,kind):
    if re.search(r'@@|\bTODO\b|\bTBD\b',text):raise ValueError('unresolved source token')
    n=text.count(RESERVED)
    if (kind=='supplement' and (n!=1 or not re.search(r'^NAVIGATION_PLACEHOLDER$',text,re.M))) or (kind=='main' and n):raise ValueError('reserved navigation token scope')
    if re.search(r'^Table [PTF]\d+\.',text,re.M):raise ValueError('unrenamed table caption')
def render_block(text,spec,token):
    if set(spec)!={'input','caption_renames','p2_label_map'}:raise ValueError('exact block specification')
    pairs=spec['caption_renames'];maps=spec['p2_label_map']
    if len(pairs)!=3 or len({p[0] for p in pairs})!=3 or [p[1] for p in pairs]!=TOKENS[token]:raise ValueError('exact3 ordered caption renames')
    if token=='@@PAIRED_TABLES@@' and [p[0] for p in pairs]!=['P1','P2','P3']:raise ValueError('paired source captions')
    if token=='@@TIMING_TABLES@@' and [p[0] for p in pairs]!=['T1','T2','T3']:raise ValueError('timing source captions')
    if maps and token!='@@PAIRED_TABLES@@':raise ValueError('label maps only paired P2')
    if len({tuple(p) for p in maps})!=len(maps) or any(tuple(p) not in LABEL_MAP for p in maps):raise ValueError('unapproved label map')
    original_tables=tables(text);active=None;lines=[]
    if len(original_tables)!=3:raise ValueError('exact three display tables')
    for line in text.splitlines(keepends=True):
        m=re.match(r'^Table ([A-Z]*\d+)\.',line)
        if m:active=m.group(1)
        if line.startswith('|') and active=='P2':
            cells=line.split('|')
            before=cells[1]
            for a,b in maps:cells[1]=cells[1].replace(a,b)
            if before!=cells[1] and not re.search('[A-Za-z]',before):raise ValueError('numeric first cell is not a reader label')
            line='|'.join(cells)
        lines.append(line)
    result=''.join(lines)
    # All cells except explicitly allowed first-column reader labels are literal.
    after=tables(result)
    if len(original_tables)!=len(after):raise ValueError('table block count changed')
    for a,b in zip(original_tables,after):
        if len(a.splitlines())!=len(b.splitlines()):raise ValueError('table row count changed')
        for x,y in zip(a.splitlines(),b.splitlines()):
            if x.split('|')[2:]!=y.split('|')[2:]:raise ValueError('data cells changed')
    for old,new in pairs:
        if not re.fullmatch('[A-Z]*[1-9][0-9]*',old):raise ValueError('caption identifier')
        pattern=r'^Table '+re.escape(old)+r'\.'
        result,n=re.subn(pattern,'Table '+new+'.',result,flags=re.M)
        if n!=1:raise ValueError('caption replacement must occur exactly once')
    return result
def compose(cfg,root):
    required={'schema','version','inputs','roles','additions','tokens','assets','evidence','predecessor'}
    if set(cfg)!=required or cfg['schema']!='V9_FINITE_ASSEMBLY_V1' or not re.fullmatch(r'v[1-9][0-9]*',cfg['version']):raise ValueError('strict config schema/version')
    if not 1<=len(cfg['inputs'])<=128:raise ValueError('finite input count')
    loaded={};pins={};total=0
    for key,spec in cfg['inputs'].items():
        if set(spec)!={'path','sha256'} or not pin(spec['sha256']):raise ValueError('exact input pin')
        p=path(root,spec['path'])
        if not spec['path'].startswith('submission_revision_20260908/') or p.suffix.lower() not in {'.md','.json','.png','.pdf','.svg'}:raise ValueError('input scope/type')
        raw=raw_file(p);total+=len(raw)
        if total>MAX_BYTES or sha(raw)!=spec['sha256']:raise ValueError('input hash/total bytes')
        loaded[key]=raw;pins[spec['path']]=spec['sha256']
    if set(cfg['roles'])!={'main','supplement','v8_main','v8_supplement'} or len(set(cfg['roles'].values()))!=4:raise ValueError('source roles')
    for role,key in cfg['roles'].items():
        expected='renewed_manuscript_v8' if role.startswith('v8_') else 'renewed_manuscript_v9'
        name={'main':'manuscript.md','supplement':'supplement.md','v8_main':'main.complete.md','v8_supplement':'supplement.complete.md'}[role]
        if not cfg['inputs'][key]['path'].endswith('/'+expected+'/'+name):raise ValueError('explicit edition source role')
    if len(cfg['additions'])!=2 or len(set(cfg['additions']))!=2 or set(cfg['tokens'])!=set(TOKENS):raise ValueError('fixed additions/tokens')
    if set(cfg['evidence'])!=EVIDENCE:raise ValueError('explicit evidence roles')
    used=set(cfg['roles'].values())|set(cfg['additions'])|set(cfg['assets'])|set(cfg['evidence'].values())|{v['input'] for v in cfg['tokens'].values()}
    if used!=set(loaded):raise ValueError('unmapped or missing finite input')
    if len(cfg['assets'])!=18 or len(set(cfg['assets']))!=18:raise ValueError('eighteen figure assets')
    assetpaths=[Path(cfg['inputs'][k]['path']) for k in cfg['assets']]
    if any('/renewed_manuscript_v9/figures/' not in str(p) for p in assetpaths):raise ValueError('current figure alias identity')
    stems={p.stem for p in assetpaths}
    if len(stems)!=6 or any({p.suffix for p in assetpaths if p.stem==stem}!={'.png','.pdf','.svg'} for stem in stems):raise ValueError('six figure stems three formats each')
    texts={k:v.decode('utf-8') for k,v in loaded.items() if k not in cfg['assets']}
    main=texts[cfg['roles']['main']];supp=texts[cfg['roles']['supplement']]
    if any(token in main or token in supp for token in TOKENS):raise ValueError('tokens only in explicitly inserted additions')
    if supp.count('# References')!=1:raise ValueError('unique supplementary insertion point')
    additions='\n\n'.join(texts[k].rstrip('\n') for k in cfg['additions'])+'\n\n'
    for token,spec in cfg['tokens'].items():
        if additions.count(token)!=1:raise ValueError('token must occur exactly once')
        additions=additions.replace(token,render_block(texts[spec['input']],spec,token))
    supp=supp.replace('# References',additions+'# References',1)
    audit={'main':preserved(texts[cfg['roles']['v8_main']],main,4,4),'supplement':preserved(texts[cfg['roles']['v8_supplement']],supp,36,35)}
    for kind,text in [('main',main),('supplement',supp)]:clean(text,kind)
    if len(captions(main))!=4 or len(captions(supp))!=44 or len(tables(main))!=4 or len(tables(supp))!=45:raise ValueError('final table inventory')
    if [m.group(1) for m in CAPTION.finditer(supp)]!=['S'+str(i) for i in range(1,45)]:raise ValueError('ordered supplementary captions')
    pngs={str(p).split('/renewed_manuscript_v9/',1)[1] for p in assetpaths if p.suffix=='.png'}
    image_audit={}
    for kind,text in [('main',main),('supplement',supp)]:
        links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text)
        if len(links)!=(4 if kind=='main' else 2):raise ValueError('figure link count')
        for value in links:
            if value not in pngs or str(PurePosixPath(value))!=value or '..' in PurePosixPath(value).parts:raise ValueError('unresolved figure alias')
        image_audit[kind]=links
    report={'status':'ASSEMBLED_NOT_RENDERED_OR_VISUALLY_VERIFIED','version':cfg['version'],'inputs':pins,'old_table_preservation':audit,'counts':{'main_tables':4,'supplement_tables':45,'main_captions':4,'supplement_captions':44,'references_each':21,'figure_assets':18},'figure_links':image_audit,'evidence':{role:cfg['inputs'][key] for role,key in cfg['evidence'].items()},'asset_sha256':{cfg['inputs'][k]['path']:cfg['inputs'][k]['sha256'] for k in cfg['assets']}}
    report['word_counts_whitespace']={'main':len(main.split()),'supplement':len(supp.split())}
    report['evidence_scope']='Exact selected file-pin authentication and table/reference preservation; no scientific replay or automatic transitive evidence discovery'
    return {'main.complete.md':main.encode(),'supplement.complete.md':supp.encode()},report

def write_new(p,raw):
    with p.open('xb') as f:
        if f.write(raw)!=len(raw):raise OSError('short write')
        f.flush();os.fsync(f.fileno())
def publish(cfg,config_raw,config_path,root,here):
    assembler_raw=Path(__file__).read_bytes()
    outputs,report=compose(cfg,root)
    version=path(here,'work/assembly_versions/'+cfg['version'])
    if version.exists():raise FileExistsError('immutable version exists')
    aliases={'main.complete.md':here/'main.complete.md','supplement.complete.md':here/'supplement.complete.md','ASSEMBLY.json':here/'work/ASSEMBLY.json'}
    previous=cfg['predecessor']
    if previous is None:
        if cfg['version']!='v1' or any(p.exists() for p in aliases.values()):raise ValueError('initial alias collision')
    else:
        if set(previous)!={'version','sha256'} or not re.fullmatch(r'v[1-9][0-9]*',previous['version']) or set(previous['sha256'])!=set(aliases):raise ValueError('explicit predecessor triplet')
        if int(cfg['version'][1:])!=int(previous['version'][1:])+1:raise ValueError('sequential explicit version')
        for n,p in aliases.items():
            expected=previous['sha256'][n]
            archived=path(here,'work/assembly_versions/'+previous['version']+'/'+n)
            if not pin(expected) or sha(raw_file(p))!=expected or raw_file(archived)!=raw_file(p):raise ValueError('predecessor alias/snapshot identity')
    report.update(config={'path':str(config_path),'sha256':sha(config_raw)},assembler_sha256=sha(assembler_raw),outputs={n:sha(b) for n,b in outputs.items()},predecessor=previous)
    receipt=(json.dumps(report,indent=2,allow_nan=False)+'\n').encode();outputs['ASSEMBLY.json']=receipt
    version.mkdir(parents=True,exist_ok=False)
    write_new(version/'CONFIG.json',config_raw)
    for n,b in outputs.items():write_new(version/n,b)
    # Reauthenticate every selected input before any current alias is replaced.
    for rel,h in report['inputs'].items():
        if sha(raw_file(path(root,rel)))!=h:raise ValueError('input changed during assembly')
    if raw_file(config_path)!=config_raw:raise ValueError('config changed during assembly')
    if Path(__file__).read_bytes()!=assembler_raw:raise ValueError('assembler changed during assembly')
    for n,p in aliases.items():
        if previous is not None and sha(raw_file(p))!=previous['sha256'][n]:raise ValueError('predecessor changed')
        if previous is None and p.exists():raise FileExistsError('alias appeared')
        temp=version/(n+'.alias.pending');write_new(temp,outputs[n]);os.replace(temp,p)
    return report
def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--config-sha256',required=True);args=p.parse_args()
    config_path=Path(args.config).absolute();raw=raw_file(config_path)
    if not pin(args.config_sha256) or sha(raw)!=args.config_sha256:raise ValueError('explicit config pin')
    cfg=parse(raw)
    publish(cfg,raw,config_path,PROJECT,HERE)
if __name__=='__main__':main()
