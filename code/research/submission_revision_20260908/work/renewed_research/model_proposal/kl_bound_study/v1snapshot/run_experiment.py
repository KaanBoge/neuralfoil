"""Fixed KL study runner. No real phase is authorized by source preparation."""
import argparse,hashlib,importlib.util,io,json,os,signal,sys,time,types,datetime
from pathlib import Path
import numpy as np
import pandas as pd
from inputs import Inputs,NEW_LABELS,OLD_LABELS,EXTERNAL,ZIP_SHA,MANIFEST_SHA,sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ARCHIVE=HERE.parent/'range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
CONFIDENCE=ROOT/'kl_confidence_production/confidence.py'
CONFIDENCE_SHA='03c41a6aa79f44bd04fe374953c560db029d2f4a98f8cd1de552ed35657d9ad9'
KEYS=['indices','BASE_CD','core','anchor','gate']

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def checked(path,pin):
    raw=Path(path).read_bytes()
    if sha(raw)!=pin:raise ValueError('hash mismatch '+str(path))
    return raw
def module(name,raw,path=None):
    m=types.ModuleType(name);m.__file__=str(path or name);sys.modules[name]=m
    exec(compile(raw,m.__file__,'exec'),m.__dict__);return m
def codec_from_source():
    # Source-only bootstrap of the unchanged canonical codec; no scientific inputs.
    import ast
    path=HERE.parent/'range_bound_feasibility/stage1_v2/run_stage1.py'
    raw=checked(path,'5cb5c4897209465f2526099aae094ddce0fc72b50446f071e955520d97568ec1')
    tree=ast.parse(raw);names=['encode','fraction','write_json']
    selected=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names]
    prefix='from fractions import Fraction as F\nfrom pathlib import Path\nimport json\n'
    return module('kl_codec',prefix+'\n'.join(ast.unparse(x) for x in selected))
def verify_roles(r):
    for a,b in [('proper_groups','calibration_groups'),('proper_groups','test_groups'),('calibration_groups','test_groups')]:
        if set(r[a])&set(r[b]):raise ValueError('role groups overlap')
    for key in ['proper_indices','calibration_indices','test_indices']:
        if len(set(r[key]))!=len(r[key]):raise ValueError('duplicate role indices')
    for a,b in [('proper_indices','calibration_indices'),('proper_indices','test_indices'),('calibration_indices','test_indices')]:
        if set(r[a])&set(r[b]):raise ValueError('row roles overlap')
def schema(z):
    n=len(z['BASE_CD'])
    if any(z[k].shape!=(n,) for k in KEYS):raise ValueError('native vector alignment')
    if z['gate'].dtype!=bool or z['indices'].dtype.kind not in 'iu':raise ValueError('gate/index dtype')
    for k in ['BASE_CD','core','anchor']:
        if z[k].dtype!=np.float64 or not np.isfinite(z[k]).all() or (z[k]<=0).any():raise ValueError('positive finite float64')
    if len(set(z['indices']))!=n:raise ValueError('duplicate indices')
    for k in ['core','anchor']:np.testing.assert_array_equal(z[k][~z['gate']],z['BASE_CD'][~z['gate']])
def authorize(args):
    freeze=json.loads(checked(HERE/'IMPLEMENTATION_FREEZE.json',args.implementation_sha256))
    for name,h in freeze['source_sha256'].items():checked(HERE/name,h)
    for name,h in freeze['external_source_sha256'].items():checked(name,h)
    approval=json.loads(checked(args.approval,args.approval_sha256))
    if approval.get('implementation_sha256')!=args.implementation_sha256 or args.phase not in approval.get('authorized_phases',[]):raise ValueError('phase approval')
    return freeze,approval
def predecessor(phase,approval,implementation):
    required={'preflight':None,'calibrate':'preflight','score':'calibrate','assess':'score'}[phase]
    if required is None:return
    p=HERE/required/'COMPLETE.json'
    record=json.loads(checked(p,approval['predecessor_sha256']))
    if record['phase']!=required or record['implementation_sha256']!=implementation:raise ValueError('predecessor identity')
    for name,h in record['outputs'].items():checked(HERE/required/name,h)
    # Recursively bind the earlier complete-chain bytes and outputs, not just immediate phase.
    if required!='preflight':predecessor(required,{'predecessor_sha256':record['predecessor_sha256']},implementation)
def npz(path,z):
    with path.open('xb') as f:np.savez_compressed(f,**z)
def matched(actual,old,codec):
    for k in ['upper','bound','exact_mean']:
        expected=codec.fraction(old[k]) if old[k] is not None else None
        if actual[k]!=expected:raise ValueError('matched scalar '+k)
    for k in ['t','groups','rows']:
        if actual[k]!=old[k]:raise ValueError('matched scalar '+k)
    if actual['group_means']!={k:codec.fraction(v) for k,v in old['group_means'].items()}:raise ValueError('matched groups')

