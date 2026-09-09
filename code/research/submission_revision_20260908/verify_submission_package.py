"""Read-only, standard-library integrity check; never executes scientific code.

Review this source and obtain the manifest digest through a trusted channel.
Integrity is not permission, scientific validity, or author approval.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key: ' + key)
        value[key] = item
    return value


def safe_name(name):
    p = PurePosixPath(name)
    if (not isinstance(name, str) or not name or p.is_absolute()
            or '..' in p.parts or '.' in p.parts or '\\' in name
            or ':' in name or str(p) != name):
        raise ValueError('Unsafe or noncanonical relative path: ' + repr(name))
    return p


def verify(root, expected):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Package root must be a real directory')
    root = root.resolve()
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('A trusted lowercase SHA256 digest is required')
    manifest = root / 'MANIFEST.json'
    if manifest.is_symlink() or sha(manifest) != expected:
        raise ValueError('Manifest authentication failed')
    data = json.loads(manifest.read_text(), object_pairs_hook=unique_object)
    if data['schema'] != 'neuralfoil_private_submission_v1':
        raise ValueError('Unknown manifest schema')
    actual = set()
    for p in root.rglob('*'):
        if p.is_symlink():
            raise ValueError('Symlink in package: ' + str(p.relative_to(root)))
        if p.is_file():
            actual.add(p.relative_to(root).as_posix())
        elif not p.is_dir():
            raise ValueError('Nonregular package entry')
    listed = set(data['files'])
    if actual != listed | {'MANIFEST.json'}:
        raise ValueError({'missing': sorted(listed - actual),
                          'unlisted': sorted(actual - listed - {'MANIFEST.json'})})
    total = 0
    for name, record in data['files'].items():
        safe_name(name)
        path = root / name
        if path.stat().st_size != record['bytes'] or sha(path) != record['sha256']:
            raise ValueError('Payload mismatch: ' + name)
        total += record['bytes']
    return {'status': 'PASS', 'mode': 'read_only_integrity_no_scientific_execution',
            'manifest_sha256': expected, 'files_authenticated': len(listed),
            'payload_bytes': total, 'author_approval': False,
            'redistribution_permission': False, 'scientific_validation': False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument('--manifest-sha256', required=True)
    args = ap.parse_args()
    print(json.dumps(verify(args.root, args.manifest_sha256), indent=2))


if __name__ == '__main__':
    main()
