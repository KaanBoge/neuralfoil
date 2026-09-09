"""Create a clean, explicitly scoped reading-edition release and SHA-256 manifest.

Refuses an existing destination: a completed release is never silently replaced.
Historical evidence manifests retain their original scopes. This release manifest
is authoritative for the newly packaged files and excludes only itself.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    destination=args.destination.resolve()
    if destination.exists(): raise SystemExit(f"Refusing existing destination: {destination}")
    # Do not include raw rows, application caches, exploratory renderings, or
    # intermediary DOCX files. Build inputs and plot provenance are explicit.
    names=["README.md","EDITION_NOTES.md","AUTHOR_INPUT_REQUIRED.md",
           "THIRD_PARTY_DATA_NOTICE.md","manuscript.md","build_manuscript.py",
           "build_document.py","validate_edition.py","check_layout.py",
           "package_edition.py","requirements-document.txt","source/manuscript_previous.md",
           "output/docx/NeuralFoil_Research_Paper.docx",
           "output/pdf/NeuralFoil_Research_Paper.pdf",
           "work/narrative_sections.json","work/methods_replacements.json",
           "work/page_map.json","work/headings.json","work/semantic_qa.json",
           "work/layout_qa.json","work/visual_qa.json","work/accessibility_qa.json",
           "work/figure_reproducibility_note.md"]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/"figures").iterdir()
              if p.suffix in {".png",".pdf"}]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/"evidence").rglob("*")
              if p.is_file() and p.suffix in {".md",".py",".csv",".json",".txt"}]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/"work").glob("build_*_figure.py")]
    names += [p.relative_to(ROOT).as_posix() for p in (ROOT/"work").glob("*_figure_provenance.json")]
    names=sorted(set(names))
    missing=[name for name in names if not (ROOT/name).is_file()]
    if missing: raise SystemExit(f"Missing release inputs: {missing}")
    for name in ("semantic_qa.json","layout_qa.json"):
        report=json.loads((ROOT/"work"/name).read_text())
        if name=="semantic_qa.json" and not report["passed"]:
            raise SystemExit("Semantic QA has a failed check")
        if name=="layout_qa.json" and not all(report["checks"].values()):
            raise SystemExit("Layout QA has a failed check")
    destination.mkdir(parents=True,exist_ok=False)
    rows=[]
    for name in names:
        src=ROOT/name; dst=destination/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        rows.append({"path":name,"bytes":dst.stat().st_size,"sha256":sha(dst)})
    manifest=destination/"SHA256SUMS.csv"
    with manifest.open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=["path","bytes","sha256"])
        writer.writeheader(); writer.writerows(rows)
    archive=destination.parent/(destination.name+".zip")
    if archive.exists(): raise SystemExit(f"Refusing existing ZIP: {archive}")
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(destination.rglob("*")):
            if p.is_file(): z.write(p,p.relative_to(destination.parent))
    # Verify the actual files and archive, not merely the intended copy list.
    assert {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} == set(names)|{"SHA256SUMS.csv"}
    assert all(sha(destination/r["path"])==r["sha256"] for r in rows)
    with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    result={"release":str(destination),"files_excluding_manifest":len(rows),
            "manifest_sha256":sha(manifest),"zip":str(archive),
            "zip_sha256":sha(archive),"zip_bytes":archive.stat().st_size}
    (ROOT/"work/release_qa.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
