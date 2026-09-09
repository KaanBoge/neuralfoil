"""Independent union feature inference QA; only hash-verified local model pickles."""
from pathlib import Path
import copy,hashlib,importlib.util,json,pickle,sys
import numpy as np
HERE=Path(__file__).resolve().parent;FRONT=HERE.parents[1];PROJECT=FRONT.parent;BUNDLE=FRONT/'union_deployment'
sys.path[:0]=[str(PROJECT/'model_development_20260907_search/ensemble'),str(FRONT/'capacity')]
import ensemble_models,capacity_models
spec=importlib.util.spec_from_file_location('independent_union_predictor',BUNDLE/'predictor.py');portable=importlib.util.module_from_spec(spec);spec.loader.exec_module(portable)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rejects(call):
    try:call()
    except (ValueError,TypeError,KeyError):return
    raise AssertionError('Malformed input accepted')

def main():
    manifest=json.loads((BUNDLE/'manifest.json').read_text());artifact=json.loads((BUNDLE/'retrospective_union.json').read_text())
    for p,k in [('retrospective_union.json','artifact_sha256'),('predictor.py','predictor_sha256'),('inference_references.npz','inference_references_sha256')]:assert sha(BUNDLE/p)==manifest[k]
    for p,h in manifest['other_source_sha256'].items():assert sha(p)==h
    models={}
    for p,h in manifest['source_hashes_verified_before_unpickle'].items():
        assert sha(p)==h
        with Path(p).open('rb') as file:models[Path(p).stem.removeprefix('fit_')]=pickle.load(file)
    sourceweights=json.loads((FRONT/'union_calibration/blend_both.json').read_text())['weights']
    assert artifact['weights']=={k:v for k,v in sourceweights.items() if v!=0}
    results={};bound_checks=0;uncast_differences=0
    with np.load(BUNDLE/'inference_references.npz',allow_pickle=False) as refs:
        for cohort in ['historical','SG_exposed','W_new_challenge']:
            features={k:refs[cohort+'_'+k] for k in ['BASE_CD','X62','all_model_CD','Re']};g=refs[cohort+'_gate'];n=len(g);idx=np.arange(n)
            d=dict(features,X24=features['X62'][:,:24])
            native={portable.KEYS[0]:ensemble_models.predict(models['simplex8_re_l1'],d,idx)}
            for key,fam in zip(portable.KEYS[1:],['hist62_regularized','extra62_mixed','extra24_mixed']):native[key]=capacity_models.predict(models[fam],d,idx)
            expected=np.where(g,sum(artifact['weights'][k]*native[k] for k in portable.KEYS),features['BASE_CD'])
            got,parts=portable.predict(artifact,features,g,True)
            np.testing.assert_array_equal(got,expected);np.testing.assert_array_equal(got,refs[cohort+'_expected_CD'])
            for key in native:np.testing.assert_array_equal(parts[key],np.where(g,native[key],features['BASE_CD']))
            np.testing.assert_array_equal(portable.predict(artifact,features,np.zeros(n,dtype=bool)),features['BASE_CD'])
            changed=dict(features,MEAS_CD=np.full(n,np.nan),source=np.full(n,'changed'),group=np.full(n,'changed'),airfoil=np.full(n,'changed'),entry=np.full(n,'changed'),name='irrelevant',labels={'arbitrary':object()})
            np.testing.assert_array_equal(portable.predict(artifact,changed,g),got)
            empty={k:v[:0] for k,v in features.items()};assert portable.predict(artifact,empty,g[:0]).shape==(0,)
            results[cohort]={'rows':n,'native_component_and_blend_bit_identical':True,'gate_false_rows':int((~g).sum()),'label_name_source_perturbations_irrelevant':True,'empty_supported':True}
        # Actual sklearn tree threshold-boundary checks independently reveal why float32 matters.
        x=refs['historical_X62'][:1]
        for family,akey,width in [('extra62_mixed','extra62',62),('extra24_mixed','extra24',24)]:
            for est,t in zip(models[family]['model'].estimators_,artifact[akey]['trees']):
                feat=int(est.tree_.feature[0]);th=float(est.tree_.threshold[0]);xx=np.repeat(x[:,:width],2,axis=0)
                xx[:,feat]=[np.nextafter(th,-np.inf),np.nextafter(th,np.inf)]
                expected=est.predict(xx);cast=portable._tree(t,xx.astype(np.float32));raw=portable._tree(t,xx)
                np.testing.assert_array_equal(cast,expected);uncast_differences+=int((raw!=expected).sum());bound_checks+=len(xx)
        assert uncast_differences>0
        features={k:refs['SG_exposed_'+k][:3].copy() for k in ['BASE_CD','X62','all_model_CD','Re']};g=np.ones(3,dtype=bool)
    malformed=0
    for field in features:
        for value in [np.nan,np.inf]:
            bad={k:v.copy() for k,v in features.items()};bad[field].flat[0]=value;rejects(lambda:portable.predict(artifact,bad,g));malformed+=1
        bad={k:v.copy() for k,v in features.items()};bad[field]=bad[field][:-1];rejects(lambda:portable.predict(artifact,bad,g));malformed+=1
    for field in ['BASE_CD','all_model_CD','Re']:
        for value in [0.,-1.]:
            bad={k:v.copy() for k,v in features.items()};bad[field].flat[0]=value;rejects(lambda:portable.predict(artifact,bad,g));malformed+=1
    for badgate in [None,[1,0,1],['true','false','true'],np.ones((3,1),bool),np.ones(2,bool)]:rejects(lambda:portable.predict(artifact,features,badgate));malformed+=1
    for value in [float('nan'),float('inf'),-1.,True,'0.2']:
        bad=copy.deepcopy(artifact);bad['weights'][portable.KEYS[0]]=value;rejects(lambda:portable.predict(bad,features,g));malformed+=1
    bad={k:v.copy() for k,v in features.items()};bad['X62'][0,0]=1e100;rejects(lambda:portable.predict(artifact,bad,g));malformed+=1
    output={'status':'PASS independent hash-verified native and portable audit','cohorts':results,'tree_boundary_samples':bound_checks,'uncast_float64_wrong_results':uncast_differences,'malformed_input_cases_rejected':malformed,'scope':'Full historical fits are engineering parity references, NOT validation. Exposed outcome-calibrated artifact; no deployment action. Feature-only API, not geometry pipeline.','provenance_sha256':{str(p):sha(p) for p in [Path(__file__),BUNDLE/'manifest.json',BUNDLE/'predictor.py',BUNDLE/'retrospective_union.json',BUNDLE/'inference_references.npz']}}
    (HERE/'union_portable_audit.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output),flush=True)

if __name__=='__main__':main()
