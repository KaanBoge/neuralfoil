"""Approval-gated two-source/eleven-synthetic-test wrapper; no default execution."""
from pathlib import Path
import argparse,datetime,hashlib,io,json,os,subprocess,sys,time,traceback,types,zipfile
HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
BASE=HERE.parent
EXTRACT=BASE.parent/'package_v5_fresh_extraction_v1/NeuralFoil_Private_Submission_Package_v5'
HREL='reproduction/qualified_harm/qualified_harm_private_v1.zip'
MONITOR=BASE.parent/'inference_benchmark_plan/watchdog_v6.py'
PINS={BASE/'PHASE2_PROPOSED_ALLOWLIST.json':'fbfa4d12b3f995bc094637b3db25e1c0e171da5dd152305def0c89fbf2e122d2',BASE/'phase1/SOURCE_TEXT.json':'34d57cf6e077d64d45082357377fb01569a53a7942eca6068c2d827252599abe',BASE/'EXTRACTION.json':'606d5063ca973ac1c207daee9d5c0b5fc1ccd2e338779bf2af7f1ba5c8f923cd',EXTRACT/'MANIFEST.json':'9158ec51bbc5414f42b338b13ca722c4d58ac93c2f5c9434312ac7842f344ba9',MONITOR:'eb0e205c0fb097b44fa5a30046171eacadfd35a0d076b4eec8cbbb70fd990e24'}
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(p):
 p=Path(p)
 if any(x.is_symlink() for x in [p,*p.parents]):raise ValueError('symlink')
 return p.read_bytes()
def checked(p,h):
 b=raw(p)
 if sha(b)!=h:raise ValueError('changed pin '+str(p))
 return b
def write(p,d):
 b=json.dumps(d,indent=2,allow_nan=False).encode()+b'\n'
 with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def approve(a,source_sha,registry_sha,output):
 if set(a)!={'phase','source_sha256','registry_sha256','output','runtime','seconds','rss_bytes','output_bytes','workers'}:raise ValueError('approval keys')
 expected={'phase':'eleven_synthetic_integrity_tests_only','source_sha256':source_sha,'registry_sha256':registry_sha,'output':str(output),'runtime':'/opt/anaconda3/bin/python','seconds':120,'rss_bytes':536870912,'output_bytes':16777216,'workers':1}
 if any(type(a[k]) is not type(v) or a[k]!=v for k,v in expected.items()):raise ValueError('approval contract')
def selected_sources(b,allow,outer,ledger):
 if sha(b)!=allow['archive_sha256'] or outer['files'][HREL]['sha256']!=sha(b):raise ValueError('inner/outer binding')
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  if len(z.namelist())!=len(set(z.namelist())):raise ValueError('duplicate members')
  mb=z.read('manifest.json');ledger.append({'member':'manifest.json','operation':'JSON parse','sha256':sha(mb)})
  if sha(mb)!=allow['inner_manifest_sha256']:raise ValueError('inner manifest')
  m=json.loads(mb);out={}
  for name,h in allow['source_members'].items():
   if name not in {'code/integrity.py','code/test_integrity.py'}:raise ValueError('source allowlist')
   value=z.read(name);ledger.append({'member':name,'operation':'source read','sha256':sha(value)})
   if sha(value)!=h or m['files'][name]!={'sha256':h,'bytes':len(value)}:raise ValueError('source member pin')
   out[Path(name).name]=value
 if set(out)!={'integrity.py','test_integrity.py'}:raise ValueError('two sources required')
 return out
