"""Explicitly approved phases: label-free parity -> scalar freeze -> outcomes.

No work at import. Never fits. Hash-authenticated safe NPZ only.
"""
from pathlib import Path
from fractions import Fraction as F
import argparse
import hashlib
import io
import json
import time
import traceback
import numpy as np
import numerics as n
from evaluator import SequentialHist

HERE=Path(__file__).resolve().parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
A=PROJECT/'model_development_20260907_cap_ablation'
OLD=HERE.parents[1]
BUNDLE=PROJECT/'submission_revision_20260908/work/scientific_review/bounds_portable/bundle'
LABELS=('qualified_structural_harm_001','qualified_generic_harm_001')
EXTERNAL=('SG_exposed','W_new_challenge')
PINS={'a_freeze':'7d07b1beacb39de88f4c1c8b96b48ac6988c619f9e344843df3b565531c835f3',
      'a_qa':'d7d9c278bd1f34628a3302bf9620efb282a098ea49249f3cb3af712d7c5c275e',
      'trees':'210e58847ae62a495aeda880eac3f911779a16cd09c852a1281f9777dc70f1ea',
      'certificate':'8cdcd2f6aa0e035aa68afa53a555b848f6012ce460c7b9f0c417607d27a00782'}
_EXECUTION={}

def begin_phase(args):
    import os
    if any(os.environ.get(k)!='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS']):
        raise ValueError('single-thread numerical environment must be set before launch')
    _EXECUTION.update(phase=args.phase,implementation_sha256=args.implementation_sha256,
        approval_sha256=args.approval_sha256,started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        started_monotonic=time.monotonic())

def receipt():
    if not _EXECUTION:raise ValueError('explicit phase execution context required')
    import sys,platform
    return {k:v for k,v in _EXECUTION.items() if k!='started_monotonic'} | {
        'completed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        'elapsed_seconds':time.monotonic()-_EXECUTION['started_monotonic'],
        'protocol_sha256':sha((HERE/'PROTOCOL.md').read_bytes()),
        'scientific_protocol_sha256':sha((HERE.parent/'STAGE1_PROTOCOL_DRAFT.md').read_bytes()),
        'runtime':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
                   'arithmetic':'float64 sequential400, nonfused graph; ties-even probe'}}

def sha(data): return hashlib.sha256(data).hexdigest()
def encode(v):
    if isinstance(v,F):
        return {'encoding':'signed-hex-v1', 'numerator':format(v.numerator,'x'),
                'denominator':format(v.denominator,'x')}
    raise TypeError(type(v).__name__)
def fraction(v):
    """Strict canonical tagged hex; authenticated legacy decimal remains readable."""
    import re
    if not isinstance(v,dict):raise ValueError('rational record required')
    if set(v)=={'encoding','numerator','denominator'} and v['encoding']=='signed-hex-v1':
        radix=16;unsigned=r'(?:0|[1-9a-f][0-9a-f]*)';positive=r'[1-9a-f][0-9a-f]*'
    elif set(v)=={'numerator','denominator'}:
        radix=10;unsigned=r'(?:0|[1-9][0-9]*)';positive=r'[1-9][0-9]*'
    else:raise ValueError('unknown rational encoding/schema')
    numerator,denominator=v['numerator'],v['denominator']
    if not isinstance(numerator,str) or not isinstance(denominator,str):raise ValueError('rational strings required')
    if not re.fullmatch(r'-?'+unsigned,numerator) or numerator=='-0' or not re.fullmatch(positive,denominator):
        raise ValueError('noncanonical rational strings')
    a,b=int(numerator,radix),int(denominator,radix)
    result=F(a,b)
    if result.numerator!=a or result.denominator!=b:raise ValueError('rational must be reduced')
    return result
def write_json(path,value):
    # Serialize before touching the destination: codec failures leave no partial file.
    payload=json.dumps(value,default=encode,indent=2,allow_nan=False)+'\n'
    with Path(path).open('x') as f:f.write(payload)