def preflight(inputs,out,codec,c):
    cert=inputs.metadata('certificates/STAGE0_CERTIFICATE.json')
    bounds={x['context']:x['B_structural'] for x in cert['records']}
    if set(bounds)!=set(inputs.contexts):raise ValueError('certificate contexts')
    for context in inputs.contexts:
        r=inputs.metadata('roles/'+context+'.json');verify_roles(r)
        z=inputs.array('calibration/'+context+'.npz',KEYS+['nf2_row_id','group']);schema(z)
        np.testing.assert_array_equal(z['indices'],r['calibration_indices'])
        np.testing.assert_array_equal(z['nf2_row_id'],r['calibration_nf2_row_ids'])
        if set(z['group'].astype(str))!=set(r['calibration_groups']):raise ValueError('calibration identities')
    for context in inputs.native:
        z=inputs.array('native/'+context+'.npz',KEYS);schema(z)
        if context not in EXTERNAL+['final']:
            r=inputs.metadata('roles/'+context+'.json');np.testing.assert_array_equal(z['indices'],r['test_indices'])
    codec.write_json(out/'REFERENCE_PASS.json',{'contexts':inputs.contexts,'native_contexts':inputs.native,
        'scope':'Saved native references; no new feature/tree execution','B_structural':bounds,
        'B_generic':c.n.q.GENERIC_BOUND,'target_members_materialized':False})

def calibrate(inputs,out,codec,c):
    cert=inputs.metadata('certificates/STAGE0_CERTIFICATE.json')
    bounds={x['context']:codec.fraction(x['B_structural']) for x in cert['records']}
    for context in inputs.contexts:
        role=inputs.metadata('roles/'+context+'.json');verify_roles(role)
        z=inputs.array('calibration/'+context+'.npz',KEYS+['MEAS_CD','group','nf2_row_id']);schema(z)
        np.testing.assert_array_equal(z['indices'],role['calibration_indices'])
        np.testing.assert_array_equal(z['nf2_row_id'],role['calibration_nf2_row_ids'])
        for new,old,B in zip(NEW_LABELS,OLD_LABELS,[bounds[context],c.n.q.GENERIC_BOUND]):
            old_record=inputs.metadata('scalars/'+old+'_'+context+'.json')
            args=(z['BASE_CD'],z['core'],z['anchor'],z['MEAS_CD'],z['group'].astype(str),B)
            h=c.n.fit_scalar(*args);matched(h,old_record,codec)
            result=c.fit_kl_scalar(*args)
            if result['matched_hoeffding_upper']!=h['upper'] or result['matched_hoeffding_t']!=h['t']:raise ValueError('KL control disagreement')
            result.update(candidate=new,context=context)
            codec.write_json(out/f'calibrator_{new}_{context}.json',result)
        codec.write_json(out/f'membership_{context}.json',role)

