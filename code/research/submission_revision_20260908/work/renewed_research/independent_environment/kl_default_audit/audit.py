"""Bounded independent audit; no root solver, fitting, extraction or source writes."""
from pathlib import Path, PurePosixPath
from fractions import Fraction as F
import hashlib, io, json, zipfile, stat, types, sys, time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
R=HERE.parents[1]
P=R/'model_proposal/kl_bound_study/portable_plan'
sha=lambda b:hashlib.sha256(b).hexdigest()
pins={}
def read(p,h=None):
    p=Path(p);b=p.read_bytes();actual=sha(b)
    if h is not None:assert actual==h,str(p)
    pins[str(p)]=actual
    return b
def archive(p,h,m):
    raw=read(p,h)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        assert len(names)==len(set(x.casefold() for x in names))
        for i in infos:
            n=i.filename;v=PurePosixPath(n)
            assert str(v)==n and not v.is_absolute() and '..' not in v.parts
            assert '\\' not in n and ':' not in n and not i.is_dir()
            assert stat.S_IFMT(i.external_attr>>16) in (0,stat.S_IFREG)
            assert not i.flag_bits&1
        data={n:z.read(n) for n in names}
    manifest=data.pop('manifest.json');assert sha(manifest)==m
    j=json.loads(manifest);assert set(data)==set(j['files'])
    for n,b in data.items():assert j['files'][n]=={'sha256':sha(b),'bytes':len(b)}
    return data,manifest
def module(name,b):
    m=types.ModuleType(name);sys.modules[name]=m;exec(compile(b,name,'exec'),m.__dict__);return m
def arr(b):
    with np.load(io.BytesIO(b),allow_pickle=False) as z:
        a={k:z[k] for k in z.files}
    assert all(not v.dtype.hasobject for v in a.values())
    return a
