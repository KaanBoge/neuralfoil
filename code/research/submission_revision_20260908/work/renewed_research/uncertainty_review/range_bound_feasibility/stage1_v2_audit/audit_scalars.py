"""Independent authenticated scalar replay. No producer imports or core fitting."""
from pathlib import Path
from fractions import Fraction as F
import hashlib, json, io, math, traceback
import numpy as np

HERE=Path(__file__).resolve().parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
S=PROJECT/'submission_revision_20260908/work/renewed_research/model_proposal/range_bound_feasibility/stage1_v2'
A=PROJECT/'model_development_20260907_cap_ablation'
PIN='9419e93aea4016d9273340d75f9252f093713e81d94d4f1e74f459d204691b85'
OPENED=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(p,h):
    p=Path(p);assert not p.is_symlink();raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==h,str(p)
    return raw
def frac(x):
    radix=16 if x.get('encoding')=='signed-hex-v1' else 10
    return F(int(x['numerator'],radix),int(x['denominator'],radix))
def npz(p,h,keys):
    with np.load(io.BytesIO(checked(p,h)),allow_pickle=False) as z:r={k:z[k].copy() for k in keys}
    OPENED.append({'path':str(p),'members':keys});return r
def directed(q,up):
    f=float(q)
    if (up and F(f)<q) or (not up and F(f)>q):f=float(np.nextafter(f,np.inf if up else -np.inf))
    assert F(f)>=q if up else F(f)<=q
    return f
def log_upper():
    def part(z):return 2*sum((z**(2*k+1)/F(2*k+1) for k in range(128)),F(0))+2*z**257/(257*(1-z*z))
    return part(F(1,9))+4*part(F(1,3))
