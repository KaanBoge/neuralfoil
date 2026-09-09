"""Saved JSON/source/byte identity audit only; no model or NPZ parsing."""
from pathlib import Path
import hashlib,json,random,statistics,math
R=Path('/PATH_TO_YOUR_HOME/Documents/NeuralFoil_Research_Paper');B=R/'submission_revision_20260908/work/renewed_research/independent_environment/inference_benchmark_plan';P=B/'actual_v6_attempt_1';pins={}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def pin(p,h):
 p=Path(p);assert not any(x.is_symlink() for x in [p,*p.parents]);assert sha(p)==h,str(p);pins[str(p)]=h;return p
def read(p):return json.loads(p.read_bytes())
cp=pin(P/'COMPLETE.json','5d0eb7516743161f1c228fed34755ffeb45b31a9108d31df1babdd0c75845fa8');c=read(cp)
assert c['status']=='COMPLETE_REQUIRES_INDEPENDENT_REVIEW' and len(c['outputs'])==102
a=read(pin(B/'ROOT_ACTUAL_APPROVAL_V6.json',c['approval_sha256']));r=read(pin(B/'REGISTRY_v6.json',c['registry_sha256']))
assert a['authorized_phase']=='one_fixed_inference_benchmark_v6' and a['registry_sha256']==c['registry_sha256'] and Path(a['output'])==P
for k in ['runtime','max_seconds','max_request_seconds','max_rss_bytes','max_output_bytes','routes','schedule','cold_repeats','warmups','warm_repeats','workers','reference_contract']:assert a[k]==r[k],k
for n,h in r['sources'].items():pin(B/n,h)
for n,h in c['outputs'].items():pin(P/n,h)
assert {p.name for p in P.iterdir()}==set(c['outputs'])|{'COMPLETE.json'}
assert c['elapsed_seconds']<r['max_seconds'] and sum(p.stat().st_size for p in P.iterdir())<r['max_output_bytes']
routes=r['routes'];rng=random.Random(20260908);schedule=[]
for i in range(7):
 order=list(routes);rng.shuffle(order);schedule.extend([[i,x] for x in order])
assert schedule==r['schedule']
pre=read(pin(P/'preflight_COMPLETE.json',c['preflight_sha256']))
assert set(pre['outputs'])=={'ARCHIVE_COMPARISONS.json'}|{'reference_'+x+'.npz' for x in routes}
phases=[]
for phase,route in [('preflight',None)]+[('cold',x) for x in routes]+[('warm',None)]:
 name=phase+('_'+route if route else '');s=read(P/(name+'_COMPLETE.json'));proc=read(P/(name+'_PROCESS.json'))
 assert s['status']=='PASS' and s['phase']==phase and s['route']==route and s['approval_sha256']==c['approval_sha256'] and s['registry_sha256']==c['registry_sha256'] and s['reference_contract']==c['reference_contract']
 assert s['predecessor_sha256']==(None if phase=='preflight' else c['preflight_sha256'])
 assert proc['failure'] is None and proc['exit_code']==0 and proc['valid_RSS_samples']>0 and proc['RSS_available'] is True
 assert 0<proc['peak_sampled_RSS_bytes']<=r['max_rss_bytes'] and 0<s['self_ru_maxrss_bytes']<=r['max_rss_bytes'] and s['ru_maxrss_units']=='bytes on explicitly required macOS'
 assert not any('error' in x for x in proc['cleanup_events']) and any('reaped' in x['action'] for x in proc['cleanup_events'])
 if proc['terminal_unavailable_recovered']:
  waits=[e for e in proc['RSS_diagnostics'] if e['event']=='terminal_wait'];assert len(waits)<=1 and all(0<x['max_seconds']<=.05 for x in waits)
  assert any(e['event']=='terminal_observed' and e['exit_code']==0 for e in proc['RSS_diagnostics'])
 for n,h in s['outputs'].items():assert c['outputs'][n]==h
 for e in s['events']:
  if e['operation']=='finish source authentication':pin(Path(e['file']),e['sha256'])
 assert any(e['operation']=='finish registry authentication' for e in s['events']) and any(e['operation']=='finish approval authentication' for e in s['events'])
 phases.append({'phase':phase,'route':route,'process_seconds':proc['elapsed_seconds'],'child_seconds':s['elapsed_seconds'],'sampled_peak_bytes':proc['peak_sampled_RSS_bytes'],'self_peak_bytes':s['self_ru_maxrss_bytes'],'samples':proc['valid_RSS_samples'],'terminal_recovered':proc['terminal_unavailable_recovered'],'diagnostics':proc['RSS_diagnostics'],'cleanup':proc['cleanup_events']})
wc=read(P/'WARM_COUNTS.json');assert wc=={'untimed_fidelity_requests':7,'untimed_warmup_requests':14,'timed_requests':49}
def quantile(v,q):
 v=sorted(v);z=(len(v)-1)*q;i=int(z);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(z-i)
summary=[]
for route in routes:
 vals=[]
 for i in range(7):
  x=read(P/f'warm_{i}_{route}.json');assert x['repeat']==i and x['route']==route and x['output_rows']==497 and 0<=x['seconds']<60;vals.append(x['seconds'])
 cold=read(P/f'cold_{route}.json');assert cold['rows']==497 and cold['route']==route and cold['request_seconds']<60
 summary.append({'route':route,'warm_seconds_all7':vals,'median_seconds':statistics.median(vals),'q25_seconds':quantile(vals,.25),'q75_seconds':quantile(vals,.75),'min_seconds':min(vals),'max_seconds':max(vals),'cold':cold})
archive=read(P/'ARCHIVE_COMPARISONS.json')
for cohort,n,changed,ulp in [('SG_exposed',242,22,1),('W_new_challenge',255,14,2)]:
 x=archive[cohort];assert (x['rows'],x['different_rows'],x['max_ulp'])==(n,changed,ulp) and not x['bit_exact'] and len(x['differences'])==changed
 for d in x['differences']:assert abs(float.fromhex(d['current_hex'])-float.fromhex(d['archived_hex']))==d['absolute_difference']
for p,h in pins.items():assert sha(Path(p))==h
out={'status':'PASS_SAVED_BENCHMARK_RECEIPT_AUDIT','parent_sha256':sha(cp),'accepted_outputs':102,'parent_seconds':c['elapsed_seconds'],'phases':phases,'timing_summary':summary,'archive_comparisons':archive,'warm_counts':wc,'scheduled_pairs':schedule,'pins':pins,'scope':'Saved JSON and byte identities only; no scientific input or reference NPZ parsing; no inference rerun.','script_sha256':sha(Path(__file__))}
with (Path(__file__).parent/'AUDIT.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'status':out['status'],'phases':phases,'timing_summary':summary},indent=2))
