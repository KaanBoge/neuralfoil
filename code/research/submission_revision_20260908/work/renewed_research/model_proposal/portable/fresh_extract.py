"""One bounded fresh extraction/replay; no package or old output overwrite."""
from pathlib import Path,PurePosixPath
import hashlib,io,json,os,stat,subprocess,sys,time,zipfile

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    record=json.loads((HERE/'EXPORT.json').read_text())
    raw=(HERE/record['archive']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==record['archive_sha256']
    root=HERE/'fresh_execution';root.mkdir(exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();assert len(names)==len(set(names))
        for item in z.infolist():
            path=PurePosixPath(item.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in item.filename
            assert path.parts[0]=='incremental_harm_private'
            assert not stat.S_ISLNK(item.external_attr>>16)
        z.extractall(root)
    package=root/'incremental_harm_private'
    assert sha(package/'manifest.json')==record['manifest_sha256']
    env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
    start=time.monotonic()
    command=[sys.executable,'-B','replay.py','--manifest-sha256',record['manifest_sha256'],'--output',str(root/'replay_output')]
    run=subprocess.run(command,cwd=package,env=env,text=True,capture_output=True)
    (root/'replay_stdout.txt').write_text(run.stdout);(root/'replay_stderr.txt').write_text(run.stderr)
    if run.returncode:raise RuntimeError('Fresh replay failed; logs preserved')
    tests=subprocess.run([sys.executable,'-B','-m','unittest','-v','test_integrity.py'],cwd=package,env=env,text=True,capture_output=True)
    (root/'integrity_tests.txt').write_text(tests.stdout+tests.stderr)
    if tests.returncode:raise RuntimeError('Fresh integrity tests failed; logs preserved')
    manifest=json.loads((package/'manifest.json').read_text())
    for path,h in manifest['members'].items():assert sha(package/path)==h
    report={'status':'fresh_extraction_replay_complete','archive_sha256':record['archive_sha256'],
        'manifest_sha256':record['manifest_sha256'],'source_sha256':sha(__file__),
        'replay_report_sha256':sha(root/'replay_output/REPORT.json'),
        'integrity_tests_sha256':sha(root/'integrity_tests.txt'),'integrity_tests':10,
        'original_synthetic_tests':15,'payload_reauthenticated_unchanged':len(manifest['members']),
        'elapsed_seconds':time.monotonic()-start,'interpreter':sys.executable,'new_core_fits':0,
        'scope':'Fresh archive extraction in same installed numerical environment, not fresh outcome validation'}
    (HERE/'FRESH_EXECUTION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
