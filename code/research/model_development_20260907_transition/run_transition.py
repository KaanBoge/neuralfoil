"""Documented adapter to frozen Cycle 3 common evaluation; separate artifacts."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import pickle
import platform
import sys
import time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
COMMON=ROOT.parent/'model_development_20260907_search'
sys.path[:0]=[str(ROOT),str(COMMON)]
import search as common
import transition_models as model_module
import shape_inputs as inputs

ORIGINAL_FIT=common.fit
ORIGINAL_PREDICT=common.predict
FAMILIES=['cycle2_fixed','gate_shrink']+model_module.FAMILIES


def fit(family,d,idx):
    return model_module.fit(family,d,idx) if family in model_module.FAMILIES else ORIGINAL_FIT(family,d,idx)


def predict(family,model,d,idx):
    return model_module.predict(model,d,idx) if family in model_module.FAMILIES else ORIGINAL_PREDICT(family,model,d,idx)


# Module-level registration is replayed identically in spawned worker processes.
# The original common source and its scientific split/selector code are never edited.
common.FAMILIES=FAMILIES
common.LABELS=['identity','xlarge_fixed']+[f'{f}__{strength:g}' for f in FAMILIES for strength in [.5,1.0]]
common.fit=fit
common.predict=predict


def main():
    out=ROOT/'results'
    out.mkdir(exist_ok=True)
    assert not (out/'run_manifest.json').exists(), 'Preserve all previous starts/results'
    d=inputs.load_historical()
    assert len(d['BASE_CD'])==8371 and len(set(d['group']))==93 and d['X44'].shape==(8371,44)
    paths=[Path(__file__),Path(model_module.__file__),Path(inputs.__file__),ROOT/'PROTOCOL.md',ROOT/'INPUT_PROTOCOL.md',
        ROOT/'generate_inputs.py',ROOT/'inputs/manifest.json',ROOT/'inputs/historical.npz',ROOT/'transition_inputs.py',
        ROOT/'SHAPE_INPUT_PROTOCOL.md',ROOT/'generate_shape.py',ROOT/'shape_inputs/manifest.json',ROOT/'shape_inputs/historical.npz',COMMON/'search.py',COMMON/'robust_models.py',
        Path(common.v2.__file__),Path(common.v2.old.__file__),common.v2.OLD/'reproduction/dataset_occurrence.npz',
        common.v2.OLD/'methods_audit/entry_group_map.csv',common.v2.OLD/'methods_audit/ambiguous_nf2_row_ids.csv']
    manifest={'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'python':platform.python_version(),
        'hashes':{str(p):common.v2.old.digest(p) for p in paths},'families':FAMILIES,'labels':common.LABELS,
        'rows':len(d['BASE_CD']),'groups':len(set(d['group'])),'external_status':'SG/W exposed, no external fit'}
    common.v2.old.dump(out/'run_manifest.json',manifest)
    ids=np.arange(len(d['BASE_CD']))
    tasks=[]
    for seed in [20260906,20260908]:
        for i,te in enumerate(common.v2.old.group_folds(d['group'],5,seed)):
            tasks.append((f'group_{seed}_fold_{i}',d,ids[~te],ids[te],out))
    for source in sorted(set(d['source']))+['all_uiuc_volumes']:
        te=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        tr=~te&~np.isin(d['group'],d['group'][te])
        tasks.append((f'strict_source_{source}',d,ids[tr],ids[te],out))
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs=[pool.submit(common.evaluate,t) for t in tasks]
        for job in as_completed(jobs):
            log=job.result()
            print(json.dumps({'finished':log['split'],'selected':log['selected'],'seconds':round(log['total_seconds'],1)}),flush=True)
    common.summarize(out)
    selected,selection=common.select(d,ids,out/'final')
    artifacts={}
    for family in FAMILIES:
        model=fit(family,d,ids)
        pred=predict(family,model,d,ids)
        path=out/f'fit_{family}.pkl'
        with path.open('wb') as f: pickle.dump(model,f,protocol=5)
        with path.open('rb') as f: restored=pickle.load(f)
        delta=float(np.max(np.abs(predict(family,restored,d,ids)-pred)))
        assert delta<1e-12
        artifacts[family]={'sha256':common.v2.old.digest(path),'all_historical_reload_parity_max_CD':delta}
    for p,h in manifest['hashes'].items(): assert common.v2.old.digest(p)==h,p
    common.v2.old.dump(out/'freeze.json',{'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'selected':selected,'selection':selection,'artifacts':artifacts,'historical_only_fit':True,'status':'experimental_not_deployed'})
    print(json.dumps({'done':True,'selected':selected}),flush=True)


if __name__=='__main__':main()
