"""Label-free parity/safety checks and predeclared interleaved microbenchmark."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import copy,csv,hashlib,importlib.util,json,time
import numpy as np
from prepared import prepare,authenticated_artifact,LABELS,MANIFEST_SHA256
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
ORIGINAL=PROJECT/'model_development_20260907_risk_policy/portable'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def reject(call):
    try:call()
    except (ValueError,TypeError,KeyError):return
    raise AssertionError('Malformed value accepted')

def main():
    assert not (HERE/'results.json').exists(),'Preserve completed benchmark'
    started=time.perf_counter();artifact,manifest=authenticated_artifact(ORIGINAL);auth_seconds=time.perf_counter()-started
    started=time.perf_counter();fast=prepare(artifact);prepare_seconds=time.perf_counter()-started
    spec=importlib.util.spec_from_file_location('authenticated_original_predictor',ORIGINAL/'predictor.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    inputs=[];results=[];maxcd=maxstrength=chunkcd=chunkstrength=0.
    with np.load(ORIGINAL/'inference_references.npz',allow_pickle=False) as refs:
        for cohort in ['historical','SG_exposed','W_new_challenge']:
            arrays=tuple(refs[cohort+'_'+k] for k in ['X62','BASE_CD','all_model_CD','gate']);inputs.append(arrays)
            for label in LABELS:
                expected=old.predict(artifact,*arrays,label);actual=fast.predict(*arrays,label)
                np.testing.assert_array_equal(actual[0],expected[0]);np.testing.assert_array_equal(actual[1],expected[1])
                np.testing.assert_allclose(actual[0],refs[cohort+'_'+label],rtol=0,atol=1e-12)
                rng=np.random.default_rng(2026090741);order=rng.permutation(len(arrays[1]));permuted=fast.predict(*(v[order] for v in arrays),label)
                maxcd=max(maxcd,float(abs(permuted[0]-actual[0][order]).max()));maxstrength=max(maxstrength,float(abs(permuted[1]-actual[1][order]).max()))
                cd=[];strength=[]
                for start in range(0,len(order),32):
                    got=fast.predict(*(v[start:start+32] for v in arrays),label);cd.extend(got[0]);strength.extend(got[1])
                chunkcd=max(chunkcd,float(abs(np.array(cd)-actual[0]).max()));chunkstrength=max(chunkstrength,float(abs(np.array(strength)-actual[1]).max()))
                empty=fast.predict(*(v[:0] for v in arrays),label);assert empty[0].shape==empty[1].shape==(0,)
                g=arrays[-1];np.testing.assert_array_equal(actual[0][~g],arrays[1][~g]);np.testing.assert_array_equal(actual[1][~g],np.zeros((~g).sum()))
                results.append({'cohort':cohort,'label':label,'rows':len(g),'original_CD_and_strength_bit_identical':True})
    # All scratch belongs to each call; caller's mutable dictionary no longer aliases prepared arrays.
    small=tuple(v[:32].copy() for v in inputs[0]);before=fast.predict(*small)
    mutated=copy.deepcopy(artifact);cached=prepare(mutated);mutated['core']['hist']['trees'][0]['value'][0]=1e100;mutated['policies']['risk_transfer']['corners'][0]=0.123
    for a,b in zip(cached.predict(*small),before):np.testing.assert_array_equal(a,b)
    frozen_checks=0
    for a in [fast.trees[0].value,fast.trees[0].feature,fast.policies[0].corners]:
        try:a.flags.writeable=True
        except ValueError:frozen_checks+=1
    assert frozen_checks==3
    originals=[v.copy() for v in small]
    with ThreadPoolExecutor(max_workers=2) as pool:
        answers=list(pool.map(lambda label:fast.predict(*small,label),LABELS*2))
    for label,pred in zip(LABELS*2,answers):
        for got,expected in zip(pred,fast.predict(*small,label)):np.testing.assert_array_equal(got,expected)
    for a,b in zip(small,originals):np.testing.assert_array_equal(a,b)
    invalid=0
    for i in [0,1,2]:
        for val in [np.nan,np.inf]:
            bad=[v.copy() for v in small];bad[i].flat[0]=val;reject(lambda:fast.predict(*bad));invalid+=1
        bad=[v.copy() for v in small];bad[i]=bad[i][:-1];reject(lambda:fast.predict(*bad));invalid+=1
    for g in [np.ones(32,int),np.ones((32,1),bool),np.ones(31,bool),np.full(32,'false')]:reject(lambda:fast.predict(*small[:3],g));invalid+=1
    for i in [1,2]:
        bad=[v.copy() for v in small];bad[i].flat[0]=0.;reject(lambda:fast.predict(*bad));invalid+=1
    for change in ['cycle','child','feature','nonfinite','shape','corner']:
        bad=copy.deepcopy(artifact);t=bad['core']['hist']['trees'][0]
        if change=='cycle':t['leaf'][0]=False;t['left'][0]=0
        if change=='child':t['right'][0]=999999
        if change=='feature':t['leaf'][0]=False;t['feature'][0]=62
        if change=='nonfinite':t['value'][0]=float('nan')
        if change=='shape':t['threshold']=[]
        if change=='corner':bad['policies']['risk_group']['corners'][0]=float('inf')
        reject(lambda:prepare(bad));invalid+=1
    reject(lambda:authenticated_artifact(ORIGINAL,'0'*64));invalid+=1
    assert maxcd<=1e-15 and maxstrength<=1e-15 and chunkcd<=1e-15 and chunkstrength<=1e-15
    # Only now benchmark; no timing-driven code or algorithm changes.
    combined=tuple(np.concatenate([v[i] for v in inputs]) for i in range(4));assert len(combined[1])==8868
    jobs=[(n,label,method) for n in [1,32,1024,8868] for label in LABELS for method in ['original','prepared']]
    def invoke(n,label,method):
        args=tuple(v[:n] for v in combined)
        return old.predict(artifact,*args,label) if method=='original' else fast.predict(*args,label)
    for n,label,method in jobs:
        for _ in range(2):invoke(n,label,method)
    timings=[];rng=np.random.default_rng(2026090741)
    for repeat in range(7):
        for index in rng.permutation(len(jobs)):
            n,label,method=jobs[int(index)];start=time.perf_counter_ns();invoke(n,label,method);seconds=(time.perf_counter_ns()-start)/1e9
            timings.append({'repeat':repeat,'batch':n,'label':label,'method':method,'seconds':seconds})
    with (HERE/'timings.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timings[0]));w.writeheader();w.writerows(timings)
    summaries=[]
    for n in [1,32,1024,8868]:
        for label in LABELS:
            row={'batch':n,'label':label}
            for method in ['original','prepared']:
                values=[r['seconds'] for r in timings if r['batch']==n and r['label']==label and r['method']==method]
                row.update({method+'_median_seconds':float(np.median(values)),method+'_min_seconds':min(values),method+'_max_seconds':max(values)})
            row['median_speedup']=row['original_median_seconds']/row['prepared_median_seconds']
            paired=[next(r['seconds'] for r in timings if r['batch']==n and r['label']==label and r['method']=='original' and r['repeat']==i)/next(r['seconds'] for r in timings if r['batch']==n and r['label']==label and r['method']=='prepared' and r['repeat']==i) for i in range(7)]
            row['paired_speedup_median']=float(np.median(paired));summaries.append(row)
    with (HERE/'benchmark_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    result={'status':'PASS optional cached engineering adapter, no model or accuracy change','parity':results,'permutation_max_abs_CD':maxcd,'permutation_max_abs_strength':maxstrength,'chunk32_max_abs_CD':chunkcd,'chunk32_max_abs_strength':chunkstrength,'invalid_cases_rejected':invalid,'immutable_bytes_arrays':True,'concurrent_call_parity':True,'authentication_and_json_seconds':auth_seconds,'prepare_validation_copy_seconds':prepare_seconds,'benchmark':summaries,'timing_context':'Single BLAS/OpenMP thread; precomputed-feature correction only; other geometry work may be concurrent, not isolated/end-to-end performance','original_manifest_sha256':MANIFEST_SHA256,'provenance_sha256':{str(p):sha(p) for p in [HERE/'PROTOCOL.md',HERE/'prepared.py',Path(__file__),ORIGINAL/'manifest.json',ORIGINAL/'predictor.py',ORIGINAL/'experimental_policies.json',ORIGINAL/'inference_references.npz',HERE/'timings.csv',HERE/'benchmark_summary.csv']}}
    # Verify frozen originals again after all tests/benchmark.
    authenticated_artifact(ORIGINAL)
    (HERE/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'setup_seconds':auth_seconds+prepare_seconds,'summaries':summaries,'chunk_delta':chunkcd}),flush=True)

if __name__=='__main__':main()
