"""Private packaging only; no numerical generation or fitting."""
from pathlib import Path
import json
import zipfile
import numpy as np
import replay as r


def main():
    here=Path(__file__).resolve().parent
    archive=here/'reference_reproduction_private.zip';manifest=here/'release_manifest.json'
    if archive.exists() or manifest.exists(): raise FileExistsError('Preserve previous package')
    if r.read(here/'results/complete.json')['status']!='PASS': raise ValueError('No completed fit')
    files=[]
    for p in sorted(here.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.zip':
            if p.suffix=='.npz':
                with np.load(p,allow_pickle=False) as z:
                    if any(z[k].dtype.kind=='O' for k in z.files):raise ValueError('Object NPZ')
            files.append(p)
    r.dump(manifest,{'scope':'Private fixed reference numerical reproduction; same installed environment',
        'files':{str(p.relative_to(here)):r.sha(p) for p in files}})
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files+[manifest]:z.write(p,'reference_reproduction/'+str(p.relative_to(here)))
    print(json.dumps({'archive_sha256':r.sha(archive),'manifest_sha256':r.sha(manifest),
        'bytes':archive.stat().st_size,'files':len(files)+1},indent=2))


if __name__=='__main__':main()
