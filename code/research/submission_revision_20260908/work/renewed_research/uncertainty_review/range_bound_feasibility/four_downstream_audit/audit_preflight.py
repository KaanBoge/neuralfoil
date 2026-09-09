"""Authorized saved preflight only. No calibration targets/scalars/frame."""
import hashlib,json,zipfile,io,time,signal
from pathlib import Path
from collections import Counter
import audit_common as ac
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];P=ROOT/'model_proposal/four_tree_matching_plan/downstream_plan'
BINDING={'phase':'preflight','root_saved_audit_authorized':True,'complete_sha256':'96f1ecb56362ad9902bf9412d26c1cda4e6da5fbc9b058ef302bae9c5a392843','approval_sha256':'f48c4cf849e2bb80a92ebbb0e28674fc5c23032693865ccb5e8f9b5126ea5330','registry_sha256':'39db3eb801e654dda6c7787612cbd94d2b7d664f7fbefb9b42f7bcf874a725d2','predecessor_sha256':'6ac63d4388cd2f2ffd4110839fef60d29142c0041300267d6ff265764748ec5c','seconds':900,'workers':1}
PARENT=ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip'
PARENT_SHA='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3';MANIFEST='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
KEYS=['indices','BASE_CD','core','anchor','gate']
def main():
    out=HERE/'preflight_attempt_1';out.mkdir(exist_ok=False);a=ac.Access(BINDING);start=time.monotonic()
    def obj(p,h):return ac.json_unique(a.read(p,h,64*2**20))
    def stream(p,h):
        p=Path(p)
        if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('stream symlink path')
        if str(p) in a.inputs and a.inputs[str(p)]!=h:raise ValueError('conflicting input pin')
        digest=hashlib.sha256();n=0
        with p.open('rb') as f:
            while b:=f.read(65536):a.tick();digest.update(b);n+=len(b)
        assert digest.hexdigest()==h;a.inputs[str(p)]=h;(a.events.append({'operation':'metadata/archive hash only','path':str(p),'sha256':h,'bytes':n}))
    try:
        source_pins={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('audit_preflight.py','audit_common.py')}
        for name,h in source_pins.items():a.read(HERE/name,h)
        r=a.receipt(a.read(P/'preflight/COMPLETE.json',BINDING['complete_sha256']));reg=obj(P/'REGISTRY.json',BINDING['registry_sha256']);ap=obj(P/'ROOT_PREFLIGHT_APPROVAL.json',BINDING['approval_sha256'])
        assert ap['predecessor_sha256']==BINDING['predecessor_sha256'] and ap['registry_sha256']==BINDING['registry_sha256'] and ap['actual_execution_authorized'] is True and ap['workers']==1 and ap['seconds']==900
        for n,h in reg['sources'].items():a.read(P/n,h)
        for n,h in reg['external_sources'].items():stream(ROOT/n,h)
        for n,h in r['outputs'].items():a.read(P/'preflight'/n,h,64*2**20)
        assert not (P/'preflight/FAILURE.json').exists();ref=obj(P/'preflight/REFERENCE_PASS.json',r['outputs']['REFERENCE_PASS.json']);assert ref['target_members_materialized'] is False
        priorroot=ROOT/'model_proposal/four_tree_matching_plan/all_context_proposal/implementation';prior=obj(priorroot/'certificates_replay/COMPLETE.json',BINDING['predecessor_sha256'])
        assert prior['status']=='COMPLETE' and set(prior['contexts'])==set(ref['contexts']) and len(ref['contexts'])==16
        bounds=[]
        for ctx in ref['contexts']:
            s=prior['contexts'][ctx]['summary'];b=ref['bounds'][ctx]
            for k,old in [('D','final'),('paired_D','original_adjacent'),('Stage0','stage0')]:assert ac.decode(b[k])==ac.decode(s[old]['B'])
            assert 0<=ac.decode(b['D'])<=ac.decode(b['paired_D'])<=ac.decode(b['Stage0']);bounds.append({'context':ctx,'B':float(ac.decode(b['D']))})
        events=obj(P/'preflight/ACCESS.json',r['outputs']['ACCESS.json']);np_events=[e for e in events if e['operation']=='NPZ materialization'];assert len(np_events)==202
        assert all(e['origin']=='parent' and e['member'] in KEYS+['group','nf2_row_id'] and e['file'].startswith(('native/','calibration/')) for e in np_events)
        json_members=[e for e in events if e['operation']=='JSON parse' and 'origin' in e]
        assert all(not e['member'].startswith(('scalars/','scoring/')) for e in json_members)
        assert not any(e['operation']=='pandas.read_csv' for e in events)
        paths={}
        for e in events:
            if 'path' in e and 'sha256' in e:
                if e['path'] in paths:assert paths[e['path']]==e['sha256']
                paths[e['path']]=e['sha256']
        for p,h in paths.items():stream(p,h)
        stream(PARENT,PARENT_SHA);z=zipfile.ZipFile(PARENT);manifest_raw=z.read('manifest.json');assert hashlib.sha256(manifest_raw).hexdigest()==MANIFEST;man=json.loads(manifest_raw)['files']
        materialized=[];roles={};case_counts=[]
        def member(name):
            allowed=(name in ['inventory.json'] or name.startswith(('roles/','native/','calibration/')))
            if not allowed:raise ValueError('reviewer preflight member deny')
            b=z.read(name);assert hashlib.sha256(b).hexdigest()==man[name]['sha256'];return b
        # Imports and allowlisted scientific intake occur only after all source,
        # phase, prior-chain, output and ledger authentication above.
        import numpy as np
        def arrays(name,keys):
            assert set(keys)<=set(KEYS+(['group','nf2_row_id'] if name.startswith('calibration/') else []))
            raw=member(name)
            with np.load(io.BytesIO(raw),allow_pickle=False) as archive:
                result={k:archive[k] for k in keys}
            for k,v in result.items():
                assert not v.dtype.hasobject;materialized.append({'file':name,'member':k,'sha256':man[name]['sha256'],'shape':list(v.shape),'dtype':str(v.dtype)})
            n=len(result['BASE_CD']);assert all(result[k].shape==(n,) for k in KEYS) and result['gate'].dtype==bool and result['indices'].dtype.kind in 'iu' and len(set(result['indices']))==n
            for k in ('BASE_CD','core','anchor'):assert result[k].dtype==np.float64 and np.isfinite(result[k]).all() and (result[k]>0).all()
            for k in ('core','anchor'):np.testing.assert_array_equal(result[k][~result['gate']],result['BASE_CD'][~result['gate']])
            case_counts.append({'case':name,'rows':n,'gate_true':int(result['gate'].sum())});return result
        inventory=json.loads(member('inventory.json'));assert inventory['contexts']==ref['contexts'] and inventory['native_contexts']==ref['native_contexts'] and len(inventory['native_contexts'])==18
        for ctx in ref['contexts']:
            role=json.loads(member('roles/'+ctx+'.json'));roles[ctx]=role
            for suffix in ('groups','indices'):
                sets=[]
                for part in ('proper','calibration','test'):
                    v=role[part+'_'+suffix];assert len(v)==len(set(v));sets.append(set(v))
                assert all(not sets[i]&sets[j] for i,j in ((0,1),(0,2),(1,2)))
            v=arrays('calibration/'+ctx+'.npz',KEYS+['group','nf2_row_id']);np.testing.assert_array_equal(v['indices'],role['calibration_indices']);np.testing.assert_array_equal(v['nf2_row_id'],role['calibration_nf2_row_ids']);assert set(v['group'].astype(str))==set(role['calibration_groups'])
        for ctx in ref['native_contexts']:
            v=arrays('native/'+ctx+'.npz',KEYS)
            if ctx not in ('final','SG_exposed','W_new_challenge'):np.testing.assert_array_equal(v['indices'],roles[ctx]['test_indices'])
        wanted=[{k:e[k] for k in ('file','member','sha256','shape','dtype')} for e in np_events];assert materialized==wanted
        z.close();assert len(materialized)==202 and len(case_counts)==34
        # Includes every consumed source/registry/approval/old-path/archive and
        # own implementation pin, not merely the three new output payloads.
        end_pins=dict(a.inputs)
        for p,h in end_pins.items():stream(Path(p),h)
        a.tick();q={'status':'PASS_INDEPENDENT_SAVED_PREFLIGHT','binding':BINDING,'bounds':bounds,'native_and_calibration_cases':case_counts,'actual_npz_member_checks':len(materialized),'contexts':16,'native_cases':18,'role_disjoint_checks':16,'producer_events':len(events),'unique_path_pins':len(paths),'audit_events':a.events,'loaded_members':materialized,'target_scalar_scoring_members_loaded':0,'new_fits':0,'runtime_seconds':time.monotonic()-start,'producer_seconds_including_early_auth':r['seconds'],'timing_scope':'producer seconds starts before attempt start_utc; no recomputed timing claim','source_sha256':source_pins,'all_consumed_end_pins':end_pins}
        with (out/'QA.json').open('x') as f:json.dump(q,f,indent=2,sort_keys=True)
        print(json.dumps({'status':q['status'],'sha256':hashlib.sha256((out/'QA.json').read_bytes()).hexdigest(),'contexts':16,'cases':34,'members':202,'seconds':q['runtime_seconds']}))
    except BaseException as e:
        with (out/'FAILURE.json').open('x') as f:json.dump({'error':repr(e),'audit_events':a.events},f,indent=2)
        raise
def guarded_main():
    old=signal.getsignal(signal.SIGALRM)
    def expired(*args):raise TimeoutError('whole saved preflight audit900second wall alarm')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:return main()
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
if __name__=='__main__':guarded_main()