def execute(approval,approval_sha):
 out=HERE/'actual_attempt_1'
 if out.exists() or out.is_symlink():raise FileExistsError('preserve attempt')
 ab=checked(approval,approval_sha);rb=raw(HERE/'REGISTRY.json');reg=json.loads(rb)
 approve(json.loads(ab),sha(raw(Path(__file__))),sha(rb),out)
 if sys.executable!='/opt/anaconda3/bin/python' or any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']):raise ValueError('runtime/thread contract')
 buffers={p:checked(p,h) for p,h in PINS.items()}
 for n,h in reg['sources'].items():checked(HERE/n,h)
 out.mkdir();start=time.monotonic();ledger=[];proc=None
 write(out/'ATTEMPT.json',{'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'approval_sha256':approval_sha,'registry_sha256':sha(rb),'source_sha256':sha(raw(Path(__file__)))})
 try:
  allow=json.loads(buffers[BASE/'PHASE2_PROPOSED_ALLOWLIST.json']);outer=json.loads(buffers[EXTRACT/'MANIFEST.json'])
  ledger.extend({'file':str(p),'sha256':sha(b),'operation':'authenticated buffer read'} for p,b in buffers.items())
  archive=checked(EXTRACT/HREL,allow['archive_sha256']);ledger.append({'file':str(EXTRACT/HREL),'sha256':sha(archive),'operation':'archive bytes authenticated'})
  src=selected_sources(archive,allow,outer,ledger);text=json.loads(buffers[BASE/'phase1/SOURCE_TEXT.json'])
  for n,b in src.items():
   if text['qualified_harm!code/'+n].encode()!=b:raise ValueError('phase1 source bridge')
  cmd=allow['command']
  if cmd[:5]!=['/opt/anaconda3/bin/python','-B','-m','unittest','-v'] or len(cmd)!=16 or len(set(cmd[5:]))!=11 or any(not x.startswith('test_integrity.Integrity.test_') for x in cmd[5:]):raise ValueError('eleven-method command')
  sd=out/'sources';sd.mkdir();tmp=out/'synthetic_tmp';tmp.mkdir()
  for n,b in src.items():
   with (sd/n).open('xb') as f:f.write(b)
  monitor=types.ModuleType('pinned_monitor');exec(compile(buffers[MONITOR],str(MONITOR),'exec'),monitor.__dict__)
  def size():return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
  env=dict(os.environ,TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1');env.pop('PYTHONPATH',None)
  monitor.budget(start,120,size,16777216)
  with (out/'stdout.txt').open('xb') as so,(out/'stderr.txt').open('xb') as se:
   proc=subprocess.Popen(cmd,cwd=sd,env=env,stdout=so,stderr=se)
   result=monitor.monitor(proc,start,120,536870912,size,16777216)
  write(out/'PROCESS.json',result)
  if result['failure'] or result['exit_code']!=0 or not result['valid_RSS_samples'] or result['terminal_unavailable_recovered']:raise RuntimeError('synthetic child/observed resource failure')
  # unittest's exact named invocation plus result count guards against discovery expansion.
  err=raw(out/'stderr.txt').decode()
  if 'Ran 11 tests in ' not in err or not err.rstrip().endswith('OK'):raise ValueError('eleven tests did not pass')
  for n,b in src.items():
   if raw(sd/n)!=b:raise ValueError('executed source mutation')
  for p,h in PINS.items():checked(p,h)
  checked(EXTRACT/HREL,allow['archive_sha256']);checked(approval,approval_sha)
  if raw(HERE/'REGISTRY.json')!=rb:raise ValueError('registry mutation')
  for n,h in reg['sources'].items():checked(HERE/n,h)
  monitor.budget(start,120,size,16777216)
  files={p.relative_to(out).as_posix():sha(raw(p)) for p in out.rglob('*') if p.is_file()}
  write(out/'COMPLETE_PENDING.json',{'status':'PASS_ELEVEN_SYNTHETIC_TESTS_ONLY','seconds':time.monotonic()-start,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'approval_sha256':approval_sha,'registry_sha256':sha(rb),'outputs':files,'ledger':ledger,'command':cmd,'new_scientific_member_reads':0,'numpy_runtime_scope':'synthetic fixtures only','observed_resource_scope':'periodic child RSS only; recovered terminal unavailable rejected because no child self-peak receipt exists'})
  monitor.budget(start,120,size,16777216);(out/'COMPLETE_PENDING.json').rename(out/'COMPLETE.json')
 except BaseException as e:
  write(out/'FAILURE.json',{'exception':repr(e),'traceback':traceback.format_exc(),'ledger':ledger,'elapsed_seconds':time.monotonic()-start,'approval_sha256':approval_sha,'registry_sha256':sha(rb)});raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True);a=p.parse_args();execute(a.approval,a.approval_sha256)
