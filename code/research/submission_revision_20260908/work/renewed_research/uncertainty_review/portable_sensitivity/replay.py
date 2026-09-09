"""Portable frozen-label sensitivity replay: inspect code and trust manifest first."""
from pathlib import Path,PurePosixPath
import argparse,ast,hashlib,json,platform,sys,time,traceback
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
EXPECTED_SCHEMA='private_sensitivity_v1'
PROCEDURES=['unpenalized_transfer','half_strength','mean8_CD','xlarge_CD']
BASELINES=['mean8_CD','xlarge_CD']
COUNTS=[0,.25,.5,1,2,5,10,20]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise ValueError('Duplicate JSON key')
        d[k]=v
    return d
def safe(n):
    if not isinstance(n,str):raise ValueError('Invalid path')
    p=PurePosixPath(n)
    if not n or p.is_absolute() or '..' in p.parts or str(p)!=n or '\\' in n or ':' in n:
        raise ValueError('Unsafe relative path')
    return p
def authenticate(root,digest):
    root=Path(root)
    if root.is_symlink():raise ValueError('Symlink root')
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Trusted SHA256 required')
    if (root/'manifest.json').is_symlink() or sha(root/'manifest.json')!=digest:raise ValueError('Manifest authentication failed')
    m=json.loads((root/'manifest.json').read_text(),object_pairs_hook=unique)
    if m['schema']!=EXPECTED_SCHEMA:raise ValueError('Unknown schema')
    actual=set()
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('Symlink forbidden')
        if p.is_file():actual.add(p.relative_to(root).as_posix())
        elif not p.is_dir():raise ValueError('Nonregular entry')
    if actual!=set(m['files'])|{'manifest.json'}:raise ValueError('Missing or unexpected payload')
    for n,h in m['files'].items():
        safe(n)
        if sha(root/n)!=h:raise ValueError('Payload mismatch '+n)
    return m

