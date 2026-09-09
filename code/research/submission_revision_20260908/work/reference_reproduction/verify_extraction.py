"""One fresh extraction smoke; no histogram or LP fitting."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2,allow_nan=False)


def main():
    root=Path(__file__).resolve().parent;archive=root/'reference_reproduction_private.zip'
    record=root/'extraction_verified.json'
    if record.exists():raise FileExistsError('Preserve previous smoke')
    assert sha(archive)=='5ed12092e3d4f8543791ff750d35f61e6172657d0fc1b1343f6240aaa73fb3bd'
    temp=Path(tempfile.mkdtemp(prefix='nf-reference-replay-',dir='/private/tmp'))
    with zipfile.ZipFile(archive) as z:
        for n in z.namelist():
            p=PurePosixPath(n)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in n
        z.extractall(temp)
    home=temp/'reference_reproduction';manifest=json.loads((home/'release_manifest.json').read_text())
    for name,h in manifest['files'].items():assert sha(home/name)==h,name
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    commands=[[sys.executable,'-m','unittest','discover','-s',str(home),'-p','test_replay.py','-v'],
              [sys.executable,str(home/'verify_results.py')]]
    logs=[]
    for command in commands:
        result=subprocess.run(command,cwd=temp,env=env,text=True,capture_output=True)
        logs.append({'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        if result.returncode:
            write(root/'extraction_failure.json',{'temporary_path':str(temp),'logs':logs})
            raise RuntimeError('Smoke failed; retain extraction')
    write(root/'extraction_transcript.json',logs)
    verdict=json.loads(logs[-1]['stdout'])
    write(record,{'status':'PASS','mode':'fresh_extraction_completed_output_verification_no_fitting',
        'archive_sha256':sha(archive),'release_manifest_sha256':sha(home/'release_manifest.json'),
        'files_authenticated':len(manifest['files']),'temporary_path':str(temp),'python':sys.executable,
        'tests':4,'verifier_result':verdict,'transcript_sha256':sha(root/'extraction_transcript.json'),
        'new_histogram_fits':0,'new_policy_fits':0,'same_installed_environment':True})
    print(record.read_text())


if __name__=='__main__':main()
