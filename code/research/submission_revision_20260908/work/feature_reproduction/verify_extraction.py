"""One fresh-extraction verification in the same installed forward environment."""
import hashlib,json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
archive=root/'feature_reproduction_private.zip'
temp=Path(tempfile.mkdtemp(prefix='nf-feature-private-',dir='/private/tmp'))
with zipfile.ZipFile(archive) as z:z.extractall(temp)
home=temp/'feature_reproduction';manifest=json.loads((home/'release_manifest.json').read_text())
for path,digest in manifest['files'].items():assert sha(home/path)==digest,path
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(temp/'mpl'),PYTHONDONTWRITEBYTECODE='1')
commands=[[sys.executable,'-m','unittest','discover','-s',str(home),'-p','test_*.py'],[sys.executable,str(home/'regenerate_portable.py'),'--output',str(temp/'results')]]
logs=[]
for cmd in commands:
    r=subprocess.run(cmd,cwd=temp,env=env,text=True,capture_output=True);logs.append({'command':cmd,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
    (root/'extraction_transcript.json').write_text(json.dumps(logs,indent=2)+'\n')
    assert r.returncode==0,r.stderr
complete=json.loads((temp/'results/complete.json').read_text())
assert all(r['unequal_elements']==0 for r in complete['comparisons'])
result={'scope':'Same installed runtime, fresh temporary extraction; no model refits.','archive_sha256':sha(archive),'release_manifest_sha256':sha(home/'release_manifest.json'),'temporary_directory':str(temp),'comparisons':len(complete['comparisons']),'unequal_elements':sum(r['unequal_elements'] for r in complete['comparisons']),'complete_sha256':sha(temp/'results/complete.json'),'transcript_sha256':sha(root/'extraction_transcript.json'),'seconds':complete['seconds']}
(root/'extraction_verified.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