def main():
    start=time.monotonic()
    approval=json.loads(read(P/'ROOT_DEFAULT_REPLAY_APPROVAL.json','4949f4f2efe45ff364dd8ba0243798cb8b8cd24145dd00c0b2e6f4a7449d3529'))
    complete=json.loads(read(P/'replay_default_attempt_1/COMPLETE.json','401f682fb4624667dcb592f6bac33e75aa7195669809c6131338a3e328c13486'))
    receipt=json.loads(read(P/'ROOT_EXTRACTION_RECEIPT.json','6c5b51073a0009ff93486e4c81403dd9aabc2bc241db508c73cbaafe1b1e4d38'))
    addon,manifest=archive(P/'kl_harm_private_v1.zip',approval['archive_sha256'],approval['manifest_sha256'])
    parent,pm=archive(R/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip',approval['parent_archive_sha256'],approval['parent_manifest_sha256'])
    extraction=P/'fresh_extraction_v1'
    actual={str(p.relative_to(extraction)) for p in extraction.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    assert actual==set(addon)|{'manifest.json'}
    for n,b in dict(addon,**{'manifest.json':manifest}).items():assert read(extraction/n)==b
    assert receipt['files']==json.loads(manifest)['files']
    registry=json.loads(read(P/'REGISTRY_v3.json',approval['source_registry_sha256']))
    for n,h in registry['sources'].items():read(P/n,h)
    for n,h in registry['inputs'].items():read(n,h)
    witness=json.loads(addon['SOURCE_WITNESS.json']);assert witness['inputs']==registry['inputs']
    req=json.loads(addon['PARENT_REQUIREMENTS.json'])
    assert req['required_members']=={n:sha(b) for n,b in parent.items()}
    for k in ['archive_sha256','manifest_sha256','parent_archive_sha256','parent_manifest_sha256']:
        assert complete[k]==approval[k]
    assert complete['approval_sha256']==pins[str(P/'ROOT_DEFAULT_REPLAY_APPROVAL.json')]
    for name,h in complete['executing_source_sha256'].items():
        assert sha(addon['code/'+name])==h
    assert complete['local_start_source_sha256']==complete['executing_source_sha256']
    assert complete['end_authentication'] is True
    for n,h in complete['outputs'].items():read(P/'replay_default_attempt_1'/n,h)
    assert complete['status']=='EXACT_REPLAY_PASS' and complete['unresolved_outside_contract']==0
    assert not complete['differences'] and json.loads(read(P/'replay_default_attempt_1/FLOAT_DIFFERENCES.json'))==[]
    ledger=complete['materializations'];assert len(ledger)==781
    for e in ledger:
        if e.get('origin')=='computed output':
            assert e['file'] in complete['counts'] and e['operation']=='self serialization and pandas.read_csv; not source input'
            continue
        if 'origin' in e:origin,n=e['origin'],e['file']
        else:origin,n=e['file'].split('/',1)
        b={'addon':addon,'parent':parent}[origin][n];assert sha(b)==e['sha256']
        if 'member' in e:
            a=arr(b)[e['member']];assert list(a.shape)==e['shape'] and str(a.dtype)==e['dtype']
    q=module('qualified_numerics',parent['code/qualified_numerics.py'])
    codec=module('audit_codec',parent['code/codec.py'])
    policy=module('audit_policy',parent['code/policy.py'])
    inventory=json.loads(parent['inventory.json']);labels=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
    scalar_models={};role_count=0
    for ctx in inventory['contexts']:
        z=arr(parent[f'calibration/{ctx}.npz']);role=json.loads(parent[f'roles/{ctx}.json'])
        sets=[set(role[k]) for k in ['proper_groups','calibration_groups','test_groups']]
        assert not any(sets[i]&sets[j] for i in range(3) for j in range(i))
        assert set(z['group'].astype(str))==sets[1]
        for key,target in [('indices','calibration_indices'),('nf2_row_id','calibration_nf2_row_ids')]:np.testing.assert_array_equal(z[key],role[target])
        losses=[q.exact_endpoint_loss(b,c,h,y) for b,c,h,y in zip(z['BASE_CD'],z['core'],z['anchor'],z['MEAS_CD'])]
        for label in labels:
            s=json.loads(addon[f'scalars/{label}_{ctx}.json']);scalar_models[label,ctx]=s
            assert s['candidate']==label and s['context']==ctx
            B=codec.fraction(s['bound']);means=policy.group_means_exact(losses,z['group'].astype(str),B)
            assert means=={g:codec.fraction(v) for g,v in s['group_means'].items()}
            assert s['groups']==len(means) and s['rows']==len(losses)
            mean=sum(means.values(),F(0))/len(means)
            assert mean==codec.fraction(s['exact_mean'])
            U=codec.fraction(s['upper']);H=codec.fraction(s['matched_hoeffding_upper'])
            assert mean<=U<=H<=B and 0<=F(s['t'])<=1 and F(s['t'])*U<=F(1,100)
            assert s['t']>=s['matched_hoeffding_t'] and s['conditional_not_certified'] is True
            w=s['root_witness'];assert codec.fraction(w['mean_exact'])==mean
            assert U==min(codec.fraction(w['kl_upper_before_hoeffding_min']),H)
            assert w['lower_endpoint_scope']=='root_at_q_upper_only' and w['upper_endpoint_scope']=='conservative_for_q_exact'
        role_count+=1
    fallback=0;rows=0
    for ctx in inventory['native_contexts']:
        z=arr(parent[f'native/{ctx}.npz']);expected=arr(addon[f'predictions/{ctx}.npz'])
        np.testing.assert_array_equal(z['indices'],expected['indices']);assert z['gate'].dtype==bool
        fallback+=int((~z['gate']).sum());rows+=len(z['indices'])
        for label in labels:
            s=scalar_models[label,ctx if ctx in inventory['contexts'] else 'final']
            p,e=policy.predictions(s,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
            for key,v in {label:p,label+'__effective_fraction':e,label+'__strength':np.where(z['gate'],.5+.5*s['t'],0),label+'__intervened':abs(p-z['anchor'])>1e-12}.items():np.testing.assert_array_equal(v,expected[key])
            np.testing.assert_array_equal(p[~z['gate']],z['BASE_CD'][~z['gate']])
    counts={}
    for name,count in complete['counts'].items():
        b=read(P/'replay_default_attempt_1'/(name+'.csv'))
        assert b==addon['expected/'+name+'.csv']
        f=pd.read_csv(io.BytesIO(b));assert len(f)==count;counts[name]=len(f)
    decisions=pd.read_csv(io.BytesIO(addon['expected/decisions.csv']))
    for col in ['performance_advance','robustness_advance']:assert not decisions[col].any()
    schema=json.loads(parent['scoring/frame_schema.json']) if 'scoring/frame_schema.json' in parent else json.loads(parent['scoring/schema.json'])
    assert len(schema['columns'])==80 and schema['rows']==29856
    assert len(arr(parent['scoring/frame.npz']))==90
    audits={n:json.loads(addon['evidence/'+n]) for n in ['KL_ASSESSMENT_QA.json','KL_SUMMARY_QA.json']}
    assert all(v['status']=='PASS' for v in audits.values())
    assert audits['KL_ASSESSMENT_QA.json']['complete_sha256']==sha(addon['evidence/assess_COMPLETE.json'])
    assert len(complete['scalar_checks'])==32 and all(v['exact'] for v in complete['scalar_checks'])
    assert len(complete['native_checks'])==18 and complete['certificates']==16
    result={'status':'PASS_BOUNDED_DEFAULT_AUDIT','seconds':time.monotonic()-start,'archive_payloads':len(addon),'ledger_events':len(ledger),'roles_checked':role_count,'exact_means_and_budget_witnesses':32,'native_contexts_recomputed':18,'native_rows_including_final':rows,'fallback_rows_per_candidate':fallback,'table_rows':counts,'byte_exact_tables':10,'differences':0,'certificate_scope':'16 completed exact certificate checks authenticated; tree traversal not repeated','KL_root_scope':'completed exact root replay authenticated; roots not rerun','assessment_scope':'authenticated prior independent equation and bootstrap audit reused, including its two historical numerical-zero sign diagnostic warnings','source_output_pins':pins}
    with (HERE/'AUDIT.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='source_output_pins'},indent=2))
if __name__=='__main__':main()
