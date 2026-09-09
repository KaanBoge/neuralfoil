"""Calibration-only independent rational replay; never opens scoring arrays."""
from pathlib import Path
from fractions import Fraction as F
import json,hashlib,zipfile,io,time,traceback,collections,sys
import numpy as np
import audit_kl_illustration as k
sys.path.insert(0,str(Path(__file__).resolve().parent/'stage1_v2_audit'))
import audit_scalars as h
HERE=Path(__file__).resolve().parent;P=HERE.parents[1]/'model_proposal/kl_bound_study'
PIN='c3ea8ba1f3d5dc7f1aa0914db96e61a47052d4d67aaf93fce7efde2361f4b0b0'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def checked(p,s):
    raw=Path(p).read_bytes();assert sha(raw)==s,str(p);return raw
def main():
    start=time.monotonic();rec=json.loads(checked(P/'calibrate/COMPLETE.json',PIN))
    freeze=json.loads(checked(P/'IMPLEMENTATION_FREEZE_v2.json',rec['implementation_sha256']))
    for n,s in freeze['source_sha256'].items():checked(P/n,s)
    for n,s in freeze['external_source_sha256'].items():checked(n,s)
    app=json.loads(checked(P/'ROOT_CALIBRATION_APPROVAL.json',rec['approval_sha256']));assert app['authorized_phases']==['calibrate']
    pre=json.loads(checked(P/'preflight/COMPLETE.json',rec['predecessor_sha256']))
    assert pre['finished_UTC']<rec['started_UTC']
    for n,s in pre['outputs'].items():checked(P/'preflight'/n,s)
    assert len(rec['outputs'])==49
    for n,s in rec['outputs'].items():checked(P/'calibrate'/n,s)
    arc=P.parent/'range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
    raw=checked(arc,rec['archive_sha256']);z=zipfile.ZipFile(io.BytesIO(raw))
    mn=next(n for n in z.namelist() if n.endswith('manifest.json'));prefix=mn[:-len('manifest.json')]
    mr=z.read(mn);assert sha(mr)==rec['manifest_sha256'];manifest=json.loads(mr)['files'];opened=[]
    def member(n):
        b=z.read(prefix+n);assert sha(b)==manifest[n]['sha256'];opened.append(n);return b
    def meta(n):return k.decode(json.loads(member(n)))
    inventory=meta('inventory.json');cert=meta('certificates/STAGE0_CERTIFICATE.json')
    contexts=list(json.loads((P/'preflight/REFERENCE_PASS.json').read_bytes())['contexts'])
    ev=rec['archive_materializations'];assert len(ev)==178
    npze=[e for e in ev if e['operation']=='NPZ member'];jse=[e for e in ev if e['operation']=='JSON parse']
    assert len(npze)==128 and len(jse)==50
    for e in ev:assert e['sha256']==manifest[e['file']]['sha256']
    fields=['indices','BASE_CD','core','anchor','gate','MEAS_CD','group','nf2_row_id']
    assert collections.Counter((e['file'],e['member']) for e in npze)==collections.Counter((f'calibration/{c}.npz',f) for c in contexts for f in fields)
    assert not rec['phase_file_reads'] and rec['end_provenance_reauthenticated']
    cr={r['context']:r for r in cert['records']};log=h.log_upper();loglo,loghi=k.log_interval(F(20));records=[];total=0
    for context in contexts:
        role=meta('roles/'+context+'.json');saved=json.loads((P/'calibrate'/f'membership_{context}.json').read_bytes());assert role==saved
        for names in [('proper_groups','calibration_groups','test_groups'),('proper_indices','calibration_indices','test_indices')]:
            sets=[set(role[n]) for n in names];assert all(not sets[i]&sets[j] for i in range(3) for j in range(i))
            assert all(len(role[n])==len(set(role[n])) for n in names)
        assert role['post_calibration_refit'] is False
        with np.load(io.BytesIO(member('calibration/'+context+'.npz')),allow_pickle=False) as a:v={f:a[f].copy() for f in fields}
        np.testing.assert_array_equal(v['indices'],role['calibration_indices']);np.testing.assert_array_equal(v['nf2_row_id'],role['calibration_nf2_row_ids'])
        groups=v['group'].astype(str);assert set(groups)==set(role['calibration_groups'])
        assert v['gate'].dtype==bool
        for name in ['core','anchor']:np.testing.assert_array_equal(v[name][~v['gate']],v['BASE_CD'][~v['gate']])
        losses=[max(abs(F(float(c))-F(float(y)))-abs(F(float(a))-F(float(y))),F(0))/F(float(b)) for b,c,a,y in zip(v['BASE_CD'],v['core'],v['anchor'],v['MEAS_CD'])]
        means={g:sum((losses[i] for i in np.flatnonzero(groups==g)),F(0))/int((groups==g).sum()) for g in np.unique(groups)}
        m=len(means);mean=sum(means.values(),F(0))/m;total+=len(losses)
        u=F(1,2**53);e=4*u+2*u*u;clip=lambda x:max(F(-1,2),min(F(1),x))
        bs=max(abs(clip(clip(h.frac(cr[context]['range']['lower']))-e)),abs(clip(clip(h.frac(cr[context]['range']['upper']))+e)))/2+3*u/2
        assert bs==h.frac(cr[context]['B_structural'])
        for kind,B in [('structural',bs),('generic',F(1,2)+3*u/2)]:
            label=f'qualified_{kind}_kl_harm_001';s=k.decode(json.loads((P/'calibrate'/f'calibrator_{label}_{context}.json').read_bytes()))
            old=meta(f'scalars/qualified_{kind}_harm_001_{context}.json')
            assert s['group_means']==means and s['exact_mean']==mean and s['bound']==B and s['groups']==m and s['rows']==len(losses)
            assert all(0<=x<=B for x in losses)
            H=min(B,mean+B*h.sqrt_upper(log/(2*m)));th=k.down(min(F(1),F(1,100)/H))
            assert s['matched_hoeffding_upper']==H==old['upper'] and s['matched_hoeffding_t']==th==old['t']
            assert old['group_means']==means and old['exact_mean']==mean and old['bound']==B
            w=s['root_witness'];r=w['root_at_upward_mean'];q=mean/B;qu=F((q.numerator*2**128+q.denominator-1)//q.denominator,2**128)
            assert r['q_exact']==q and r['q_upper']==qu and r['q_rounding_gap']==qu-q and r['groups']==m
            assert r['budget_lower']==loglo/m and r['budget_upper']==loghi/m
            lo,hi=r['lower'],r['upper'];assert qu<=lo<=hi<=1
            li=k.kl_interval(qu,lo);assert list(li)==r['lower_kl_interval'] and li[1]<=loglo/m
            if hi<1:
                ui=k.kl_interval(qu,hi);assert list(ui)==r['upper_kl_interval'] and ui[0]>=loghi/m
            else:assert r['upper_kl_interval'] is None
            assert w['mean_exact']==mean and w['kl_upper_before_hoeffding_min']==B*hi
            assert w['lower_endpoint_scope']=='root_at_q_upper_only' and w['upper_endpoint_scope']=='conservative_for_q_exact'
            U=min(B*hi,H);t=k.down(min(F(1),F(1,100)/U))
            assert s['upper']==U and s['t']==t and U<=H and t>=th and F(t)*U<=F(1,100)
            assert s['conditional_not_certified'] is True
            records.append({'context':context,'candidate':label,'groups':m,'rows':len(losses),'t':t,'matched_t':th,'exact_checks':'PASS'})
    expectedjson=['inventory.json','certificates/STAGE0_CERTIFICATE.json']+[f'roles/{c}.json' for c in contexts]+[f'scalars/qualified_{t}_harm_001_{c}.json' for c in contexts for t in ['structural','generic']]
    assert collections.Counter(e['file'] for e in jse)==collections.Counter(expectedjson)
    for n,s in rec['outputs'].items():checked(P/'calibrate'/n,s)
    return {'status':'PASS','complete_sha256':PIN,'scalars':len(records),'role_contexts':len(contexts),'calibration_row_instances':total,'source_output_pins':49,'event_counts':{'NPZ':128,'MEAS_CD':16,'JSON':50},'seconds':time.monotonic()-start,'records':records,'opened_archive_files':opened,'scope':'calibration validation only; no root bisection rerun, scoring frame, features, model fits or new candidate'}
if __name__=='__main__':
    out=HERE/'KL_CALIBRATION_QA.json';assert not out.exists()
    try:result=main()
    except BaseException:
        with (HERE/'KL_CALIBRATION_AUDIT_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ['records','opened_archive_files']},indent=2))
