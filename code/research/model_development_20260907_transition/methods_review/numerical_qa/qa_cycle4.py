"""Reuse independent arithmetic checker with explicit Cycle 4 schema mappings.

No fitting and no source edits. The shared QA source is read, hashed, and mapped
in memory. Outputs remain beside this driver because __file__ is this path.
"""
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SOURCE=ROOT.parent/'model_development_20260907_search/methods_review/numerical_qa/qa_cycle3.py'
code=SOURCE.read_text()
replacements={
    "manifest['candidate_labels']":"manifest['labels']",
    "for name,h in freeze['artifact_hashes'].items():assert hashlib.sha256((RESULTS/name).read_bytes()).hexdigest()==h":
        "for name,record in freeze['artifacts'].items():assert hashlib.sha256((RESULTS/('fit_'+name+'.pkl')).read_bytes()).hexdigest()==record['sha256']",
}
for old,new in replacements.items():
    assert old in code,old
    code=code.replace(old,new)
provenance={'shared_checker_path':str(SOURCE),'shared_checker_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'schema_replacements':replacements,'no_experiment_source_changes':True}
(OUT/'qa_adapter_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
exec(compile(code,str(SOURCE),'exec'),{'__file__':__file__,'__name__':'__main__'})
