"""Stage a finite successor from the immutable V8 scientific reading sources.

No scientific arrays, refits, inherited visual approval, or old-file mutation.
The new assembly will operate on already expanded prose and retain prior tables.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
OLD = BASE / 'renewed_manuscript_v8'
NEW = BASE / 'renewed_manuscript_v9'
PINS = {
    'main.complete.md': '768ffc2a37b7ecae4e644fa00a04a367c2e86868f1ff2981a6b700f843a8357e',
    'supplement.complete.md': 'cd1fd7942bd7dbf1881a6012d8c90de5726315f45d0c97b7651e0bf709c81157',
    'work/FINAL_TECHNICAL_QA.json': 'ac58346bdc55f51370197788354319ead001f4ae0cbe90ea810b693f3c6fe2b7',
}
FIGURES = (
    'accuracy_harm', 'calibration_utility', 'external_complete_eligible',
    'measurement_label_sensitivity', 'method_roles', 'confidence_rule_illustration',
)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    if NEW.exists():
        raise FileExistsError('V9 already exists; preserve staged work')
    for rel, pin in PINS.items():
        if digest((OLD/rel).read_bytes()) != pin:
            raise ValueError('immutable V8 input mismatch '+rel)
    files = {'main.complete.md': 'manuscript.md', 'supplement.complete.md': 'supplement.md'}
    for name in ('build_documents.py', 'render_version.py', 'audit_layout.py'):
        files[name] = name
    for figure in FIGURES:
        for ext in ('png', 'pdf', 'svg'):
            files[f'figures/{figure}.{ext}'] = f'figures/{figure}.{ext}'
    payload = {}
    for origin, target in files.items():
        path = OLD/origin
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise ValueError('regular staged input')
        payload[target] = (path, path.read_bytes())
    NEW.mkdir()
    (NEW/'work').mkdir()
    inputs = dict(PINS)
    copied = {}
    for target, (path, raw) in payload.items():
        destination = NEW/target
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(raw)
        inputs[str(path.relative_to(OLD))] = digest(raw)
        copied[target] = digest(raw)
    record = {
        'status': 'STAGED_DRAFT_NOT_ASSEMBLED_RENDERED_OR_REVIEWED',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_v8': str(OLD), 'source_pins': inputs, 'staged_pins': copied,
        'source_code_sha256': digest(Path(__file__).read_bytes()),
        'purpose': 'Integrate verified bound refinements and literal inference cost with all adverse results',
        'old_scientific_sources_changed': False,
        'inherited_visual_approval': False,
        'scientific_arrays_or_outcomes_parsed': 0,
    }
    with (NEW/'work/STAGING.json').open('x') as stream:
        json.dump(record, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': record['status'], 'files': len(payload), 'path': str(NEW)}))


if __name__ == '__main__':
    main()