def read_checked(path,expected):
    path=Path(path)
    if path.is_symlink():raise ValueError('symlink input')
    raw=path.read_bytes()
    if sha(raw)!=expected:raise ValueError('authentication failed: '+str(path))
    return raw
def json_checked(path,expected):return json.loads(read_checked(path,expected))
def save_npz(path,**values):
    with Path(path).open('xb') as f:np.savez_compressed(f,**values)

class Inputs:
    def __init__(self):
        self.ledger={};self.members=[]
        self.freeze=self.js(A/'results/freeze.json',PINS['a_freeze'])
        qa=self.js(A/'DELIVERY_QA.json',PINS['a_qa'])
        self.complete=self.js(A/'results/complete.json',qa['source_and_result_sha256'][str(A/'results/complete.json')])
        if self.complete['freeze_sha256']!=PINS['a_freeze']:raise ValueError('A freeze chain')
        self.hashes={**self.freeze['artifact_sha256'],**self.complete['output_sha256']}
        self.contexts=self.freeze['contexts']
        if len(self.contexts)!=16 or len(set(self.contexts))!=16:raise ValueError('16 contexts required')
        self.tree_manifest=self.js(BUNDLE/'manifest.json',PINS['trees'])
        self.cert=self.js(HERE.parent/'STAGE0_CERTIFICATE.json',PINS['certificate'])
        self.bounds={r['context']:r for r in self.cert['records']}
        self.models={}
        for row in self.tree_manifest['trees']:
            if row['branch']!='proper':continue
            name=row['capped']
            import re
            if not re.fullmatch(r'arrays/tree_\d{2}_capped\.npz',name):raise ValueError('tree whitelist')
            arrays=self.npz(BUNDLE/name,self.tree_manifest['files'][name],None)
            model=SequentialHist(arrays)
            # Recreate the complete input-independent machine envelope, not only realized predictions.
            reproduced=n.q.sequential_range(model.initial,
                (stage['value'][stage['is_leaf'].astype(bool)] for stage in model.stages))
            cert=self.bounds[row['context']]
            for key in ['lower','upper','real_lower','real_upper']:
                if reproduced[key]!=fraction(cert['range'][key]):raise ValueError('exact range replay mismatch')
            if reproduced['stages']!=400 or n.q.structural_bound(reproduced['lower'],reproduced['upper'])!=fraction(cert['B_structural']):
                raise ValueError('structural B replay mismatch')
            self.models[row['context']]=model
        if set(self.models)!=set(self.contexts):raise ValueError('tree context mismatch')

    def js(self,path,h):
        raw=read_checked(path,h);self.ledger[str(path)]=h;return json.loads(raw)
    def npz(self,path,h,keys):
        raw=read_checked(path,h);self.ledger[str(path)]=h
        with np.load(io.BytesIO(raw),allow_pickle=False) as z:
            chosen=z.files if keys is None else keys
            out={k:z[k].copy() for k in chosen}
        self.members.append({'path':str(path),'materialized_members':list(chosen)})
        return out
    def archived(self,path,keys):return self.npz(path,self.hashes[str(path)],keys)
    def member(self,context):
        path=A/'results'/f'membership_{context}.json'
        m=self.js(path,self.hashes[str(path)])
        sets=[set(m[k]) for k in ['proper_groups','calibration_groups','test_groups']]
        if any(sets[i]&sets[j] for i in range(3) for j in range(i)) or m['post_calibration_refit'] is not False:
            raise ValueError('role leakage')
        return m
    def inference_path(self,context):
        return A/'exposed_results'/f'{context}_inference.npz' if context in EXTERNAL else A/'results'/f'inference_{context}.npz'

def authorize(args):
    manifest=json_checked(HERE/'IMPLEMENTATION_FREEZE.json',args.implementation_sha256)
    for path,h in manifest['source_sha256'].items():read_checked(HERE/path,h)
    read_checked(HERE.parent/'STAGE1_PROTOCOL_DRAFT.md',manifest['protocol_draft_sha256'])
    approved=json_checked(args.approval,args.approval_sha256)
    if approved.get('implementation_sha256')!=args.implementation_sha256 or args.phase not in approved.get('authorized_phases',[]):
        raise ValueError('phase has no explicit root execution approval')
    return manifest

