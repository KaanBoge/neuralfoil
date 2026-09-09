"""Root orchestration of reviewed safe extraction; no scientific parsing."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import os
import signal
import sys
import time
import traceback


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write(path, value):
    raw = json.dumps(value, indent=2, allow_nan=False).encode() + b'\n'
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    root = Path(__file__).resolve().parent
    approval_path = root / 'ROOT_EXTRACTION_APPROVAL.json'
    approval_raw = approval_path.read_bytes()
    if digest(approval_raw) != sys.argv[1]:
        raise ValueError('approval identity')
    approval = json.loads(approval_raw)
    if approval['authorized_phases'] != ['safe_extraction_only']:
        raise ValueError('extraction scope')
    source_path = root / 'integrity.py'
    source_raw = source_path.read_bytes()
    if digest(source_raw) != approval['integrity_sha256']:
        raise ValueError('reviewed extraction source')
    # Execute the exact authenticated source buffer, not a second disk import.
    spec = importlib.util.spec_from_loader('root_extraction_integrity', loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(source_raw, str(source_path), 'exec'), module.__dict__)
    archive = root / 'kl_harm_private_v1.zip'
    destination = root / approval['destination']
    receipt = root / approval['receipt']
    attempt = root / 'ROOT_EXTRACTION_ATTEMPT.json'
    failure = root / 'ROOT_EXTRACTION_FAILURE.json'
    for path in (destination, receipt, attempt, failure):
        module.new_target(path)
    start = time.monotonic()
    record = {'started_UTC': now(), 'approval_sha256': sys.argv[1],
              'orchestrator_sha256': digest(Path(__file__).read_bytes()),
              'archive_sha256': approval['archive_sha256'],
              'manifest_sha256': approval['manifest_sha256'],
              'runtime': sys.version, 'scientific_members_parsed': False}
    write(attempt, record)
    try:
        target = module.extract_verified(archive, approval['archive_sha256'],
                                        approval['manifest_sha256'], destination)
        raw_manifest = (target / 'manifest.json').read_bytes()
        if digest(raw_manifest) != approval['manifest_sha256']:
            raise ValueError('extracted manifest')
        manifest = json.loads(raw_manifest)
        files = {}
        for name, expected in manifest['files'].items():
            path = target / name
            if path.is_symlink():
                raise ValueError('extracted symlink')
            raw = path.read_bytes()
            actual = {'sha256': digest(raw), 'bytes': len(raw)}
            if actual != expected:
                raise ValueError('extracted payload: ' + name)
            files[name] = actual
        observed = {str(p.relative_to(target)) for p in target.rglob('*') if p.is_file()}
        if observed != set(files) | {'manifest.json'}:
            raise ValueError('extracted inventory')
        if approval_path.read_bytes() != approval_raw or source_path.read_bytes() != source_raw:
            raise ValueError('changed approval or source')
        if digest(archive.read_bytes()) != approval['archive_sha256']:
            raise ValueError('changed archive')
        record.update(status='PASS_SAFE_EXTRACTION', finished_UTC=now(),
                      seconds=time.monotonic()-start, files=files,
                      destination=str(destination), payload_count=len(files))
        write(receipt, record)
        print(json.dumps({k: v for k, v in record.items() if k != 'files'}))
    except BaseException as exc:
        record.update(status='FAIL', exception=repr(exc), traceback=traceback.format_exc(),
                      finished_UTC=now(), seconds=time.monotonic()-start)
        write(failure, record)
        raise


if __name__ == '__main__':
    def timeout(*unused):
        raise TimeoutError('60-second extraction guard')
    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(60)
    main()
