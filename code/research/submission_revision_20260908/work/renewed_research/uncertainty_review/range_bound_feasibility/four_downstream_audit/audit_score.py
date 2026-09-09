"""Saved prediction-only audit. Explicit binding+digest; no automatic intake."""
import json,io,zipfile,hashlib,time,signal,sys
from pathlib import Path
from collections import Counter
import audit_common as ac
import score_math as sm
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
P=ROOT/'model_proposal/four_tree_matching_plan/downstream_plan'
REG='39db3eb801e654dda6c7787612cbd94d2b7d664f7fbefb9b42f7bcf874a725d2'
PRE='96f1ecb56362ad9902bf9412d26c1cda4e6da5fbc9b058ef302bae9c5a392843'
ARC=ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
ARC_SHA='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
MAN_SHA='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
KEYS=['indices','BASE_CD','core','anchor','gate'];EXT=('SG_exposed','W_new_challenge')
SUFFIXES=('','__effective_fraction','__strength','__intervened')
def main(binding_path,binding_sha):
    bp=Path(binding_path)
    if not ac.pin(binding_sha) or any(p.is_symlink() for p in (bp,*bp.parents)) or bp.stat().st_size>4096:raise ValueError('small explicit binding')
    raw=bp.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=binding_sha:raise ValueError('binding SHA')
    b=ac.json_unique(raw);a=ac.Access(b)
    if b['phase']!='score' or b['registry_sha256']!=REG or b['predecessor_sha256']==PRE:raise ValueError('score calibration predecessor required')
    out=HERE/'score_attempt_1';out.mkdir(exist_ok=False);start=time.monotonic();z=None
    def obj(path,pin):return ac.json_unique(a.read(path,pin,64*2**20))
    def stream(path,pin):
        p=Path(path)
        if not ac.pin(pin) or any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('stream pin/path')
        if str(p) in a.inputs and a.inputs[str(p)]!=pin:raise ValueError('conflicting input pin')
        h=hashlib.sha256();n=0
        with p.open('rb') as f:
            while block:=f.read(65536):a.tick();h.update(block);n+=len(block)
        if h.hexdigest()!=pin:raise ValueError('stream bytes')
        a.inputs[str(p)]=pin;a.events.append({'operation':'stream hash only','path':str(p),'sha256':pin,'bytes':n})
    try:
        a.read(bp,binding_sha,4096)
        sources={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('audit_score.py','score_math.py','audit_common.py')}
        for n,pin in sources.items():a.read(HERE/n,pin)
        rec=a.receipt(a.read(P/'score/COMPLETE.json',b['complete_sha256']))
        reg=obj(P/'REGISTRY.json',REG);ap=obj(P/'ROOT_SCORE_APPROVAL.json',b['approval_sha256'])
        assert ap['phase']=='score' and ap['actual_execution_authorized'] is True and ap['registry_sha256']==REG and ap['predecessor_sha256']==b['predecessor_sha256'] and ap['seconds']==900 and ap['workers']==1
        assert rec['seconds']<900 and not (P/'score/FAILURE.json').exists()
        for n,pin in reg['sources'].items():a.read(P/n,pin)
        for n,pin in reg['external_sources'].items():stream(ROOT/n,pin)
        cal=obj(P/'calibrate/COMPLETE.json',b['predecessor_sha256'])
        assert cal['phase']=='calibrate' and cal['status']=='COMPLETE' and cal['registry_sha256']==REG and cal['summary']['predecessor_sha256']==PRE and cal['finish_utc']<rec['start_utc']
        cap=obj(P/'ROOT_CALIBRATE_APPROVAL.json',cal['approval_sha256'])
        assert cap['phase']=='calibrate' and cap['registry_sha256']==REG and cap['actual_execution_authorized'] is True and cap['predecessor_sha256']==PRE
        for n,pin in cal['outputs'].items():stream(P/'calibrate'/n,pin)
        contexts=reg['contexts'];assert len(contexts)==16
        scalar_names={f'calibrator_{l}_{c}.json' for l in ac.NEW for c in contexts}
        assert {n for n in cal['outputs'] if n.startswith('calibrator_')}==scalar_names
        names={'ATTEMPT.json','ACCESS.json'}|{f'inference_{c}.npz' for c in contexts+list(EXT)}|{f'predictions_{c}.csv' for c in contexts+list(EXT) if c!='final'}
        assert set(rec['outputs'])==names and len(names)==37
        for n,pin in rec['outputs'].items():stream(P/'score'/n,pin)
        events=obj(P/'score/ACCESS.json',rec['outputs']['ACCESS.json']);paths={}
        for e in events:
            if 'path' in e and 'sha256' in e:
                if e['path'] in paths:assert paths[e['path']]==e['sha256']
                paths[e['path']]=e['sha256']
        for path,pin in paths.items():stream(path,pin)
        ne=[e for e in events if e.get('operation')=='NPZ materialization']
        assert Counter((e['origin'],e['file'],e['member']) for e in ne)==Counter(('parent',f'native/{c}.npz',k) for c in contexts+list(EXT) for k in KEYS)
        assert not any(e.get('member')=='MEAS_CD' or e.get('operation')=='pandas.read_csv' or str(e.get('file','')).startswith(('calibration/','scoring/')) for e in events)
        stream(ARC,ARC_SHA);z=zipfile.ZipFile(ARC);mr=z.read('manifest.json');assert hashlib.sha256(mr).hexdigest()==MAN_SHA;man=ac.json_unique(mr)['files'];opened=[];members=[]
        def member(name):
            if name!='inventory.json' and not name.startswith(('native/','roles/')):raise ValueError('prediction-only archive member')
            raw=z.read(name);assert hashlib.sha256(raw).hexdigest()==man[name]['sha256'];opened.append({'member':name,'sha256':man[name]['sha256']});return raw
        # All source, phase and provenance authentication precedes this point.
        import numpy as np
        import pandas as pd
        def exact(x,y):
            x,y=np.asarray(x),np.asarray(y)
            assert x.dtype==y.dtype and x.shape==y.shape and x.tobytes()==y.tobytes()
        info=ac.json_unique(member('inventory.json'));cases=info['native_contexts']
        assert len(cases)==18 and len(set(cases))==18 and set(cases)==set(contexts+list(EXT))
        records=[];total=fallback=csvrows=0;maxcsv=0.;scalar_reads=[]
        for ctx in cases:
            a.tick();name='native/'+ctx+'.npz'
            with np.load(io.BytesIO(member(name)),allow_pickle=False) as ar:v={k:ar[k] for k in KEYS}
            for k,x in v.items():
                assert not x.dtype.hasobject;members.append({'origin':'parent','file':name,'member':k,'sha256':man[name]['sha256'],'shape':list(x.shape),'dtype':str(x.dtype)})
            n=len(v['BASE_CD']);assert all(x.shape==(n,) for x in v.values()) and v['gate'].dtype==bool and v['indices'].dtype.kind in 'iu' and len(set(v['indices']))==n
            for k in ('BASE_CD','core','anchor'):assert v[k].dtype==np.float64 and np.isfinite(v[k]).all() and (v[k]>0).all()
            name='inference_'+ctx+'.npz'
            with np.load(io.BytesIO(a.read(P/'score'/name,rec['outputs'][name],64*2**20)),allow_pickle=False) as ar:
                assert set(ar.files)==set(KEYS+['qualified_gate']+[l+s for l in ac.NEW for s in SUFFIXES]);got={k:ar[k] for k in ar.files}
            for k in KEYS:exact(got[k],v[k])
            exact(got['qualified_gate'],v['gate']);total+=n;nf=int((~v['gate']).sum());fallback+=nf;role=None
            if ctx not in ('final',*EXT):
                role=ac.json_unique(member('roles/'+ctx+'.json'));np.testing.assert_array_equal(v['indices'],role['test_indices'])
            for label in ac.NEW:
                sc='final' if ctx in EXT else ctx;name=f'calibrator_{label}_{sc}.json'
                s=obj(P/'calibrate'/name,cal['outputs'][name]);scalar_reads.append(name)
                assert s['candidate']==label and s['context']==sc
                values=[sm.prediction(float(b),float(c),float(h),bool(g),s['t']) for b,c,h,g in zip(v['BASE_CD'],v['core'],v['anchor'],v['gate'])]
                pred=np.array([x[0] for x in values],dtype=np.float64);effective=np.array([x[1] for x in values],dtype=np.float64)
                exact(got[label],pred);exact(got[label+'__effective_fraction'],effective)
                exact(got[label+'__strength'],np.where(v['gate'],.5+.5*s['t'],0.))
                exact(got[label+'__intervened'],abs(pred-v['anchor'])>1e-12)
                exact(pred[~v['gate']],v['BASE_CD'][~v['gate']])
            if ctx!='final':
                name='predictions_'+ctx+'.csv'
                frame=pd.read_csv(io.BytesIO(a.read(P/'score'/name,rec['outputs'][name],64*2**20)),low_memory=False)
                cols=['indices','BASE_CD','qualified_gate']+[l+s for l in ac.NEW for s in SUFFIXES]+(['nf2_row_id'] if role else [])
                assert list(frame)==cols and len(frame)==n;csvrows+=n
                for k in cols:
                    if k=='nf2_row_id':np.testing.assert_array_equal(frame[k],role['test_nf2_row_ids'])
                    elif got[k].dtype.kind in 'biu':exact(frame[k].to_numpy(),got[k])
                    else:
                        assert np.isfinite(frame[k]).all();delta=float(np.max(abs(frame[k].to_numpy()-got[k])));maxcsv=max(maxcsv,delta)
                        np.testing.assert_allclose(frame[k],got[k],atol=1e-13,rtol=0)
            records.append({'context':ctx,'rows':n,'fallback_rows_per_candidate':nf,'prediction_and_effective_fraction_bit_exact':True})
        assert members==[{k:e[k] for k in ('origin','file','member','sha256','shape','dtype')} for e in ne]
        je=[e for e in events if e.get('operation')=='JSON parse' and 'origin' in e]
        assert Counter((e['origin'],e['member']) for e in je)==Counter([('parent','inventory.json')]+[('parent',f'roles/{c}.json') for c in cases if c not in ('final',*EXT)])
        for e in je:assert e['sha256']==man[e['member']]['sha256']
        se=[e for e in events if e.get('operation')=='JSON parse' and str(e.get('identity','')).startswith('calibrate/')]
        assert Counter(e['identity'] for e in se)==Counter('calibrate/'+n for n in scalar_reads)
        for e in se:assert e['sha256']==cal['outputs'][e['identity'].split('/')[-1]]
        assert total==38227 and total*2==76454 and csvrows==29856 and fallback==25 and len(scalar_reads)==36 and len(set(scalar_reads))==32
        z.close();used=0
        for name in reg['output_roots']:
            for path in (ROOT/name).rglob('*'):
                a.tick()
                if path.is_symlink():raise ValueError('logical output symlink')
                if path.is_file():used+=path.stat().st_size
        assert used<=reg['logical_cap']-reg['failure_reserve']
        end=dict(a.inputs)
        for path,pin in end.items():stream(path,pin)
        a.tick();qa={'status':'PASS_INDEPENDENT_SAVED_SCORE','binding':b,'source_sha256':sources,'producer_seconds':rec['seconds'],'audit_seconds':time.monotonic()-start,'native_cases':18,'repeated_rows':total,'exact_candidate_values':total*2,'exact_effective_fraction_values':total*2,'CSV_files':17,'CSV_rows':csvrows,'CSV_max_absolute_parser_difference':maxcsv,'fallback_rows_per_candidate':fallback,'outputs':37,'scalar_parses':36,'unique_scalars':32,'NPZ_input_members':90,'producer_events':len(events),'logical_bytes_at_audit':used,'records':records,'loaded_members':members,'opened_archive_members':opened,'all_consumed_end_pins':end,'events':a.events,'targets_loaded':0,'fits':0,'scope':'Native bit equality and independent exact-rational inward arithmetic; inherited 1e-13 CSV parser tolerance, not relaxed native equality. No confidence recalculation/model inference/scoring targets. Separate assessment approval required.'}
        with (out/'QA.json').open('x') as f:json.dump(qa,f,indent=2,sort_keys=True)
        print(json.dumps({'status':qa['status'],'sha256':hashlib.sha256((out/'QA.json').read_bytes()).hexdigest(),'seconds':qa['audit_seconds'],'values':76454}))
    except BaseException as e:
        with (out/'FAILURE.json').open('x') as f:json.dump({'error':repr(e),'events':a.events},f,indent=2)
        raise
    finally:
        if z is not None:z.close()
def guarded_main():
    if len(sys.argv)!=3:raise ValueError('explicit binding path and SHA required')
    old=signal.getsignal(signal.SIGALRM)
    def expired(*args):raise TimeoutError('whole score audit900seconds')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:return main(*sys.argv[1:])
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
if __name__=='__main__':guarded_main()
