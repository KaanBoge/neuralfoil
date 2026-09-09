"""Post-run difference inventory only; no numerical replay or threshold changes."""
from pathlib import Path
import json,hashlib,collections
import pandas as pd
H=Path(__file__).resolve().parent;P=H.parents[1]/'model_proposal/kl_bound_study/portable_plan'
out=P/'replay_isolated_attempt_1';default=P/'replay_default_attempt_1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((out/'COMPLETE.json').read_text());f=json.loads((out/'FLOAT_DIFFERENCES.json').read_text())
assert c['differences']==len(f)==316 and c['unresolved_outside_contract']==0
for n,h in c['outputs'].items():assert sha(out/n)==h
assert all(v['exact'] for v in c['scalar_checks']+c['native_checks'])
exact={n:(out/(n+'.csv')).read_bytes()==(default/(n+'.csv')).read_bytes() for n in c['counts']}
assert sum(exact.values())==9 and not exact['bootstrap']
groups={}
for col in sorted({e['column'] for e in f}):
 v=[e for e in f if e['column']==col]
 groups[col]={'count':len(v),'max_absolute_difference':max(abs(e['difference']) for e in v),'within_inherited_tolerance':sum(e['within_inherited_audit_tolerance'] for e in v),'known_zero_sign_diagnostic':sum(e['known_zero_sign_diagnostic'] for e in v)}
df=pd.read_csv(out/'bootstrap.csv');old=pd.read_csv(default/'bootstrap.csv')
for e in f:
 assert df.loc[e['row'],e['column']]==e['actual'] and old.loc[e['row'],e['column']]==e['expected']
special=[dict(e,row_identity={k:str(df.loc[e['row'],k]) for k in ['candidate','reference','assignment']}) for e in f if e['known_zero_sign_diagnostic']]
d={'status':'PRODUCER_DIAGNOSTIC_PENDING_INDEPENDENT_REVIEW','complete_sha256':sha(out/'COMPLETE.json'),'differences_sha256':sha(out/'FLOAT_DIFFERENCES.json'),'byte_exact_table_flags':exact,'column_differences':groups,'special_diagnostics':special,'unresolved_outside_contract':0,'source_and_archives_unchanged':json.loads((H/'ISOLATED_END.json').read_text())['archive_unchanged'],'no_retry':True}
with (H/'ISOLATED_DIAGNOSTIC.json').open('x') as s:json.dump(d,s,indent=2)
print(json.dumps(d,indent=2))
