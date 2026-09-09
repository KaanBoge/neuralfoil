"""Authenticate and freshly extract the completed private outer package.

Runs only its reviewed integrity checker, synthetic tests, and connected
archive-integrity mode. No feature/model/certificate fitting or public writes.
The temporary extraction and external transcript are retained.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
import verify_submission_package as v

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--archive-sha256', required=True)
    ap.add_argument('--manifest-sha256', required=True)
    a = ap.parse_args()
    if not a.name.replace('_', '').isalnum():
        raise ValueError('Simple versioned name required')
    archive = HERE / 'deliverables' / (a.name + '.zip')
    if v.sha(archive) != a.archive_sha256:
        raise ValueError('Archive authentication failed')
    record = HERE / 'deliverables' / (a.name + '_EXTRACTION.json')
    if record.exists():
        raise FileExistsError('Previous extraction record exists')
    tmp = Path(tempfile.mkdtemp(prefix='nf-submission-review-', dir='/private/tmp'))
    events = []
    try:
        with zipfile.ZipFile(archive) as z:
            names = set()
            if sum(i.file_size for i in z.infolist()) > 512 * 1024 * 1024:
                raise ValueError('Unexpected package expansion')
            for info in z.infolist():
                v.safe_name(info.filename)
                if (info.filename in names or info.is_dir()
                        or not info.filename.startswith(a.name + '/')
                        or stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError('Unsafe or duplicate archive entry')
                names.add(info.filename)
            manifest_data = z.read(a.name + '/MANIFEST.json')
            if hashlib.sha256(manifest_data).hexdigest() != a.manifest_sha256:
                raise ValueError('Manifest authentication failed')
            manifest = json.loads(manifest_data, object_pairs_hook=v.unique_object)
            expected = {a.name + '/' + n for n in manifest['files']} | {a.name + '/MANIFEST.json'}
            if names != expected:
                raise ValueError('ZIP inventory mismatch')
            for info in z.infolist():
                p = tmp / info.filename
                p.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, p.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
        root = tmp / a.name
        events.append(v.verify(root, a.manifest_sha256))
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        commands = [
            [sys.executable, '-B', str(root / 'verify_submission_package.py'), '--manifest-sha256', a.manifest_sha256],
            [sys.executable, '-B', '-m', 'unittest', 'test_submission_package', '-v'],
            [sys.executable, '-B', str(root / 'reproduction/connected/reviewer.py'), 'verify'],
        ]
        for command in commands:
            p = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True, timeout=60)
            events.append({'command': command, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr})
            if p.returncode:
                raise ValueError('Fresh-extraction command failed')
        events.append(v.verify(root, a.manifest_sha256))
        if v.sha(archive) != a.archive_sha256:
            raise ValueError('Archive changed during extraction check')
        record.write_text(json.dumps({'status': 'PASS', 'fresh_extraction': str(root),
            'archive_sha256': a.archive_sha256, 'manifest_sha256': a.manifest_sha256,
            'mode': 'integrity_and_synthetic_tests_only', 'refits': 0,
            'scientific_modules_executed': False, 'events': events,
            'same_machine': True, 'source_sha256': v.sha(Path(__file__))}, indent=2) + '\n')
        print(json.dumps({'status': 'PASS', 'record': str(record), 'fresh_extraction': str(root),
                          'files_authenticated': len(manifest['files']), 'refits': 0}, indent=2))
    except BaseException as exc:
        record.write_text(json.dumps({'status': 'FAIL', 'extraction_retained': str(tmp),
                                     'events': events, 'error': repr(exc)}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()