def ast_equivalence(root):
    old=ast.parse((root/'witness/production_sensitivity.py').read_text())
    new=ast.parse((root/'sensitivity.py').read_text())
    names={'arrays','margin','RowBox','ShiftCurve','SharedShifts','first_zero'}
    def nodes(tree):return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names}
    if nodes(old)!=nodes(new) or set(nodes(new))!=names:raise ValueError('Engine AST mismatch')
    for name in ['ATOL_CD','RADIUS_TOL_CD','LD']:
        def value(tree):return [ast.dump(n.value,include_attributes=False) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
        if value(old)!=value(new):raise ValueError('Engine constant mismatch')

def compare(actual,path):
    expected=pd.read_csv(path,float_precision='round_trip')
    if list(actual.columns)!=list(expected.columns) or actual.shape!=expected.shape:raise ValueError('Table shape mismatch')
    maximum=0.
    for col in actual:
        a=actual[col];b=expected[col]
        if pd.api.types.is_numeric_dtype(a) and not pd.api.types.is_bool_dtype(a):
            x=a.to_numpy(dtype=float);y=b.to_numpy(dtype=float)
            if not np.array_equal(np.isnan(x),np.isnan(y)):raise ValueError('Missing-value mismatch '+col)
            finite=~np.isnan(x)
            if not np.isfinite(x[finite]).all() or not np.isfinite(y[finite]).all():raise ValueError('Nonfinite '+col)
            err=np.max(abs(x[finite]-y[finite]),initial=0)
            if err>1e-13:raise ValueError('Numeric mismatch '+col)
            maximum=max(maximum,float(err))
        elif not a.fillna('<missing>').equals(b.fillna('<missing>')):raise ValueError('Exact field mismatch '+col)
    return maximum

def run(output,digest):
    if not __debug__:raise ValueError('Do not run with -O')
    output=Path(output)
    if output.exists():raise FileExistsError('Existing attempt preserved')
    if output.resolve().is_relative_to(HERE.resolve()):raise ValueError('Output must be outside immutable bundle')
    m=authenticate(HERE,digest);ast_equivalence(HERE)
    if np.__version__!='2.3.5' or pd.__version__!='2.2.3':raise ValueError('Use recorded NumPy2.3.5/pandas2.2.3')
    # The authenticated module has mathematical definitions only, no data loader or main.
    import sensitivity as engine
    with np.load(HERE/'data.npz',allow_pickle=False) as f:
        data={k:f[k] for k in f.files}
    roles=json.loads((HERE/'panels.json').read_text(),object_pairs_hook=unique)
    n=len(data['y']);assert n==29856
    assert data['predictions'].shape==(n,4)
    assert np.isfinite(data['y']).all() and (data['y']>=0).all()
    assert np.isfinite(data['predictions']).all() and (data['predictions']>0).all()
    for k in ['bundle','source','split','row_id']:assert data[k].shape==(n,)
    assert len(roles)==31
    output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    try:
        grid=[];radii=[];panels=[]
        for panel,indices in roles.items():
            ix=np.asarray(indices,dtype=np.int64)
            assert ix.ndim==1 and len(ix)==len(set(indices)) and (ix>=0).all() and (ix<n).all()
            bnames=data['bundle'][ix];sources=data['source'][ix]
            names,inv,counts=np.unique(bnames,return_inverse=True,return_counts=True)
            size=len(ix);y=data['y'][ix]
            panels.append(dict(panel=panel,rows=size,bundles=len(names),source_blocks=len(np.unique(sources))))
            for procedure in PROCEDURES:
                c=data['predictions'][ix,PROCEDURES.index(procedure)]
                for baseline in BASELINES:
                    b=data['predictions'][ix,PROCEDURES.index(baseline)]
                    for weighting in ['row','equal_bundle']:
                        w=np.full(size,1/size) if weighting=='row' else 1/(len(names)*counts[inv])
                        np.testing.assert_allclose(w.sum(),1,rtol=0,atol=1e-14)
                        for r in [0.,.09]:
                            common=dict(panel=panel,procedure=procedure,baseline=baseline,weighting=weighting,target_fraction=r,rows=size,bundles=len(names))
                            box=engine.RowBox(b,c,y,w,r)
                            models={'row_box':box,'source_shift':engine.SharedShifts(b,c,y,w,r,sources),'bundle_shift':engine.SharedShifts(b,c,y,w,r,bnames)}
                            for model_name,model in models.items():
                                radii.append(common|dict(uncertainty_model=model_name)|engine.first_zero(model,r))
                                for e in COUNTS:
                                    eps=e*1e-4;lo,hi=model.bounds(eps);minimum=box.minimum_baseline_mae(eps)
                                    grid.append(common|dict(uncertainty_model=model_name,epsilon_drag_counts=e,epsilon_CD=eps,
                                        lower_margin_CD=lo,upper_margin_CD=hi,observed_margin_CD=box.observed,
                                        box_minimum_baseline_mae_CD=minimum,percentage_defined_everywhere_sufficient=minimum>0,strict_positive_margin=lo>0))
            print('replayed',panel,flush=True)
        assert len(grid)==23808 and len(radii)==2976
        diffs={}
        for name,records in [('grid',grid),('radii',radii),('panels',panels)]:
            table=pd.DataFrame(records)
            diffs[name]=compare(table,HERE/'expected'/f'{name}.csv')
            table.to_csv(output/f'{name}.csv',index=False)
        authenticate(HERE,digest)
        result=dict(status='PASS',grid_rows=len(grid),radius_rows=len(radii),panels=31,panel_baseline_pairs_per_procedure=62,
            maximum_numeric_differences=diffs,exact_table_hash_match={name:sha(output/f'{name}.csv')==sha(HERE/'expected'/f'{name}.csv') for name in ['grid','radii','panels']},
            manifest_sha256=digest,python=sys.version,numpy=np.__version__,pandas=pd.__version__,platform=platform.platform(),
            seconds=time.monotonic()-started,new_fits=0,new_measurements=0,independent_environment=False,
            output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()})
        (output/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    except Exception:
        (output/'failure.txt').write_text(traceback.format_exc());raise

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['verify','reproduce']);ap.add_argument('--manifest-sha256',required=True);ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.mode=='verify':
        auth=authenticate(HERE,args.manifest_sha256);ast_equivalence(HERE);print(json.dumps({'status':'PASS','files':len(auth['files']),'scientific_execution':False}))
    else:
        if args.output is None:ap.error('--output is required for reproduce')
        run(args.output,args.manifest_sha256)
