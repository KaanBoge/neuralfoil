"""Score-only validation; no calibration targets or typed scoring frame."""
import json,io,zipfile,collections,traceback,time
from fractions import Fraction as F
import numpy as np
import pandas as pd
from audit_kl_calibration import HERE,P,checked,sha
import audit_scalars as h
PIN='ff0604357bdda4a321424380c77362c1e22a419979a798ba118b0865a98eb104'
def main():
    start=time.monotonic();rec=json.loads(checked(P/'score/COMPLETE.json',PIN));cal=json.loads(checked(P/'calibrate/COMPLETE.json',rec['predecessor_sha256']))
    assert cal['finished_UTC']<rec['started_UTC'];assert len(rec['outputs'])==36
    freeze=json.loads(checked(P/'IMPLEMENTATION_FREEZE_v2.json',rec['implementation_sha256']))
    for n,s in freeze['source_sha256'].items():checked(P/n,s)
    for n,s in freeze['external_source_sha256'].items():checked(n,s)
    app=json.loads(checked(P/'ROOT_SCORE_APPROVAL.json',rec['approval_sha256']));assert app['authorized_phases']==['score']
    for n,s in rec['outputs'].items():checked(P/'score'/n,s)
    for n,s in cal['outputs'].items():checked(P/'calibrate'/n,s)
    arc=P.parent/'range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip';a=zipfile.ZipFile(io.BytesIO(checked(arc,rec['archive_sha256'])))
    mn=next(n for n in a.namelist() if n.endswith('manifest.json'));prefix=mn[:-13];raw=a.read(mn);assert sha(raw)==rec['manifest_sha256'];man=json.loads(raw)['files']
    def member(n):
        raw=a.read(prefix+n);assert sha(raw)==man[n]['sha256'];return raw
    contexts=json.loads((P/'preflight/REFERENCE_PASS.json').read_bytes())['native_contexts'];labels=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001'];keys=['indices','BASE_CD','core','anchor','gate'];total=0;fallback=0
    for context in contexts:
        with np.load(io.BytesIO(member('native/'+context+'.npz')),allow_pickle=False) as z:v={k:z[k].copy() for k in keys}
        name='inference_'+context+'.npz'
        with np.load(io.BytesIO(checked(P/'score'/name,rec['outputs'][name])),allow_pickle=False) as z:got={k:z[k].copy() for k in z.files}
        for k in keys:np.testing.assert_array_equal(got[k],v[k])
        total+=len(v['indices']);fallback+=int((~v['gate']).sum())
        for label in labels:
            sc='final' if context in ['SG_exposed','W_new_challenge'] else context;n=f'calibrator_{label}_{sc}.json';model=json.loads(checked(P/'calibrate'/n,cal['outputs'][n]));t=F(model['t']);exp=[];eff=[]
            for b,c,an,g in zip(v['BASE_CD'],v['core'],v['anchor'],v['gate']):
                c,an=F(float(c)),F(float(an));p=h.directed(an+t*(c-an),c<an) if g and c!=an else float(an) if g else float(b)
                theta=(F(p)-an)/(c-an) if g and c!=an else F(0);assert 0<=theta<=t;exp.append(p);eff.append(float(theta))
            np.testing.assert_array_equal(got[label],exp);np.testing.assert_array_equal(got[label+'__effective_fraction'],eff)
            np.testing.assert_array_equal(got[label+'__strength'],np.where(v['gate'],.5+.5*float(t),0.));np.testing.assert_array_equal(got[label+'__intervened'],abs(np.array(exp)-v['anchor'])>1e-12)
            np.testing.assert_array_equal(got[label][~v['gate']],v['BASE_CD'][~v['gate']])
        if context!='final':
            n=f'predictions_{context}.csv';f=pd.read_csv(io.BytesIO(checked(P/'score'/n,rec['outputs'][n])))
            for k in f:
                assert k not in ['MEAS_CD','measured_CD']
                if k=='nf2_row_id':
                    role=json.loads(member('roles/'+context+'.json'));np.testing.assert_array_equal(f[k],role['test_nf2_row_ids'])
                elif got[k].dtype.kind in 'biu':np.testing.assert_array_equal(f[k],got[k])
                else:np.testing.assert_allclose(f[k],got[k],atol=1e-13,rtol=0)
    e=rec['archive_materializations'];assert len(e)==106
    for x in e:assert x['sha256']==man[x['file']]['sha256']
    assert collections.Counter((x['file'],x['member']) for x in e if x['operation']=='NPZ member')==collections.Counter((f'native/{c}.npz',k) for c in contexts for k in keys)
    assert collections.Counter(x['file'] for x in e if x['operation']=='JSON parse')==collections.Counter(['inventory.json']+[f'roles/{c}.json' for c in contexts if c not in ['final','SG_exposed','W_new_challenge']])
    reads=rec['phase_file_reads'];assert len(reads)==36 and len(set(x['path'] for x in reads))==32
    for x in reads:
        from pathlib import Path
        path=Path(x['path']);assert path.parent==P/'calibrate';raw=checked(path,x['sha256']);assert len(raw)==x['bytes'] and x['parser']=='JSON parse';assert x['sha256']==cal['outputs'][path.name]
    assert total==38227 and fallback==25
    return {'status':'PASS','complete_sha256':PIN,'native_contexts':18,'rows_repeated':total,'exact_candidate_values':total*2,'fallback_rows_each':fallback,'CSV_files':17,'output_pins':36,'archive_events':106,'scalar_parses':36,'unique_scalars':32,'seconds':time.monotonic()-start,'scope':'score-only; exact native predictions, inherited1e-13 CSV tolerance; no scoring targets/assessment'}
if __name__=='__main__':
    out=HERE/'KL_SCORE_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'KL_SCORE_AUDIT_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
