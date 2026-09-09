"""Mechanical successor staging; never overwrite the reviewed V6/V3 edition."""
from pathlib import Path
import hashlib
import json
import shutil

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1]
PROJECT=BASE.parent
DEST=BASE/'renewed_manuscript_v7'
TITLE='Accuracy and reliability of measurement informed NeuralFoil drag correction'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if DEST.exists():raise FileExistsError(DEST)
    files=[BASE/x for x in ['manuscript.md','supplement.md','assemble_submission.py','build_documents.py']]
    files += sorted((BASE/'figures').glob('*'))
    files += sorted((BASE/'work/displays').glob('*'))
    files += [BASE/'work/scientific_review/SUPPLEMENT_SECTIONS.md',BASE/'work/literature/REFERENCES_NUMBERED.md']
    sources={str(p):sha(p) for p in files if p.is_file()}
    DEST.mkdir()
    for source in sources:
        p=Path(source);target=DEST/p.relative_to(BASE)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    for name in ['manuscript.md','supplement.md','build_documents.py']:
        p=DEST/name
        p.write_text(p.read_text().replace('Measurement informed NeuralFoil drag correction with grouped validation and uncertainty projection',TITLE))
    p=DEST/'assemble_submission.py'
    p.write_text(p.read_text().replace('ROOT=HERE.parent',f'ROOT=Path({str(PROJECT)!r})'))
    p=DEST/'build_documents.py'
    p.write_text(p.read_text().replace("DESIGN=HERE.parent/'modern_edition/build_document.py'",f'DESIGN=Path({str(PROJECT/"modern_edition/build_document.py")!r})'))
    for path,digest in sources.items():assert sha(Path(path))==digest
    manifest=dict(purpose='new editable successor stage not yet built or reviewed',base_source_sha256=sources,
                  stage_code_sha256=sha(Path(__file__)),staged_sha256={str(p.relative_to(DEST)):sha(p) for p in DEST.rglob('*') if p.is_file()})
    (DEST/'STAGING.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(destination=str(DEST),copied_files=len(sources),old_sources_unchanged=True)))

if __name__=='__main__':main()
