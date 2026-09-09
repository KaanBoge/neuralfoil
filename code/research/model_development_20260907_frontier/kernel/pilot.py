"""Timing-only pilot and isolated regression checks; no pilot accuracy selection."""
import json,time,hashlib
from pathlib import Path
import numpy as np
import run_kernel as run
import kernel_models as m

def main():
    root=Path(__file__).resolve().parent
    assert not (root/'pilot_manifest.json').exists()
    paths=[root/n for n in ['PROTOCOL.md','kernel_models.py','run_kernel.py','pilot.py']]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    run.dump(root/'pilot_manifest.json',{'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'hashes':hashes,'purpose':'timing_and_validation_only_no_accuracy_tuning'})
    d=run.inputs.load_historical();ids=np.arange(len(d['BASE_CD']))
    outer=next(iter(run.v2.old.group_folds(d['group'],5,20260906)));enclosing=ids[~outer]
    inner=next(iter(run.v2.old.group_folds(d['group'][enclosing],3,20260907)));tr=enclosing[~inner];te=enclosing[inner]
    result={'train_rows':len(tr),'test_rows':len(te),'group_overlap':len(set(d['group'][tr])&set(d['group'][te])),'families':{}}
    np.testing.assert_allclose(m.balanced_weights(d['group'],d['source']),run.v2.old.balanced_weights(d['group'],d['source']),rtol=0,atol=1e-13)
    first=None
    for family in m.FAMILIES:
        tick=time.monotonic();model=m.fit(family,d,tr);pred=m.predict(model,d,te)
        assert pred.shape==(len(te),) and np.isfinite(pred).all() and (pred>0).all()
        assert (pred>=.5*d['BASE_CD'][te]).all() and (pred<=2*d['BASE_CD'][te]).all()
        key=model['feature_key'];np.testing.assert_array_equal(model['center'],np.median(d[key][tr],axis=0))
        changed={k:np.array(v,copy=True) for k,v in d.items()};changed['MEAS_CD'][:]=999.
        np.testing.assert_array_equal(pred,m.predict(model,changed,te))
        result['families'][family]={'seconds':time.monotonic()-tick,'shape_bounds_training_center_label_free_predict':True}
        if first is None:first=(model,pred)
    changed={k:np.array(v,copy=True) for k,v in d.items()};outside=np.setdiff1d(ids,tr)
    changed['MEAS_CD'][outside]=12345.;changed['X24'][outside]=54321.
    again=m.fit(m.FAMILIES[0],changed,tr)
    np.testing.assert_array_equal(first[0]['model'].coef_,again['model'].coef_)
    np.testing.assert_array_equal(first[0]['kernel'].components_,again['kernel'].components_)
    np.testing.assert_array_equal(first[0]['center'],again['center'])
    result['outside_label_feature_fit_isolation']=True
    for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    run.dump(root/'pilot_timing.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
