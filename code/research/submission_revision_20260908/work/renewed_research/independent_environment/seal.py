"""Seal the environment-reproduction handoff, excluding installed runtimes/caches."""
import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parent
files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(r.iterdir()) if p.is_file()}
with (r/'DELIVERY.json').open('x') as f:
    json.dump({'status':'COMPLETE','active_owned_processes':0,'root_files':files,
      'scientific_output_manifests':['VERIFIED.json','reference_attempt_1/complete.json','matched_feature_results/complete.json'],
      'preserved_failure':'connected_attempt_1/failure.json','new_statistical_validation':False},f,indent=2)
print(hashlib.sha256((r/'DELIVERY.json').read_bytes()).hexdigest())
