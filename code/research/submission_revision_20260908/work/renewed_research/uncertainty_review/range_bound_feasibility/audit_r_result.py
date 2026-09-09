"""Receipt/checkpoint audit only. Does not execute search or load model arrays."""
import hashlib,json
from pathlib import Path
from fractions import Fraction as F

ROOT=Path(__file__).resolve().parents[2]/'tree_range_refinement/relation_domain_plan'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def main():
    out=Path(__file__).with_name('R_PILOT_RESULT_QA.json')
    if out.exists():raise FileExistsError(out)
    r=ROOT/'producer/R_PILOT_REGISTRY.json';reg=read(r)
    assert sha(r)=='3cd06c7f85b42eaf960b76c22e0e32d53bfbdfa284cfcaa4dddb60a2bd38a4f2'
    for v in reg['sources'].values():assert sha((r.parent/v['path']).resolve())==v['sha256']
    p=ROOT/'pilot_r_attempt_1';final=read(p/'FINAL.json');ver=read(p/'verified.json');old=read(p/'checkpoint_000_inherited.json')
    assert sha(ROOT/'ROOT_PILOT_APPROVAL.json')=='f194c567292b349da39774337eb762c9b046617d388c2cbeaa38eee028ac9d8f'
    assert all(final[k]==v for k,v in ver.items())
    assert ver['status']=='PASS_RESTRICTED_DOMAIN_REPLAY'
    assert ver['registry_sha256']==sha(r)
    assert ver['model_sha256']==reg['input']['sha256']
    assert sha(p/'candidate_001.json')==ver['candidate_sha256']=='60a14ac823d0a3aaf21db2a1e95b2b6d80402fb52213562a4058ab0d68296557'
    c=read(p/'candidate_001.json')
    assert c['domain']==ver['domain'] and c['splits']==ver['splits']==1
    assert len(c['frontier'])==ver['boxes']==2
    assert sum(x['status']=='R_NONEMPTY' for x in c['frontier'])==ver['r_nonempty_boxes']==2
    assert ver['r_empty_boxes']==0
    for k in ('lower','upper'):
        z=old['range'][k];assert F(ver[k])==F(int(z['numerator']),int(z['denominator']))
    def clip(x):return max(F(-1,2),min(F(1),x))
    u=F(1,2**53);e=4*u+2*u*u
    b=max(abs(clip(clip(F(ver['lower']))-e)),abs(clip(clip(F(ver['upper']))+e)))/2+3*u/2
    assert b==F(ver['B_structural'])
    assert F(c['lower'])==F(ver['lower']) and F(c['upper'])==F(ver['upper'])
    assert ver['replay_node_visits']==22786 and ver['replay_oracle_calls']==22570
    assert final['search']=={'returncode':None,'timeout':True}
    assert final['verification']=={'returncode':0,'timeout':False}
    assert not (p/'worker_status.json').exists()
    end=read(ROOT/'R_ATTEMPT_EXTERNAL_END.json')
    assert end['approval_sha256']==sha(ROOT/'ROOT_PILOT_APPROVAL.json')
    assert end['registry_sha256']==sha(r)
    assert end['start_witness_sha256']==sha(ROOT/'R_ATTEMPT_EXTERNAL_START.json')
    assert end['runner_returncode']==0 and end['external_elapsed_seconds']>=final['seconds']
    files=list(p.iterdir())+[ROOT/'ROOT_PILOT_APPROVAL.json',ROOT/'R_ATTEMPT_EXTERNAL_START.json',ROOT/'R_ATTEMPT_EXTERNAL_END.json',r]
    report={'status':'PASS_RECEIPT_CHECKPOINT_AUDIT','source_pins':len(reg['sources']),
      'splits':1,'boxes':2,'r_empty_boxes':0,'range_and_B_equal_inherited':True,
      'model_arrays_materialized':False,'search_rerun':False,'checker_rerun':False,
      'worker_total_statistics_available':False,'runner_seconds':final['seconds'],
      'external_seconds':end['external_elapsed_seconds'],
      'hashes':{str(x):sha(x) for x in files if x.is_file()}}
    with out.open('x') as f:json.dump(report,f,indent=2)
    print(report['status'])
if __name__=='__main__':main()
