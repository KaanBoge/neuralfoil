"""One-worker geometry routing experiment; frozen producers remain read-only."""
from pathlib import Path
import importlib.util
import hashlib,json,sys,time,traceback
import numpy as np
import pandas as pd
import router

HERE=Path(__file__).resolve().parent; PROJECT=HERE.parents[1]
FRONTIER=PROJECT/'model_development_20260907_frontier'
UNION=FRONTIER/'union_historical'; OUT=HERE/'results'
SHAPE=PROJECT/'model_development_20260907_transition/shape_inputs'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def dump(p,v): Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def verify(hashes):
    for p,h in hashes.items(): assert sha(p)==h,p

def load_union():
    manifest=read(UNION/'results/manifest.json'); verify(manifest['hashes'])
    p=UNION/'run_union.py';spec=importlib.util.spec_from_file_location('geometry_union_helper',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def load_shape(name):
    p=SHAPE/f'{name}.npz'
    prior=read(FRONTIER/'capacity/results/run_manifest.json')['hashes']
    assert sha(p)==prior[str(p)],p
    with np.load(p,allow_pickle=False) as a: return {k:a[k].copy() for k in a.files}


def fit_one(union,d,k18,name):
    anchorpath=UNION/f'results/weights_{name}.json'
    frozen=read(UNION/'results/freeze.json')['weights_sha256']
    assert sha(anchorpath)==frozen[str(anchorpath)]
    anchor=read(anchorpath)
    # Verify completed consumer hashes BEFORE helper opens NPZ archives.
    verify(anchor['input_sha256'])
    frame,enclosing,hashes=union.training(name)
    assert hashes==anchor['input_sha256']
    assert list(frame.loc[frame.context=='group','nf2_row_id'])==anchor['training_nf2_row_ids']
    indices=frame.historical_index.to_numpy(dtype=int)
    assert set(indices)<=set(enclosing)
    group=frame.context.to_numpy()=='group'
    re=d['Re'][indices]; alpha=d['alpha'][indices]; geom=k18[indices]
    center=np.asarray([anchor['solutions']['primary_union_both']['weights'][c] for c in union.COMPONENTS])
    rows=[]
    for variant in router.VARIANTS:
        tick=time.monotonic()
        model=router.build_router(variant,geom[group],re[group],alpha[group])
        model=router.fit_variant(frame,union.loader.training_panels(frame),center,model,geom,re,alpha,union.COMPONENTS)
        model.update(split=name,training_nf2_row_ids=anchor['training_nf2_row_ids'],training_groups=anchor['training_groups'],
                     input_sha256=hashes,anchor_sha256=sha(anchorpath),unique_training_rows=len(enclosing),
                     prediction_context_rows=len(frame),status='adaptive_historical_only_experimental_no_selector')
        dump(OUT/f'{name}_{variant}.json',model)
        row={'split':name,'variant':variant,'seconds':time.monotonic()-tick,
             'inner_fitted_worst_ratio':model['actual_worst_training_ratio']}
        rows.append(row); print(json.dumps(row),flush=True)
    verify(hashes)
    return rows


def evaluate(union,d,k18):
    # First external prediction/outcome read occurs only after 64-model freeze.
    assert len(read(OUT/'freeze.json')['model_sha256'])==64
    sys.path.insert(0,str(FRONTIER)); import frontier_assessment as assess
    frame,_,_,hashes=assess.load_frame(['capacity','kernel'])
    for branch,names in union.NEW.items():
        for name in names: frame[name+'__1']=frame[branch+'__'+name+'__1']
    for variant in router.VARIANTS: frame[variant]=np.nan
    id_lookup={int(v):i for i,v in enumerate(d['nf2_row_id'])}
    external_dir=HERE/'exposed_results';external_dir.mkdir(exist_ok=False)
    for split in frame.split.unique():
        external=split in ['SG_exposed','W_new_challenge'];mask=frame.split==split; f=frame.loc[mask]
        if external:
            shape=load_shape(split); geom=shape['K18']
            np.testing.assert_allclose(shape['Re'],f.Re.to_numpy(),rtol=0,atol=1e-12)
            np.testing.assert_allclose(shape['alpha'],f.alpha.to_numpy(),rtol=0,atol=1e-12)
            gate=f.inference_gate.map(lambda v:str(v).lower()=='true' or v==1).to_numpy(bool)
            assert gate.sum()=={'SG_exposed':234,'W_new_challenge':238}[split]
        else:
            indices=np.array([id_lookup[int(v)] for v in f.nf2_row_id]);geom=k18[indices];gate=np.ones(len(f),bool)
        for variant in router.VARIANTS:
            model=read(OUT/f"{'final' if external else split}_{variant}.json")
            if not external:
                assert set(f.nf2_row_id).isdisjoint(model['training_nf2_row_ids'])
                assert set(f.group).isdisjoint(model['training_groups'])
            pred=router.predict(model,f[union.COMPONENTS].to_numpy(),geom,f.Re.to_numpy(),f.alpha.to_numpy(),f.mean8_CD.to_numpy(),gate)
            assert np.isfinite(pred).all() and (pred>0).all()
            np.testing.assert_array_equal(pred[~gate],f.mean8_CD.to_numpy()[~gate])
            frame.loc[mask,variant]=pred
        path=external_dir/f'{split}_predictions.csv' if external else OUT/f'predictions_{split}.csv'
        frame.loc[mask].to_csv(path,index=False)
    frame.to_csv(OUT/'all_row_predictions.csv',index=False)
    verify(hashes)
    return hashes


def main():
    OUT.mkdir(exist_ok=False)
    try:
        union=load_union()
        paths=[Path(__file__),HERE/'router.py',HERE/'PROTOCOL.md',HERE/'test_router.py',
               UNION/'run_union.py',UNION/'results/freeze.json',
               FRONTIER/'conditional/conditional_stack.py']
        hashes={str(p):sha(p) for p in paths}
        # Historical data/helper files were already pinned by completed consumers.
        prior=read(FRONTIER/'capacity/results/run_manifest.json')['hashes']
        historical={p:h for p,h in prior.items() if 'SG_exposed' not in p and 'W_new_challenge' not in p}
        verify(historical);hashes.update(historical)
        shape=load_shape('historical');d=union.loader.v2.load_data();k18=shape['K18']
        np.testing.assert_array_equal(shape['nf2_row_id'],d['nf2_row_id'])
        np.testing.assert_array_equal(shape['Re'],d['Re']);np.testing.assert_array_equal(shape['alpha'],d['alpha'])
        names=read(UNION/'results/manifest.json')['names'];assert len(names)==16
        dump(OUT/'manifest.json',{'source_sha256':hashes,'variants':list(router.VARIANTS),
             'components':union.COMPONENTS,'contexts':names,'workers':1,'highs_threads':1})
        logs=[]
        for name in names: logs+=fit_one(union,d,k18,name)
        models={str(p):sha(p) for p in OUT.glob('*.json') if p.name not in ['manifest.json']}
        assert len(models)==64
        verify(hashes)
        dump(OUT/'freeze.json',{'model_sha256':models,'all_64_frozen_before_exposed':True})
        evaluation=evaluate(union,d,k18)
        verify(hashes);verify(models)
        dump(OUT/'complete.json',{'fits':logs,'model_count':64,'source_sha256':hashes,
             'evaluation_sha256':evaluation,'rows':29856,'status':'experimental_not_deployed'})
        print('COMPLETE: 64 routers frozen; all row predictions retained',flush=True)
    except Exception:
        dump(OUT/'failure.json',{'traceback':traceback.format_exc()})
        raise


if __name__=='__main__':main()
