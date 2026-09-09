"""Immutable authoring-input snapshots for each rendered successor iteration."""
from pathlib import Path
import argparse
import hashlib
import shutil
import json

HERE=Path(__file__).resolve().parent
NAMES={'main':'NeuralFoil_Measurement_Correction_Manuscript','supplement':'NeuralFoil_Measurement_Correction_Supplement'}
def sha(p):return hashlib.sha256(p.read_bytes()).digest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('version');args=parser.parse_args()
    if not args.version.startswith('v') or not args.version[1:].isdigit():raise ValueError('numbered version required')
    # A yielding subprocess may still be authoring one document. Validate
    # both completed builds before creating either immutable snapshot.
    for kind,name in NAMES.items():
        root=HERE/'work'/('render_'+kind)
        build=json.loads((root/'BUILD.json').read_text())
        expected=[(HERE/(kind+'.complete.md'),'source_sha256'),
                  (HERE/'build_documents.py','builder_sha256'),
                  (HERE/'deliverables'/(name+'.docx'),'docx_sha256')]
        for path,key in expected:
            if sha(path).hex()!=build[key]:
                raise ValueError(f'Build not complete or current: {kind} {key}')
    for kind,name in NAMES.items():
        root=HERE/'work'/('render_'+kind);target=root/args.version
        target.mkdir(parents=True,exist_ok=True)
        sources=[HERE/'deliverables'/(name+'.docx'),root/'BUILD.json',HERE/(kind+'.complete.md'),
                 HERE/('manuscript.md' if kind=='main' else 'supplement.md'),HERE/'build_documents.py',
                 HERE/'assemble_submission.py',HERE/'work/ASSEMBLY.json']
        for source in sources:
            dest=target/source.name
            if dest.exists():
                if sha(source)!=sha(dest):raise FileExistsError(dest)
            else:shutil.copy2(source,dest)
        print('Preserved',target)
if __name__=='__main__':main()
