"""One separately approved saved calibration audit; no producer or scoring call.

Usage: audit_calibration.py BINDING.json BINDING_SHA256
The binding must be explicitly supplied after root approval; nothing discovers
or selects a current calibration COMPLETE automatically.
"""
import hashlib,json,io,zipfile,time,signal,sys
from pathlib import Path
from collections import Counter
from fractions import Fraction as F
import audit_common as ac
import calibration_math as cm
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
P=ROOT/'model_proposal/four_tree_matching_plan/downstream_plan'
OLD=ROOT/'model_proposal/paired_tree_plan/all_context_downstream_plan'
REG='39db3eb801e654dda6c7787612cbd94d2b7d664f7fbefb9b42f7bcf874a725d2'
PRE='96f1ecb56362ad9902bf9412d26c1cda4e6da5fbc9b058ef302bae9c5a392843'
OLD_CAL='4429be8179cbc28aba09fbe6599af53d74dd0e9536ac34f9b3eb3b2e3973150f'
ARCHIVES={
 'parent':('model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip','673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3','3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'),
 'KL addon':('model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip','45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b','dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d')}
FIELDS=['indices','BASE_CD','core','anchor','gate','group','nf2_row_id','MEAS_CD']
PAIRED=('qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001')
STAGE0=('qualified_structural_harm_001','qualified_structural_kl_harm_001')
def main(binding_path,binding_sha):
    bp=Path(binding_path)
    if not ac.pin(binding_sha) or any(x.is_symlink() for x in (bp,*bp.parents)) or bp.stat().st_size>4096:raise ValueError('explicit small binding')
    raw=bp.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=binding_sha:raise ValueError('binding digest')
    b=ac.json_unique(raw);a=ac.Access(b)
    if b['phase']!='calibrate' or b['registry_sha256']!=REG or b['predecessor_sha256']!=PRE:raise ValueError('fixed approved calibration successor')
    out=HERE/'calibration_attempt_2';out.mkdir(exist_ok=False);start=time.monotonic();zips=[]
    def obj(path,pin):return ac.json_unique(a.read(path,pin,64*2**20))
    def stream(path,pin):
        p=Path(path)
        if not ac.pin(pin) or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('stream path/pin')
        if str(p) in a.inputs and a.inputs[str(p)]!=pin:raise ValueError('conflicting consumed pin')
        h=hashlib.sha256();size=0
        with p.open('rb') as f:
            while block:=f.read(65536):a.tick();h.update(block);size+=len(block)
        if h.hexdigest()!=pin:raise ValueError('stream content')
        a.inputs[str(p)]=pin;a.events.append({'operation':'stream hash only','path':str(p),'sha256':pin,'bytes':size})
    try:
        a.read(bp,binding_sha,4096)
        source_pins={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('audit_calibration.py','calibration_math.py','audit_common.py')}
        for name,pin in source_pins.items():a.read(HERE/name,pin)
        rec=a.receipt(a.read(P/'calibrate/COMPLETE.json',b['complete_sha256']))
        reg=obj(P/'REGISTRY.json',REG);ap=obj(P/'ROOT_CALIBRATE_APPROVAL.json',b['approval_sha256'])
        assert ap['phase']=='calibrate' and ap['actual_execution_authorized'] is True and ap['registry_sha256']==REG and ap['predecessor_sha256']==PRE and ap['seconds']==900 and ap['workers']==1
        assert rec['seconds']<900 and not (P/'calibrate/FAILURE.json').exists()
        for name,pin in reg['sources'].items():a.read(P/name,pin)
        for name,pin in reg['external_sources'].items():stream(ROOT/name,pin)
        pre=obj(P/'preflight/COMPLETE.json',PRE)
        assert pre['finish_utc']<rec['start_utc'] and pre['registry_sha256']==REG
        for name,pin in pre['outputs'].items():a.read(P/'preflight'/name,pin,64*2**20)
        refs=cm.decode(obj(P/'preflight/REFERENCE_PASS.json',pre['outputs']['REFERENCE_PASS.json']))
        contexts=reg['contexts'];assert len(contexts)==16 and contexts==refs['contexts']
        wanted={'ATTEMPT.json','ACCESS.json','SCALAR_DIRECTIONS.json'}|{'membership_'+c+'.json' for c in contexts}|{f'calibrator_{l}_{c}.json' for c in contexts for l in ac.NEW}
        assert set(rec['outputs'])==wanted and len(wanted)==51
        for name,pin in rec['outputs'].items():a.read(P/'calibrate'/name,pin,64*2**20)
        events=obj(P/'calibrate/ACCESS.json',rec['outputs']['ACCESS.json'])
        native=[e for e in events if e.get('operation')=='NPZ materialization']
        assert Counter((e['origin'],e['file'],e['member']) for e in native)==Counter(('parent',f'calibration/{c}.npz',f) for c in contexts for f in FIELDS)
        assert not any(e.get('operation')=='pandas.read_csv' or str(e.get('file','')).startswith(('native/','scoring/')) for e in events)
        for e in events:
            if e.get('operation')=='JSON parse' and 'origin' in e:assert e['member'].startswith(('roles/','scalars/'))
        paths={}
        for e in events:
            if 'path' in e and 'sha256' in e:
                if e['path'] in paths:assert paths[e['path']]==e['sha256']
                paths[e['path']]=e['sha256']
        for path,pin in paths.items():stream(path,pin)
        oldrec=obj(OLD/'calibrate/COMPLETE.json',OLD_CAL)
        assert oldrec['status']=='COMPLETE' and oldrec['phase']=='calibrate'
        # These bytes have already appeared in the authenticated producer ledger;
        # old calibration-only JSON is the sole materialized legacy payload role.
        def old_scalar(name):
            path=OLD/'calibrate'/name;pin=oldrec['outputs'][name]
            assert paths[str(path)]==pin
            return obj(path,pin)
        maths=cm.load(a);members=[];opened=[];readers={};manifests={}
        for origin,(path,pin,mpin) in ARCHIVES.items():
            path=ROOT/path;stream(path,pin);z=zipfile.ZipFile(path);zips.append(z)
            mr=z.read('manifest.json');assert hashlib.sha256(mr).hexdigest()==mpin
            man=ac.json_unique(mr)['files'];manifests[origin]=man
            def member(name,z=z,man=man,origin=origin):
                if not name.startswith(('calibration/','roles/','scalars/')):raise ValueError('calibration-only archive permission')
                if origin!='parent' and not name.startswith('scalars/'):raise ValueError('KL addon scalar only')
                raw=z.read(name);assert hashlib.sha256(raw).hexdigest()==man[name]['sha256']
                opened.append({'origin':origin,'member':name,'sha256':man[name]['sha256']});return raw
            readers[origin]=member
        # No scientific member materialization precedes all phase/source/ledger
        # barriers above. Whole ZIP hashes include sealed-by-role other payloads.
        import numpy as np
        records=[];directions=[];total=0
        for ctx in contexts:
            a.tick();role=ac.json_unique(readers['parent']('roles/'+ctx+'.json'))
            assert role==obj(P/'calibrate'/('membership_'+ctx+'.json'),rec['outputs']['membership_'+ctx+'.json'])==old_scalar('membership_'+ctx+'.json')
            assert role['post_calibration_refit'] is False
            for suffix in ('groups','indices'):
                sets=[set(role[p+'_'+suffix]) for p in ('proper','calibration','test')]
                assert all(len(role[p+'_'+suffix])==len(sets[i]) for i,p in enumerate(('proper','calibration','test')))
                assert all(not sets[i]&sets[j] for i in range(3) for j in range(i))
            name='calibration/'+ctx+'.npz'
            with np.load(io.BytesIO(readers['parent'](name)),allow_pickle=False) as z:v={f:z[f] for f in FIELDS}
            n=len(v['BASE_CD']);assert all(x.shape==(n,) and not x.dtype.hasobject for x in v.values())
            assert v['gate'].dtype==bool and v['indices'].dtype.kind in 'iu'
            for f in FIELDS:members.append({'origin':'parent','file':name,'member':f,'sha256':manifests['parent'][name]['sha256'],'shape':list(v[f].shape),'dtype':str(v[f].dtype)})
            for f in ('BASE_CD','core','anchor','MEAS_CD'):assert v[f].dtype==np.float64 and np.isfinite(v[f]).all()
            assert (v['BASE_CD']>0).all() and (v['core']>0).all() and (v['anchor']>0).all()
            np.testing.assert_array_equal(v['indices'],role['calibration_indices']);np.testing.assert_array_equal(v['nf2_row_id'],role['calibration_nf2_row_ids'])
            groups=v['group'].astype(str);assert set(groups)==set(role['calibration_groups'])
            for f in ('core','anchor'):np.testing.assert_array_equal(v[f][~v['gate']],v['BASE_CD'][~v['gate']])
            losses,means,mean=ac.group_positive_losses(*(v[f].tolist() for f in ('BASE_CD','core','anchor','MEAS_CD')),groups.tolist())
            B,Bp,B0=(refs['bounds'][ctx][k] for k in ('D','paired_D','Stage0'))
            assert 0<B<=Bp<=B0 and all(0<=loss<=B for loss in losses);total+=n
            for i,kind in enumerate(('H','KL')):
                label=ac.NEW[i];fn=f'calibrator_{label}_{ctx}.json'
                raw=obj(P/'calibrate'/fn,rec['outputs'][fn]);paired_raw=old_scalar(f'calibrator_{PAIRED[i]}_{ctx}.json')
                oldraw=ac.json_unique(readers['parent' if i==0 else 'KL addon'](f'scalars/{STAGE0[i]}_{ctx}.json'))
                s,paired,old=map(cm.decode,(raw,paired_raw,oldraw))
                assert s['candidate']==label and s['context']==ctx and paired['candidate']==PAIRED[i] and paired['context']==ctx
                U,t=cm.verify(s,B,mean,means,n,kind,maths)
                Up,tp=cm.verify(paired,Bp,mean,means,n,kind,maths)
                U0,t0=cm.verify(old,B0,mean,means,n,kind,maths)
                d={'context':ctx,'candidate':label,'paired_candidate':PAIRED[i],'B':raw['bound'],'paired_B':paired_raw['bound'],'upper_direction':ac.sign(U-Up),'t_direction':ac.sign(F(t)-F(tp)),'tU_direction':ac.sign(F(t)*U-F(tp)*Up)}
                directions.append(d)
                records.append({'context':ctx,'candidate':label,'rows':n,'groups':len(means),'B':float(B),'paired_B':float(Bp),'Stage0_B':float(B0),'mean':float(mean),'max_loss':float(max(losses)),'U':float(U),'paired_U':float(Up),'Stage0_U':float(U0),'t':t,'paired_t':tp,'Stage0_t':t0,'tU':float(F(t)*U),'paired_tU':float(F(tp)*Up),'Stage0_tU':float(F(t0)*U0),'directions_vs_paired':{k:d[k] for k in ('upper_direction','t_direction','tU_direction')}})
        assert members==[{k:e[k] for k in ('origin','file','member','sha256','shape','dtype')} for e in native]
        saved=cm.decode(obj(P/'calibrate/SCALAR_DIRECTIONS.json',rec['outputs']['SCALAR_DIRECTIONS.json']))
        assert saved==cm.decode(directions) and len(saved)==32
        for z in zips:z.close()
        used=0
        for name in reg['output_roots']:
            root=ROOT/name
            for path in root.rglob('*'):
                a.tick()
                if path.is_symlink():raise ValueError('storage symlink')
                if path.is_file():used+=path.stat().st_size
        assert used<=reg['logical_cap']-reg['failure_reserve']
        end=dict(a.inputs)
        for path,pin in end.items():stream(path,pin)
        a.tick()
        qa={'status':'PASS_INDEPENDENT_SAVED_CALIBRATION','binding':b,'source_sha256':source_pins,'outputs':51,'new_scalars':32,'paired_scalars':32,'Stage0_scalars':32,'contexts':16,'roles':16,'calibration_row_instances':total,'NPZ_members':len(members),'MEAS_CD_members':16,'scoring_members':0,'fits':0,'producer_seconds':rec['seconds'],'audit_seconds':time.monotonic()-start,'producer_events':len(events),'current_logical_bytes':used,'records':records,'SCALAR_DIRECTIONS':directions,'loaded_members':members,'opened_archive_members':opened,'all_consumed_end_pins':end,'events':a.events,'scope':'Fixed saved calibration only; exact means and endpoint certificates, no root bisection/fit/scoring rerun. Cross-B signs observed, never assumed. Separate score approval required.'}
        with (out/'QA.json').open('x') as f:json.dump(qa,f,indent=2,sort_keys=True)
        print(json.dumps({'status':qa['status'],'sha256':hashlib.sha256((out/'QA.json').read_bytes()).hexdigest(),'seconds':qa['audit_seconds'],'records':len(records)}))
    except BaseException as e:
        with (out/'FAILURE.json').open('x') as f:json.dump({'error':repr(e),'events':a.events},f,indent=2)
        raise
    finally:
        for z in zips:z.close()
def guarded_main():
    if len(sys.argv)!=3:raise ValueError('explicit binding path and digest required')
    old=signal.getsignal(signal.SIGALRM)
    def expired(*args):raise TimeoutError('whole calibration audit900seconds')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:return main(*sys.argv[1:])
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
if __name__=='__main__':guarded_main()
