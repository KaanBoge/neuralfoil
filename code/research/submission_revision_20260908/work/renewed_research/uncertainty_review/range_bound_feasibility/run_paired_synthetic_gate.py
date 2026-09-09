"""One cold prescribed synthetic checker gate. No real model/data inputs."""
import hashlib,json,time,traceback
from pathlib import Path
import numpy as np
import paired_checker as c

def main():
    root=Path(__file__).resolve().parent;out=root/'PAIRED_SYNTHETIC_GATE.json'
    if out.exists():raise FileExistsError(out)
    p=root.parents[1]/'model_proposal/paired_tree_plan/synthetic_attempt_1/certificate.json'
    raw=p.read_bytes();pin=hashlib.sha256(raw).hexdigest()
    assert pin=='ce8c2e1fade37918e169941fcaaf2acd63fb5f9e903cfef87c32d3709101ad60'
    start=time.monotonic();result=None;failure=None
    try:
        # Independent reconstruction directly from the fixed protocol, not
        # producer fixture/support imports.
        fields=('value','is_leaf','feature_idx','num_threshold','left','right','missing_go_to_left','is_categorical')
        dt=np.dtype([(k,'f8' if k in ('value','num_threshold') else 'i8') for k in fields])
        nodes=np.zeros(400*29,dtype=dt)
        for stage in range(400):
            tree=nodes[stage*29:(stage+1)*29]
            for k in range(14):
                tree[2*k]['feature_idx']=20+stage%42;tree[2*k]['num_threshold']=k-7
                tree[2*k]['left']=2*k+1;tree[2*k]['right']=2*k+2
                tree[2*k+1]['is_leaf']=1;tree[2*k+1]['value']=((stage+k)%17-8)/1024
            tree[28]['is_leaf']=1;tree[28]['value']=((stage+14)%17-8)/1024
        arrays={'initial':np.array([0.]),'nodes':nodes,'nodes_offsets':np.arange(0,11601,29,dtype='i8')}
        for name in ('raw_left_cat_bitsets','binned_left_cat_bitsets'):
            arrays[name]=np.zeros((0,8),dtype='u4');arrays[name+'_offsets']=np.zeros(401,dtype='i8')
        cert=json.loads(raw)
        result=c.check(cert,arrays,deadline=start+120,expected_model_sha=hashlib.sha256(b'fixed-400x15-chain-fixture-v1').hexdigest())
        assert result['counts']['attempted_pairs']==90000
    except BaseException:failure=traceback.format_exc()
    elapsed=time.monotonic()-start
    report={'status':'PASS_FIXED_SYNTHETIC_GATE' if failure is None and elapsed<=120 else 'FAIL_PRESERVED',
            'seconds':elapsed,'failure':failure,'result':result,'certificate_sha256':pin,
            'checker_sha256':hashlib.sha256(Path(c.__file__).read_bytes()).hexdigest(),
            'actual_model_arrays_opened':False,'producer_implementation_imported':False}
    with out.open('x') as f:json.dump(report,f,indent=2)
    print(report['status'],elapsed)
    if failure:raise RuntimeError(failure)
if __name__=='__main__':main()
