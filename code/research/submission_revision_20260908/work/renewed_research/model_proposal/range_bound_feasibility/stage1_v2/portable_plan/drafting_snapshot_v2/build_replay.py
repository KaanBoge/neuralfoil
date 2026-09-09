"""Approved-export-only builder; no project model/array work at import."""
from pathlib import Path
import argparse,ast,hashlib,io,json,sys,types,time,signal
import numpy as np
import pandas as pd
import integrity
import frame_codec

HERE=Path(__file__).resolve().parent;STUDY=HERE.parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')

def checked(path,pin):
    b=Path(path).read_bytes()
    if integrity.sha(b)!=pin:raise ValueError('input hash mismatch: '+str(path))
    return b
def npzbytes(values):
    out=io.BytesIO();np.savez_compressed(out,**values);return out.getvalue()
def load_npz(raw):
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def module(name,raw,filename):
    m=types.ModuleType(name);m.__file__=str(filename);sys.modules[name]=m
    exec(compile(raw,str(filename),'exec'),m.__dict__);return m
def jsonbytes(v):return json.dumps(v,indent=2,allow_nan=False).encode()+b'\n'

def extract_functions(raw,names,witness,source_id,renames=None):
    text=raw.decode();tree=ast.parse(text);parts=[]
    for name in names:
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        before=ast.dump(node,include_attributes=False)
        if renames and name in renames:
            node.name=renames[name]
            node.body[0]=ast.Expr(ast.Constant('Production exact arithmetic; packaged approved study replay.'))
            segment=ast.unparse(ast.fix_missing_locations(node))
        else:segment=ast.get_source_segment(text,node)
        witness.append({'source':source_id,'source_sha256':integrity.sha(raw),'function':name,
            'original_AST_sha256':integrity.sha(before.encode()),'packaged_AST_sha256':integrity.sha(ast.dump(ast.parse(segment).body[0],include_attributes=False).encode()),
            'permitted_adapter':'name/docstring only' if renames and name in renames else 'unchanged AST'})
        parts.append(segment)
    return '\n\n'.join(parts)+'\n'

def authorize(args):
    frozen=json.loads(checked(HERE/'REGISTRY_v2.json',args.registry_sha256))
    for rel,h in frozen['implementation_sha256'].items():checked(HERE/rel,h)
    approval=json.loads(checked(args.approval,args.approval_sha256))
    if approval.get('registry_sha256')!=args.registry_sha256 or 'export' not in approval.get('authorized_phases',[]):raise ValueError('export approval required')
    return frozen

