"""Fresh NumPy-only replay and adversarial input/weight regression checks."""
from pathlib import Path
import copy,hashlib,json,sys
import numpy as np
from predictor import predict,KEYS,_forest

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    manifest=json.loads((HERE/'manifest.json').read_text())
    for file,key in [('predictor.py','predictor_sha256'),('retrospective_union.json','artifact_sha256'),('inference_references.npz','inference_references_sha256')]:assert sha(HERE/file)==manifest[key]
    a=json.loads((HERE/'retrospective_union.json').read_text());data=np.load(HERE/'inference_references.npz',allow_pickle=False)
    tests=[];total=0;maxerr=0
    for cohort in ['historical','SG_exposed','W_new_challenge']:
        f={k:data[cohort+'_'+k] for k in ['BASE_CD','X62','all_model_CD','Re']};gate=data[cohort+'_gate'];got=predict(a,f,gate)
        err=float(np.max(abs(got-data[cohort+'_expected_CD'])));assert err<1e-12;maxerr=max(maxerr,err);total+=len(got)
        np.testing.assert_array_equal(got[~gate],f['BASE_CD'][~gate])
        tests.append({'cohort':cohort,'max_abs_CD':err})
    f={k:data['SG_exposed_'+k][:2].copy() for k in ['BASE_CD','X62','all_model_CD','Re']};good=np.ones(2,dtype=bool)
    badweights=[]
    for value in [np.nan,np.inf,-.1,True,'0.25',1+2j]:
        weights=dict(a['weights']);weights[KEYS[0]]=value;badweights.append(weights)
    badweights += [{}, {**a['weights'],'extra':0.}, {k:0. for k in KEYS}]
    weight_tests=0
    for w in badweights:
        bad=dict(a,weights=w)
        for gate in [good,np.zeros(2,dtype=bool)]:
            try:predict(bad,f,gate)
            except (ValueError,TypeError):weight_tests+=1
            else:raise AssertionError('Invalid weights accepted')
    cases=[]
    for gate in [np.array([1,0]),np.array([1.,0.]),np.array(['True','False']),True,np.array([True])]:cases.append((f,gate))
    for key,value in [('BASE_CD',np.array([0.,1.])),('BASE_CD',np.array([np.nan,1.])),('BASE_CD',np.ones((2,1))),('Re',np.array([-1.,1.])),('Re',np.ones(3)),('all_model_CD',np.zeros((2,8))),('all_model_CD',np.ones((2,7))),('X62',np.ones((2,61))),('X62',np.full((2,62),np.inf)),('X62',np.full((2,62),1e300))]:cases.append(({**f,key:value},good))
    for features,gate in cases:
        try:predict(a,features,gate)
        except (ValueError,TypeError):pass
        else:raise AssertionError('Invalid input accepted')
    empty={k:v[:0] for k,v in f.items()};assert predict(a,empty,np.zeros(0,dtype=bool)).shape==(0,)
    # A double input just above one rounds DOWN to float32 one; native forests go left.
    tree={'feature':[0,-2,-2],'threshold':[1.,-2.,-2.],'left':[1,-1,-1],'right':[2,-1,-1],'leaf':[False,True,True],'value':[0.,2.,3.]}
    out=_forest({'trees':[tree]},np.array([[1.+2**-25],[1.+2**-22]]));np.testing.assert_array_equal(out,[2.,3.])
    assert not any(k=='sklearn' or k.startswith('sklearn.') or k=='scipy' or k.startswith('scipy.') for k in sys.modules)
    result={'status':'passed','rows_replayed':total,'max_abs_CD_error':maxerr,'cohorts':tests,'malformed_weight_gate_tests':weight_tests,'malformed_input_cases':len(cases),'empty_batch':True,'float32_boundary_regression':True,'no_sklearn_or_scipy_imported':True,'reference_hash_verified':True}
    (HERE/'portable_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
