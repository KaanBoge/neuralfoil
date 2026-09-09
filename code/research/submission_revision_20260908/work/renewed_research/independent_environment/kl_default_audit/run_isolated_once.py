"""One explicit approved isolated replay; no retry or source modification."""
from pathlib import Path
import datetime,hashlib,json,os,subprocess,time
H=Path(__file__).resolve().parent
R=H.parents[1];P=R/'model_proposal/kl_bound_study/portable_plan'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
 with p.open('x') as f:json.dump(d,f,indent=2)
approval=P/'ROOT_ISOLATED_REPLAY_APPROVAL.json'
ah='d734b915bd7d3e563d35bd9806e15718000e139e8389be789bdb9cce2660c9d2'
assert sha(approval)==ah
a=json.loads(approval.read_text())
registry=P/'REGISTRY_v3.json';assert sha(registry)==a['source_registry_sha256']
r=json.loads(registry.read_text())
for n,h in r['sources'].items():assert sha(P/n)==h
for n,h in r['inputs'].items():assert sha(Path(n))==h
entry=P/'fresh_extraction_v1/code/replay.py';assert sha(entry)==a['executed_replay_sha256']
parent=R/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
addon=P/'kl_harm_private_v1.zip'
assert sha(parent)==a['parent_archive_sha256'] and sha(addon)==a['archive_sha256']
assert sha(P/'replay_default_attempt_1/COMPLETE.json')==a['prerequisite_default_complete_sha256']
assert sha(H/'AUDIT.json')==a['prerequisite_independent_audit_sha256']
out=P/a['output'];assert not out.exists()
for n in ['ISOLATED_START.json','ISOLATED_END.json','ISOLATED_STDOUT.txt','ISOLATED_STDERR.txt']:assert not (H/n).exists()
cmd=[a['interpreter'],str(entry),'--parent',str(parent),'--archive',str(addon),'--archive-sha256',a['archive_sha256'],'--manifest-sha256',a['manifest_sha256'],'--output',str(out),'--approval',str(approval),'--approval-sha256',ah]
env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
runtime=subprocess.check_output([a['interpreter'],'-c','import sys,site,json,numpy,pandas;print(json.dumps(dict(executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,python=sys.version,numpy=numpy.__version__,pandas=pandas.__version__,path=sys.path,user_site=site.ENABLE_USER_SITE)))'],env=env,text=True)
record={'started_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'approval_sha256':ah,'command':cmd,'runtime':json.loads(runtime),'pyvenv_cfg':(Path(a['interpreter']).parents[1]/'pyvenv.cfg').read_text(),'entry_sha256':sha(entry),'orchestrator_sha256':sha(Path(__file__)),'output':str(out)}
write(H/'ISOLATED_START.json',record);start=time.monotonic()
with (H/'ISOLATED_STDOUT.txt').open('x') as stdout,(H/'ISOLATED_STDERR.txt').open('x') as stderr:
 try:
  proc=subprocess.run(cmd,env=env,stdout=stdout,stderr=stderr,timeout=930)
  record['exit_code']=proc.returncode
 except BaseException as e:record['orchestration_exception']=repr(e)
record.update(finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start)
record['archive_unchanged']=sha(addon)==a['archive_sha256'] and sha(parent)==a['parent_archive_sha256']
record['entry_unchanged']=sha(entry)==a['executed_replay_sha256']
record['output_sha256']={p.name:sha(p) for p in out.iterdir() if p.is_file()} if out.exists() else {}
write(H/'ISOLATED_END.json',record)
print(json.dumps({k:v for k,v in record.items() if k in ['exit_code','elapsed_seconds','output_sha256','orchestration_exception']},indent=2))
