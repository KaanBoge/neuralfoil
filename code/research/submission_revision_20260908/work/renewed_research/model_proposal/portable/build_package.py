"""Private artifact exporter, not a fit/algorithm change. No work on import."""
from pathlib import Path
import ast,hashlib,importlib.util,io,json,zipfile
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;P=HERE.parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
A=PROJECT/'model_development_20260907_cap_ablation'
FROZEN='719b239b7799b156e57b35c19708fec154ea1687a4bd9e934542ef31a42e4861'
COMPLETE='0357329dc882b6db1c8ea7fb5852f26118f13c168c1a2453b7ffef5bec5dc8ff'
ASSESS='1c34134f311695a54a9c91c0ffa19699c7ce826eb1c8f50e671336f263cce9ff'
DEST=HERE/'incremental_harm_private'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(p,h):
    b=Path(p).read_bytes();assert hashlib.sha256(b).hexdigest()==h,p;return b
def read(p):return json.loads(Path(p).read_text())
def dump(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def save_npz(p,**values):
    with Path(p).open('xb') as f:np.savez_compressed(f,**values)
def npz(p,h):
    with np.load(io.BytesIO(checked(p,h)),allow_pickle=False) as z:return {k:z[k] for k in z.files}


def main():
    assert not DEST.exists(),'Never overwrite package'
    freeze=json.loads(checked(P/'results/freeze.json',FROZEN));complete=json.loads(checked(P/'results/complete.json',COMPLETE))
    assessment=json.loads(checked(P/'assessment/report.json',ASSESS))
    witnesses={}
    for d in [freeze,complete,assessment]:
        for key in ['artifact_sha256','source_input_sha256','external_input_sha256','output_sha256']:
            witnesses.update(d.get(key,{}))
    af=read(A/'results/freeze.json')
    checked(A/'results/freeze.json',witnesses[str(A/'results/freeze.json')])
    # Export-time reconstruction of original in-memory scoring inputs only.
    helper=A/'assess_cap.py';checked(helper,witnesses[str(helper)])
    spec=importlib.util.spec_from_file_location('portable_export_frozen_assessment',helper)
    cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
    f,panels,metrics,prior,inherited=cap.load()
    for split in f.split.unique():
        external=split in ['SG_exposed','W_new_challenge']
        p=P/('exposed_results' if external else 'results')/(f'{split}_predictions.csv' if external else f'predictions_{split}.csv')
        fresh=pd.read_csv(io.BytesIO(checked(p,witnesses[str(p)])),low_memory=False)
        mask=f.split.eq(split);old=f.loc[mask]
        if not external:fresh=fresh.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(fresh.configuration,old.configuration)
        for field in ['calibrated_incremental_harm_001','calibrated_incremental_harm_001__strength',
                      'calibrated_incremental_harm_001__intervened','calibration_t']:
            f.loc[mask,field]=fresh[field].to_numpy()
    labels=['calibrated_incremental_harm_001','proper_capped_half','proper_capped_full','project_mean8_capped',
            'project_xlarge_capped','mean8_CD','xlarge_CD','capped_half','capped_full','unpenalized_transfer','half_strength']
    metadata=['split','nf2_row_id','group','source','airfoil','configuration','Re','alpha','measured_CD','interval_applicable']
    extra=['calibrated_incremental_harm_001__strength','calibrated_incremental_harm_001__intervened','calibration_t']
    columns=list(dict.fromkeys(metadata+labels+extra));f=f[columns]
    assert len(f)==29856 and len(panels)==31
    DEST.mkdir();provenance={};ast_witness=[]
    def copy(source,name,expected=None):
        expected=expected or witnesses[str(source)];b=checked(source,expected)
        target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
        provenance[name]={'source_id':str(source.relative_to(PROJECT)),'sha256':expected}
    for name in ['incremental_harm.py','test_incremental_harm.py','PROPOSAL.md','APPROVAL.md']:
        copy(P/name,name)
    for name in ['replay.py','test_integrity.py','README.md','PROTOCOL.md']:
        copy(HERE/name,('PORTABLE_PROTOCOL.md' if name=='PROTOCOL.md' else name),sha(HERE/name))
    arrays={};objects=[]
    for name in columns:
        if f[name].dtype==object:
            objects.append(name);arrays[name]=f[name].astype(str).to_numpy(dtype=str);arrays[name+'__null']=f[name].isna().to_numpy()
        else:arrays[name]=f[name].to_numpy()
    save_npz(DEST/'scoring_inputs.npz',**arrays)
    dump(DEST/'scoring_schema.json',{'columns':columns,'object_columns':objects,
        'provenance':'Authenticated original pre-assessment CSV-overlay frame, no re-fitting; labels included privately',
        'source_assessment_sha256':ASSESS,'rows':len(f)})
    for context in freeze['contexts']:
        for folder,prefix in [('calibrators','calibrator'),('roles','membership')]:
            copy(P/'results'/f'{prefix}_{context}.json',f'{folder}/{context}.json')
        source=A/'results'/f'calibration_{context}.npz';z=npz(source,af['artifact_sha256'][str(source)])
        keys=['indices','nf2_row_id','group','BASE_CD','MEAS_CD','CORE_CD_capped']
        (DEST/'calibration').mkdir(exist_ok=True)
        save_npz(DEST/'calibration'/f'{context}.npz',**{k:z[k] for k in keys},gate=np.ones(len(z['indices']),bool))
        provenance[f'calibration/{context}.npz']={'source_id':str(source.relative_to(PROJECT)),
            'source_sha256':af['artifact_sha256'][str(source)],'transformation':'Selected safe arrays; all historical gates verified true by producer'}
    for context in freeze['contexts']+['SG_exposed','W_new_challenge']:
        source=P/('exposed_results' if context in ['SG_exposed','W_new_challenge'] else 'results')/f'inference_{context}.npz'
        copy(source,f'native/{context}.npz')
    for source in sorted((P/'assessment').glob('*.csv')):
        if source.name!='all_row_predictions.csv':copy(source,'expected/'+source.name)
    # Required functions copied verbatim; no project import/loader retained.
    sources=[(PROJECT/'model_development_20260907_geometry_frontier/assess_frontier.py',
              ['panel_metrics','bootstrap','group_metrics','harms','identity_guard','decisions','summary']),
             (PROJECT/'model_development_20260907_selective/assess_selective.py',['make_panels']),
             (P/'assess_experiment.py',['extra_metrics'])]
    header='import numpy as np\nimport pandas as pd\nimport incremental_harm as policy\n'
    constants={'LABELS':labels,'CANDIDATES':[labels[0]],'CONTROLS':labels[1:],
        'REFERENCES':['unpenalized_transfer','half_strength','proper_capped_half'],
        'PERFORMANCE':'unpenalized_transfer','ROBUSTNESS':'half_strength',
        'ASSIGNMENTS':[20260906,20260908],'EXTERNAL':['SG_exposed','W_new_challenge'],
        'FIELDS':['xlarge_CD_improvement_percent','mean8_CD_improvement_percent'],
        'BASELINES':['xlarge_CD','mean8_CD'],'ROW_TOL':1e-12,'PP_TOL':1e-6,'N_BOOTSTRAP':20000,'SEED':2026090831}
    header+='\n'.join(k+'='+repr(v) for k,v in constants.items())+'\n\n'
    parts=[]
    for source,names in sources:
        text=checked(source,witnesses[str(source)]).decode();tree=ast.parse(text)
        for name in names:
            node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            segment=ast.get_source_segment(text,node);assert ast.dump(ast.parse(segment).body[0])==ast.dump(node)
            parts.append(segment)
            ast_witness.append({'function':name,'source_id':str(source.relative_to(PROJECT)),
                'source_sha256':witnesses[str(source)],'function_source_sha256':hashlib.sha256(segment.encode()).hexdigest(),
                'ast_sha256':hashlib.sha256(ast.dump(node).encode()).hexdigest(),'unchanged_function_AST':True})
    (DEST/'metrics.py').write_text(header+'\n\n'.join(parts)+'\n')
    dump(DEST/'SOURCE_WITNESS.json',{'members':provenance,'extracted_functions':ast_witness,'constants':constants,
        'proposal_sha256':freeze['proposal_sha256'],'calibration_freeze_sha256':FROZEN,
        'producer_completion_sha256':COMPLETE,'assessment_sha256':ASSESS})
    manifest={'schema':'private_incremental_replay_v1','private_contains_experimental_labels':True,
        'contexts':freeze['contexts'],'native_contexts':freeze['contexts']+['SG_exposed','W_new_challenge'],
        'candidates':[labels[0]],'controls':labels[1:],'new_core_fits':0,
        'members':{str(p.relative_to(DEST)):sha(p) for p in sorted(DEST.rglob('*')) if p.is_file()}}
    dump(DEST/'manifest.json',manifest)
    archive=HERE/'incremental_harm_private.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(DEST.rglob('*')):
            if p.is_file():z.write(p,str(Path(DEST.name)/p.relative_to(DEST)))
    record={'archive':archive.name,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,
        'manifest_sha256':sha(DEST/'manifest.json'),'payload_members':len(manifest['members']),
        'builder_sha256':sha(__file__),'source_witness_sha256':sha(DEST/'SOURCE_WITNESS.json')}
    dump(HERE/'EXPORT.json',record);print(json.dumps(record,indent=2))


if __name__=='__main__':main()
