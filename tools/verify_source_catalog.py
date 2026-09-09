"""Verify the staged catalog and all source bytes against a clean working tree."""
import argparse
import hashlib
from pathlib import Path
from build_source_catalog import CATALOG, blobs, catalog, encode, git, index_entries


def verify(repo):
    # Staged additions are allowed; tracked worktree bytes must equal the index.
    git(repo, 'diff', '--quiet', '--no-ext-diff')
    entries = index_entries(repo)
    if CATALOG not in entries or entries[CATALOG][0] not in ('100644', '100755'):
        raise ValueError('Catalog must be staged as a regular file')
    value = catalog(repo)
    expected = encode(value)
    actual = blobs(repo, {CATALOG: entries[CATALOG]})[CATALOG]
    if actual != expected:
        raise ValueError('Catalog is stale, incomplete, noncanonical, or has incorrect hashes')
    # Explicit readback also covers assume-unchanged/skip-worktree flags.
    for row in value['files']:
        path = Path(repo) / row['path']
        if any(p.is_symlink() for p in [path, *path.parents] if p != Path(repo).parent):
            raise ValueError('Symlink in working source path')
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Working source differs from index: ' + row['path'])
    if (Path(repo) / CATALOG).read_bytes() != expected:
        raise ValueError('Working catalog differs from index')
    return len(value['files'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    args = parser.parse_args()
    repo = Path(git(args.repo, 'rev-parse', '--show-toplevel').decode().strip())
    print(f'PASS: {verify(repo)} tracked source files; listing is not license clearance')


if __name__ == '__main__':
    main()