def build(args):
    frozen=authorize(args);payload={};witness=[];access=[]
    integrity.new_target(args.output)
    receipt_path=integrity.new_target(str(args.output)+'.receipt.json')
    def read(path):
        path=Path(path);raw=checked(path,frozen['inputs'][str(path)])
        access.append(str(path));return raw
    def put(name,raw):
        if name in payload:raise ValueError('duplicate export member')
        payload[name]=raw
        if sum(map(len,payload.values()))>integrity.MAX_BYTES:raise ValueError('256MiB export cap')
    # Restore modules from exact authenticated sources, not a mutable project import graph.
    qpath=STUDY.parent/'qualified_numerics.py';qraw=read(qpath)
    nraw=read(STUDY/'numerics.py');rraw=read(STUDY/'run_stage1.py');araw=read(STUDY/'assess_stage1.py')
    evraw=read(STUDY/'evaluator.py')
    module('numerics',nraw,STUDY/'numerics.py');module('evaluator',evraw,STUDY/'evaluator.py')
    run=module('run_stage1',rraw,STUDY/'run_stage1.py')
    run._EXECUTION={'implementation_sha256':frozen['study_implementation_sha256']}
    assess=module('assess_stage1',araw,STUDY/'assess_stage1.py')
    # Exact prefix of original assess(): stop before any metric computation or file output.
    tree=ast.parse(araw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='assess')
    prefix=[]
    for node in fn.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id=='metrics' and t.attr=='CANDIDATES' for t in node.targets):break
        prefix.append(node)
    if not prefix:raise ValueError('preassessment prefix not found')
    prefix_witness=integrity.sha(ast.dump(ast.Module(body=prefix,type_ignores=[]),include_attributes=False).encode())
    fn.name='capture_preassessment';fn.body=prefix+[ast.Return(ast.Tuple(elts=[ast.Name(id=k,ctx=ast.Load()) for k in ['frame','panels','metrics']],ctx=ast.Load()))]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<original preassessment prefix>','exec'),assess.__dict__)
    # Reauthenticate every registered input before invoking the authenticated original prefix.
    for path,h in frozen['inputs'].items():checked(path,h)
    frame,panels,metrics=assess.capture_preassessment(None)
    if len(frame)!=29856 or len(panels)!=31:raise ValueError('full typed frame inventory')
    arr,schema=frame_codec.pack(frame)
    pd.testing.assert_frame_equal(frame_codec.unpack(arr,schema),frame,check_exact=True)
    put('scoring/frame.npz',npzbytes(arr));put('scoring/schema.json',jsonbytes(schema))
    put('scoring/panels.json',jsonbytes({k:list(map(int,v)) for k,v in panels.items()}))
    scalars=json.loads(read(STUDY/'results/freeze.json'));pred=json.loads(read(STUDY/'predictions/complete.json'))
    contexts=scalars['contexts'];native=contexts+list(run.EXTERNAL)
    master=None;master_base=None;feature_maps={}
    if args.include_features:
        rows=[];bases=[]
        for context in ['final',*run.EXTERNAL]:
            path=run.A/('exposed_results' if context in run.EXTERNAL else 'results')/(f'{context}_inference.npz' if context in run.EXTERNAL else 'inference_final.npz')
            z=load_npz(read(path))
            np.testing.assert_array_equal(z['indices'],np.arange(len(z['BASE_CD'])))
            rows.append(z['X62']);bases.append(z['BASE_CD'])
        master=np.concatenate(rows)
        if master.shape!=(8868,62):raise ValueError('master feature shape')
        master_base=np.concatenate(bases)
        put('features/X62.npz',npzbytes({'X62':master,'BASE_CD':master_base}))
    for context in contexts:
        original=load_npz(read(run.A/'results'/f'calibration_{context}.npz'))
        reference=load_npz(read(STUDY/'precalibration'/f'calibration_reference_{context}.npz'))
        np.testing.assert_array_equal(original['indices'],reference['indices'])
        z={k:reference[k] for k in ['indices','BASE_CD','core','anchor','gate']}
        z.update({k:original[k] for k in ['nf2_row_id','group','MEAS_CD']})
        put(f'calibration/{context}.npz',npzbytes(z))
        put(f'roles/{context}.json',read(STUDY/'results'/f'membership_{context}.json'))
        for label in run.LABELS:put(f'scalars/{label}_{context}.json',read(STUDY/'results'/f'calibrator_{label}_{context}.json'))
        if master is not None:
            ix=original['indices'];np.testing.assert_array_equal(master[ix],original['X62']);np.testing.assert_array_equal(master_base[ix],original['BASE_CD']);feature_maps['calibration/'+context]=list(map(int,ix))
    for context in native:
        put(f'native/{context}.npz',read(STUDY/'predictions'/f'inference_{context}.npz'))
        if master is not None:
            path=run.A/('exposed_results' if context in run.EXTERNAL else 'results')/(f'{context}_inference.npz' if context in run.EXTERNAL else f'inference_{context}.npz')
            z=load_npz(read(path));ix=z['indices']+(8371 if context=='SG_exposed' else 8613 if context=='W_new_challenge' else 0)
            np.testing.assert_array_equal(master[ix],z['X62']);np.testing.assert_array_equal(master_base[ix],z['BASE_CD']);feature_maps['native/'+context]=list(map(int,ix))
    if master is not None:put('features/maps.json',jsonbytes(feature_maps))
    for source_id,record in frozen['evidence'].items():put(source_id,read(record))
    for name in json.loads(read(STUDY/'assessment/report.json'))['output_sha256']:put('expected/'+name,read(STUDY/'assessment'/name))
    # Standalone functions: no original loader, model fit, or project paths at replay.
    put('code/qualified_numerics.py',qraw);put('code/evaluator.py',evraw)
    policy='import qualified_numerics as q\n'
    policy+=extract_functions(qraw,['exact_group_means','synthetic_confidence'],witness,'qualified_numerics.py',
        {'exact_group_means':'group_means_exact','synthetic_confidence':'calibrate_exact_groups'})
    # The two renamed bodies retain their original global arithmetic namespace.
    policy='from qualified_numerics import *\n'+policy
    policy+=extract_functions(nraw,['fit_scalar','predictions'],witness,'numerics.py')
    put('code/policy.py',policy.encode())
    codec='from fractions import Fraction as F\nfrom pathlib import Path\nimport json\n'+extract_functions(rraw,['encode','fraction','write_json'],witness,'run_stage1.py')
    put('code/codec.py',codec.encode())
    constants={'LABELS':assess.LABELS,'CANDIDATES':list(run.LABELS),'CONTROLS':assess.CONTROLS,
        'REFERENCES':['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half',run.LABELS[1]],
        'PERFORMANCE':'unpenalized_transfer','ROBUSTNESS':'half_strength','ASSIGNMENTS':[20260906,20260908],
        'EXTERNAL':list(run.EXTERNAL),'FIELDS':['xlarge_CD_improvement_percent','mean8_CD_improvement_percent'],
        'BASELINES':['xlarge_CD','mean8_CD'],'ROW_TOL':1e-12,'PP_TOL':1e-6,'N_BOOTSTRAP':20000,'SEED':2026090831}
    header='import numpy as np\nimport pandas as pd\nfrom types import SimpleNamespace\n'
    header+='\n'.join(k+'='+repr(v) for k,v in constants.items())+'\nrun=SimpleNamespace(LABELS=CANDIDATES,EXTERNAL=EXTERNAL)\n'
    mpath=PROJECT/'model_development_20260907_geometry_frontier/assess_frontier.py'
    header+=extract_functions(read(mpath),['panel_metrics','bootstrap','group_metrics','harms','identity_guard','decisions','summary'],witness,'assess_frontier.py')
    header+=extract_functions(araw,['extras'],witness,'assess_stage1.py')
    put('code/metrics.py',header.encode())
    for name in ['replay.py','integrity.py','frame_codec.py']:put('code/'+name,checked(HERE/name,frozen['implementation_sha256'][name]))
    put('code/test_integrity.py',checked(HERE/'test_integrity.py',frozen['implementation_sha256']['test_integrity.py']))
    put('README.md',checked(HERE/'PACKAGE_README.md',frozen['implementation_sha256']['PACKAGE_README.md']))
    put('PRIVATE_ACCESS.md',b'Private verification material containing experimental labels. No public release or onward-transfer permission is established. Human release approval remains false. Source rights and recipient permissions require separate author review.\n')
    put('SOURCE_WITNESS.json',jsonbytes({'functions':witness,'original_preassessment_prefix_AST_sha256':prefix_witness,'inputs':frozen['inputs'],'accessed':access}))
    put('inventory.json',jsonbytes({'contexts':contexts,'native_contexts':native,'labels':list(run.LABELS),
        'features_included':bool(master is not None),'new_fits':0,'panels':31,'rows':29856}))
    result=integrity.build_private_zip(payload,args.output)
    result.update(registry_sha256=args.registry_sha256,feature_parity_payload=args.include_features)
    with receipt_path.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry-sha256',required=True);p.add_argument('--approval',required=True)
    p.add_argument('--approval-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--include-features',action='store_true')
    a=p.parse_args()
    if __import__('os').environ.get('OMP_NUM_THREADS')!='1' or __import__('os').environ.get('OPENBLAS_NUM_THREADS')!='1':raise ValueError('single thread required')
    def timeout(*unused):raise TimeoutError('900-second export guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900);build(a)
