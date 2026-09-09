"""Approved bounded source-text/ZIP-metadata inspection. Never imports inner code."""
from pathlib import Path,PurePosixPath
import ast,hashlib,io,json,signal,stat,time,zipfile
H=Path(__file__).resolve().parent
PKG=H.parent/'package_v5_fresh_extraction_v1/NeuralFoil_Private_Submission_Package_v5'
OUT=H/'phase1'
TEXT_CAP=16*1024**2;REPORT_CAP=8*1024**2
sha=lambda b:hashlib.sha256(b).hexdigest()
def timeout(*unused):raise TimeoutError('60-second Phase1 cap')
def safe(n):
    p=PurePosixPath(n.rstrip('/'))
    if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n or any(ord(c)<32 for c in n):raise ValueError('unsafe ZIP path')
def selected(n):
    b=PurePosixPath(n).name.lower()
    return n.endswith('.py') or b in {'readme.md','readme.txt','pyproject.toml','setup.cfg','environment.yml'} or b.startswith('requirements') and b.endswith('.txt')
def write(n,d):
    raw=json.dumps(d,indent=2,allow_nan=False).encode()+b'\n'
    used=sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    if used+len(raw)>REPORT_CAP:raise ValueError('8MiB report cap')
    with (OUT/n).open('xb') as f:f.write(raw)
def main():
    if OUT.exists():raise FileExistsError('preserve Phase1 attempt')
    OUT.mkdir();start=time.monotonic();signal.signal(signal.SIGALRM,timeout);signal.alarm(60)
    decoded=0;records=[];texts={}
    try:
        raw=(PKG/'INPUT_MANIFEST.json').read_bytes();assert sha(raw)=='0f7f6ae7ac18a61cebbeab3a7c0e25a105af5cad55e72c6c058f8962e3fc82d8'
        archives=[r for r in json.loads(raw)['files'] if r['role']=='private_archive'];assert len(archives)==8
        for row in archives:
            raw=(PKG/row['target']).read_bytes();assert sha(raw)==row['sha256']
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                infos=z.infolist();names=[i.filename for i in infos]
                assert len(names)==len(set(n.casefold() for n in names))
                for i in infos:
                    safe(i.filename);mode=stat.S_IFMT(i.external_attr>>16)
                    if mode not in (0,stat.S_IFREG,stat.S_IFDIR) or i.flag_bits&1:raise ValueError('unsupported ZIP type/encryption')
                manifest_names=[n for n in names if PurePosixPath(n).name in {'manifest.json','MANIFEST.json'}]
                manifests={}
                for n in manifest_names:
                    # Manifest metadata only; never read a data/calibration member.
                    b=z.read(n);decoded+=len(b)
                    if decoded>TEXT_CAP:raise ValueError('16MiB decoded text cap')
                    d=json.loads(b);manifests[n]={'sha256':sha(b),'top_keys':list(d),'schema':d.get('schema')}
                sources={}
                for n in sorted(x for x in names if selected(x)):
                    b=z.read(n);decoded+=len(b)
                    if decoded>TEXT_CAP:raise ValueError('16MiB decoded text cap')
                    s=b.decode('utf-8');key=row['id']+'!'+n;texts[key]=s
                    item={'sha256':sha(b),'bytes':len(b)}
                    if n.endswith('.py'):
                        tree=ast.parse(s,filename=key)
                        item['imports']=sorted({x.module or '' for x in ast.walk(tree) if isinstance(x,ast.ImportFrom)}|{v.name for x in ast.walk(tree) if isinstance(x,ast.Import) for v in x.names})
                        item['functions']=[x.name for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
                        item['tests']=[x.name for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name.startswith('test_')]
                        item['calls']=sorted({ast.unparse(x.func) for x in ast.walk(tree) if isinstance(x,ast.Call)})
                    sources[n]=item
                records.append({'id':row['id'],'archive':row['target'],'archive_sha256':row['sha256'],'members':names,'expanded_bytes_declared':sum(i.file_size for i in infos),'manifest_metadata':manifests,'source_files':sources})
            assert sha((PKG/row['target']).read_bytes())==row['sha256']
        write('SOURCE_TEXT.json',texts)
        write('INVENTORY.json',{'archives':records,'decoded_source_and_manifest_bytes':decoded,'seconds':time.monotonic()-start,'scientific_members_read':False,'inner_modules_executed':False,'source_sha256':sha(Path(__file__).read_bytes()),'status':'PHASE1_TEXT_AND_METADATA_CAPTURED_FOR_REVIEW'})
    except BaseException as e:
        write('FAILURE.json',{'exception':repr(e),'seconds':time.monotonic()-start,'completed_archives':[r['id'] for r in records],'decoded_bytes':decoded});raise
    finally:signal.alarm(0)
if __name__=='__main__':main()
