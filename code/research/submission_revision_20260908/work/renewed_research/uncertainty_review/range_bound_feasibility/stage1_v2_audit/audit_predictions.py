"""Independent exact-affine prediction replay, no producer numerical imports."""
from audit_scalars import *
import pandas as pd

def main():
    freeze=json.loads(checked(S/'results/freeze.json',PIN))
    complete=json.loads((S/'predictions/complete.json').read_bytes())
    assert complete['freeze_sha256']==PIN and complete['new_core_fits']==0
    assert complete['execution']['started_utc']>=freeze['execution']['completed_utc']
    approval=json.loads(checked(S/'ROOT_SCORING_APPROVAL.json',complete['execution']['approval_sha256']))
    assert 'score' in approval['authorized_phases']
    assert approval['implementation_sha256']==complete['execution']['implementation_sha256']==freeze['execution']['implementation_sha256']
    for p,h in complete['source_input_sha256'].items():checked(p,h)
    assert len(complete['output_sha256'])==35
    for p,h in complete['output_sha256'].items():checked(S/'predictions'/p,h)
    parity=json.loads(checked(S/'precalibration/PARITY_PASS.json',freeze['parity_sha256']))
    records=[];total=fallback=0
    for context in freeze['contexts']+['SG_exposed','W_new_challenge']:
        name=f'inference_{context}.npz'
        keys=['indices','BASE_CD','core','anchor','gate']
        v=npz(S/'precalibration'/name,parity['artifact_sha256'][name],keys)
        additional=['qualified_matched_half','qualified_matched_full']+[label+suffix for label in freeze['procedures'] for suffix in ['', '__effective_fraction','__strength','__intervened']]
        z=npz(S/'predictions'/name,complete['output_sha256'][name],keys+additional)
        for key in keys:np.testing.assert_array_equal(z[key],v[key])
        np.testing.assert_array_equal(z['qualified_matched_half'],v['anchor']);np.testing.assert_array_equal(z['qualified_matched_full'],v['core'])
        assert v['gate'].dtype==bool
        total+=len(v['indices']);fallback+=int((~v['gate']).sum())
        for label in freeze['procedures']:
            scalar=f'calibrator_{label}_{"final" if context in ["SG_exposed","W_new_challenge"] else context}.json'
            model=json.loads(checked(S/'results'/scalar,freeze['artifact_sha256'][scalar]));t=F(model['t'])
            expected=[];effective=[]
            for b,c,h,g in zip(v['BASE_CD'],v['core'],v['anchor'],v['gate']):
                c,h=F(float(c)),F(float(h))
                p=directed(h+t*(c-h),c<h) if g and c!=h else float(h) if g else float(b)
                theta=(F(p)-h)/(c-h) if g and c!=h else F(0)
                assert 0<=theta<=t
                expected.append(p);effective.append(float(theta))
            expected=np.array(expected)
            np.testing.assert_array_equal(z[label],expected)
            np.testing.assert_array_equal(z[label+'__effective_fraction'],effective)
            np.testing.assert_array_equal(z[label+'__strength'],np.where(v['gate'],.5+.5*float(t),0.))
            np.testing.assert_array_equal(z[label+'__intervened'],abs(expected-v['anchor'])>1e-12)
            np.testing.assert_array_equal(z[label][~v['gate']],v['BASE_CD'][~v['gate']])
        if context!='final':
            csv=f'predictions_{context}.csv'
            f=pd.read_csv(io.BytesIO(checked(S/'predictions'/csv,complete['output_sha256'][csv])))
            assert len(f)==len(v['indices'])
            for key in additional:
                if z[key].dtype==bool:np.testing.assert_array_equal(f[key],z[key])
                else:np.testing.assert_allclose(f[key],z[key],atol=1e-13,rtol=0)
        records.append({'context':context,'rows':len(v['indices']),'native_exact':True,'fallback_rows':int((~v['gate']).sum())})
    assert total==38227 and len(records)==18
    report=json.loads((S/'assessment/report.json').read_bytes())
    assert report['execution']['started_utc']>=complete['execution']['completed_utc']
    for p,h in report['output_sha256'].items():checked(S/'assessment'/p,h)
    for p,h in report['source_input_sha256'].items():checked(p,h)
    return {'status':'PASS','source_sha256':sha(__file__),'complete_sha256':sha(S/'predictions/complete.json'),'assessment_report_sha256':sha(S/'assessment/report.json'),'contexts':18,'rows_repeated':total,'candidate_values_exact':total*2,'fallback_rows_per_candidate':fallback,'records':records,'scope':'Native predictions exact; serialized CSV comparisons retain declared 1e-13 CD tolerance. Assessment arithmetic separate.'}
if __name__=='__main__':
    out=HERE/'PREDICTION_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'PREDICTION_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