def score(inputs,out,codec,c):
    for context in inputs.native:
        z=inputs.array('native/'+context+'.npz',KEYS);schema(z)
        scalar_context='final' if context in EXTERNAL else context
        table={'indices':z['indices'],'BASE_CD':z['BASE_CD'],'qualified_gate':z['gate']}
        for label in NEW_LABELS:
            model=json.loads((HERE/'calibrate'/f'calibrator_{label}_{scalar_context}.json').read_bytes())
            p,e=c.n.predictions(model,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
            for b,core,h,g,v in zip(z['BASE_CD'],z['core'],z['anchor'],z['gate'],p):
                if g and core!=h:
                    f=(c.n.q.rat(v)-c.n.q.rat(h))/(c.n.q.rat(core)-c.n.q.rat(h))
                    if not 0<=f<=c.n.q.rat(model['t']):raise ValueError('effective interpolation')
                elif v!=b and not g:raise ValueError('fallback')
            table.update({label:p,label+'__effective_fraction':e,label+'__strength':np.where(z['gate'],.5+.5*model['t'],0.),
                label+'__intervened':abs(p-z['anchor'])>1e-12})
        npz(out/f'inference_{context}.npz',{**z,**table})
        if context!='final':
            if context not in EXTERNAL:table['nf2_row_id']=inputs.metadata('roles/'+context+'.json')['test_nf2_row_ids']
            pd.DataFrame(table).to_csv(out/f'predictions_{context}.csv',index=False,mode='x')

def assess(inputs,out,codec,c):
    q=module('qualified_numerics',inputs.code('code/qualified_numerics.py'))
    fc=module('kl_frame',inputs.code('code/frame_codec.py'))
    m=module('kl_metrics',inputs.code('code/metrics.py'))
    frame=fc.unpack(inputs.scoring_arrays(),inputs.metadata('scoring/schema.json'))
    original=frame.copy(deep=True);panels={k:np.array(v,int) for k,v in inputs.metadata('scoring/panels.json').items()}
    if len(frame)!=29856 or len(panels)!=31:raise ValueError('frame inventory')
    for split in frame.split.unique():
        # Outcome-free saved CSV roundtrip, same convention as qualified study.
        f=pd.read_csv(HERE/'score'/f'predictions_{split}.csv',low_memory=False)
        mask=frame.split.eq(split);old=frame.loc[mask]
        if len(old)!=len(f):raise ValueError('split length')
        if split not in EXTERNAL:
            if f.nf2_row_id.duplicated().any():raise ValueError('duplicate score ID')
            f=f.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(f['indices'],np.arange(len(f)))
        # Exact same CSV roundtrip may move one bit; inherited alignment tolerance only.
        np.testing.assert_allclose(f.BASE_CD,old.mean8_CD,rtol=0,atol=1e-13)
        for label in NEW_LABELS:
            for key in [label,label+'__effective_fraction',label+'__strength',label+'__intervened']:
                frame.loc[mask,key]=f[key].to_numpy()
    pd.testing.assert_frame_equal(frame[original.columns],original,check_exact=True)
    m.CANDIDATES=NEW_LABELS;m.CONTROLS=list(m.LABELS);m.LABELS=NEW_LABELS+m.CONTROLS
    m.REFERENCES=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half',OLD_LABELS[1],OLD_LABELS[0],NEW_LABELS[1]]
    m.run=types.SimpleNamespace(LABELS=NEW_LABELS,EXTERNAL=EXTERNAL)
    tables={'panel_metrics':m.panel_metrics(frame,panels),'bootstrap':m.bootstrap(frame),'group_metrics':m.group_metrics(frame)}
    tables['decisions']=m.decisions(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
    tables['candidate_summary']=m.summary(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
    tables['harm_metrics']=m.harms(frame,panels)
    risk,bundles,interventions=m.extras(frame,panels)
    tables.update(expected_harm_metrics=risk,bundle_harm_metrics=bundles,intervention_metrics=interventions,all_row_predictions=frame)
    if len(tables['panel_metrics'])!=527 or len(tables['bootstrap'])!=238:raise ValueError('table counts')
    for name,t in tables.items():t.to_csv(out/(name+'.csv'),index=False,mode='x')

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['preflight','calibrate','score','assess'])
    p.add_argument('--implementation-sha256',required=True);p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True)
    args=p.parse_args()
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):raise ValueError('one thread')
    codec=codec_from_source();freeze,approval=authorize(args);predecessor(args.phase,approval,args.implementation_sha256)
    out=HERE/args.phase
    if out.is_symlink() or any(x.is_symlink() for x in out.parents):raise ValueError('symlink output')
    out.mkdir(exist_ok=False)
    start=time.monotonic();record={'phase':args.phase,'started_UTC':now(),'implementation_sha256':args.implementation_sha256,
        'approval_sha256':args.approval_sha256,'predecessor_sha256':approval.get('predecessor_sha256'),'new_core_fits':0}
    codec.write_json(out/'ATTEMPT.json',record);inputs=None
    def timeout(*unused):raise TimeoutError('900-second phase guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900)
    try:
        inputs=Inputs(ARCHIVE,args.phase);c=module('kl_production',checked(CONFIDENCE,CONFIDENCE_SHA),CONFIDENCE)
        globals()[args.phase](inputs,out,codec,c)
        if args.phase=='calibrate' and (len(list(out.glob('calibrator_*.json')))!=32 or len(list(out.glob('membership_*.json')))!=16):raise ValueError('32 scalar/16 role inventory')
        if args.phase=='score' and (len(list(out.glob('inference_*.npz')))!=18 or len(list(out.glob('predictions_*.csv')))!=17):raise ValueError('18 native/17 outcome-free CSV inventory')
        record.update(finished_UTC=now(),seconds=time.monotonic()-start,actual_reads=inputs.events,
            outputs={f.name:sha(f.read_bytes()) for f in out.iterdir() if f.is_file()},
            runtime={'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__})
        codec.write_json(out/'COMPLETE.json',record)
    except BaseException as exc:
        import traceback
        record.update(exception=repr(exc),traceback=traceback.format_exc(),finished_UTC=now(),seconds=time.monotonic()-start,
            actual_reads=inputs.events if inputs else [])
        codec.write_json(out/'FAILURE.json',record);raise
    finally:signal.alarm(0)

if __name__=='__main__':main()
