"""Private assembly utility. Accepts an explicit local project; never fits models."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
import numpy as np
import pandas as pd
import scipy
import sklearn

HERE=Path(__file__).resolve().parent
BUNDLE=HERE/'bundle'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path,obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')


def npz(path,values):
    for key,a in values.items():
        assert isinstance(a,np.ndarray),key
        assert a.dtype.kind != 'O',key
    with path.open('xb') as f:np.savez_compressed(f,**values)


def main(project):
    project=project.resolve();a=project/'model_development_20260907_cap_ablation';b=project/'model_development_20260908_adaptive_scale'
    assert not (BUNDLE/'manifest.json').exists(),'Do not overwrite assembled package'
    assert sha(b/'results/complete.json')=='05c120f90075946c76057f5fd6c19a95e3c25968a629e0040a28022ce237d20a'
    assert sha(b/'results/freeze.json')=='9b2cdfb23b57d92c9f4f142170c5583296e5ec6be54e7c14a20af618cdf6b9a3'
    sources={}
    def witness(path,expected=None):
        digest=sha(path)
        if expected is not None:assert digest==expected,path
        sources[str(Path(path).relative_to(project))]=digest
        return digest
    completes={}
    for stage,base in [('A',a),('B',b)]:
        cp=base/'results/complete.json';complete=json.loads(cp.read_text());completes[stage]=complete
        witness(cp);witness(base/'results/freeze.json',complete['freeze_sha256'])
        for key in ['source_input_sha256','artifact_sha256','output_sha256','external_input_sha256']:
            for name,h in complete[key].items():witness(name,h)
    for src,dest in [(a/'cap_models.py','cap_models.py'),(a/'test_cap_models.py','test_cap_models.py'),
        (project/'model_development_20260907_selective/selective.py','selective.py'),
        (project/'model_development_20260907_selective/test_selective.py','test_selective.py'),
        (b/'adaptive_scale.py','adaptive_scale.py'),(b/'test_adaptive_scale.py','test_adaptive_scale.py'),
        (a/'PROTOCOL.md','protocols/A.md'),(b/'PROTOCOL.md','protocols/B.md')]:
        assert (BUNDLE/dest).read_bytes()==src.read_bytes(),dest
        witness(src)
    for name in ['data','references','memberships','archived_assessment']:(BUNDLE/name).mkdir(exist_ok=False)
    sys.path.insert(0,str(project/'model_development_20260907_transition'));import shape_inputs
    d=shape_inputs.load_historical();keys=['X62','BASE_CD','XLARGE_CD','MEAS_CD','all_model_CD','group','source','nf2_row_id','Re','alpha','entry']
    npz(BUNDLE/'data/historical.npz',{k:d[k] for k in keys})
    assessment_reports={}
    for stage,base in [('A',a),('B',b)]:
        rp=base/'assessment/report.json';report=json.loads(rp.read_text());witness(rp)
        assessment_reports[stage]=report
        for name,h in report['output_sha256'].items():witness(name,h)
        for csvpath in sorted((base/'assessment').glob('*.csv')):
            if csvpath.name!='all_row_predictions.csv':
                shutil.copyfile(csvpath,BUNDLE/'archived_assessment'/f'{stage}_{csvpath.name}')
    # Keep just the two named archived references, not unrelated old expert columns.
    af=pd.read_csv(a/'assessment/all_row_predictions.csv',low_memory=False)
    required=['split','nf2_row_id','group','source','configuration','Re','alpha','measured_CD','mean8_CD','xlarge_CD','interval_applicable','unpenalized_transfer','half_strength']
    meta=af[required].copy();assert len(meta)==29856
    meta['configuration']=meta.configuration.fillna('').astype(str)
    meta['group']=meta.group.fillna('').astype(str)
    meta['source']=meta.source.fillna('').astype(str)
    meta['nf2_row_id']=meta.nf2_row_id.fillna(-1).astype(np.int64)
    assert meta.interval_applicable.dtype==bool
    positions={};contexts=json.loads((a/'results/freeze.json').read_text())['contexts']
    lookup={int(v):i for i,v in enumerate(d['nf2_row_id'])}
    for context in contexts:
        ma=json.loads((a/'results'/f'membership_{context}.json').read_text());mb=json.loads((b/'results'/f'membership_{context}.json').read_text())
        merged={k:v for k,v in ma.items() if k not in ['calibration_group_scores','calibration_q','calibration_rank','unbounded']}
        merged['inner_folds']=mb['inner_folds'];merged['A_calibrators']={}
        for f in ['capped','upper_free','positive_log']:
            merged['A_calibrators'][f]=json.loads((a/'results'/f'calibrator_{context}_{f}.json').read_text())
        merged['B_calibrator']=json.loads((b/'results'/f'calibrator_{context}.json').read_text())
        dump(BUNDLE/'memberships'/f'{context}.json',merged)
        if context!='final':
            mask=meta.split.eq(context);byid={int(meta.loc[i,'nf2_row_id']):int(i) for i in meta.index[mask]}
            idx=np.array(ma['test_indices'],int);positions[context]=[byid[int(v)] for v in d['nf2_row_id'][idx]]
            for col,key in [('mean8_CD','BASE_CD'),('xlarge_CD','XLARGE_CD'),('measured_CD','MEAS_CD')]:meta.loc[positions[context],col]=d[key][idx]
        for stage,base in [('A',a),('B',b)]:
            with np.load(base/'results'/f'inference_{context}.npz',allow_pickle=False) as z:
                skip={'indices','X62','BASE_CD','XLARGE_CD','all_model_CD','gate'}
                npz(BUNDLE/'references'/f'{stage}_inference_{context}.npz',{k:z[k] for k in z.files if k not in skip})
            with np.load(base/'results'/f'calibration_{context}.npz',allow_pickle=False) as z:
                keep=[k for k in z.files if k.startswith('CORE_CD') or k in ['dimensionless_scale','scale_CD']]
                npz(BUNDLE/'references'/f'{stage}_calibration_{context}.npz',{k:z[k] for k in keep})
        with np.load(b/'results'/f'scale_training_{context}.npz',allow_pickle=False) as z:
            npz(BUNDLE/'references'/f'B_training_{context}.npz',{k:z[k] for k in ['INNER_OOF_CORE_CD','scale_target','scale_weight','dimensionless_scale']})
    for name,n in [('SG_exposed',242),('W_new_challenge',255)]:
        ex=shape_inputs.load_exposed(name)
        with np.load(a/'exposed_results'/f'{name}_inference.npz',allow_pickle=False) as z:gate=z['gate'].copy()
        npz(BUNDLE/'data'/f'{name}.npz',{**{k:ex[k] for k in ['X62','BASE_CD','XLARGE_CD','all_model_CD','Re','alpha']},'gate':gate})
        ii=np.flatnonzero(meta.split.eq(name));assert len(ii)==n;positions[name]=ii.tolist()
        np.testing.assert_array_equal(meta.loc[ii,'alpha'],ex['alpha']);np.testing.assert_array_equal(meta.loc[ii,'Re'],ex['Re'])
        np.testing.assert_array_equal(meta.loc[ii,'interval_applicable'],gate)
        for col,key in [('mean8_CD','BASE_CD'),('xlarge_CD','XLARGE_CD')]:meta.loc[ii,col]=ex[key]
        for stage,base in [('A',a),('B',b)]:
            with np.load(base/'exposed_results'/f'{name}_inference.npz',allow_pickle=False) as z:
                skip={'indices','X62','BASE_CD','XLARGE_CD','all_model_CD','gate'}
                npz(BUNDLE/'references'/f'{stage}_inference_{name}.npz',{k:z[k] for k in z.files if k not in skip})
    arr={k:(meta[k].to_numpy(dtype=str) if meta[k].dtype.kind=='O' else meta[k].to_numpy()) for k in meta}
    npz(BUNDLE/'data/evaluation.npz',arr)
    # Preserve readable archived controls with an explicit original snapshot witness.
    meta[['split','nf2_row_id','configuration','Re','alpha','unpenalized_transfer','half_strength']].to_csv(BUNDLE/'data/archived_controls.csv',index=False,mode='x')
    # Source manifests are evidence only and use project-relative origins.
    dump(BUNDLE/'provenance.json',{'source_project_relative_sha256':sources,
        'archived_controls_original_csv':'model_development_20260907_cap_ablation/assessment/all_row_predictions.csv',
        'rights':'Private study only; experimental-data redistribution rights unresolved',
        'neuralfoil_forward_recomputed':False,'uses_precomputed_X62':True,
        'A_complete_sha256':sha(a/'results/complete.json'),'B_complete_sha256':sha(b/'results/complete.json'),
        'original_assessment_reports':{stage:{k:v for k,v in report.items() if k not in ['input_source_sha256','output_sha256']} for stage,report in assessment_reports.items()}})
    observed={'numpy':np.__version__,'scipy':scipy.__version__,'scikit-learn':sklearn.__version__,'pandas':pd.__version__}
    files={str(p.relative_to(BUNDLE)):sha(p) for p in sorted(BUNDLE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    dump(BUNDLE/'manifest.json',{'files':files,'contexts':contexts,'evaluation_positions':positions,
        'observed_dependencies':observed,'observed_python':sys.version,'A_core_fits':96,'B_fits':64,
        'archived_references_retrained':False,'independent_environment':False})
    print(json.dumps({'bundle_files':len(files),'bytes':sum((BUNDLE/n).stat().st_size for n in files),
                      'contexts':len(contexts),'native_reference_files':len(list((BUNDLE/'references').glob('*.npz')))}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project-root',required=True,type=Path)
    main(parser.parse_args().project_root)
