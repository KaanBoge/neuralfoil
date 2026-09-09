"""Snapshot and render one immutable numbered build with bundled tools only."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
PYTHON = Path('/PATH_TO_YOUR_HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
RENDERER = Path('/PATH_TO_YOUR_HOME/.codex/plugins/cache/openai-primary-runtime/documents/26.905.11957/skills/documents/render_docx.py')
SOFFICE = Path('/PATH_TO_YOUR_HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/libreoffice-headless/libreoffice/LibreOfficeDev.app/Contents/MacOS/soffice')
NAMES = {'main': 'NeuralFoil_Measurement_Correction_Manuscript',
         'supplement': 'NeuralFoil_Measurement_Correction_Supplement'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=NAMES)
    parser.add_argument('version')
    args = parser.parse_args()
    if not re.fullmatch(r'v[1-9]\d*', args.version):
        raise ValueError('numbered version required')
    assert PYTHON.is_file() and RENDERER.is_file() and SOFFICE.is_file()
    parent = HERE/'work'/('render_'+args.kind)
    folder = parent/args.version
    if folder.exists():
        raise FileExistsError(folder)
    build = json.loads((parent/'BUILD.json').read_bytes())
    docx = HERE/'deliverables'/(NAMES[args.kind]+'.docx')
    assert sha(docx) == build['docx_sha256']
    assert sha(HERE/(args.kind+'.complete.md')) == build['source_sha256']
    assert sha(HERE/'build_documents.py') == build['builder_sha256']
    files = [HERE/(args.kind+'.complete.md'), HERE/('manuscript.md' if args.kind=='main' else 'supplement.md'),
             HERE/'build_documents.py', HERE/'assemble_submission.py', HERE/'render_version.py',
             HERE/'work/ASSEMBLY.json', parent/'BUILD.json', docx]
    pins = {str(p): sha(p) for p in files}
    folder.mkdir()
    for source in files:
        dest = folder/source.name
        shutil.copy2(source, dest)
        assert sha(dest) == pins[str(source)]
    attempt = {'kind': args.kind, 'version': args.version, 'start_utc': utc(),
               'renderer_sha256': sha(RENDERER), 'bundled_soffice': str(SOFFICE),
               'source_sha256': pins, 'status': 'ATTEMPTED_NOT_VERIFIED'}
    with (folder/'RENDER_ATTEMPT.json').open('x') as stream:
        json.dump(attempt, stream, indent=2)
    start = time.monotonic()
    command = [str(PYTHON), str(RENDERER), str(folder/docx.name),
               '--output_dir', str(folder), '--emit_pdf', '--verbose']
    try:
        with (folder/'render.stdout.log').open('x') as out, (folder/'render.stderr.log').open('x') as err:
            subprocess.run(command, stdout=out, stderr=err, check=True, timeout=900)
        for source, pin in pins.items():
            assert sha(Path(source)) == pin, source
        pdf = folder/(NAMES[args.kind]+'.pdf')
        pages = sorted(folder.glob('page-*.png'))
        assert pdf.is_file() and pages
        result = dict(attempt, status='RENDERED_NOT_VISUALLY_REVIEWED',
                      finish_utc=utc(), seconds=time.monotonic()-start,
                      pdf_sha256=sha(pdf), pages=len(pages),
                      png_sha256={p.name: sha(p) for p in pages})
        with (folder/'RENDER_COMPLETE.json').open('x') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps({key: result[key] for key in ['status','kind','version','seconds','pages','pdf_sha256']}))
    except BaseException as exc:
        failure = dict(attempt, status='FAILED_PRESERVED', finish_utc=utc(),
                       seconds=time.monotonic()-start, error=repr(exc))
        with (folder/'RENDER_FAILURE.json').open('x') as stream:
            json.dump(failure, stream, indent=2)
        raise

if __name__ == '__main__':
    main()
