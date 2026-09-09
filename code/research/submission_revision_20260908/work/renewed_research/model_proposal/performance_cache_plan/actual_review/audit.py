"""Saved metadata/opaque-byte audit only. Never imports inference or loads NPZ."""
from pathlib import Path
import hashlib,json,random,statistics,math,collections
H=Path(__file__).resolve().parent
P=next(p for p in H.parents if p.name=='NeuralFoil_Research_Paper')
W=P/'submission_revision_20260908/work/renewed_research'
E=H.parent/'implementation/execution_plan';A=E/'actual_attempt_1'
V=W/'independent_environment/inference_benchmark_plan/actual_v6_attempt_1'
pins={}
def digest(p):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if p in pins:assert pins[p]==h
 pins[p]=h;return h
def read(p):return json.loads(Path(p).read_bytes())
def bound(p,h):assert digest(p)==h,str(p)
bound(A/'COMPLETE.json','e7541ec72e28cda18ae2ee63fe4819feac258cfa62295289fca9e9ccb8652e86')
bound(E/'ROOT_ACTUAL_APPROVAL.json','c9aebf28856df4bede78cbed9343758888ce0d705ee465dbf701ea8d9ff8fce5')
bound(E/'REGISTRY.json','79ecee7877ae7fd9aa9e9fd8f10391c09dee7532e4f28dd78c48e24b0031b11a')
c=read(A/'COMPLETE.json');r=read(E/'REGISTRY.json');approval=read(E/'ROOT_ACTUAL_APPROVAL.json')
assert approval['output']==str(A) and approval['host_other_scientific_jobs_stopped'] is True
for k in ['runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','routes','schedule','cold_repeats','warmups','warm_repeats','workers','reference_contract','optimization_contract']:assert approval[k]==r[k]
assert c['approval_sha256']==digest(E/'ROOT_ACTUAL_APPROVAL.json') and c['registry_sha256']==digest(E/'REGISTRY.json')
assert c['status']=='COMPLETE_REQUIRES_INDEPENDENT_REVIEW' and c['elapsed_seconds']<600
assert len(c['outputs'])==103 and set(p.name for p in A.iterdir() if p.is_file())==set(c['outputs'])|{'COMPLETE.json'}
for n,h in c['outputs'].items():bound(A/n,h)
for n,h in r['sources'].items():bound(E/r['source_paths'][n],h)
for n,h in r['v6_receipts'].items():bound(P/n,h)
for n,h in r['scopes']['all']['files'].items():bound(P/n,h)
for n,s in r['scopes']['all']['archives'].items():bound(P/n,s['sha256'])
bound(A/'preflight_COMPLETE.json','95997529f74bca989ea10c065fce2a000309f294ffd185469ad8494ac74a1ecf')
bound(A/'COMPONENT_FIDELITY.json','87cec19424dde5f932cc340b925c5d0c00e167c7aa06455dc46f2f06ee9426c2')
f=read(A/'COMPONENT_FIDELITY.json');assert f['status']=='PASS_FULL_COMPONENT_BIT_FIDELITY' and f['routes']==7
assert f['archive_inventory']==read(A/'ARCHIVE_COMPARISONS.json')==read(V/'ARCHIVE_COMPARISONS.json')
for route,s in r['v6_reference_files'].items():bound(A/('reference_'+route+'.npz'),s['sha256'])
phase_rows=[];all_events=[]
for phase,route in [('preflight',None)]+[('cold',x) for x in r['routes']]+[('warm',None)]:
 name=phase+('_'+route if route else '');rec=read(A/(name+'_COMPLETE.json'));proc=read(A/(name+'_PROCESS.json'))
 assert rec['status']=='PASS' and rec['phase']==phase and rec['route']==route
 for k in ['approval_sha256','registry_sha256','reference_contract','optimization_contract']:assert rec[k]==c[k]
 assert rec['predecessor_sha256']==(None if phase=='preflight' else c['preflight_sha256'])
 for n,h in rec['outputs'].items():bound(A/n,h);assert c['outputs'][n]==h
 assert proc['exit_code']==0 and proc['failure'] is None and proc['valid_RSS_samples']>0
 assert 0<proc['peak_sampled_RSS_bytes']<=r['max_rss_bytes']
 assert math.isfinite(rec['self_ru_maxrss_bytes']) and 0<rec['self_ru_maxrss_bytes']<=r['max_rss_bytes']
 assert rec['ru_maxrss_units']=='bytes on explicitly required macOS'
 cmd=[r['runtime'],str(E/'runner_cache.py'),'--project',str(P),'--approval',str(E/'ROOT_ACTUAL_APPROVAL.json'),'--approval-sha256',c['approval_sha256'],'--output',str(A),'--phase',phase]
 if route:cmd+=['--route',route]
 if phase!='preflight':cmd+=['--predecessor-sha256',c['preflight_sha256']]
 assert proc['command']==cmd
 scope=r['scopes'][route if phase=='cold' else 'all'];members=[]
 for event in rec['events']:
  file=event.get('file');operation=event['operation']
  if not file:continue
  if operation=='NPZ member materialization':
   if file.startswith(str(A)):
    rr=next(x for x in r['routes'] if file.endswith('reference_'+x+'.npz'));allowed=r['v6_reference_files'][rr]['members']
   else:allowed=scope['arrays'][file]
   assert event['member'] in allowed;members.append((file,event['member']))
  elif operation=='archive member read':
   ar,member=file.split('!',1);assert scope['archives'][ar]['members'][member]['sha256']==event['sha256']
  elif '!' not in file and 'sha256' in event:
   path=Path(file) if Path(file).is_absolute() else P/file;bound(path,event['sha256'])
  if operation=='file read' and not Path(file).is_absolute():assert file in scope['files']
  if operation=='archive read':assert file in scope['archives']
 all_events+=rec['events']
 phase_rows.append({'phase':name,'process_seconds':proc['elapsed_seconds'],'child_receipt_seconds':rec['elapsed_seconds'],'samples':proc['valid_RSS_samples'],'sampled_peak_bytes':proc['peak_sampled_RSS_bytes'],'self_peak_bytes':rec['self_ru_maxrss_bytes'],'terminal_recovery':proc['terminal_unavailable_recovered'],'RSS_diagnostics':proc['RSS_diagnostics'],'cleanup_events':proc['cleanup_events'],'materializations':len(members),'unique_materializations':len(set(members))})