def evaluate(inputs,context,z):
    model_context='final' if context in EXTERNAL else context
    raw=inputs.models[model_context].predict_raw(z['X62'])
    cert=inputs.bounds[model_context]['range'];lo,hi=fraction(cert['lower']),fraction(cert['upper'])
    if any(not lo<=n.q.rat(r)<=hi for r in raw):raise ValueError('machine raw envelope violation')
    c,h,g=n.q.guarded_core(z['BASE_CD'],raw,z['gate'])
    return c,h,g

def parity(inputs,dest):
    final=inputs.archived(inputs.inference_path('final'),['indices','gate'])
    if len(final['indices'])!=8371 or len(set(final['indices']))!=8371:raise ValueError('historical row inventory')
    if final['gate'].dtype!=bool:raise ValueError('strict historical gate dtype')
    gates=dict(zip(map(int,final['indices']),map(bool,final['gate'])))
    records=[];artifacts={}
    for context in inputs.contexts:
        member=inputs.member(context)
        z=inputs.archived(A/'results'/f'calibration_{context}.npz',
                          ['indices','nf2_row_id','X62','BASE_CD','CORE_CD_capped'])
        np.testing.assert_array_equal(z['indices'],member['calibration_indices'])
        np.testing.assert_array_equal(z['nf2_row_id'],member['calibration_nf2_row_ids'])
        z['gate']=np.array([gates[int(i)] for i in z['indices']],bool)
        c,h,g=evaluate(inputs,context,z)
        numerical=(z['BASE_CD']>=n.q.DOMAIN_MIN)&(z['BASE_CD']<=n.q.DOMAIN_MAX)
        # Calibration references are ungated CD, not raw tree scores.
        expected=np.where(z['gate'],z['CORE_CD_capped'],z['BASE_CD'])
        expected_h=np.where(z['gate'],z['BASE_CD']+.5*(z['CORE_CD_capped']-z['BASE_CD']),z['BASE_CD'])
        np.testing.assert_array_equal(c[numerical],expected[numerical])
        np.testing.assert_array_equal(h[numerical],expected_h[numerical])
        p=dest/f'calibration_reference_{context}.npz'
        save_npz(p,indices=z['indices'],BASE_CD=z['BASE_CD'],core=c,anchor=h,gate=g)
        artifacts[p.name]=sha(p.read_bytes())
        records.append({'kind':'calibration','context':context,'rows':len(c),'numerical_fallback':int((~numerical).sum()),'exact':True})
    for context in list(inputs.contexts)+list(EXTERNAL):
        z=inputs.archived(inputs.inference_path(context),['indices','X62','BASE_CD','gate','proper_core_capped','proper_capped_full','proper_capped_half'])
        if context not in EXTERNAL and context!='final':
            np.testing.assert_array_equal(z['indices'],inputs.member(context)['test_indices'])
        c,h,g=evaluate(inputs,context,z)
        numerical=(z['BASE_CD']>=n.q.DOMAIN_MIN)&(z['BASE_CD']<=n.q.DOMAIN_MAX)
        np.testing.assert_array_equal(c[numerical],z['proper_capped_full'][numerical])
        np.testing.assert_array_equal(h[numerical],z['proper_capped_half'][numerical])
        # Explicit ungated reference check on gate-true rows.
        np.testing.assert_array_equal(c[g],z['proper_core_capped'][g])
        np.testing.assert_array_equal(c[~g],z['BASE_CD'][~g]);np.testing.assert_array_equal(h[~g],z['BASE_CD'][~g])
        p=dest/f'inference_{context}.npz'
        save_npz(p,indices=z['indices'],BASE_CD=z['BASE_CD'],core=c,anchor=h,gate=g)
        artifacts[p.name]=sha(p.read_bytes())
        records.append({'kind':'inference','context':context,'rows':len(c),'numerical_fallback':int((~numerical).sum()),'exact':True})
    if sum(r['rows'] for r in records if r['context'] in EXTERNAL)!=497:raise ValueError('external reference inventory')
    write_json(dest/'PARITY_PASS.json',{'status':'EXACT_PRELOSS_PARITY_PASS','execution':receipt(),'records':records,
        'artifact_sha256':artifacts,'source_input_sha256':inputs.ledger,'member_access':inputs.members,
        'target_members_materialized':False,'topology_validated':16,'stage_count':400,
        'ast_sha256':{'group':n.GROUP_AST,'confidence':n.CONFIDENCE_AST}})

