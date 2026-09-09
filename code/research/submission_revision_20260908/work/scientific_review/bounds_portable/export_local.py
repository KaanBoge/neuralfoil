"""Author-side one-time export: trusted local pickle only after frozen hash check."""
from pathlib import Path
import hashlib, json, pickle, shutil
import numpy as np

HERE=Path(__file__).resolve().parent
EXPECTED='b0e9c6c7b3610505fe1178c78e2fa1077c51619fbe48e1b3dadb174b505a60d7'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=HERE.parent/'EXACT_BOUNDS.json'
    if sha(p)!=EXPECTED: raise ValueError('frozen exact witness changed')
    old=json.loads(p.read_text()); sources=old['source_sha256']
    for name,h in sources.items():
        if sha(name)!=h: raise ValueError('source changed: '+name)
    print('Authenticated source bytes before export:',sum(Path(x).stat().st_size for x in sources))
    bundle=HERE/'bundle'; bundle.mkdir(exist_ok=False)
    (bundle/'arrays').mkdir()
    shutil.copyfile(p,bundle/'expected.json')
    for name in ['check.py','test_check.py','README.md']:
        shutil.copyfile(HERE/name,bundle/name)
    meta={'format':1,'trees':[],'floors':[], 'provenance':[], 'files':{}}
    for i,ref in enumerate(old['trees']):
        rec={'context':ref['context'],'branch':ref['branch']}
        for family in ['capped','upper_free']:
            suffix=f"core_{ref['context']}_{ref['branch']}_{family}.pkl"
            source=next(Path(x) for x in sources if x.endswith('/'+suffix))
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=sources[str(source)]: raise ValueError('source drift')
            model=pickle.loads(raw)['model']
            if len(model._predictors)!=400 or any(len(x)!=1 for x in model._predictors): raise ValueError('stage count')
            arrays={'initial':model._baseline_prediction}
            for key in ['nodes','raw_left_cat_bitsets','binned_left_cat_bitsets']:
                values=[getattr(stage[0],key) for stage in model._predictors]
                arrays[key]=np.concatenate(values)
                arrays[key+'_offsets']=np.cumsum([0]+[len(x) for x in values],dtype=np.int64)
            dest=f'arrays/tree_{i:02d}_{family}.npz'
            np.savez_compressed(bundle/dest,**arrays);rec[family]=dest
            meta['provenance'].append({'output':dest,'source_basename':source.name,'source_sha256':sources[str(source)],'transformation':'lossless concatenation with stage offsets; both members retained'})
        meta['trees'].append(rec)
    for i,ref in enumerate(old['floors']):
        source=next(Path(x) for x in sources if x.endswith(f"/calibration_{ref['context']}.npz"))
        with np.load(source,allow_pickle=False) as z:
            arrays={k:z[k] for k in ['indices','nf2_row_id','group','BASE_CD','CORE_CD','MEAS_CD']}
        dest=f'arrays/calibration_{i:02d}.npz';np.savez_compressed(bundle/dest,**arrays)
        meta['floors'].append({'context':ref['context'],'file':dest})
        meta['provenance'].append({'output':dest,'source_basename':source.name,'source_sha256':sources[str(source)],'transformation':'unchanged required arrays plus row IDs/core; X62 omitted as irrelevant to floor'})
    for name,h in sources.items():
        if sha(name)!=h: raise ValueError('source changed during export')
    for p in sorted(bundle.rglob('*')):
        if p.is_file():meta['files'][str(p.relative_to(bundle))]=sha(p)
    meta['frozen_exact_sha256']=EXPECTED
    (bundle/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('Bundle bytes:',sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file()))
    print('MANIFEST_SHA256',sha(bundle/'manifest.json'))
if __name__=='__main__':main()
