"""Export only verified local fits; compare native and portable research inference."""
from pathlib import Path
import hashlib,json,pickle,sys,time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;F=HERE.parent;P=F.parent
C3=P/'model_development_20260907_search';C4=P/'model_development_20260907_transition';CAP=F/'capacity'
sys.path[:0]=[str(C3/'ensemble'),str(C3/'portable'),str(C4),str(CAP)]
import ensemble_models,capacity_models,shape_inputs,portable_models
from predictor import predict,KEYS,validate_weights

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):Path(path).write_text(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n')

def forest(model):
    assert model.n_estimators==256 and model.n_outputs_==1
    trees=[]
    for est in model.estimators_:
        t=est.tree_;trees.append({'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),
            'left':t.children_left.tolist(),'right':t.children_right.tolist(),'leaf':(t.children_left<0).tolist(),'value':t.value[:,0,0].tolist()})
    return {'input_dtype':'float32','aggregation':'arithmetic_mean_in_estimator_order','trees':trees}

def main():
    assert not (HERE/'manifest.json').exists(),'Preserve completed bundle'
    m3path=C3/'exposed_results/fit_manifest.json';mcpath=CAP/'results/freeze.json'
    m3=json.loads(m3path.read_text());mc=json.loads(mcpath.read_text())
    sources=[('simplex8_re_l1',C3/'exposed_results/fit_simplex8_re_l1.pkl',m3)]
    sources += [(name,CAP/'results'/f'fit_{name}.pkl',mc) for name in ['hist62_regularized','extra62_mixed','extra24_mixed']]
    verified={}
    for family,path,manifest in sources:
        digest=sha(path);assert digest==manifest['artifacts'][family]['sha256'];verified[str(path)]=digest
    models={}
    for family,path,_ in sources:
        assert sha(path)==verified[str(path)]
        with path.open('rb') as f:models[family]=pickle.load(f)
    weight_path=F/'union_calibration/blend_both.json';sourceweights=json.loads(weight_path.read_text())['weights']
    weights={k:v for k,v in sourceweights.items() if v!=0};validate_weights(weights)
    assert all(weights[k]==sourceweights[k] for k in KEYS)
    artifact={'schema':'retrospective-neuralfoil-union-v1','status':'exposed_outcome_calibrated_research_candidate_not_validated_universal',
       'weights':weights,'source_pickle_sha256':verified,'weight_source_sha256':sha(weight_path),
       'input_contract':{'BASE_CD':'positive mean8 CD, shape(n,)','X62':portable_models.FEATURES['X62'],
         'X24':'the first24 X62 columns; verified identical on all three cohorts','all_model_CD':['xxsmall','xsmall','small','medium','large','xlarge','xxlarge','xxxlarge'],
         'Re':'positive Reynolds number vector','inference_gate':'required boolean vector; false returns supplied BASE_CD bitwise'},
       'convention':'Original frozen normalization, feature order, ncrit/quantization and X62 sensitivity/Kulfan contract; not tie-safe alternate normalization',
       'simplex':{k:np.asarray(models['simplex8_re_l1'][k]).tolist() for k in ['coef','endpoints']},
       'hist62':portable_models.export_hist(models['hist62_regularized']['model']),
       'extra62':forest(models['extra62_mixed']['model']),'extra24':forest(models['extra24_mixed']['model'])}
    target=HERE/'retrospective_union.json';dump(target,artifact);loaded=json.loads(target.read_text())
    refs={};tests=[]
    calibration_path=F/'union_calibration/all_row_predictions.csv';cal=pd.read_csv(calibration_path,low_memory=False,float_precision='round_trip')
    for cohort in ['historical','SG_exposed','W_new_challenge']:
        d=shape_inputs.load_historical() if cohort=='historical' else shape_inputs.load_exposed(cohort)
        n=len(d['BASE_CD']);idx=np.arange(n);np.testing.assert_array_equal(d['X24'],d['X62'][:,:24])
        gate=np.ones(n,dtype=bool) if cohort=='historical' else pd.read_csv(C3/'exposed_results'/f'{cohort}_predictions.csv',usecols=['inference_gate']).inference_gate.to_numpy()
        assert gate.dtype==bool
        minimal={k:d[k] for k in ['BASE_CD','X62','all_model_CD','Re']}
        originals={KEYS[0]:ensemble_models.predict(models['simplex8_re_l1'],d,idx)}
        for key,family in zip(KEYS[1:],['hist62_regularized','extra62_mixed','extra24_mixed']):originals[key]=capacity_models.predict(models[family],d,idx)
        expected=np.where(gate,sum(weights[k]*originals[k] for k in KEYS),d['BASE_CD'])
        tick=time.monotonic();got,parts=predict(loaded,minimal,gate,True);seconds=time.monotonic()-tick
        err=float(np.max(abs(got-expected)));assert err<1e-12
        deltas={k:float(np.max(abs(parts[k]-np.where(gate,v,d['BASE_CD'])))) for k,v in originals.items()};assert max(deltas.values())<1e-12
        assert (got>=.5*d['BASE_CD']-1e-14).all() and (got<=2*d['BASE_CD']+1e-14).all()
        np.testing.assert_array_equal(got[~gate],d['BASE_CD'][~gate]);np.testing.assert_array_equal(predict(loaded,minimal,np.zeros(n,dtype=bool)),d['BASE_CD'])
        changed=dict(minimal,MEAS_CD=np.full(n,np.nan),source=np.full(n,'ignored'),airfoil=np.full(n,'ignored'))
        np.testing.assert_array_equal(predict(loaded,changed,gate),got)
        cached_delta=None
        if cohort!='historical':
            old=cal[cal.split==cohort];assert len(old)==n
            np.testing.assert_allclose(old.alpha,d['alpha'],atol=1e-12,rtol=0);np.testing.assert_allclose(old.Re,d['Re'],atol=1e-8,rtol=0)
            cached_delta=float(np.max(abs(got-old.union_blend_both.to_numpy())));assert cached_delta<1e-12
        for k,v in minimal.items():refs[cohort+'_'+k]=v
        refs[cohort+'_gate']=gate;refs[cohort+'_expected_CD']=expected
        pd.DataFrame({'row':idx,'inference_gate':gate,'BASE_CD':d['BASE_CD'],'native_CD':expected,'portable_CD':got,**parts}).to_csv(HERE/f'{cohort}_predictions.csv',index=False)
        tests.append({'cohort':cohort,'rows':n,'fallback_rows':int((~gate).sum()),'native_max_abs_CD':err,'component_max_abs_CD':deltas,'union_external_max_abs_CD':cached_delta,'seconds':seconds})
    np.savez_compressed(HERE/'inference_references.npz',**refs)
    sourcepaths=[weight_path,calibration_path,m3path,mcpath,Path(ensemble_models.__file__),Path(capacity_models.__file__),Path(shape_inputs.__file__),Path(portable_models.__file__),Path(__file__)]
    sourcepaths += [C4/section/f'{cohort}.npz' for section in ['inputs','shape_inputs'] for cohort in ['historical','SG_exposed','W_new_challenge']]
    for p,h in verified.items():assert sha(p)==h
    manifest={'status':artifact['status'],'tests':tests,'source_hashes_verified_before_unpickle':verified,'other_source_sha256':{str(p):sha(p) for p in sourcepaths},
       'artifact_sha256':sha(target),'predictor_sha256':sha(HERE/'predictor.py'),'inference_references_sha256':sha(HERE/'inference_references.npz'),
       'artifact_bytes':target.stat().st_size,'runtime_dependencies':['Python','NumPy'],'hist_is_full_strength':True,'forest_input_cast':'float32 before comparison','X24_prefix_verified_all8868':True}
    dump(HERE/'manifest.json',manifest);print(json.dumps(manifest['tests'],indent=2),flush=True)

if __name__=='__main__':main()
