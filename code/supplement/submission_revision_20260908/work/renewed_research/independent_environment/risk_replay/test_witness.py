"""Run frozen synthetic tests in the fresh fitting environment; no data fitting."""
from pathlib import Path
import os,subprocess,json,hashlib,time
r=Path(__file__).resolve().parent
p=r.parents[3]/'work/renewed_research/model_proposal'
cmd=[str(r.parent/'venv_fit/bin/python'),'-B','-m','unittest','discover','-s',str(p),'-p','test_incremental_harm.py','-v']
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
env.pop('PYTHONPATH',None)
t=time.monotonic()
with (r/'synthetic_tests.log').open('x') as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env)
with (r/'synthetic_tests.json').open('x') as f:json.dump({'command':cmd,'returncode':result.returncode,'seconds':time.monotonic()-t,'stdout_sha256':hashlib.sha256((r/'synthetic_tests.log').read_bytes()).hexdigest()},f,indent=2)
assert result.returncode==0
print((r/'synthetic_tests.log').read_text())
