"""Read-only, standard-library integrity check; never execute archived science.

Supply both digests from an independently authenticated delivery record.
No extraction, fitting, inference, dependency installation or array parsing.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import struct
import time
import zipfile

CHUNK = 1024 ** 2
MAX_ARCHIVE = 240 * 1024 ** 2
MAX_METADATA = 16 * 1024 ** 2
MAX_EXPANDED = 9 * 1024 ** 3 // 4
MAX_FILES = 20000
MAX_SECONDS = 900


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'SHA256 required')


def safe_name(value):
    require(type(value) is str and bool(value), 'Member name required')
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and '..' not in p.parts
            and value != '.' and '\\' not in value and ':' not in value
            and all(ord(c) >= 32 and not 127 <= ord(c) <= 159 for c in value),
            'Unsafe member name')


def regular(path):
    require(not any(p.is_symlink() for p in [path, *path.parents]), 'Symlink path')
    require(stat.S_ISREG(path.stat().st_mode), 'Regular file required')


def stream_hash(reader, limit, check):
    h = hashlib.sha256()
    count = 0
    while True:
        check()
        chunk = reader.read(CHUNK)
        if not chunk:
            break
        count += len(chunk)
        require(count <= limit, 'Read exceeds admitted size')
        h.update(chunk)
    return h.hexdigest(), count


def unique_pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def central_directory(archive, check):
    """Count fixed-format headers before ZipFile allocates its directory objects."""
    size = archive.stat().st_size
    require(22 <= size <= MAX_ARCHIVE, 'Archive size cap')
    with archive.open('rb') as src:
        src.seek(-22, 2)
        sig, disk, start, local_n, n, length, offset, comment = struct.unpack('<4s4H2LH', src.read(22))
        require(sig == b'PK\x05\x06' and disk == start == comment == 0
                and local_n == n and 1 <= n <= MAX_FILES + 1
                and length <= MAX_METADATA and offset + length == size - 22,
                'Unsupported or unbounded central directory')
        src.seek(offset)
        remaining = length
        seen = 0
        while remaining:
            check()
            require(remaining >= 46, 'Truncated directory header')
            header = src.read(46)
            require(len(header) == 46 and header[:4] == b'PK\x01\x02', 'Directory signature')
            name_n, extra_n, comment_n = struct.unpack_from('<3H', header, 28)
            variable = name_n + extra_n + comment_n
            require(variable <= remaining - 46, 'Directory lengths')
            src.seek(variable, 1)
            remaining -= 46 + variable
            seen += 1
            require(seen <= MAX_FILES + 1, 'Directory record cap')
        require(seen == n, 'Directory count disagreement')


def verify(archive, archive_sha256, manifest_sha256, extracted=None):
    pin(archive_sha256)
    pin(manifest_sha256)
    archive = Path(archive).absolute()
    regular(archive)
    require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), 'Existing timer')
    old_handler = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    def timeout(*_):
        raise TimeoutError('900-second read-only verification deadline')
    def check():
        if time.monotonic() - started >= MAX_SECONDS:
            timeout()
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, MAX_SECONDS)
    try:
        central_directory(archive, check)
        with archive.open('rb') as src:
            actual, archive_bytes = stream_hash(src, MAX_ARCHIVE, check)
        require(actual == archive_sha256, 'Archive digest mismatch')
        with zipfile.ZipFile(archive) as z:
            info = z.infolist()
            names = [i.filename for i in info]
            for name in names:
                safe_name(name)
            folded = sorted(name.casefold() for name in names)
            require(len(names) == len(set(folded)) and 'MANIFEST.json' in names, 'Member inventory')
            folded_set = set(folded)
            require(not any(str(parent) in folded_set for name in folded
                            for parent in PurePosixPath(name).parents), 'File-directory collision')
            for item in info:
                require(not item.is_dir() and stat.S_IFMT(item.external_attr >> 16) in {0, stat.S_IFREG}
                        and not item.flag_bits & 1 and item.compress_type == zipfile.ZIP_DEFLATED,
                        'Unsupported member type')
            require(z.getinfo('MANIFEST.json').file_size <= MAX_METADATA, 'Manifest size cap')
            with z.open('MANIFEST.json') as src:
                raw = src.read(MAX_METADATA + 1)
            require(len(raw) <= MAX_METADATA and hashlib.sha256(raw).hexdigest() == manifest_sha256,
                    'Manifest digest mismatch')
            m = json.loads(raw, object_pairs_hook=unique_pairs,
                           parse_constant=lambda _: require(False, 'Nonfinite JSON'))
            require(set(m) == {'schema', 'selection_sha256', 'claim', 'files'}
                    and m['schema'] == 'v9-saved-evidence-1'
                    and m['claim'] == 'SAVED_EVIDENCE_NOT_NEW_PORTABLE_PIPELINE', 'Manifest contract')
            pin(m['selection_sha256'])
            files = m['files']
            require(type(files) is dict and 1 <= len(files) <= MAX_FILES
                    and set(names) == set(files) | {'MANIFEST.json'}, 'Exact manifest membership')
            total = len(raw)
            for name, row in files.items():
                safe_name(name)
                require(type(row) is dict and set(row) == {'bytes', 'sha256'}, 'Member record')
                pin(row['sha256'])
                require(type(row['bytes']) is int and 0 <= row['bytes'] <= MAX_EXPANDED, 'Member byte count')
                require(z.getinfo(name).file_size == row['bytes'], 'Declared member size')
                total += row['bytes']
            require(total <= MAX_EXPANDED, 'Expanded size cap')
            expected = {**files, 'MANIFEST.json': {'bytes': len(raw), 'sha256': manifest_sha256}}
            for name, row in expected.items():
                with z.open(name) as src:
                    h, n = stream_hash(src, row['bytes'], check)
                require((h, n) == (row['sha256'], row['bytes']), 'Member content mismatch: ' + name)
                if extracted is not None:
                    target = Path(extracted).absolute() / name
                    regular(target)
                    with target.open('rb') as src:
                        h, n = stream_hash(src, row['bytes'], check)
                    require((h, n) == (row['sha256'], row['bytes']), 'Extracted content mismatch: ' + name)
        with archive.open('rb') as src:
            h, n = stream_hash(src, MAX_ARCHIVE, check)
        require((h, n) == (archive_sha256, archive_bytes), 'Archive changed during check')
        check()
        return {'status': 'PASS_SAVED_FILE_INTEGRITY', 'files': len(files), 'expanded_bytes': total,
                'archive_bytes': archive_bytes, 'extracted_selected_files_checked': extracted is not None,
                'extra_extracted_files_not_checked': extracted is not None,
                'scientific_code_executed': False, 'seconds': time.monotonic() - started}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['archive', 'archive-sha256', 'manifest-sha256']:
        p.add_argument('--' + name, required=True)
    p.add_argument('--extracted', help='Optional existing directory; verify selected files, not extras')
    args = p.parse_args()
    print(json.dumps(verify(args.archive, args.archive_sha256, args.manifest_sha256, args.extracted), indent=2))
