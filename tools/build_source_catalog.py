"""Deterministic metadata catalog of source blobs in the Git index (Python 3.12+)."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

EXTENSIONS = {
    '.py': 'Python', '.js': 'JavaScript', '.mjs': 'JavaScript', '.cjs': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript', '.jsx': 'JavaScript',
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell', '.ps1': 'PowerShell',
    '.bat': 'Batch', '.cmd': 'Batch', '.ipynb': 'Jupyter Notebook',
    '.html': 'HTML', '.css': 'CSS', '.c': 'C', '.cpp': 'C++',
    '.h': 'C/C++ Header', '.hpp': 'C++', '.rs': 'Rust',
    '.f': 'Fortran', '.for': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran',
    '.f03': 'Fortran', '.f08': 'Fortran', '.cmake': 'CMake',
    '.yml': 'YAML', '.yaml': 'YAML',
}
FILENAMES = {'Makefile': 'Makefile', 'GNUmakefile': 'Makefile', 'makefile': 'Makefile',
             'CMakeLists.txt': 'CMake', 'Dockerfile': 'Dockerfile'}
CATALOG = 'code/source-catalog.json'


def language_for(path):
    name = PurePosixPath(path)
    return FILENAMES.get(name.name, EXTENSIONS.get(name.suffix.lower()))


def git(repo, *args, input=None):
    return subprocess.run(['git', '-C', str(repo), *args], input=input,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


def index_entries(repo):
    entries = {}
    for record in git(repo, 'ls-files', '--stage', '-z').split(b'\0'):
        if not record:
            continue
        metadata, raw_path = record.split(b'\t', 1)
        mode, oid, stage = metadata.decode('ascii').split()
        path = raw_path.decode('utf-8')
        if stage != '0':
            raise ValueError('Unmerged index entry: ' + path)
        if mode == '160000':
            raise ValueError('Opaque submodule cannot be cataloged: ' + path)
        if path in entries:
            raise ValueError('Duplicate index path: ' + path)
        if path.startswith('/') or any(p in ('', '.', '..') for p in path.split('/')):
            raise ValueError('Unsafe index path')
        entries[path] = (mode, oid)
    return entries


def blobs(repo, entries):
    """Read object IDs, never working-tree source bytes; validate batch framing."""
    requests = ''.join(oid + '\n' for _, oid in entries.values()).encode('ascii')
    raw = git(repo, 'cat-file', '--batch', input=requests)
    offset = 0
    result = {}
    for path, (_, expected) in entries.items():
        end = raw.index(b'\n', offset)
        oid, kind, size = raw[offset:end].decode('ascii').split()
        size = int(size)
        if oid != expected or kind != 'blob' or size < 0:
            raise ValueError('Unexpected Git object: ' + path)
        start = end + 1
        stop = start + size
        if raw[stop:stop + 1] != b'\n':
            raise ValueError('Truncated Git object')
        result[path] = raw[start:stop]
        offset = stop + 1
    if offset != len(raw):
        raise ValueError('Trailing Git output')
    return result


def role(path):
    lower = path.lower()
    if language_for(path) in ('YAML', 'CMake', 'Makefile', 'Dockerfile'):
        return 'build/configuration'
    if lower.startswith('code/research/'):
        return 'research archive'
    if lower.startswith('code/'):
        return 'supplementary research source'
    if lower.startswith(('tools/', 'tests/', '.github/')):
        return 'public checks/utilities'
    if lower.endswith('.html'):
        return 'embedded-data HTML/report'
    if lower.startswith('study/'):
        return 'historical study source'
    if PurePosixPath(lower).suffix in ('.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.css'):
        return 'browser UI'
    return 'public checks/utilities'


def catalog(repo):
    entries = index_entries(repo)
    selected = {p: entries[p] for p in sorted(entries)
                if language_for(p) is not None}
    for path, (mode, _) in selected.items():
        if mode not in ('100644', '100755'):
            raise ValueError('Source must be a regular Git blob, not symlink: ' + path)
    content = blobs(repo, selected)
    files = []
    languages = {}
    for path, data in content.items():
        language = language_for(path)
        files.append({'path': path, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest(),
                      'language': language, 'role': role(path)})
        total = languages.setdefault(language, {'files': 0, 'bytes': 0})
        total['files'] += 1
        total['bytes'] += len(data)
    return {'schema': 'source-catalog-v1',
            'scope': 'Git index source blobs; source listing, not license clearance',
            'extensions': sorted(EXTENSIONS), 'exact_filenames': sorted(FILENAMES),
            'excluded_source_paths': [],
            'directory_policy': 'All tracked source directories included, including vendor and dependencies',
            'counts': {'files': len(files), 'bytes': sum(f['bytes'] for f in files),
                       'by_language': languages}, 'files': files}


def encode(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    args = parser.parse_args()
    repo = Path(git(args.repo, 'rev-parse', '--show-toplevel').decode().strip())
    value = catalog(repo)
    output = repo / CATALOG
    if output.is_symlink() or output.parent.is_symlink():
        raise ValueError('Refusing symlink output')
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(encode(value))
    print(f"Wrote {CATALOG}: {value['counts']['files']} files, {value['counts']['bytes']} bytes")


if __name__ == '__main__':
    main()
