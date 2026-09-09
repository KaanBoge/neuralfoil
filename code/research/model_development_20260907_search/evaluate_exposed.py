"""All frozen Cycle 3 families on already-exposed SG/W, never new confirmation."""
import json
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd
import search as s

ROOT=Path(__file__).resolve().parent


def main():
    out=ROOT/'exposed_results'
    out.mkdir(exist_ok=True)
    assert not (out/'fit_manifest.json').exists(), 'Preserve prior starts/results'
    frozen=json.loads((ROOT/'results/freeze.json').read_text())
    original=json.loads((ROOT/'results/run_manifest.json').read_text())
    for path,h in original['hashes'].items(): assert s.v2.old.digest(path)==h,path
    inputs=ROOT/'exposed_inputs/forward_verified'
    meta=json.loads((inputs/'manifest.json').read_text())
    d=s.v2.load_data()
    ids=np.arange(len(d['BASE_CD']))
    models,checks={},{ }
    for family in s.FAMILIES:
        start=time.monotonic()
        model=s.fit(family,d,ids)
        p=s.predict(family,model,d,ids)
        path=out/f'fit_{family}.pkl'
        with path.open('wb') as f: pickle.dump(model,f,protocol=5)
        with path.open('rb') as f: got=pickle.load(f)
        difference=float(np.max(np.abs(s.predict(family,got,d,ids)-p)))
        assert difference<1e-12,difference
        models[family]=got
        checks[family]={'sha256':s.v2.old.digest(path),'reload_parity_rows':len(ids),'reload_parity_max_abs_CD':difference,'seconds':time.monotonic()-start}
    paths=[Path(__file__),ROOT/'EXPOSED_PROTOCOL.md',ROOT/'results/freeze.json',inputs/'manifest.json']
    for record in meta['cohorts']:
        path=Path(record['source_csv'])
        assert s.v2.old.digest(path)==record['source_sha256']
        npz=inputs/f"{record['cohort']}.npz"
        assert s.v2.old.digest(npz)==record['feature_npz_sha256']
        paths += [path,npz]
    manifest={'frozen_fit_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'historical_only_fit':True,
        'selected':frozen['selected'],'artifacts':checks,'hashes':{str(p):s.v2.old.digest(p) for p in paths},
        'status':'all external outcomes previously exposed; not independent confirmation'}
    s.v2.old.dump(out/'fit_manifest.json',manifest)
    summaries=[]
    for record in meta['cohorts']:
        name=record['cohort']
        frame=pd.read_csv(record['source_csv'])
        with np.load(inputs/f'{name}.npz',allow_pickle=False) as archive: ext={k:archive[k] for k in archive.files}
        idx=np.arange(len(frame))
        base=ext['BASE_CD']
        domain=frame.inference_gate.to_numpy(dtype=bool)
        frame['identity']=base
        frame['xlarge_fixed']=ext['XLARGE_CD']
        for family in s.FAMILIES:
            pred=s.predict(family,models[family],ext,idx)
            for strength in [.5,1.0]:
                label=f'{family}__{strength:g}'
                frame[label]=np.where(domain,base+strength*(pred-base),base)
        for rule,label in frozen['selected'].items(): frame[rule]=frame[label]
        assert np.max(np.abs(frame['cycle2_fixed__1']-frame.cycle2_CD))<1e-12,'Refit control mismatch'
        assert np.max(np.abs(frame['cycle1_fixed__1']-frame.cycle1_CD))<1e-12,'Refit control mismatch'
        assert np.isfinite(frame[s.LABELS+list(frozen['selected'])].to_numpy()).all()
        frame.to_csv(out/f'{name}_predictions.csv',index=False)
        for cohort,mask in [('eligible',frame.eligible.to_numpy(dtype=bool)),('all_complete_with_fallback',np.ones(len(frame),dtype=bool))]:
            part=frame[mask]
            subsets=[('pooled',part)]+[(a,part[part.airfoil==a]) for a in sorted(part.airfoil.unique())]
            if part.configuration.nunique()>part.airfoil.nunique(): subsets += [(c,part[part.configuration==c]) for c in sorted(part.configuration.unique())]
            for subset,f in subsets:
                for label in s.LABELS+list(frozen['selected']):
                    for baseline in ['xlarge_CD','mean8_CD','cycle1_CD','cycle2_CD']:
                        metric=s.v2.old.metrics(f.measured_CD.to_numpy(),f[label].to_numpy(),f[baseline].to_numpy(),f.airfoil.to_numpy())
                        summaries.append({'set':name,'cohort':cohort,'subset':subset,'candidate':label,'baseline':baseline,**metric})
    for p,h in manifest['hashes'].items(): assert s.v2.old.digest(p)==h,p
    for family,check in checks.items(): assert s.v2.old.digest(out/f'fit_{family}.pkl')==check['sha256']
    s.v2.old.dump(out/'results.json',{'manifest':manifest,'summaries':summaries})
    pd.DataFrame(summaries).to_csv(out/'metric_summary.csv',index=False)
    for row in summaries:
        if row['cohort']=='eligible' and row['subset']=='pooled' and row['candidate'] in frozen['selected'] and row['baseline']=='xlarge_CD':
            print(json.dumps(row),flush=True)


if __name__=='__main__':main()
