"""Single fresh-extraction replay; no fitting and no original source access."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,zipfile
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    bundle=HERE/'bundle'; archive=HERE/'bounds_private.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(bundle)))
    target=Path(tempfile.mkdtemp(prefix='nf-bounds-replay-'))
    with zipfile.ZipFile(archive) as z:z.extractall(target)
    h=sha(bundle/'manifest.json')
    if sha(target/'manifest.json')!=h:raise ValueError('extraction manifest mismatch')
    replay=subprocess.run([sys.executable,str(target/'check.py'),'--manifest-sha256',h],cwd=target,text=True,capture_output=True)
    tests=subprocess.run([sys.executable,'-m','unittest','test_check','-v'],cwd=target,text=True,capture_output=True)
    transcript=replay.stdout+replay.stderr+tests.stdout+tests.stderr
    (HERE/'clean_extraction_transcript.txt').write_text(transcript)
    if replay.returncode or tests.returncode:raise RuntimeError(transcript)
    result={'status':'PASS','python':sys.version,'numpy_only_replay':json.loads(replay.stdout),'tests':6,
            'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'manifest_sha256':h,
            'fresh_extraction':str(target),'transcript_sha256':sha(HERE/'clean_extraction_transcript.txt'),
            'extracted_payload_sha256':{str(p.relative_to(target)):sha(p) for p in sorted(target.rglob('*')) if p.is_file() and '__pycache__' not in str(p)},
            'scope':'Same installed environment, new directory; no independent-environment claim; no fits.'}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='extracted_payload_sha256'},indent=2))
if __name__=='__main__':main()
