"""Independent engineering parity/state and saved benchmark arithmetic; no timing run."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import copy,hashlib,importlib.util,json,sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;ROUND=HERE.parent;PROJECT=ROUND.parent
FAST=ROUND/'engineering/fast_inference';OLD=PROJECT/'model_development_20260907_risk_policy/portable'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
def arrays(prepared):
    return [getattr(t,k) for t in prepared.trees for k in ['feature','threshold','left','right','leaf','value']]+[getattr(p,k) for p in prepared.policies for k in ['endpoints','corners']]
def state(prepared):return [hashlib.sha256(a.tobytes()).hexdigest() for a in arrays(prepared)]

def main():
    report=json.loads((FAST/'results.json').read_text())
    for p,h in report['provenance_sha256'].items():assert sha(p)==h,p
    prepared=module('independent_prepared_adapter',FAST/'prepared.py')
    artifact,manifest=prepared.authenticated_artifact(OLD)
    assert sha(OLD/'manifest.json')==report['original_manifest_sha256']==prepared.MANIFEST_SHA256
    old=module('independent_original_adapter',OLD/'predictor.py');fast=prepared.prepare(artifact);initial=state(fast)
    source=[];parity=[];deltas=[]
    with np.load(OLD/'inference_references.npz',allow_pickle=False) as z:
        for cohort in ['historical','SG_exposed','W_new_challenge']:
            args=tuple(z[cohort+'_'+k].copy() for k in ['X62','BASE_CD','all_model_CD','gate']);source.append(args)
            for label in prepared.LABELS:
                a=old.predict(artifact,*args,label);b=fast.predict(*args,label)
                for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
                np.testing.assert_allclose(b[0],z[cohort+'_'+label],atol=1e-12,rtol=0)
                np.testing.assert_array_equal(b[0][~args[3]],args[1][~args[3]])
                parity.append({'cohort':cohort,'label':label,'rows':len(args[1]),'same_shape_original_prepared_bit_identical':True})
    combined=tuple(np.concatenate([a[i] for a in source]) for i in range(4));assert len(combined[1])==8868
    for label in prepared.LABELS:
        full=fast.predict(*combined,label)
        # Every benchmark batch size against original for that identical shape.
        common={}
        for n in [1,32,1024,8868]:
            args=tuple(v[:n] for v in combined);a=old.predict(artifact,*args,label);b=fast.predict(*args,label)
            for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
            if n>=32:common[n]=tuple(v[:32] for v in b)
        single=[fast.predict(*(v[i:i+1] for v in combined),label) for i in range(32)]
        common[1]=tuple(np.concatenate([r[j] for r in single]) for j in range(2))
        for i,n in enumerate([1,32,1024,8868]):
            for other in [1,32,1024,8868][i+1:]:
                delta=[float(abs(a-b).max()) for a,b in zip(common[n],common[other])]
                assert max(delta)<=1e-15
                deltas.append({'label':label,'batch_a':n,'batch_b':other,'common_rows':32,'CD_delta':delta[0],'strength_delta':delta[1]})
        for size in [32,1024]:
            chunks=[fast.predict(*(v[i:i+size] for v in combined),label) for i in range(0,8868,size)]
            assembled=tuple(np.concatenate([r[j] for r in chunks]) for j in range(2))
            delta=[float(abs(a-b).max()) for a,b in zip(assembled,full)];assert max(delta)<=1e-15
            deltas.append({'label':label,'batch_a':size,'batch_b':8868,'common_rows':8868,'CD_delta':delta[0],'strength_delta':delta[1]})
        perm=np.random.default_rng(824).permutation(8868);out=fast.predict(*(v[perm] for v in combined),label)
        for a,b in zip(out,full):np.testing.assert_allclose(a,b[perm],atol=1e-15,rtol=0)
        empty=fast.predict(*(v[:0] for v in combined),label);assert empty[0].shape==empty[1].shape==(0,)
    # All bytes-backed state rejects write-enablement, not merely first arrays.
    immutable_count=0
    for a in arrays(fast):
        assert not a.flags.writeable
        try:a.flags.writeable=True
        except ValueError:immutable_count+=1
        else:raise AssertionError('Prepared array can be made mutable')
    small=tuple(v[:32].copy() for v in combined);saved=fast.predict(*small)
    mutated=copy.deepcopy(artifact);cached=prepared.prepare(mutated);mutated['policies']['risk_transfer']['corners']=[0,0,0,0];mutated['core']['hist']['trees'][0]['value'][0]=1e100
    for a,b in zip(cached.predict(*small),saved):np.testing.assert_array_equal(a,b)
    original_inputs=[v.copy() for v in small];small[0][0,0]+=1.;changed=fast.predict(*small)
    for a,b in zip(changed,old.predict(artifact,*small)):np.testing.assert_array_equal(a,b)
    small[0][:]=original_inputs[0]
    with patch.object(prepared,'prepare',side_effect=AssertionError('Repreparation')),patch.object(prepared,'authenticated_artifact',side_effect=AssertionError('Reauthentication')),patch.object(Path,'read_bytes',side_effect=AssertionError('Inference file read')):
        repeated=fast.predict(*small)
        with ThreadPoolExecutor(max_workers=3) as pool:concurrent=list(pool.map(lambda label:fast.predict(*small,label),prepared.LABELS*3))
    for a,b in zip(repeated,saved):np.testing.assert_array_equal(a,b)
    for label,r in zip(prepared.LABELS*3,concurrent):
        for a,b in zip(r,fast.predict(*small,label)):np.testing.assert_array_equal(a,b)
    for a,b in zip(small,original_inputs):np.testing.assert_array_equal(a,b)
    assert state(fast)==initial
    # Inspect previously recorded randomized benchmark; do not rerun timing.
    timing=pd.read_csv(FAST/'timings.csv');summary=pd.read_csv(FAST/'benchmark_summary.csv')
    assert len(timing)==168 and len(summary)==12
    jobs=[(n,l,m) for n in [1,32,1024,8868] for l in prepared.LABELS for m in ['original','prepared']]
    rng=np.random.default_rng(2026090741)
    for repeat in range(7):
        block=timing[timing['repeat']==repeat]
        assert list(zip(block.batch,block.label,block.method))==[jobs[int(i)] for i in rng.permutation(24)]
    for row in summary.itertuples():
        f=timing[(timing.batch==row.batch)&(timing.label==row.label)]
        for method in ['original','prepared']:
            v=f[f.method==method].seconds.to_numpy();assert len(v)==7
            for key,value in [('median',np.median(v)),('min',v.min()),('max',v.max())]:np.testing.assert_allclose(getattr(row,method+'_'+key+'_seconds'),value,atol=1e-15,rtol=0)
        wide=f.pivot(index='repeat',columns='method',values='seconds');paired=np.median(wide.original/wide.prepared)
        np.testing.assert_allclose(row.paired_speedup_median,paired,atol=1e-12,rtol=0)
        np.testing.assert_allclose(row.median_speedup,row.original_median_seconds/row.prepared_median_seconds,atol=1e-12,rtol=0)
    prepared.authenticated_artifact(OLD)
    result={'status':'PASS','reference_rows_per_label':8868,'labels':3,'same_shape_parity':parity,'batch_comparisons':deltas,
            'all_prepared_arrays_immutable':immutable_count,'concurrent_calls_checked':9,'no_reprepare_or_file_read_during_repeated_prediction':True,
            'timing_samples_reconciled':168,'timing_rerun':False,'benchmark_scope':'Precomputed-feature adapter calls only; excludes preparation/authentication and upstream NeuralFoil/geometry; concurrent system work possible.',
            'producer_result_sha256':sha(FAST/'results.json'),'audit_code_sha256':sha(Path(__file__))}
    (HERE/'fast_inference_audit.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['same_shape_parity','batch_comparisons']})

if __name__=='__main__':main()
