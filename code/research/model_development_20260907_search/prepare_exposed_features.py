"""Rebuild inputs only for previously scored SG and W, checking old predictions."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT.parent/'model_development_20260906_v2')]
import evaluate_external_v2 as ext
import robust_models as robust


def main():
    import aerosandbox, neuralfoil
    assert aerosandbox.__version__=='4.2.10' and neuralfoil.__version__=='0.3.3'
    out=ROOT/'exposed_inputs'/'forward_verified'
    out.mkdir(parents=True,exist_ok=True)
    assert not (out/'manifest.json').exists()
    frozen=json.loads((ext.ROOT/'results/candidate.json').read_text())
    logs=[]
    for name in ['SG_exposed','W_new_challenge']:
        source=ext.ROOT/'external_results'/f'{name}_predictions.csv'
        frame=pd.read_csv(source)
        pieces={}
        rowlogs=[]
        for airfoil in sorted(frame.airfoil.unique()):
            idx=np.flatnonzero(frame.airfoil.to_numpy()==airfoil)
            path=(ext.v.OLD if airfoil.startswith('sg') else ext.ROOT)/'external_screening/nominal_coordinates'/f'{airfoil}.dat'
            coords=np.asarray(ext.load_pts(path.read_text()))
            values=ext.prior.predict_base(coords,frame.alpha.to_numpy()[idx],frame.Re.to_numpy()[idx])
            d=ext.rich(values)
            d['XLARGE_CD']=values['XLARGE_CD']
            for key,val in d.items():
                if key not in pieces: pieces[key]=np.full((len(frame),)+val.shape[1:],np.nan)
                pieces[key][idx]=val
            p=ext.v.portable_predict(frozen,d)
            p=np.where(frame.inference_gate.to_numpy()[idx],p,d['BASE_CD'])
            err=float(np.max(np.abs(p-frame.cycle2_CD.to_numpy()[idx])))
            assert err<1e-12,err
            assert np.max(np.abs(d['BASE_CD']-frame.mean8_CD.to_numpy()[idx]))<1e-12
            assert np.max(np.abs(d['XLARGE_CD']-frame.xlarge_CD.to_numpy()[idx]))<1e-12
            # A simultaneous geometry/angle reflection. This is not an alpha-only symmetry assumption.
            mirror=coords[::-1].copy()
            mirror[:,1]*=-1
            k=idx[:min(12,len(idx))]
            mirrorvalues=ext.prior.predict_base(mirror,-frame.alpha.to_numpy()[k],frame.Re.to_numpy()[k])
            mirrord=ext.rich(mirrorvalues)
            original=ext.rich(ext.prior.predict_base(coords,frame.alpha.to_numpy()[k],frame.Re.to_numpy()[k]))
            diff=np.max(np.abs(mirrord['X24']-robust.reflect(original['X24'])),axis=0)
            rowlogs.append({'airfoil':airfoil,'rows':len(idx),'coordinate_sha256':ext.v.old.digest(path),
                'old_cycle2_prediction_max_abs_difference':err,'reflection_rows':len(k),'reflection_X24_max_abs_by_feature':diff.tolist(),
                'raw_coordinate_reflection_within_tolerance':bool(np.max(diff)<1e-4),
                'reflection_CD_max_abs_difference':float(np.max(np.abs(mirrord['BASE_CD']-original['BASE_CD'])))})
        pieces['Re']=frame.Re.to_numpy()
        pieces['alpha']=frame.alpha.to_numpy()
        assert all(np.isfinite(v).all() for v in pieces.values())
        np.savez_compressed(out/f'{name}.npz',**pieces)
        logs.append({'cohort':name,'source_csv':str(source),'source_sha256':ext.v.old.digest(source),
                     'feature_npz_sha256':ext.v.old.digest(out/f'{name}.npz'),'rows':len(frame),'checks':rowlogs})
    ext.v.old.dump(out/'manifest.json',{'status':'Previously exposed outcomes only; features not fitted to measurements',
        'neuralfoil':neuralfoil.__version__,'aerosandbox':aerosandbox.__version__,'generator_sha256':ext.v.old.digest(__file__),'cohorts':logs})
    print(json.dumps(logs),flush=True)


if __name__=='__main__':main()