def read_parity():
    p=HERE/'precalibration/PARITY_PASS.json'
    z=json.loads(p.read_bytes())
    if z['status']!='EXACT_PRELOSS_PARITY_PASS' or z['target_members_materialized']:raise ValueError('parity barrier')
    if _EXECUTION and z.get('execution',{}).get('implementation_sha256')!=_EXECUTION['implementation_sha256']:
        raise ValueError('parity implementation provenance mismatch')
    for path,h in z['source_input_sha256'].items():read_checked(path,h)
    for path,h in z['artifact_sha256'].items():read_checked(HERE/'precalibration'/path,h)
    return z,sha(p.read_bytes())

def calibrate(inputs,dest):
    parity_record,parity_hash=read_parity();artifacts={}
    for context in inputs.contexts:
        member=inputs.member(context)
        p=HERE/'precalibration'/f'calibration_reference_{context}.npz'
        v=inputs.npz(p,parity_record['artifact_sha256'][p.name],['indices','BASE_CD','core','anchor','gate'])
        z=inputs.archived(A/'results'/f'calibration_{context}.npz',['indices','nf2_row_id','BASE_CD','MEAS_CD','group'])
        np.testing.assert_array_equal(z['indices'],v['indices']);np.testing.assert_array_equal(z['BASE_CD'],v['BASE_CD'])
        np.testing.assert_array_equal(z['nf2_row_id'],member['calibration_nf2_row_ids'])
        if set(z['group'].astype(str))!=set(member['calibration_groups']):raise ValueError('calibration identity mismatch')
        for label,bound in zip(LABELS,[fraction(inputs.bounds[context]['B_structural']),n.q.GENERIC_BOUND]):
            model=n.fit_scalar(v['BASE_CD'],v['core'],v['anchor'],z['MEAS_CD'],z['group'].astype(str),bound)
            model.update(context=context,procedure=label,conditional_not_certified=True)
            path=dest/f'calibrator_{label}_{context}.json';write_json(path,model);artifacts[path.name]=sha(path.read_bytes())
        path=dest/f'membership_{context}.json';write_json(path,member);artifacts[path.name]=sha(path.read_bytes())
    if len(artifacts)!=48:raise ValueError('32 scalar +16 role artifacts required')
    write_json(dest/'freeze.json',{'calibrator_count':32,'new_core_fits':0,'external_outcomes_opened':False,
        'execution':receipt(),
        'contexts':inputs.contexts,'procedures':LABELS,'parity_sha256':parity_hash,'artifact_sha256':artifacts,
        'source_input_sha256':inputs.ledger,'member_access':inputs.members})

