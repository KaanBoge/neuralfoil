"""Post-fit exact bridge to immutable compact-package predictions; no outcomes or fits."""
from pathlib import Path
import numpy as np
import replay as r


def main():
    here=Path(__file__).resolve().parent;original=here.parents[2]/'reproduction_20260908_private/bundle'
    manifest=r.read(original/'manifest.json');path=original/'data/evaluation.npz'
    assert r.sha(path)==manifest['files']['data/evaluation.npz']
    with np.load(path,allow_pickle=False) as z:
        # Only the two already frozen reference predictions; no measured outcome read.
        refs={k:z[k].copy() for k in ['unpenalized_transfer','half_strength']}
    target=here/'evaluation';target.mkdir(exist_ok=False)
    records=[]
    for name,pos in manifest['evaluation_positions'].items():
        suffix='_final.npz' if name in ['SG_exposed','W_new_challenge'] else '_outer.npz'
        out=r.load(here/'results'/(name+suffix))
        for label,key in [('unpenalized_transfer','prediction'),('half_strength','half')]:
            pred=r.csv_roundtrip(out[key]);r.exact(pred,refs[label][pos])
            records.append({'context':name,'label':label,'rows':len(pos),'unequal_elements':0,'max_abs_difference':0.})
    np.savez_compressed(target/'reference_predictions.npz',**refs)
    r.dump(target/'manifest.json',{'original_manifest_sha256':r.sha(original/'manifest.json'),
        'original_evaluation_sha256':r.sha(path),'positions':manifest['evaluation_positions'],
        'reference_sha256':r.sha(target/'reference_predictions.npz'),'comparisons':records,
        'rows_per_reference':29856,'outcomes_loaded':False,'scope':'Post-fit equality to pre-existing compact reference columns'})
    print('Exact evaluation bridge: 34 comparisons, 29,856 rows per reference')


if __name__=='__main__': main()
