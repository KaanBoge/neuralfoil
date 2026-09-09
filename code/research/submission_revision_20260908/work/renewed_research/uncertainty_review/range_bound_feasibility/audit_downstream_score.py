"""Independent prediction-only replay; no calibration/scoring targets or producer calls."""
import json,io,zipfile,collections,time,traceback,hashlib
from fractions import Fraction as F
import numpy as np
import pandas as pd
from audit_downstream_calibration import HERE,ROOT,P,read,obj,h
PIN='4c8ae022383787196fe5ed7522f8c9dcbe9d06bd0737a035d9773521d7f72726'
def main():
    start=time.monotonic();rec=obj(P/'score/COMPLETE.json',PIN)
    assert not (P/'score/FAILURE.json').exists() and read(P/'score/COMPLETE.pending.json')==read(P/'score/COMPLETE.json')
    cal=obj(P/'calibrate/COMPLETE.json',rec['summary']['predecessor_sha256']);assert cal['finish_utc']<rec['start_utc']
    assert rec['summary']['predecessor_sha256']=='4429be8179cbc28aba09fbe6599af53d74dd0e9536ac34f9b3eb3b2e3973150f'
    reg=obj(P/'REGISTRY.json',rec['registry_sha256']);assert rec['registry_sha256']=='f55a993c6b9029db25bb53e0329d84f8f6f4b4efdb14107ceabd7af5b82b2b17'
    for n,s in reg['sources'].items():read(P/n,s)
    for n,s in reg['external_sources'].items():read(ROOT/n,s)
    ap=obj(P/'ROOT_SCORE_APPROVAL.json',rec['approval_sha256']);assert rec['approval_sha256']=='e57f6b9f8db8ca8495a1c053e376930bb6c001d81545ea308fc4b63bce676635'
    assert ap['actual_execution_authorized'] and ap['phase']=='score' and ap['workers']==1 and ap['seconds']==900 and rec['seconds']<900
    assert ap['registry_sha256']==rec['registry_sha256'] and ap['predecessor_sha256']==rec['summary']['predecessor_sha256']
    assert len(rec['outputs'])==37
    for n,s in rec['outputs'].items():read(P/'score'/n,s)
    for n,s in cal['outputs'].items():read(P/'calibrate'/n,s)
    access=obj(P/'score/ACCESS.json');pins={}
    for e in access:
        if 'path' in e and 'sha256' in e:
            assert e['path'] not in pins or pins[e['path']]==e['sha256'];pins[e['path']]=e['sha256']
    for p,s in pins.items():read(p,s)
    arc=ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
    z=zipfile.ZipFile(io.BytesIO(read(arc,'673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3')))
    mn=next(n for n in z.namelist() if n.endswith('manifest.json'));prefix=mn[:-13];raw=z.read(mn);assert hashlib.sha256(raw).hexdigest()=='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154';man=json.loads(raw)['files'];opened=[]
    def member(n):
        assert n=='inventory.json' or n.startswith(('native/','roles/'))
        b=z.read(prefix+n);assert hashlib.sha256(b).hexdigest()==man[n]['sha256'];opened.append(n);return b
    info=json.loads(member('inventory.json'));contexts=info['native_contexts'];assert len(contexts)==18 and set(contexts)==set(reg['contexts']+['SG_exposed','W_new_challenge'])
    labels=['qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001'];keys=['indices','BASE_CD','core','anchor','gate'];total=0;fallback=0;csvrows=0;maxcsv=0.;records=[]
    for ctx in contexts:
        assert time.monotonic()-start<900
        with np.load(io.BytesIO(member('native/'+ctx+'.npz')),allow_pickle=False) as a:v={k:a[k].copy() for k in keys}
        n='inference_'+ctx+'.npz'
        with np.load(io.BytesIO(read(P/'score'/n,rec['outputs'][n])),allow_pickle=False) as a:got={k:a[k].copy() for k in a.files}
        expected=set(keys+['qualified_gate']+[l+s for l in labels for s in ['', '__effective_fraction','__strength','__intervened']]);assert set(got)==expected
        for k in keys:assert got[k].dtype==v[k].dtype;np.testing.assert_array_equal(got[k],v[k])
        assert v['gate'].dtype==bool;np.testing.assert_array_equal(got['qualified_gate'],v['gate'])
        for k in ['BASE_CD','core','anchor']:assert np.isfinite(v[k]).all()
        total+=len(v['indices']);nf=int((~v['gate']).sum());fallback+=nf
        role=None
        if ctx not in ['final','SG_exposed','W_new_challenge']:
            role=json.loads(member('roles/'+ctx+'.json'));np.testing.assert_array_equal(v['indices'],role['test_indices'])
        for label in labels:
            sc='final' if ctx in ['SG_exposed','W_new_challenge'] else ctx;n=f'calibrator_{label}_{sc}.json';s=obj(P/'calibrate'/n,cal['outputs'][n]);assert s['candidate']==label and s['context']==sc
            t=F(s['t']);assert 0<=t<=1;exp=[];eff=[]
            for b,c,an,g in zip(v['BASE_CD'],v['core'],v['anchor'],v['gate']):
                c,an=F(float(c)),F(float(an));p=h.directed(an+t*(c-an),c<an) if g and c!=an else float(an) if g else float(b)
                theta=(F(p)-an)/(c-an) if g and c!=an else F(0);assert 0<=theta<=t
                exp.append(p);eff.append(float(theta))
            np.testing.assert_array_equal(got[label],exp);np.testing.assert_array_equal(got[label+'__effective_fraction'],eff)
            np.testing.assert_array_equal(got[label+'__strength'],np.where(v['gate'],.5+.5*float(t),0.));np.testing.assert_array_equal(got[label+'__intervened'],abs(np.array(exp)-v['anchor'])>1e-12)
            np.testing.assert_array_equal(got[label][~v['gate']],v['BASE_CD'][~v['gate']])
        if ctx!='final':
            n=f'predictions_{ctx}.csv';f=pd.read_csv(io.BytesIO(read(P/'score'/n,rec['outputs'][n])),low_memory=False)
            cols=['indices','BASE_CD','qualified_gate']+[l+s for l in labels for s in ['', '__effective_fraction','__strength','__intervened']]+(['nf2_row_id'] if role else [])
            assert list(f)==cols;csvrows+=len(f)
            for k in f:
                if k=='nf2_row_id':np.testing.assert_array_equal(f[k],role['test_nf2_row_ids'])
                elif got[k].dtype.kind in 'biu':np.testing.assert_array_equal(f[k],got[k])
                else:
                    d=np.max(abs(f[k].to_numpy()-got[k]));maxcsv=max(maxcsv,float(d));np.testing.assert_allclose(f[k],got[k],atol=1e-13,rtol=0)
        records.append({'context':ctx,'rows':len(v['indices']),'fallback_rows_per_candidate':nf,'prediction_and_effective_fraction_exact':True})
    ne=[e for e in access if e.get('operation')=='NPZ materialization']
    assert collections.Counter((e['origin'],e['file'],e['member']) for e in ne)==collections.Counter(('parent',f'native/{c}.npz',k) for c in contexts for k in keys)
    for e in ne:assert e['sha256']==man[e['file']]['sha256']
    je=[e for e in access if e.get('operation')=='JSON parse' and 'origin' in e]
    assert collections.Counter((e['origin'],e['member']) for e in je)==collections.Counter([('parent','inventory.json')]+[('parent',f'roles/{c}.json') for c in contexts if c not in ['final','SG_exposed','W_new_challenge']])
    for e in je:assert e['sha256']==man[e['member']]['sha256']
    se=[e for e in access if e.get('operation')=='JSON parse' and str(e.get('identity','')).startswith('calibrate/')]
    expected=[f'calibrate/calibrator_{l}_{"final" if c in ["SG_exposed","W_new_challenge"] else c}.json' for c in contexts for l in labels]
    assert collections.Counter(e['identity'] for e in se)==collections.Counter(expected)
    for e in se:assert e['sha256']==cal['outputs'][e['identity'].split('/')[-1]]
    assert not any(e.get('member')=='MEAS_CD' or e.get('operation')=='pandas.read_csv' for e in access)
    assert total==38227 and csvrows==29856 and fallback==25
    for n,s in rec['outputs'].items():read(P/'score'/n,s)
    used=sum(x.stat().st_size for n in reg['output_roots'] for x in (ROOT/n).rglob('*') if x.is_file());assert used<reg['logical_cap']-reg['failure_reserve']
    return {'status':'PASS_PREDICTION_ONLY_EXACT_REPLAY','complete_sha256':PIN,'audit_sha256':hashlib.sha256(read(__file__)).hexdigest(),'producer_seconds':rec['seconds'],'audit_seconds':time.monotonic()-start,'native_contexts':18,'native_repeated_rows':total,'exact_candidate_values':total*2,'exact_effective_fraction_values':total*2,'CSV_files':17,'CSV_rows':csvrows,'CSV_max_absolute_parser_difference':maxcsv,'fallback_rows_per_candidate':fallback,'output_pins':37,'events':len(access),'unique_path_pins':len(pins),'NPZ_members':90,'archive_JSON_parses':16,'scalar_parses':36,'unique_scalars':32,'logical_bytes_at_audit':used,'records':records,'reviewer_archive_members':opened,'scope':'No calibration targets, scoring targets, fits, new core inference or producer/scoring rerun. CSV tolerance inherited1e-13; native exact. Separate assessment approval required.'}
if __name__=='__main__':
    out=HERE/'DOWNSTREAM_SCORE_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/('DOWNSTREAM_SCORE_FAILURE_'+str(time.time_ns())+'.txt')).open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k not in ['records','reviewer_archive_members']},indent=2))
