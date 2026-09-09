"""Build a private label-free addon; never imports project data-loading modules."""
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--project-root',type=Path,required=True)
    root=parser.parse_args().project_root.resolve(); out=Path(__file__).parent/'addon'
    data=out/'data'; data.mkdir(exist_ok=False); (out/'coordinates').mkdir(exist_ok=False)
    witnesses={}
    def witness(path,expected=None):
        path=Path(path); digest=sha(path)
        if expected is not None: assert digest==expected,(path,digest,expected)
        witnesses[str(path.relative_to(root))]=digest
        return path
    trans=root/'model_development_20260907_transition'
    manifest=json.loads(witness(trans/'inputs/manifest.json').read_text())
    for path,digest in manifest['hashes'].items(): witness(root/path if not Path(path).is_absolute() else path,digest)
    dm=json.loads(witness(root/'model_development_20260906/reproduction/dataset_manifest.json').read_text())
    nfrel=next(k for k in dm['input_sha256'] if k.endswith('/lsat-nf2.csv'))
    nf=witness(root/nfrel,dm['input_sha256'][nfrel])
    from addon.feature_math import SIZES
    cols=['source','airfoil','Re','alpha','conf_xlarge','topxtr','botxtr','cm8']+[f'{v}_{s}' for v in ['CD','CL'] for s in SIZES]
    teacher=pd.read_csv(nf,usecols=cols,float_precision='round_trip')
    teacher['entry']=teacher.source+'|'+teacher.airfoil
    coordinate_map={}; counts={}
    for cohort in manifest['cohorts']:
        name=cohort['name']; trpath=witness(trans/'inputs'/f'{name}.npz',cohort['output_sha256'])
        with np.load(trpath,allow_pickle=False) as z: tr={k:z[k] for k in z.files}
        shape_manifest=json.loads(witness(trans/'shape_inputs/manifest.json').read_text())
        shco=next(c for c in shape_manifest['cohorts'] if c['name']==name)
        with np.load(witness(trans/'shape_inputs'/f'{name}.npz',shco['output_sha256']),allow_pickle=False) as z: tr['K18']=z['K18']
        if name=='historical':
            old=witness(root/'model_development_20260906/reproduction/dataset_occurrence.npz','54ea9aa6973be93fd428f78445fb2096ff70b50a8f6510119f31459d897c378e')
            with np.load(old,allow_pickle=False) as z:
                lookup={int(v):i for i,v in enumerate(z['nf2_row_id'])}; ix=np.array([lookup[int(v)] for v in tr['nf2_row_id']])
                ref={k:z[k][ix] for k in ['X9','X16','BASE_CD','XLARGE_CD','all_model_CD','all_model_CL']}
            selected=teacher.iloc[tr['nf2_row_id']]
            assert np.array_equal(selected.alpha,tr['alpha']) and np.array_equal(selected.Re,tr['Re'])
            assert np.array_equal(selected.entry,tr['entry'])
            used=teacher[teacher.entry.isin(tr['entry'])]
            np.savez_compressed(data/'teacher.npz',nf2_row_id=used.index.to_numpy(),**{k:used[k].to_numpy(dtype=str if k in ['entry','source','airfoil'] else float) for k in used.columns})
        else:
            fp=root/'model_development_20260907_search/exposed_inputs/forward_verified'
            fm=json.loads(witness(fp/'manifest.json').read_text())
            # The transition manifest already authenticates these forward inputs.
            with np.load(witness(fp/f'{name}.npz'),allow_pickle=False) as z: ref={k:z[k] for k in z.files}
        ref.update(tr); ref['X24']=tr['X44'][:,:24];ref['X62']=np.column_stack([tr['X44'],tr['K18']])
        np.savez_compressed(data/f'{name}.npz',**ref); counts[name]=len(tr['alpha'])
        coordinate_map[name]={}
        for check in cohort['checks']:
            origin=check['coordinate_origin']; bits=origin.split('::')
            path=Path(bits[0]); witness(path)
            if len(bits)==2:
                with zipfile.ZipFile(path) as z: raw=z.read(bits[1])
            else: raw=path.read_bytes()
            digest=hashlib.sha256(raw).hexdigest();assert digest==check['coordinate_sha256']
            target=out/'coordinates'/f'{digest}.dat'
            if not target.exists(): target.write_bytes(raw)
            key=check.get('entry',check.get('airfoil')); assert key is not None
            coordinate_map[name][key]={'path':str(target.relative_to(out)),'sha256':digest,'origin':str(path.relative_to(root))+('::'+bits[1] if len(bits)==2 else '')}
    sources=['model_development_20260906/reproduction/reproduce_doubleclean.py','model_development_20260906/score_external.py','model_development_20260906_v2/develop_v2.py','model_development_20260907_transition/generate_inputs.py','model_development_20260907_transition/generate_shape.py',str(Path(nfrel).with_name('lsat_run2.py'))]
    for source in sources:witness(root/source)
    result={'scope':'Private label-free feature regeneration; frozen cohort membership inherited. No measured labels exported.','counts':counts,'coordinates':coordinate_map,'source_sha256':witnesses,'files':{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(counts))
if __name__=='__main__': main()
