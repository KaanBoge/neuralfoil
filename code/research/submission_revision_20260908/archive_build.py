"""Preserve an already rendered iteration and its exact authoring inputs."""
from pathlib import Path
import argparse
import hashlib
import shutil

HERE = Path(__file__).resolve().parent
NAMES = {
    'main': 'NeuralFoil_Measurement_Correction_Manuscript',
    'supplement': 'NeuralFoil_Measurement_Correction_Supplement',
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('version')
    args = ap.parse_args()
    if not args.version.startswith('v') or not args.version[1:].isdigit():
        raise ValueError('A numbered version is required')
    for kind, name in NAMES.items():
        root = HERE / 'work' / ('render_' + kind)
        target = root / args.version
        if not target.is_dir():
            raise FileNotFoundError(target)
        sources = [HERE / 'deliverables' / (name + '.docx'),
                   root / 'BUILD.json', HERE / (kind + '.complete.md'),
                   HERE / 'build_documents.py',
                   HERE / 'assemble_submission.py', HERE / 'work' / 'ASSEMBLY.json']
        for source in sources:
            dest = target / source.name
            if dest.exists():
                if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(dest.read_bytes()).digest():
                    raise FileExistsError('Refuse to change archived input: ' + str(dest))
            else:
                shutil.copy2(source, dest)
        print('Preserved', target)

if __name__ == '__main__':
    main()
