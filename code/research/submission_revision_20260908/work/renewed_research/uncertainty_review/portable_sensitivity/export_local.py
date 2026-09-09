"""Author-side export from authenticated originals; not a portable runtime dependency."""
from pathlib import Path
import ast,hashlib,json,shutil,sys,zipfile
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[4]
REV=PROJECT/'submission_revision_20260908';STUDY=HERE.parents[1]/'measurement_sensitivity'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    bundle=HERE/'bundle';archive=HERE/'portable_sensitivity_private.zip'
    if bundle.exists() or archive.exists():raise FileExistsError('Preserve existing export')
    manifest_path=STUDY/'attempt_1/manifest.json'
    assert sha(manifest_path)=='5afa8ac4d181ec654c7802c917e6098039e533914a8ca533d167b81177cb934f'
    manifest=json.loads(manifest_path.read_text());pins=manifest['input_sha256']
    for p,h in pins.items():assert sha(p)==h,p
    for n,h in manifest['output_sha256'].items():assert sha(STUDY/'attempt_1'/n)==h,n
    own={name:sha(HERE/name) for name in ['replay.py','test_portable.py','README.md','export_local.py']}
    source=STUDY/'sensitivity.py';text=source.read_text();tree=ast.parse(text);lines=text.splitlines(keepends=True)
    definitions={'arrays','margin','RowBox','ShiftCurve','SharedShifts','first_zero'}
    constants={'ATOL_CD','RADIUS_TOL_CD','LD'}
    selected=[]
    for node in tree.body:
        keep=isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in definitions
        keep|=isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in node.targets)
        if keep:selected.append(''.join(lines[node.lineno-1:node.end_lineno]))
    engine='"""Verbatim AST-equivalent frozen mathematical engine; no loader or scientific main."""\nimport numpy as np\n\n'+'\n\n'.join(selected)
    # Author-side panel reconstruction is independently implemented and has no side effects.
    sys.path.insert(0,str(HERE.parent));from audit_empirical import panel_map
    frame=pd.read_csv(PROJECT/'model_development_20260908_adaptive_scale/assessment/all_row_predictions.csv',low_memory=False)
    indices=panel_map(frame);expected_panels=pd.read_csv(STUDY/'attempt_1/panels.csv')
    indices={name:indices[name] for name in expected_panels.panel}
    for row in expected_panels.itertuples():assert len(indices[row.panel])==row.rows
    ext=frame.split.isin(['SG_exposed','W_new_challenge'])
    bundle_names=frame.group.where(~ext,frame.configuration).astype(str).to_numpy(dtype=str)
    sources=frame.source.where(~ext,frame.split).astype(str).to_numpy(dtype=str)
    for seed in [20260906,20260908]:
        f=frame.iloc[indices[f'history_{seed}_pooled']]
        assert len(f)==f.nf2_row_id.nunique()==8371 and f.group.nunique()==93
    bundle.mkdir();(bundle/'witness').mkdir();(bundle/'expected').mkdir()
    for name in ['replay.py','test_portable.py','README.md']:shutil.copyfile(HERE/name,bundle/name)
    shutil.copyfile(STUDY/'test_sensitivity.py',bundle/'test_sensitivity.py')
    shutil.copyfile(source,bundle/'witness/production_sensitivity.py')
    shutil.copyfile(STUDY/'PROTOCOL.md',bundle/'witness/PROTOCOL.md')
    shutil.copyfile(manifest_path,bundle/'witness/production_manifest.json')
    (bundle/'sensitivity.py').write_text(engine)
    for name in ['grid','radii','panels']:shutil.copyfile(STUDY/f'attempt_1/{name}.csv',bundle/f'expected/{name}.csv')
    np.savez_compressed(bundle/'data.npz',y=frame.measured_CD.to_numpy(),
        predictions=frame[['unpenalized_transfer','half_strength','mean8_CD','xlarge_CD']].to_numpy(),
        bundle=bundle_names,source=sources,split=frame.split.to_numpy(dtype=str),row_id=frame.nf2_row_id.astype(str).to_numpy(dtype=str))
    (bundle/'panels.json').write_text(json.dumps({k:v.tolist() for k,v in indices.items()},separators=(',',':'))+'\n')
    provenance=dict(source_manifest_sha256=sha(manifest_path),source_pins={str(Path(k).relative_to(PROJECT)):v for k,v in pins.items()},
        exporter_sha256=own['export_local.py'],role='retrospective_fixed_prediction_label_sensitivity',raw_inputs_not_rederived=True,
        engine_definitions=sorted(definitions),engine_constants=sorted(constants),copied_expectations=manifest['output_sha256'],source_rows=29856)
    (bundle/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (bundle/'requirements-observed.txt').write_text('numpy==2.3.5\npandas==2.2.3\n')
    for p,h in pins.items():assert sha(p)==h,p
    for n,h in own.items():assert sha(HERE/n)==h,n
    files={p.relative_to(bundle).as_posix():sha(p) for p in sorted(bundle.rglob('*')) if p.is_file()}
    (bundle/'manifest.json').write_text(json.dumps(dict(schema='private_sensitivity_v1',private_data=True,not_rights_clearance=True,files=files),indent=2)+'\n')
    import replay
    digest=sha(bundle/'manifest.json');replay.authenticate(bundle,digest);replay.ast_equivalence(bundle)
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,'portable_sensitivity/'+p.relative_to(bundle).as_posix())
    record=dict(status='EXPORTED_VERIFICATION_PENDING',manifest_sha256=digest,archive_sha256=sha(archive),
        archive_bytes=archive.stat().st_size,payload_files=len(files),safe_data_bytes=(bundle/'data.npz').stat().st_size,
        source_manifest_sha256=sha(manifest_path),original_files_unchanged=True)
    (HERE/'export_verified.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))

if __name__=='__main__':main()
