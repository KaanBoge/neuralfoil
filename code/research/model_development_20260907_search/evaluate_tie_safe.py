"""Separate optional input-convention sensitivity; no refitting or baseline mixing."""
import json
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import search as s

ROOT=Path(__file__).resolve().parent


def main():
    out=ROOT/'tie_safe'/'evaluation'
    out.mkdir(exist_ok=True)
    assert not (out/'results.json').exists()
    inputs=ROOT/'tie_safe/inputs'
    im=json.loads((inputs/'manifest.json').read_text())
    fm=json.loads((ROOT/'exposed_results/fit_manifest.json').read_text())
    for path,h in im['code_hashes'].items(): assert s.v2.old.digest(path)==h
    models={}
    for family in ['cycle2_fixed','gate_shrink']:
        path=ROOT/'exposed_results'/f'fit_{family}.pkl'
        assert s.v2.old.digest(path)==fm['artifacts'][family]['sha256']
        with path.open('rb') as f: models[family]=pickle.load(f)
    summaries=[]
    for record in im['cohorts']:
        name=record['cohort']
        path=inputs/f'{name}.npz'
        assert s.v2.old.digest(path)==record['npz_sha256']
        with np.load(path,allow_pickle=False) as f: d={k:f[k] for k in f.files}
        frame=pd.read_csv(ROOT/'exposed_results'/f'{name}_predictions.csv')
        assert np.array_equal(d['Re'],frame.Re) and np.array_equal(d['alpha'],frame.alpha)
        frame['legacy_gate_CD']=frame['gate_shrink__1']
        frame['tie_safe_xlarge_CD']=d['XLARGE_CD']
        frame['tie_safe_mean8_CD']=d['BASE_CD']
        idx=np.arange(len(frame))
        for family,model in models.items():
            frame[f'tie_safe_{family}_CD']=np.where(frame.inference_gate,s.predict(family,model,d,idx),d['BASE_CD'])
        frame.to_csv(out/f'{name}_predictions.csv',index=False)
        part=frame[frame.eligible]
        subsets=[('pooled',part)]+[(a,part[part.airfoil==a]) for a in sorted(part.airfoil.unique())]
        if part.configuration.nunique()>part.airfoil.nunique(): subsets += [(c,part[part.configuration==c]) for c in sorted(part.configuration.unique())]
        for subset,f in subsets:
            for candidate in ['tie_safe_xlarge_CD','tie_safe_mean8_CD','tie_safe_cycle2_fixed_CD','tie_safe_gate_shrink_CD']:
                for baseline in ['xlarge_CD','tie_safe_xlarge_CD','cycle2_CD','legacy_gate_CD']:
                    metric=s.v2.old.metrics(f.measured_CD.to_numpy(),f[candidate].to_numpy(),f[baseline].to_numpy(),f.airfoil.to_numpy())
                    summaries.append({'set':name,'cohort':'eligible','subset':subset,'candidate':candidate,'baseline':baseline,**metric})
    s.v2.old.dump(out/'results.json',{'status':'Optional input convention sensitivity, exposed data, unchanged fitted models',
        'input_manifest_sha256':s.v2.old.digest(inputs/'manifest.json'),'scoring_code_sha256':s.v2.old.digest(__file__),'summaries':summaries})
    pd.DataFrame(summaries).to_csv(out/'metric_summary.csv',index=False)
    print(pd.DataFrame(summaries).query('subset == "pooled" and baseline == "tie_safe_xlarge_CD"')[['set','candidate','candidate_mae_counts','relative_reduction_percent']].to_string(index=False))


if __name__=='__main__':main()
