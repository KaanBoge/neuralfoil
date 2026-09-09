"""Independent calibration-only exact replay; no producer imports or scoring reads."""
from pathlib import Path
from fractions import Fraction as F
import json,hashlib,zipfile,io,collections,time,traceback,sys
import numpy as np
import audit_kl_illustration as k
sys.path.insert(0,str(Path(__file__).resolve().parent/'stage1_v2_audit'))
import audit_scalars as h
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
P=ROOT/'model_proposal/paired_tree_plan/all_context_downstream_plan'
PIN='4429be8179cbc28aba09fbe6599af53d74dd0e9536ac34f9b3eb3b2e3973150f'
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p,pin=None):
    b=Path(p).read_bytes()
    if pin:assert sha(b)==pin,str(p)
    return b
def obj(p,pin=None):return json.loads(read(p,pin))
def main():
    start=time.monotonic();rec=obj(P/'calibrate/COMPLETE.json',PIN)
    assert read(P/'calibrate/COMPLETE.pending.json')==read(P/'calibrate/COMPLETE.json')
    assert not (P/'calibrate/FAILURE.json').exists() and rec['seconds']<900
    reg=obj(P/'REGISTRY.json',rec['registry_sha256']);assert rec['registry_sha256']=='f55a993c6b9029db25bb53e0329d84f8f6f4b4efdb14107ceabd7af5b82b2b17'
    for n,pin in reg['sources'].items():read(P/n,pin)
    for n,pin in reg['external_sources'].items():read(ROOT/n,pin)
    ap=obj(P/'ROOT_CALIBRATE_APPROVAL.json',rec['approval_sha256'])
    assert rec['approval_sha256']=='38c13a84e1055a772a4a8b8bad52583001748f210decfc946d6d22675d123795'
    assert ap['phase']=='calibrate' and ap['registry_sha256']==rec['registry_sha256']
    assert ap['predecessor_sha256']==rec['summary']['predecessor_sha256']
    pre=obj(P/'preflight/COMPLETE.json',ap['predecessor_sha256']);assert pre['finish_utc']<rec['start_utc']
    for n,pin in pre['outputs'].items():read(P/'preflight'/n,pin)
    assert len(rec['outputs'])==50
    for n,pin in rec['outputs'].items():read(P/'calibrate'/n,pin)
    access=obj(P/'calibrate/ACCESS.json');pins={}
    for e in access:
        if 'path' in e and 'sha256' in e:
            assert e['path'] not in pins or pins[e['path']]==e['sha256'];pins[e['path']]=e['sha256']
    for p,pin in pins.items():read(p,pin)
    contexts=reg['contexts'];fields=['indices','BASE_CD','core','anchor','gate','group','nf2_row_id','MEAS_CD']
    events=[e for e in access if e.get('operation')=='NPZ materialization']
    assert collections.Counter((e['origin'],e['file'],e['member']) for e in events)==collections.Counter(('parent',f'calibration/{c}.npz',f) for c in contexts for f in fields)
    assert not any(e.get('operation')=='pandas.read_csv' or str(e.get('file','')).startswith(('native/','scoring/')) for e in access)
    opened=[]
    def archive(path,pin,manifestpin):
        z=zipfile.ZipFile(io.BytesIO(read(path,pin)));mn=next(n for n in z.namelist() if n.endswith('manifest.json'));prefix=mn[:-13]
        raw=z.read(mn);assert sha(raw)==manifestpin;manifest=json.loads(raw)['files']
        def member(n):
            assert n.startswith(('calibration/','roles/','scalars/'))
            b=z.read(prefix+n);assert sha(b)==manifest[n]['sha256'];opened.append({'archive':path.name,'member':n});return b
        return member,manifest
    parent,pm=archive(ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip','673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3','3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154')
    addon,am=archive(ROOT/'model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip','45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b','dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d')
    for e in events:assert e['sha256']==pm[e['file']]['sha256']
    refs=k.decode(obj(P/'preflight/REFERENCE_PASS.json'));records=[];total=0
    log=h.log_upper();loglo,loghi=k.log_interval(F(20))
    def check_scalar(s,B,mean,means,rows,kind):
        m=len(means);assert s['group_means']==means and s['exact_mean']==mean and s['bound']==B and s['rows']==rows and s['groups']==m
        H=min(B,mean+B*h.sqrt_upper(log/(2*m)));th=k.down(min(F(1),F(1,100)/H))
        U=H
        if kind=='KL':
            assert s['matched_hoeffding_upper']==H and s['matched_hoeffding_t']==th
            w=s['root_witness'];r=w['root_at_upward_mean'];q=mean/B;qu=F((q.numerator*2**128+q.denominator-1)//q.denominator,2**128)
            assert r['q_exact']==q and r['q_upper']==qu and r['q_rounding_gap']==qu-q and r['groups']==m
            assert r['budget_lower']==loglo/m and r['budget_upper']==loghi/m
            lo,hi=r['lower'],r['upper'];assert qu<=lo<=hi<=1
            assert r['iterations']==64 and r['stop']=='step_limit' and hi-lo==(1-qu)/2**64
            li=k.kl_interval(qu,lo);assert list(li)==r['lower_kl_interval'] and li[1]<=loglo/m
            if hi<1:
                ui=k.kl_interval(qu,hi);assert list(ui)==r['upper_kl_interval'] and ui[0]>=loghi/m
            else:assert r['upper_kl_interval'] is None
            assert w['mean_exact']==mean and w['kl_upper_before_hoeffding_min']==B*hi
            assert w['lower_endpoint_scope']=='root_at_q_upper_only' and w['upper_endpoint_scope']=='conservative_for_q_exact'
            U=min(B*hi,H)
        t=k.down(min(F(1),F(1,100)/U))
        assert s['upper']==U and s['t']==t and F(t)*U<=F(1,100)
        if kind=='KL':assert s['conditional_not_certified'] is True
        return U,t
    for ctx in contexts:
        assert time.monotonic()-start<900
        role=json.loads(parent('roles/'+ctx+'.json'));assert role==obj(P/'calibrate'/f'membership_{ctx}.json')
        for names in [('proper_groups','calibration_groups','test_groups'),('proper_indices','calibration_indices','test_indices')]:
            sets=[set(role[n]) for n in names];assert all(not sets[i]&sets[j] for i in range(3) for j in range(i));assert all(len(role[n])==len(set(role[n])) for n in names)
        assert role['post_calibration_refit'] is False
        with np.load(io.BytesIO(parent('calibration/'+ctx+'.npz')),allow_pickle=False) as z:v={f:z[f].copy() for f in fields}
        np.testing.assert_array_equal(v['indices'],role['calibration_indices']);np.testing.assert_array_equal(v['nf2_row_id'],role['calibration_nf2_row_ids'])
        groups=v['group'].astype(str);assert set(groups)==set(role['calibration_groups']) and v['gate'].dtype==bool
        for f in ['BASE_CD','core','anchor','MEAS_CD']:assert np.isfinite(v[f]).all()
        assert (v['BASE_CD']>0).all()
        for f in ['core','anchor']:np.testing.assert_array_equal(v[f][~v['gate']],v['BASE_CD'][~v['gate']])
        losses=[max(abs(F(float(c))-F(float(y)))-abs(F(float(a))-F(float(y))),F(0))/F(float(b)) for b,c,a,y in zip(v['BASE_CD'],v['core'],v['anchor'],v['MEAS_CD'])]
        means={g:sum((losses[i] for i in np.flatnonzero(groups==g)),F(0))/int((groups==g).sum()) for g in np.unique(groups)}
        mean=sum(means.values(),F(0))/len(means);total+=len(losses)
        B=refs['bounds'][ctx]['D'];B0=refs['bounds'][ctx]['Stage0'];assert 0<B<B0 and max(losses)<=B
        for kind,newlabel,oldlabel,reader in [('H','qualified_paired_D_harm_001','qualified_structural_harm_001',parent),('KL','qualified_paired_D_kl_harm_001','qualified_structural_kl_harm_001',addon)]:
            s=k.decode(obj(P/'calibrate'/f'calibrator_{newlabel}_{ctx}.json'));old=k.decode(json.loads(reader(f'scalars/{oldlabel}_{ctx}.json')))
            assert s['candidate']==newlabel and s['context']==ctx
            U,t=check_scalar(s,B,mean,means,len(losses),kind);U0,t0=check_scalar(old,B0,mean,means,len(losses),kind)
            records.append({'context':ctx,'kind':kind,'rows':len(losses),'groups':len(means),'B':float(B),'Stage0_B':float(B0),'max_loss':float(max(losses)),'mean':float(mean),'U':float(U),'Stage0_U':float(U0),'t':t,'Stage0_t':t0,'tU':float(F(t)*U),'Stage0_tU':float(F(t0)*U0),'U_decreased_exact':U<U0,'t_increased_exact':F(t)>F(t0),'t_decreased_exact':F(t)<F(t0),'tU_change_exact_sign':(F(t)*U>F(t0)*U0)-(F(t)*U<F(t0)*U0)})
    for n,pin in rec['outputs'].items():read(P/'calibrate'/n,pin)
    used=sum(x.stat().st_size for n in reg['output_roots'] for x in (ROOT/n).rglob('*') if x.is_file());assert used<reg['logical_cap']-reg['failure_reserve']
    return {'status':'PASS_CALIBRATION_ONLY_EXACT_AUDIT','complete_sha256':PIN,'audit_sha256':sha(read(__file__)),'producer_seconds':rec['seconds'],'audit_seconds':time.monotonic()-start,'outputs':50,'contexts':16,'new_scalars':32,'old_scalars':32,'calibration_row_instances':total,'events':len(access),'unique_path_pins':len(pins),'NPZ_members':128,'MEAS_CD_members':16,'current_logical_bytes':used,'records':records,'opened_archive_files':opened,'scope':'Exact saved endpoints independently verified, no 64-step root rerun; calibration-only arrays, no scoring/fit/search; separate score approval required.'}
if __name__=='__main__':
    out=HERE/'DOWNSTREAM_CALIBRATION_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        failure=HERE/'DOWNSTREAM_CALIBRATION_FAILURE.txt'
        if failure.exists():failure=HERE/('DOWNSTREAM_CALIBRATION_FAILURE_'+str(time.time_ns())+'.txt')
        with failure.open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k not in ['records','opened_archive_files']},indent=2))
