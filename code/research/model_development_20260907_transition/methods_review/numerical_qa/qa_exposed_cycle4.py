"""Explicit schema adapter for prior independent exposed numerical checker."""
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
SOURCE=ROOT.parent/'model_development_20260907_search/methods_review/numerical_qa/qa_exposed.py'
code=SOURCE.read_text()
replacements={
    "manifest['candidate_labels']":"manifest['labels']",
    "ROOT/'exposed_inputs/forward_verified'":"ROOT.parent/'model_development_20260907_search/exposed_inputs/forward_verified'",
    "for cycle in [1,2]:":"for cycle in [2]:",
    "['xlarge_CD','mean8_CD','cycle1_CD','cycle2_CD']":"['xlarge_CD','mean8_CD','cycle2_CD','cycle3_gate_CD']",
    "for family,record in results['manifest']['artifacts'].items():assert hashlib.sha256((EX/f'fit_{family}.pkl').read_bytes()).hexdigest()==record['sha256']":
        "for family,record in freeze['artifacts'].items():assert hashlib.sha256((ROOT/'results'/f'fit_{family}.pkl').read_bytes()).hexdigest()==record['sha256']",
    "    frames[name]=f":"""    previous=pd.read_csv(ROOT.parent/'model_development_20260907_search/exposed_results'/(name+'_predictions.csv'))
    assert np.array_equal(previous[['configuration','block','source_line']].to_numpy(),f[['configuration','block','source_line']].to_numpy())
    assert np.max(np.abs(f['cycle3_gate_CD']-previous['gate_shrink__1']))<1e-12
    assert np.max(np.abs(f['gate_shrink__1']-f['cycle3_gate_CD']))<1e-12
    with np.load(ROOT/'inputs'/(name+'.npz'),allow_pickle=False) as trans:
        assert np.array_equal(trans['row_id'],np.arange(len(f)))
        assert np.array_equal(trans['alpha'],f.alpha) and np.array_equal(trans['Re'],f.Re)
        assert np.array_equal(trans['airfoil'],f.airfoil)
        assert np.max(np.abs(trans['ncrit_CD'][:,2]-f.xlarge_CD))<1e-12
    with np.load(ROOT/'shape_inputs'/(name+'.npz'),allow_pickle=False) as shape:
        assert np.array_equal(shape['row_id'],np.arange(len(f)))
        assert np.array_equal(shape['alpha'],f.alpha) and np.array_equal(shape['Re'],f.Re)
        assert np.array_equal(shape['airfoil'],f.airfoil)
        assert shape['K18'].shape==(len(f),18) and np.isfinite(shape['K18']).all()
    frames[name]=f""",
}
for old,new in replacements.items():
    assert old in code,old
    code=code.replace(old,new)
(OUT/'exposed_adapter_provenance.json').write_text(json.dumps({'source':str(SOURCE),
    'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'schema_mappings':replacements},indent=2)+'\n')
exec(compile(code,str(SOURCE),'exec'),{'__file__':__file__,'__name__':'__main__'})
