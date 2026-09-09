"""Standard-library source integrity only; never import archived research code."""
import hashlib,json
from pathlib import Path,PurePosixPath

def verify(root):
    root=Path(root).resolve();base=root/'code/supplement'
    manifest_path=root/'code/supplement-manifest.json'
    if manifest_path.is_symlink() or base.is_symlink() or (root/'code').is_symlink():raise ValueError('Symlink boundary')
    m=json.loads(manifest_path.read_text());entries=m['files'];expected=set()
    if m.get('schema')!='reviewed-source-supplement-v1' or type(m.get('file_count')) is not int or m['file_count']!=len(entries):raise ValueError('Manifest schema/count')
    for r in entries:
        name=r['target'];p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or p.as_posix()!=name or p.parts[:2]!=('code','supplement') or p.suffix!='.py' or name in expected:raise ValueError('Invalid source path')
        expected.add(name);q=root/p
        if any(x.is_symlink() for x in [q,*q.parents] if x!=root and x.is_relative_to(root)):raise ValueError('Source symlink')
        b=q.read_bytes()
        if type(r['published_bytes']) is not int or len(b)!=r['published_bytes'] or hashlib.sha256(b).hexdigest()!=r['published_sha256']:raise ValueError('Source identity mismatch')
    actual={p.relative_to(root).as_posix() for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    if actual!=expected:raise ValueError('Missing/unlisted source files')
    return len(entries)

if __name__=='__main__':
    print('PASS:',verify(Path(__file__).resolve().parents[1]),'supplemental source files match their public manifest.')
    print('Integrity only; no research modules, models or measurements loaded.')
