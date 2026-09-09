"""Finite, byte-preserving mechanical staging of an editable V8 successor."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
OLD = BASE / 'renewed_manuscript_v7'
DEST = BASE / 'renewed_manuscript_v8'
QA_PIN = 'e96a7dc085cc558b6eb2a4f8dc430fbbbe59aca63a402b652ddc83baddc0de58'
DISPLAY_PIN = 'f5af3a6763d2f8f089b9e683fb9f1b90b64682c74767977c50393130fc2318ad'
FIGURE_PIN = '92fd06924d87ae2d60a7b88c2ddffec5570edd2182bd7d6c31a54e1f354db731'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def read_pinned(path, pin=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError(str(path))
    raw = path.read_bytes()
    if pin is not None and sha(raw) != pin:
        raise ValueError('pin mismatch: ' + str(path))
    return raw

def main():
    if DEST.exists():
        raise FileExistsError(DEST)
    qa = json.loads(read_pinned(OLD/'work/FINAL_TECHNICAL_QA_v7.json', QA_PIN))
    assert qa['status'] == 'PASS_TECHNICAL_PREPARATION'
    # Sources needed to assemble/render, not previous rendered histories or ZIPs.
    names = ['manuscript.md', 'supplement.md', 'assemble_submission.py',
             'build_documents.py', 'build_reading_copy.py', 'audit_layout.py']
    for directory in ['figures', 'work/displays', 'work/risk_displays',
                      'work/measurement_displays']:
        names += [str(p.relative_to(OLD)) for p in sorted((OLD/directory).iterdir())
                  if p.is_file() and not p.is_symlink()]
    names += ['work/literature/REFERENCES_NUMBERED.md',
              'work/scientific_review/SUPPLEMENT_SECTIONS.md']
    assert len(names) == len(set(names))
    jobs = {}
    for rel in names:
        raw = read_pinned(OLD/rel, qa['files'].get(rel))
        jobs[rel] = (OLD/rel, raw)
    display_dir = HERE/'qualified_confidence_displays/attempt_1'
    display = json.loads(read_pinned(display_dir/'MANIFEST.json', DISPLAY_PIN))
    for rel, pin in display['output_sha256'].items():
        assert '/' not in rel and rel.endswith(('.md', '.csv'))
        jobs['work/qualified_displays/'+rel] = (display_dir/rel, read_pinned(display_dir/rel, pin))
    jobs['work/qualified_displays/MANIFEST.json'] = (display_dir/'MANIFEST.json', read_pinned(display_dir/'MANIFEST.json', DISPLAY_PIN))
    figure_dir = HERE/'kl_confidence_design/illustration_attempt_1'
    figure = json.loads(read_pinned(figure_dir/'MANIFEST.json', FIGURE_PIN))
    for suffix in ['pdf', 'png', 'svg']:
        rel = 'confidence_rule_illustration.'+suffix
        jobs['figures/'+rel] = (figure_dir/rel, read_pinned(figure_dir/rel, figure['output_sha256'][rel]))
    for rel in ['SUPPLEMENT_QUALIFIED_DRAFT.md', 'MANUSCRIPT_ADDITIONS_DRAFT.md']:
        jobs['work/integration_inputs/'+rel] = (HERE/rel, read_pinned(HERE/rel))
    sources = {str(p): sha(raw) for p, raw in jobs.values()}
    DEST.mkdir()
    for rel, (source, raw) in jobs.items():
        target = DEST/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Copy only the preflighted unchanged source; then independently check bytes.
        shutil.copy2(source, target)
        assert target.read_bytes() == raw, rel
    for path, pin in sources.items():
        read_pinned(Path(path), pin)
    receipt = {
        'status': 'STAGED_NOT_ASSEMBLED_OR_REVIEWED',
        'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'purpose': 'Editable integrated successor; no changed scientific result or inherited visual approval',
        'source_v7_technical_qa_sha256': QA_PIN,
        'code_sha256': sha(Path(__file__).read_bytes()),
        'source_sha256': sources,
        'staged_sha256': {rel: sha(raw) for rel, (_, raw) in jobs.items()},
        'prior_edition_unchanged': True,
        'actual_model_or_target_arrays_parsed': 0,
    }
    with (DEST/'STAGING.json').open('x') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'destination': str(DEST), 'copied_files': len(jobs), 'status': receipt['status']}))

if __name__ == '__main__':
    main()
