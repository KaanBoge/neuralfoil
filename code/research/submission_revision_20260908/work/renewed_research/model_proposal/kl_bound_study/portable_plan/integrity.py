"""Prototype private-bundle integrity helpers. Real export requires separate approval.

No project data lookup or replay on import. Caller supplies bytes explicitly.
"""
from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import stat
import zipfile

MAX_MEMBERS=512
MAX_BYTES=256*1024*1024

def sha(data):return hashlib.sha256(data).hexdigest()

def member_name(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name:
        raise ValueError('canonical relative member required')
    if any(ord(c)<32 or 127<=ord(c)<=159 for c in name):
        raise ValueError('control characters forbidden')
    p=PurePosixPath(name)
    if not p.parts or p.is_absolute() or str(p)!=name or any(v in ('','.','..') for v in p.parts):
        raise ValueError('unsafe member path')
    return name

def names_ok(names):
    seen=set()
    for name in names:
        member_name(name)
        folded=name.casefold()
        if folded in seen:raise ValueError('duplicate or case-colliding member')
        seen.add(folded)
    for name in seen:
        if any('/'.join(name.split('/')[:i]) in seen for i in range(1,len(name.split('/')))):
            raise ValueError('file/directory member collision')

def new_target(path):
    path=Path(path).absolute()
    for component in (path,*path.parents):
        if component.is_symlink():raise ValueError('symlink destination or ancestor')
    if path.exists():raise FileExistsError('refuse overwrite')
    if not path.parent.is_dir():raise ValueError('existing non-symlink parent required')
    return path

def build_private_zip(payload,destination):
    """Build a private bytes-only archive; tests use synthetic bytes exclusively."""
    if not isinstance(payload,dict) or not payload or len(payload)+1>MAX_MEMBERS:
        raise ValueError('bounded nonempty payload required')
    names_ok(list(payload)+['manifest.json'])
    if any(not isinstance(v,bytes) for v in payload.values()):raise ValueError('immutable bytes required')
    if sum(map(len,payload.values()))>MAX_BYTES:raise ValueError('payload size cap')
    manifest={'format':'qualified_private_replay_v1','private_contains_measurements':True,
        'release_permission_resolved':False,'human_release_approval':False,
        'files':{k:{'sha256':sha(v),'bytes':len(v)} for k,v in sorted(payload.items())}}
    raw=json.dumps(manifest,sort_keys=True,indent=2,allow_nan=False).encode()+b'\n'
    members=dict(payload,**{'manifest.json':raw})
    if sum(map(len,members.values()))>MAX_BYTES:raise ValueError('total size cap')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,data in sorted(members.items()):
            info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
            info.external_attr=(stat.S_IFREG|0o644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,data)
    archive=stream.getvalue();path=new_target(destination)
    with path.open('xb') as f:f.write(archive)
    return {'archive_sha256':sha(archive),'manifest_sha256':sha(raw),'payload_files':len(payload),
            'archive_bytes':len(archive),'uncompressed_bytes':sum(map(len,members.values()))}

def verified_members(archive_path,archive_sha256,manifest_sha256):
    """Authenticate exact archive bytes and all payloads before returning any."""
    path=Path(archive_path)
    if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('archive symlink or ancestor')
    raw=path.read_bytes()
    if sha(raw)!=archive_sha256:raise ValueError('archive authentication failed')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if not 1<len(infos)<=MAX_MEMBERS or sum(x.file_size for x in infos)>MAX_BYTES:
            raise ValueError('archive inventory/size cap')
        names_ok([x.filename for x in infos])
        for item in infos:
            mode=item.external_attr>>16
            if item.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0,stat.S_IFREG)) or item.flag_bits&1:
                raise ValueError('only unencrypted regular files supported')
        data={item.filename:z.read(item) for item in infos}
    manifest_raw=data.pop('manifest.json')
    if sha(manifest_raw)!=manifest_sha256:raise ValueError('manifest authentication failed')
    manifest=json.loads(manifest_raw)
    if manifest.get('format')!='qualified_private_replay_v1' or manifest.get('human_release_approval') is not False or manifest.get('release_permission_resolved') is not False or manifest.get('private_contains_measurements') is not True:
        raise ValueError('private research scope mismatch')
    if set(manifest['files'])!=set(data):raise ValueError('member inventory mismatch')
    for name,value in data.items():
        expected=manifest['files'][name]
        if set(expected)!={'sha256','bytes'} or expected['bytes']!=len(value) or expected['sha256']!=sha(value):
            raise ValueError('payload authentication failed')
    return data,manifest_raw

def extract_verified(archive_path,archive_sha256,manifest_sha256,destination):
    """No code execution. Verify every member before creating destination."""
    data,manifest=verified_members(archive_path,archive_sha256,manifest_sha256)
    target=new_target(destination)
    target.mkdir()
    for name,value in dict(data,**{'manifest.json':manifest}).items():
        out=target.joinpath(*PurePosixPath(name).parts)
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('xb') as f:f.write(value)
    return target

def inspect_safe_npz(raw,expected_keys):
    """Safe-array schema preflight, never unpickles; caller supplies authenticated bytes."""
    import numpy as np
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)>MAX_MEMBERS or sum(v.file_size for v in infos)>MAX_BYTES:raise ValueError('NPZ size cap')
        names_ok([x.filename for x in infos])
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        if set(z.files)!=set(expected_keys):raise ValueError('NPZ member schema mismatch')
        out={}
        for key in z.files:
            a=z[key]
            if a.dtype.hasobject:raise ValueError('object arrays forbidden')
            out[key]={'shape':list(a.shape),'dtype':a.dtype.str,'bytes':int(a.nbytes)}
    return out
