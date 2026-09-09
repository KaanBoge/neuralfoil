"""One fresh-extraction same-environment replay, preserving all attempt evidence."""
from pathlib import Path,PurePosixPath
import hashlib,json,os,stat,subprocess,sys,tempfile,zipfile

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    if (HERE/'fresh_verification.json').exists() or (HERE/'fresh_start.json').exists():raise FileExistsError('Fresh attempt already exists')
    export=json.loads((HERE/'export_verified.json').read_text());archive=HERE/'portable_sensitivity_private.zip'
    if sha(archive)!=export['archive_sha256']:raise ValueError('Archive changed')
    temp=Path(tempfile.mkdtemp(prefix='nf-sensitivity-portable-'))
    (HERE/'fresh_start.json').write_text(json.dumps(dict(archive_sha256=sha(archive),temporary_directory=str(temp),python=sys.executable),indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        seen=set()
        for info in z.infolist():
            name=PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or str(name)!=info.filename or '\\' in info.filename or info.filename in seen:raise ValueError('Unsafe archive path')
            if stat.S_ISLNK(info.external_attr>>16):raise ValueError('Symlink archive')
            seen.add(info.filename)
        z.extractall(temp)
    root=temp/'portable_sensitivity';out=temp/'reproduced';records=[]
    commands=[['replay.py','verify','--manifest-sha256',export['manifest_sha256']],
              ['-m','unittest','-v','test_sensitivity','test_portable'],
              ['replay.py','reproduce','--manifest-sha256',export['manifest_sha256'],'--output',str(out)]]
    for i,args in enumerate(commands):
        completed=subprocess.run([sys.executable,'-B']+args,cwd=root,text=True,capture_output=True,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'))
        p=HERE/f'fresh_step_{i}.txt';p.write_text(completed.stdout+completed.stderr)
        records.append(dict(command=[sys.executable,'-B']+args,returncode=completed.returncode,transcript_sha256=sha(p)))
        if completed.returncode:raise RuntimeError('Fresh step failed; evidence preserved '+str(i))
    result=json.loads((out/'verification.json').read_text())
    assert result['status']=='PASS' and result['grid_rows']==23808 and result['radius_rows']==2976
    assert 'Ran 17 tests' in (HERE/'fresh_step_1.txt').read_text()
    # Refusal must not add a failure file or change any completed output byte.
    before={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    refused=subprocess.run([sys.executable,'-B']+commands[-1],cwd=root,text=True,capture_output=True)
    (HERE/'existing_output_refusal.txt').write_text(refused.stdout+refused.stderr)
    assert refused.returncode!=0 and before=={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    assert sha(archive)==export['archive_sha256']
    for n,h in json.loads((root/'manifest.json').read_text())['files'].items():assert sha(root/n)==h
    final=dict(status='PASS',archive_sha256=sha(archive),manifest_sha256=export['manifest_sha256'],fresh_root=str(root),output_root=str(out),
        tests=17,new_model_fits=0,scientific_replays=1,existing_output_refused_without_mutation=True,steps=records,
        result=result,result_sha256=sha(out/'verification.json'),same_installed_environment=True,
        output_files_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    (HERE/'fresh_verification.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps(final,indent=2))

if __name__=='__main__':main()