def score_predictions(inputs,dest):
    import pandas as pd
    freeze=json.loads((HERE/'results/freeze.json').read_bytes())
    _,ph=read_parity()
    if freeze['parity_sha256']!=ph or freeze['calibrator_count']!=32 or freeze['external_outcomes_opened']:
        raise ValueError('scalar freeze barrier')
    if freeze.get('execution',{}).get('implementation_sha256')!=_EXECUTION.get('implementation_sha256'):
        raise ValueError('scalar implementation provenance mismatch')
    for path,h in freeze['artifact_sha256'].items():read_checked(HERE/'results'/path,h)
    for path,h in freeze['source_input_sha256'].items():read_checked(path,h)
    pr,_=read_parity();outputs={}
    for context in list(inputs.contexts)+list(EXTERNAL):
        p=HERE/'precalibration'/f'inference_{context}.npz'
        z=inputs.npz(p,pr['artifact_sha256'][p.name],['indices','BASE_CD','core','anchor','gate'])
        vals={'qualified_matched_half':z['anchor'],'qualified_matched_full':z['core']}
        for label in LABELS:
            name=f'calibrator_{label}_{"final" if context in EXTERNAL else context}.json'
            model=json_checked(HERE/'results'/name,freeze['artifact_sha256'][name])
            if n.q.rat(model['t'])*fraction(model['upper'])>n.q.TAU:
                raise ValueError('scalar numerical budget invariant')
            pred,effective=n.predictions(model,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
            vals[label]=pred;vals[label+'__effective_fraction']=effective
            vals[label+'__strength']=np.where(z['gate'],.5+.5*model['t'],0.)
            vals[label+'__intervened']=abs(pred-z['anchor'])>1e-12
        out=dest/f'inference_{context}.npz';save_npz(out,**z,**vals);outputs[out.name]=sha(out.read_bytes())
        if context=='final':continue
        path=A/('exposed_results' if context in EXTERNAL else 'results')/(f'{context}_predictions.csv' if context in EXTERNAL else f'predictions_{context}.csv')
        frame=pd.read_csv(io.BytesIO(read_checked(path,inputs.hashes[str(path)])),low_memory=False)
        inputs.ledger[str(path)]=inputs.hashes[str(path)]
        if len(frame)!=len(z['indices']):raise ValueError('CSV row alignment')
        if context not in EXTERNAL:np.testing.assert_array_equal(frame.nf2_row_id,inputs.member(context)['test_nf2_row_ids'])
        np.testing.assert_allclose(frame['mean8_CD'],z['BASE_CD'],rtol=0,atol=1e-13)
        numerical=(z['BASE_CD']>=n.q.DOMAIN_MIN)&(z['BASE_CD']<=n.q.DOMAIN_MAX)
        np.testing.assert_allclose(frame['proper_capped_full'].to_numpy()[numerical],z['core'][numerical],rtol=0,atol=1e-13)
        for k,v in vals.items():frame[k]=v
        frame['qualified_gate']=z['gate']
        out=dest/f'predictions_{context}.csv';frame.to_csv(out,index=False,mode='x');outputs[out.name]=sha(out.read_bytes())
    if len(outputs)!=35:raise ValueError('18 inference +17 scored CSV artifacts required')
    write_json(dest/'complete.json',{'status':'EXPLORATORY_NOT_CERTIFIED','calibrator_count':32,'freeze_sha256':sha((HERE/'results/freeze.json').read_bytes()),
        'execution':receipt(),
        'output_sha256':outputs,'source_input_sha256':inputs.ledger,'new_core_fits':0})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',required=True,choices=['parity','calibrate','score'])
    parser.add_argument('--implementation-sha256',required=True)
    parser.add_argument('--approval',required=True);parser.add_argument('--approval-sha256',required=True)
    args=parser.parse_args();authorize(args);begin_phase(args)
    dest=HERE/{'parity':'precalibration','calibrate':'results','score':'predictions'}[args.phase]
    dest.mkdir(exist_ok=False)
    # Hard per-phase guard; timeout is retained, never switches arithmetic.
    import signal
    def timeout(*unused):raise TimeoutError('fixed 900-second phase guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900)
    started=time.monotonic()
    try:
        inputs=Inputs()
        {'parity':parity,'calibrate':calibrate,'score':score_predictions}[args.phase](inputs,dest)
    except BaseException as exc:
        write_json(dest/'FAILURE.json',{'phase':args.phase,'execution':receipt(),'exception':repr(exc),'traceback':traceback.format_exc()})
        raise
    finally:signal.alarm(0)
    print(json.dumps({'phase':args.phase,'seconds':time.monotonic()-started,'status':'COMPLETE'}))

if __name__=='__main__':main()
