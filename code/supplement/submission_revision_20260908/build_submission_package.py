"""Assemble an immutable local private package from explicitly scoped inputs.

Does not execute scientific code, publish files, or change earlier archives.
Requires a matching completed technical QA record before packaging.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import shutil
import stat
import zipfile
import verify_submission_package as verify

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
NAMES = {'main': 'NeuralFoil_Measurement_Correction_Manuscript',
         'supplement': 'NeuralFoil_Measurement_Correction_Supplement'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--qa', type=Path, default=HERE / 'work/FINAL_TECHNICAL_QA.json')
    args = ap.parse_args()
    if not args.name.replace('_', '').isalnum():
        raise ValueError('Use a simple versioned package name')
    dest = HERE / 'deliverables' / args.name
    archive = dest.with_suffix('.zip')
    delivery = dest.with_name(args.name + '_DELIVERY.json')
    if any(p.exists() for p in [dest, archive, delivery]):
        raise FileExistsError('Existing package attempts must be preserved')
    qa_path = args.qa.resolve()
    if not qa_path.is_relative_to(HERE / 'work'):
        raise ValueError('QA record must be within this successor work directory')
    qa_digest = verify.sha(qa_path)
    qa = json.loads(qa_path.read_text())
    if verify.sha(qa_path) != qa_digest:
        raise ValueError('Concurrent QA mutation')
    if qa['status'] != 'PASS_TECHNICAL_PREPARATION':
        raise ValueError('Technical QA is incomplete')
    if not set(qa['review_files']).issubset(qa['files']):
        raise ValueError('Every review must be bound to its QA digest')
    required = {kind + '.complete.md' for kind in NAMES}
    required |= {'deliverables/' + stem + '.' + ext for stem in NAMES.values() for ext in ['docx', 'pdf']}
    if not required.issubset(qa['files']):
        raise ValueError('Required manuscript outputs are not QA-bound')
    qa_expected = {(HERE / name).resolve(): h for name, h in qa['files'].items()}
    qa_expected[qa_path.resolve()] = qa_digest
    for name, h in qa['files'].items():
        if verify.sha(HERE / name) != h:
            raise ValueError('QA input changed: ' + name)
    files = {}

    def add(source, target):
        source = Path(source)
        verify.safe_name(target)
        if target in files or source.is_symlink() or not source.is_file():
            raise ValueError('Invalid or repeated package input: ' + str(source))
        if not source.resolve().is_relative_to(PROJECT):
            raise ValueError('Input is outside the research project')
        files[target] = source

    add(HERE / 'PACKAGE_README.md', 'README.md')
    add(HERE / 'work/feature_reproduction/NAVIGATION_AND_REPLAY.md', 'NAVIGATION_AND_REPLAY.md')
    for name in ['verify_submission_package.py', 'test_submission_package.py']:
        add(HERE / name, name)
    for kind, stem in NAMES.items():
        for ext in ['docx', 'pdf']:
            add(HERE / 'deliverables' / (stem + '.' + ext), 'manuscript/' + stem + '.' + ext)
        add(HERE / (kind + '.complete.md'), 'manuscript/' + kind + '.md')
    for stem in ['method_roles', 'accuracy_harm', 'calibration_utility', 'external_complete_eligible']:
        for ext in ['pdf', 'svg', 'png']:
            add(HERE / 'figures' / (stem + '.' + ext), 'figures/' + stem + '.' + ext)
        # Preserve the exact scientific Markdown and its relative image paths.
        add(HERE / 'figures' / (stem + '.png'), 'manuscript/figures/' + stem + '.png')
    for study in ['model_development_20260907_cap_ablation', 'model_development_20260908_adaptive_scale']:
        # This finite directory is the already exposed study assessment, not an outcome discovery route.
        for p in sorted((PROJECT / study / 'assessment').iterdir()):
            if p.is_file() and p.suffix in ['.json', '.csv']:
                add(p, 'evidence/' + study + '/assessment/' + p.name)
        for name in ['PROTOCOL.md', 'REPORT.md', 'DELIVERY_QA.json']:
            add(PROJECT / study / name, 'evidence/' + study + '/' + name)
    for name in ['all_candidate_summary.csv', 'all_panel_metrics.csv', 'DISPLAY_MANIFEST.json',
                 'METHOD_DIAGRAM.json', 'main_results.md', 'coverage.md', 'complete_panels.md']:
        add(HERE / 'work/displays' / name, 'evidence/displays/' + name)
    scientific = HERE / 'work/scientific_review'
    for name in ['THEOREMS.md', 'EXACT_BOUNDS.json', 'SUPPLEMENT_SECTIONS.md', 'SENSITIVITY_PLAN.md']:
        add(scientific / name, 'evidence/mathematics/' + name)
    for p in sorted((scientific / 'sensitivity_results').iterdir()):
        if p.is_file() and p.suffix in ['.json', '.csv']:
            add(p, 'evidence/sensitivity/' + p.name)
    connected = HERE / 'work/reviewer_reproduction'
    manifest = json.loads((connected / 'manifest.json').read_text())
    for name, h in manifest['files'].items():
        if verify.sha(connected / name) != h:
            raise ValueError('Connected source changed: ' + name)
        add(connected / name, 'reproduction/connected/' + name)
    add(connected / 'manifest.json', 'reproduction/connected/manifest.json')
    for category, relative, names in [
        ('references', 'work/reference_reproduction',
         ['reference_reproduction_private.zip', 'release_manifest.json', 'REPORT.md', 'PACKAGE_GUIDE.md',
          'extraction_verified.json', 'extraction_transcript.json', 'FINAL_STATUS.md']),
        ('bounds', 'work/scientific_review/bounds_portable',
         ['bounds_private.zip', 'REPORT.md', 'README.md', 'verification.json', 'clean_extraction_transcript.txt']),
        ('feature_witness', 'work/feature_reproduction',
         ['REPORT.md', 'extraction_verified.json', 'source_bridge_verified.json']),
    ]:
        for name in names:
            add(HERE / relative / name, 'reproduction/' + category + '/' + name)
    add(scientific / 'bounds_portable/bundle/manifest.json', 'reproduction/bounds/manifest.json')
    for name in ['VERIFICATION.md', 'verification_complete.json', 'fresh_extraction_transcript.txt']:
        add(PROJECT / 'reproduction_20260908_private' / name, 'reproduction/correction_witness/' + name)
    for name in ['COVER_LETTER_DRAFT.md', 'HIGHLIGHTS_DRAFT.md', 'AUTHOR_POLICY_CHECKLIST.md',
                 'AUTHOR_READTHROUGH_GUIDE.md', 'ACCESS_RIGHTS_MATRIX.md', 'DATA_CODE_ACCESS_DRAFT.md',
                 'REVIEWER_PACKAGE_CHECKLIST.md', 'VENUE_REVIEW.md', 'CITATION_LEDGER.md']:
        add(HERE / 'work/literature' / name, 'author_approval/' + name)
    for name in qa['review_files']:
        add(HERE / name, 'quality/' + name.removeprefix('work/'))
    add(qa_path, 'quality/FINAL_TECHNICAL_QA.json')
    for name in ['manuscript.md', 'supplement.md', 'assemble_submission.py', 'build_documents.py',
                 'build_evidence.py', 'build_method_diagram.py', 'audit_layout.py',
                 'archive_build.py', 'build_submission_package.py', 'work/ASSEMBLY.json']:
        add(HERE / name, 'authoring_provenance/' + name.removeprefix('work/'))
    for name in ['sensitivity.py', 'exact_bounds.py']:
        add(scientific / name, 'authoring_provenance/' + name)
    dest.mkdir(parents=True, exist_ok=False)
    records = {}
    for name, source in sorted(files.items()):
        h = verify.sha(source)
        if source.resolve() in qa_expected and h != qa_expected[source.resolve()]:
            raise ValueError('QA-covered source changed before copy: ' + name)
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if verify.sha(target) != h or verify.sha(source) != h:
            raise ValueError('Copy or concurrent source mutation: ' + name)
        records[name] = {'bytes': target.stat().st_size, 'sha256': h,
                         'source': source.relative_to(PROJECT).as_posix()}
    for source, expected in qa_expected.items():
        if verify.sha(source) != expected:
            raise ValueError('QA-covered source changed during assembly: ' + str(source))
    (dest / 'MANIFEST.json').write_text(json.dumps({
        'schema': 'neuralfoil_private_submission_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PRIVATE_TECHNICAL_PREPARATION',
        'not_author_approved': True, 'not_submitted': True,
        'no_blanket_redistribution_license': True,
        'technical_qa_sha256': qa_digest,
        'files': records}, indent=2) + '\n')
    mh = verify.sha(dest / 'MANIFEST.json')
    checked = verify.verify(dest, mh)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(dest.rglob('*')):
            if not p.is_file():
                continue
            info = zipfile.ZipInfo(dest.name + '/' + p.relative_to(dest).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info, p.read_bytes())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('Archive CRC check failed')
    for source, expected in qa_expected.items():
        if verify.sha(source) != expected:
            raise ValueError('QA-covered source changed during ZIP creation: ' + str(source))
    result = {'status': 'ASSEMBLED_AND_AUTHENTICATED_FRESH_EXTRACTION_PENDING',
              'archive': str(archive), 'archive_bytes': archive.stat().st_size,
              'archive_sha256': verify.sha(archive), 'manifest_sha256': mh,
              'files_authenticated': checked['files_authenticated'],
              'technical_qa_sha256': qa_digest,
              'original_archives_unchanged': True}
    delivery.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