def sqrt_upper(q):
    d=2**256;n=math.isqrt(q.numerator*d*d//q.denominator)
    if n*n*q.denominator<q.numerator*d*d:n+=1
    assert F(n*n,d*d)>=q and (n==0 or F((n-1)**2,d*d)<q)
    return F(n,d)
def main():
    freeze=json.loads(checked(S/'results/freeze.json',PIN))
    impl=json.loads(checked(S/'IMPLEMENTATION_FREEZE.json',freeze['execution']['implementation_sha256']))
    for p,h in impl['source_sha256'].items():checked(S/p,h)
    checked(S.parent/'STAGE1_PROTOCOL_DRAFT.md',impl['protocol_draft_sha256'])
    for p,h in freeze['source_input_sha256'].items():checked(p,h)
    for p,h in freeze['artifact_sha256'].items():checked(S/'results'/p,h)
    assert len(freeze['artifact_sha256'])==48 and freeze['calibrator_count']==32
    assert freeze['new_core_fits']==0 and freeze['external_outcomes_opened'] is False
    parity=json.loads(checked(S/'precalibration/PARITY_PASS.json',freeze['parity_sha256']))
    assert parity['target_members_materialized'] is False
    assert not any('MEAS_CD' in e['materialized_members'] for e in parity['member_access'])
    assert parity['execution']['completed_utc']<=freeze['execution']['started_utc']
    for rec,phase in [(parity,'parity'),(freeze,'calibrate')]:
        ex=rec['execution'];assert ex['phase']==phase and ex['implementation_sha256']==freeze['execution']['implementation_sha256']
        approval=json.loads(checked(S/f'ROOT_{"PARITY" if phase=="parity" else "CALIBRATION"}_APPROVAL.json',ex['approval_sha256']))
        assert phase in approval['authorized_phases'] and approval['implementation_sha256']==ex['implementation_sha256']
        for p,h in rec['source_input_sha256'].items():checked(p,h)
        assert not any(Path(p).suffix=='.csv' for p in rec['source_input_sha256'])
    targets=[e for e in freeze['member_access'] if 'MEAS_CD' in e['materialized_members']]
    assert len(targets)==16 and all(Path(e['path']).parent==A/'results' and Path(e['path']).name.startswith('calibration_') for e in targets)
    certpath=S.parent/'STAGE0_CERTIFICATE.json'
    cert=json.loads(checked(certpath,freeze['source_input_sha256'][str(certpath)]))
    certs={r['context']:r for r in cert['records']}
    rows=[];total=0;u=F(1,2**53);e=4*u+2*u*u;log=log_upper()
    clip=lambda q:min(F(1),max(F(-1,2),q))
    for context in freeze['contexts']:
        mp=S/'results'/f'membership_{context}.json';m=json.loads(checked(mp,freeze['artifact_sha256'][mp.name]))
        old=A/'results'/mp.name;assert json.loads(checked(old,freeze['source_input_sha256'][str(old)]))==m
        sets=[set(m[k]) for k in ['proper_groups','calibration_groups','test_groups']]
        ids=[set(m[k]) for k in ['proper_indices','calibration_indices','test_indices']]
        assert all(not s[i]&s[j] for s in [sets,ids] for i in range(3) for j in range(i))
        assert m['post_calibration_refit'] is False
        p=A/'results'/f'calibration_{context}.npz'
        z=npz(p,freeze['source_input_sha256'][str(p)],['indices','nf2_row_id','BASE_CD','MEAS_CD','group'])
        p=S/'precalibration'/f'calibration_reference_{context}.npz'
        v=npz(p,parity['artifact_sha256'][p.name],['indices','BASE_CD','core','anchor','gate'])
        np.testing.assert_array_equal(z['indices'],m['calibration_indices']);np.testing.assert_array_equal(z['nf2_row_id'],m['calibration_nf2_row_ids'])
        np.testing.assert_array_equal(z['indices'],v['indices']);np.testing.assert_array_equal(z['BASE_CD'],v['BASE_CD'])
        assert set(z['group'].astype(str))==sets[1] and v['gate'].dtype==bool
        losses=[max(abs(F(float(c))-F(float(y)))-abs(F(float(h))-F(float(y))),F(0))/F(float(b)) for b,c,h,y in zip(v['BASE_CD'],v['core'],v['anchor'],z['MEAS_CD'])]
        groups=z['group'].astype(str);means={g:sum((losses[i] for i in np.flatnonzero(groups==g)),F(0))/int((groups==g).sum()) for g in np.unique(groups)}
        mean=sum(means.values(),F(0))/len(means);total+=len(losses)
        cr=certs[context];lo=frac(cr['range']['lower']);hi=frac(cr['range']['upper'])
        bs=max(abs(clip(clip(lo)-e)),abs(clip(clip(hi)+e)))/2+3*u/2
        assert bs==frac(cr['B_structural'])
        for label,bound in zip(freeze['procedures'],[bs,F(1,2)+3*u/2]):
            p=S/'results'/f'calibrator_{label}_{context}.json';saved=json.loads(checked(p,freeze['artifact_sha256'][p.name]))
            assert all(0<=x<=bound for x in losses)
            upper=min(bound,mean+bound*sqrt_upper(log/(2*len(means))))
            t=directed(min(F(1),F(1,100)/upper),False)
            assert saved['rows']==len(losses) and saved['groups']==len(means)
            assert saved['context']==context and saved['procedure']==label and saved['conditional_not_certified'] is True
            assert {g:frac(x) for g,x in saved['group_means'].items()}==means
            assert frac(saved['exact_mean'])==mean and frac(saved['bound'])==bound and frac(saved['upper'])==upper and saved['t']==t
            assert F(t)*upper<=F(1,100)
            rows.append({'context':context,'procedure':label,'rows':len(losses),'groups':len(means),'mean':float(mean),'bound':float(bound),'upper':float(upper),'t':t,'exact_comparisons_pass':True})
    assert len(rows)==32
    return {'status':'PASS','freeze_sha256':PIN,'source_sha256':sha(__file__),'scalar_count':32,'role_contexts':16,'calibration_rows_repeated':total,'target_member_materializations':16,'comparison':'exact Fraction equality for every group mean, mean, B, U and binary64 t','records':rows,'audit_member_access':OPENED,'scope':'Fixed-experiment validation, not independent generalization or a new calibrator.'}
if __name__=='__main__':
    out=HERE/'SCALAR_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'SCALAR_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k not in ['records','audit_member_access']},indent=2))
