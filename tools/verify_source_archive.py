"""Check archived source bytes without importing or executing research modules."""
import hashlib
import json
from pathlib import Path, PurePosixPath


def verify(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'code/research-manifest.json').read_text())
    entries = manifest['files']
    expected = set()
    for entry in entries:
        name = entry['target']
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name
                or path.parts[:2] != ('code', 'research') or path.suffix != '.py'
                or path.as_posix() != name or name in expected):
            raise ValueError('Invalid or duplicate source path: ' + name)
        expected.add(name)
        source = root / path
        if source.is_symlink() or not source.resolve().is_relative_to(root / 'code/research'):
            raise ValueError('Unexpected source symlink: ' + name)
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['published_sha256']:
            raise ValueError('Source hash mismatch: ' + name)
        if len(raw) != entry['published_bytes']:
            raise ValueError('Source size mismatch: ' + name)
    actual = {p.relative_to(root).as_posix() for p in (root / 'code/research').rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    if actual != expected:
        raise ValueError('Missing or unlisted archive files')
    if manifest['file_count'] != len(entries):
        raise ValueError('Manifest count mismatch')
    return len(entries)


if __name__ == '__main__':
    count = verify(Path(__file__).resolve().parents[1])
    print(f'PASS: {count} research source files match the public manifest.')
    print('Integrity check only; no research module, model or measurement was loaded.')
