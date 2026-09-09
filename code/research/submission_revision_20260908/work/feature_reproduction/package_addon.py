"""Package generated numeric inputs and observed runtime witness without bytecode."""
import hashlib,json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent;addon=root/'addon'
runtime=json.loads((root/'results/runtime.json').read_text())
(addon/'expected_runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
files={str(p.relative_to(addon)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(addon.rglob('*')) if p.is_file() and '__pycache__' not in str(p) and p.name!='release_manifest.json'}
(addon/'release_manifest.json').write_text(json.dumps({'files':files,'scope':'Private nominal coordinate to feature reproduction; no measurement labels.'},indent=2)+'\n')
with zipfile.ZipFile(root/'feature_reproduction_private.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(addon.rglob('*')):
        if p.is_file() and '__pycache__' not in str(p):z.write(p,'feature_reproduction/'+str(p.relative_to(addon)))