assert read(A/'WARM_COUNTS.json')=={'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49}
rng=random.Random(20260908);schedule=[]
for rep in range(7):
 order=list(r['routes']);rng.shuffle(order);schedule.extend((rep,x) for x in order)
actual_order=[(int(n.split('_')[1]),read(A/n)['route']) for n in read(A/'warm_COMPLETE.json')['outputs'] if n.startswith('warm_')]
assert actual_order==schedule
rows=[]
def quantile(v,q):
 s=sorted(v);x=(len(s)-1)*q;i=int(x);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(x-i)
for route in r['routes']:
 vals=[];old=[]
 for rep in range(7):
  x=read(A/f'warm_{rep}_{route}.json');y=read(V/f'warm_{rep}_{route}.json')
  assert x['route']==route and x['repeat']==rep and x['output_rows']==497 and x['seconds']>0
  vals.append(x['seconds']);old.append(y['seconds'])
 med=statistics.median(vals);previous=statistics.median(old);cold=read(A/f'cold_{route}.json')
 assert cold['route']==route and cold['rows']==497
 rows.append({'route':route,'warm_median_seconds':med,'warm_Q25_seconds':quantile(vals,.25),'warm_Q75_seconds':quantile(vals,.75),'cold_request_seconds':cold['request_seconds'],'cold_setup_seconds':cold['route_specific_setup_seconds'],'V6_median_seconds':previous,'separate_run_median_reduction_percent':100*(1-med/previous)})
for p,h in list(pins.items()):bound(p,h)
out={'status':'PASS_SAVED_METADATA_AND_BYTE_AUDIT_NO_INFERENCE_REPLAY','complete_sha256':digest(A/'COMPLETE.json'),'registry_sha256':digest(E/'REGISTRY.json'),'approval_sha256':digest(E/'ROOT_ACTUAL_APPROVAL.json'),'parent_seconds':c['elapsed_seconds'],'accepted_outputs':103,'authenticated_unique_paths':len(pins),'reference_archives_byte_identical':7,'schedule':schedule,'timings':rows,'phases':phase_rows,'archive_difference_inventory':f['archive_inventory'],'source_implied_component_checks':{'design_blocks':4,'independent_original_parameter_fits':12,'shared_parameter_fits':4,'complete_unquantized_response_comparisons':8,'routes':7,'cohorts':2,'rows_per_route':497,'false_gate_rows':25},'component_count_scope':'implied by authenticated fixed source and successful full barrier; no per-block counter receipts or new diagnostic arrays were saved','file_sha256':{str(p):h for p,h in pins.items()},'inference_calls_in_audit':0,'NPZ_materializations_in_audit':0}
with (H/'AUDIT.json').open('x') as f:json.dump(out,f,indent=2,allow_nan=False)
print(json.dumps({k:out[k] for k in ['status','parent_seconds','accepted_outputs','authenticated_unique_paths','timings','phases']},indent=2))
