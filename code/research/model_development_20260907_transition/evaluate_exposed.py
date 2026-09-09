"""Cycle 4 diagnostics on SG/W, already exposed before this research cycle."""
import json
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd
import run_transition as run

ROOT=Path(__file__).resolve().parent


def main():
    out=ROOT/'exposed_results'
    out.mkdir(exist_ok=True)
    assert not (out/'pre_score_manifest.json').exists(), 'Preserve started/completed scoring'
    frozen=json.loads((ROOT/'results/freeze.json').read_text())
    original=json.loads((ROOT/'results/run_manifest.json').read_text())
    for p,h in original['hashes'].items(): assert run.common.v2.old.digest(p)==h,p
    paths=[Path(__file__),ROOT/'PROTOCOL.md',ROOT/'results/freeze.json',ROOT/'shape_inputs.py',ROOT/'transition_inputs.py',
        run.common.v2.OLD/'reproduction/reproduce_doubleclean.py']
    models={}
    for family,record in frozen['artifacts'].items():
        path=ROOT/'results'/f'fit_{family}.pkl'
        assert run.common.v2.old.digest(path)==record['sha256']
        with path.open('rb') as f: models[family]=pickle.load(f)
        paths.append(path)
    for name in ['SG_exposed','W_new_challenge']:
        paths += [ROOT/'inputs'/f'{name}.npz',ROOT/'shape_inputs'/f'{name}.npz',
            run.COMMON/'exposed_results'/f'{name}_predictions.csv',
            run.common.v2.ROOT/'external_results'/f'{name}_predictions.csv']
    manifest={'scored_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selected':frozen['selected'],
        'hashes':{str(p):run.common.v2.old.digest(p) for p in paths},'external_status':'Already exposed development diagnostics; no external fitting'}
    run.common.v2.old.dump(out/'pre_score_manifest.json',manifest)
    summaries=[]
    for name in ['SG_exposed','W_new_challenge']:
        d=run.inputs.load_exposed(name)
        frame=pd.read_csv(run.common.v2.ROOT/'external_results'/f'{name}_predictions.csv')
        previous=pd.read_csv(run.COMMON/'exposed_results'/f'{name}_predictions.csv')
        assert len(frame)==len(d['BASE_CD']) and np.array_equal(frame.alpha,previous.alpha) and np.array_equal(frame.Re,previous.Re)
        assert np.max(np.abs(d['BASE_CD']-frame.mean8_CD))<1e-12
        assert np.max(np.abs(d['XLARGE_CD']-frame.xlarge_CD))<1e-12
        frame['cycle3_gate_CD']=previous['gate_shrink__1']
        idx=np.arange(len(frame))
        base=d['BASE_CD']
        domain=frame.inference_gate.to_numpy(dtype=bool)
        frame['identity']=base
        frame['xlarge_fixed']=d['XLARGE_CD']
        for family,model in models.items():
            pred=run.predict(family,model,d,idx)
            for strength in [.5,1.0]: frame[f'{family}__{strength:g}']=np.where(domain,base+strength*(pred-base),base)
        for rule,label in frozen['selected'].items(): frame[rule]=frame[label]
        assert np.max(np.abs(frame['cycle2_fixed__1']-frame.cycle2_CD))<1e-12
        assert np.max(np.abs(frame['gate_shrink__1']-frame.cycle3_gate_CD))<1e-12
        assert np.isfinite(frame[run.common.LABELS+list(frozen['selected'])].to_numpy()).all()
        frame.to_csv(out/f'{name}_predictions.csv',index=False)
        for cohort,mask in [('eligible',frame.eligible.to_numpy(dtype=bool)),('all_complete_with_fallback',np.ones(len(frame),dtype=bool))]:
            part=frame[mask]
            subsets=[('pooled',part)]+[(a,part[part.airfoil==a]) for a in sorted(part.airfoil.unique())]
            if part.configuration.nunique()>part.airfoil.nunique(): subsets += [(c,part[part.configuration==c]) for c in sorted(part.configuration.unique())]
            for subset,f in subsets:
                for label in run.common.LABELS+list(frozen['selected']):
                    for baseline in ['xlarge_CD','mean8_CD','cycle2_CD','cycle3_gate_CD']:
                        metric=run.common.v2.old.metrics(f.measured_CD.to_numpy(),f[label].to_numpy(),f[baseline].to_numpy(),f.airfoil.to_numpy())
                        summaries.append({'set':name,'cohort':cohort,'subset':subset,'candidate':label,'baseline':baseline,**metric})
    for p,h in manifest['hashes'].items(): assert run.common.v2.old.digest(p)==h,p
    run.common.v2.old.dump(out/'results.json',{'manifest':manifest,'summaries':summaries})
    pd.DataFrame(summaries).to_csv(out/'metric_summary.csv',index=False)
    for row in summaries:
        if row['cohort']=='eligible' and row['subset']=='pooled' and row['candidate'] in frozen['selected'] and row['baseline']=='xlarge_CD':
            print(json.dumps(row),flush=True)


if __name__=='__main__':main()
