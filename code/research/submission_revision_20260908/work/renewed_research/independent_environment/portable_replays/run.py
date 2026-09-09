"""Witness unchanged portable arithmetic in separately provisioned fitting venv."""
from pathlib import Path, PurePosixPath
import hashlib,json,os,stat,subprocess,time,zipfile,sys
HERE=Path(__file__).resolve().parent
ENV=HERE.parent
STUDY=ENV.parent
PY=ENV/'venv_fit/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
jobs=[('sensitivity',STUDY/'uncertainty_review/portable_sensitivity/portable_sensitivity_private.zip','5bb33a1b14d9d4377d9720f7123e20d0e8b5a16e738448c6798e2f38d32be750','2bbc8e5e87a5a8cab31afcd24bcda887ecad405d301e1c8e0015b549162ed78d'),('incremental',STUDY/'model_proposal/portable/incremental_harm_private.zip','6b95849963500179f19e81915f61693c6837f53c0d294bd5f4f4a5abac135c5c','13573747b961d9d02ef230e21e70e3b5c7663d361b2c4df874cb661e5cdf244a')]
env=os.environ.copy();env.update(PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
records=[]
def command(name,args,cwd):
    start=time.monotonic();p=subprocess.run([str(PY),'-B',*args],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log=HERE/(name+'.log');assert not log.exists();log.write_text(p.stdout)
    r=dict(name=name,args=args,cwd=str(cwd),seconds=time.monotonic()-start,exit_code=p.returncode,log_sha256=sha(log));records.append(r)
    (HERE/'EXECUTION.json').write_text(json.dumps(records,indent=2)+'\n')
    print(name,p.returncode,r['seconds'],flush=True)
    if p.returncode:raise RuntimeError('Retained failure '+name)
command('environment',['-c','import sys,site,numpy,pandas,json; print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,site=site.getsitepackages(),user_site=site.ENABLE_USER_SITE,path=sys.path,numpy=numpy.__version__,numpy_path=numpy.__file__,pandas=pandas.__version__,pandas_path=pandas.__file__)))'],HERE)
for name,archive,zipsha,msha in jobs:
    assert sha(archive)==zipsha
    dest=HERE/(name+'_extracted');dest.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        members=z.infolist();names=[i.filename for i in members]
        assert len(names)==len(set(names))
        assert sum(i.file_size for i in members)<100_000_000
        for i in members:
            p=PurePosixPath(i.filename)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in i.filename and ':' not in i.filename
            assert not stat.S_ISLNK(i.external_attr>>16)
            assert not i.flag_bits&1
        z.extractall(dest)
    manifests=list(dest.rglob('manifest.json'));assert len(manifests)==1
    root=manifests[0].parent;assert sha(manifests[0])==msha
    m=json.loads(manifests[0].read_text());files=m.get('files',m.get('members'))
    assert {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}==set(files)|{'manifest.json'}
    for f,h in files.items():assert sha(root/f)==h
    before={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}
    records.append(dict(stage=name,archive=str(archive),archive_sha256=zipsha,manifest_sha256=msha,root=str(root),file_count=len(before)))
    if name=='sensitivity':
        command(name+'_verify',['replay.py','verify','--manifest-sha256',msha],root)
        command(name+'_tests',['-m','unittest','-v','test_sensitivity','test_portable'],root)
        command(name+'_replay',['replay.py','reproduce','--manifest-sha256',msha,'--output',str(HERE/(name+'_output'))],root)
    else:
        command(name+'_tests',['-m','unittest','-v','test_integrity.py'],root)
        command(name+'_replay',['replay.py','--manifest-sha256',msha,'--output',str(HERE/(name+'_output'))],root)
    after={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}
    assert before==after and sha(archive)==zipsha
    records.append(dict(stage=name,source_immutable=True,output_sha256={p.name:sha(p) for p in (HERE/(name+'_output')).iterdir() if p.is_file()}))
(HERE/'COMPLETE.json').write_text(json.dumps(dict(records=records,new_core_fits=0,new_dependencies=0,isolated_third_party_environment=True,same_host=True),indent=2)+'\n')
