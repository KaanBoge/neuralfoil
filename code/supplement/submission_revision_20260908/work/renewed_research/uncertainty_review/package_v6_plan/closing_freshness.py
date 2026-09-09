"""Read-only closing authentication of reviewed artifacts; no science execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

PROJECT = Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper')
EDITION = PROJECT / 'submission_revision_20260908/renewed_manuscript_v9'
DEADLINE = datetime(2026, 9, 9, 1, 35, 33, tzinfo=timezone.utc)


def digest(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
        raise ValueError('Nonregular or symlink path: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def authenticate(path, expected):
    if digest(path) != expected:
        raise ValueError('Hash mismatch: ' + str(path))


def metadata(path, expected):
    authenticate(path, expected)
    data = json.loads(Path(path).read_bytes())
    authenticate(path, expected)
    return data


def main():
    now = datetime.now(timezone.utc)
    if now < DEADLINE:
        raise ValueError('Closing review is not due before the requested minimum')
    started = time.monotonic()
    qa_path = EDITION / 'work/FINAL_TECHNICAL_QA_v9.json'
    qa_hash = '24282221edca95bfefe05e2add3f5974e49c406d6d68565d421f5faabb1bcc26'
    qa = metadata(qa_path, qa_hash)
    if qa['status'] != 'PASS_TECHNICAL_PREPARATION' or len(qa['files']) != 3635:
        raise ValueError('Unexpected technical QA contract')
    config = metadata(EDITION / qa['config_path'], qa['config_sha256'])
    external = qa['external_readonly_files']
    if len(external) != 360 or external != config['external_readonly_pins']:
        raise ValueError('External provenance contract mismatch')
    seen_external = {}
    for name, h in qa['files'].items():
        p = EDITION / name
        authenticate(p, h)
        if not p.resolve().is_relative_to(PROJECT):
            seen_external[str(p.resolve())] = h
    if seen_external != external:
        raise ValueError('External provenance membership mismatch')
    for document in qa['documents'].values():
        for artifact in document['artifacts'].values():
            authenticate(artifact['path'], artifact['sha256'])

    package = EDITION / 'deliverables/NeuralFoil_Private_Submission_Package_v6'
    archive = package.with_name(package.name + '.zip')
    archive_sha = 'd203b7e674711c53b557cd1a2746fa4b4008d4dc7cfca8a581e9e064092614f3'
    manifest_sha = 'a84869769cb8952e2e9e82f6ccf16489e5f6dba3a19ccb3b5d357329c6446149'
    authenticate(archive, archive_sha)
    manifest = metadata(package / 'MANIFEST.json', manifest_sha)
    if len(manifest['files']) != 541 or manifest['public_release'] is not False or manifest['human_author_approval'] is not False:
        raise ValueError('Outer manifest contract mismatch')
    actual = set()
    for p in package.rglob('*'):
        if p.is_symlink():
            raise ValueError('Package symlink')
        if p.is_file():
            actual.add(p.relative_to(package).as_posix())
        elif not p.is_dir():
            raise ValueError('Unexpected package entry')
    if actual != set(manifest['files']) | {'MANIFEST.json'}:
        raise ValueError('Package inventory drift')
    for name, row in manifest['files'].items():
        p = package / name
        authenticate(p, row['sha256'])
        if p.stat().st_size != row['bytes']:
            raise ValueError('Package size drift')

    author_path = EDITION / 'author_materials/build_v1/FINAL_QA.json'
    author = metadata(author_path, '6e497d4dd69a1bd5ad155c04c467f3908bf857280be6ea4e58179e74e92584e6')
    author_pins = {**author['sources'], **author['tools']}
    author_pins.update({p: row['sha256'] for p, row in author['outputs'].items()})
    author_pins.update({row['path']: row['sha256'] for row in author['visual_ledger']})
    for p, h in author_pins.items():
        authenticate(p, h)
    entry = EDITION / 'START_HERE.md'
    entry_sha = '734743c9170dff5241c6652bd7adf51fdb378117246d09e6521702a36a8745fe'
    authenticate(entry, entry_sha)
    links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', entry.read_text())
    if len(links) != 17 or not all((EDITION / link).is_file() for link in links):
        raise ValueError('Delivery links drifted')
    authenticate(EDITION / 'author_materials/OPTIONAL_SHORT_ABSTRACT.md',
                 'b51a3cd13cd3a734ae9f12388287ec1e944a2e44b4261dbe3f0e231c07f86d4a')
    authenticate(qa_path, qa_hash)
    authenticate(archive, archive_sha)
    return {
        'status': 'PASS_CLOSING_FRESHNESS_ONLY',
        'started_utc': now.isoformat(),
        'completed_utc': datetime.now(timezone.utc).isoformat(),
        'minimum_window_end_utc': DEADLINE.isoformat(),
        'seconds': time.monotonic() - started,
        'technical_qa_pins': 3635,
        'external_readonly_pins': 360,
        'outer_manifest_payloads': 541,
        'outer_disk_files_including_manifest': len(actual),
        'author_artifact_pins': len(author_pins),
        'delivery_links': len(links),
        'archive_sha256': archive_sha,
        'manifest_sha256': manifest_sha,
        'scientific_code_executed': False,
        'scientific_payloads_parsed': False,
        'new_visual_inspections': False,
        'human_author_approval': False,
        'public_release': False,
        'scope': 'Reauthentication of existing reviewed files and links, not a scientific rerun, new visual inspection, independent experimental validation or continuous-compute claim.'
    }


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
