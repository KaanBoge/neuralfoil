"""Fixed saved assessment audit, explicit phase binding; no fitting or selection."""
import json,io,zipfile,hashlib,time,signal,sys
from pathlib import Path
from collections import Counter
import audit_common as ac
import assessment_equations as eqs
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
P=ROOT/'model_proposal/four_tree_matching_plan/downstream_plan'
OLD=ROOT/'model_proposal/paired_tree_plan/all_context_downstream_plan'
REG='39db3eb801e654dda6c7787612cbd94d2b7d664f7fbefb9b42f7bcf874a725d2'
OLD_ASSESS='341b16e2b738a8f01592d2671e57615e602b0fd896f2108241b0c2f53d0a46bc'
OLD_SCORE='4c8ae022383787196fe5ed7522f8c9dcbe9d06bd0737a035d9773521d7f72726'
ARCHIVES={
 'parent':('model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip','673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3','3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'),
 'KL addon':('model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip','45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b','dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d')}
PAIRED=['qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001']
OLDKL=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
REFS=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half','qualified_generic_harm_001','qualified_structural_harm_001','qualified_generic_kl_harm_001','qualified_structural_kl_harm_001',*PAIRED]
OLD_REFS=REFS[:-1]
TABLES=('panel_metrics','bootstrap','group_metrics','harm_metrics','decisions','candidate_summary','expected_harm_metrics','bundle_harm_metrics','intervention_metrics','all_row_predictions')
def summary_schema(tables,labels):
    for name,expected in [('decisions',set(ac.NEW)),('candidate_summary',set(labels))]:
        t=tables[name]
        if len(t)!=len(expected) or not t.candidate.is_unique or set(t.candidate)!=expected:raise ValueError('complete unique '+name+' label inventory')
def unpack(schema,arrays,np,pd):
    cols={};used=[]
    for row in schema['columns']:
        key=row['key'];used.append(key);v=arrays[key]
        if row['name'] in cols or v.ndim!=1 or v.dtype.hasobject:raise ValueError('typed column schema')
        if row['dtype']=='object':
            kinds=arrays[key+'_kind'];used.append(key+'_kind')
            if kinds.shape!=v.shape or kinds.dtype.kind not in 'iu':raise ValueError('typed tag schema')
            vals=[]
            for s,t in zip(v,kinds):
                if t==0:value=None
                elif t==1:value=str(s)
                elif t==2:
                    if s not in ('0','1'):raise ValueError('boolean tag value')
                    value=s=='1'
                elif t==3:value=int(s)
                elif t==4:value=float.fromhex(s)
                else:raise ValueError('object tag')
                vals.append(value)
            v=np.array(vals,object)
        cols[row['name']]=v
    if len(used)!=len(set(used)) or set(used)!=set(arrays):raise ValueError('typed member coverage')
    return pd.DataFrame(cols)
def overlay(frame,labels,loader,np,pd):
    before=frame.copy(deep=True)
    if any(l+s in before for l in labels for s in ('','__effective_fraction','__strength','__intervened')):raise ValueError('old field collision')
    for split in frame.split.unique():
        f=pd.read_csv(io.BytesIO(loader(split)),low_memory=False);mask=frame.split.eq(split)
        if len(f)!=mask.sum():raise ValueError('overlay length')
        if split not in ['SG_exposed','W_new_challenge']:
            if not f.nf2_row_id.is_unique or set(f.nf2_row_id)!=set(frame.loc[mask,'nf2_row_id']):raise ValueError('identity mismatch')
            f=f.set_index('nf2_row_id').loc[frame.loc[mask,'nf2_row_id']]
        else:np.testing.assert_array_equal(f['indices'],np.arange(mask.sum()))
        np.testing.assert_allclose(f.BASE_CD,frame.loc[mask,'mean8_CD'],atol=1e-13,rtol=0)
        for label in labels:
            for suffix in ('','__effective_fraction','__strength','__intervened'):frame.loc[mask,label+suffix]=f[label+suffix].to_numpy()
    pd.testing.assert_frame_equal(frame[before.columns],before,check_exact=True)
def main(binding_path,binding_sha):
    bp=Path(binding_path)
    if not ac.pin(binding_sha) or any(p.is_symlink() for p in (bp,*bp.parents)) or bp.stat().st_size>4096:raise ValueError('explicit small binding')
    raw=bp.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=binding_sha:raise ValueError('binding SHA')
    binding=ac.json_unique(raw);a=ac.Access(binding)
    if binding['phase']!='assess' or binding['registry_sha256']!=REG:raise ValueError('fixed assessment only')
    out=HERE/'assessment_attempt_2';out.mkdir(exist_ok=False);start=time.monotonic();zips=[]
    def obj(path,pin):return ac.json_unique(a.read(path,pin,64*2**20))
    def stream(path,pin):
        p=Path(path)
        if not ac.pin(pin) or any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('stream pin/path')
        if str(p) in a.inputs and a.inputs[str(p)]!=pin:raise ValueError('conflicting consumed pin')
        h=hashlib.sha256();n=0
        with p.open('rb') as f:
            while block:=f.read(65536):a.tick();h.update(block);n+=len(block)
        if h.hexdigest()!=pin:raise ValueError('stream bytes')
        a.inputs[str(p)]=pin;a.events.append({'operation':'stream hash only','path':str(p),'sha256':pin,'bytes':n})
    try:
        a.read(bp,binding_sha,4096)
        sources={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ('audit_assessment.py','assessment_equations.py','audit_common.py')}
        for n,pin in sources.items():a.read(HERE/n,pin)
        r=a.receipt(a.read(P/'assess/COMPLETE.json',binding['complete_sha256']));reg=obj(P/'REGISTRY.json',REG);ap=obj(P/'ROOT_ASSESS_APPROVAL.json',binding['approval_sha256'])
        assert ap['phase']=='assess' and ap['actual_execution_authorized'] is True and ap['registry_sha256']==REG and ap['predecessor_sha256']==binding['predecessor_sha256'] and ap['seconds']==900 and ap['workers']==1
        assert r['seconds']<900 and not (P/'assess/FAILURE.json').exists()
        for n,pin in reg['sources'].items():a.read(P/n,pin)
        for n,pin in reg['external_sources'].items():stream(ROOT/n,pin)
        score=obj(P/'score/COMPLETE.json',binding['predecessor_sha256'])
        assert score['phase']=='score' and score['status']=='COMPLETE' and score['registry_sha256']==REG and score['finish_utc']<r['start_utc']
        sap=obj(P/'ROOT_SCORE_APPROVAL.json',score['approval_sha256']);assert sap['phase']=='score' and sap['actual_execution_authorized'] is True and sap['registry_sha256']==REG and sap['predecessor_sha256']==score['summary']['predecessor_sha256']
        assert set(r['outputs'])=={'ATTEMPT.json','ACCESS.json','PARITY.json','OLD_FLOAT_DIFFERENCES.json'}|{n+'.csv' for n in TABLES}
        for phase,rec in [('assess',r),('score',score)]:
            for n,pin in rec['outputs'].items():stream(P/phase/n,pin)
        events=obj(P/'assess/ACCESS.json',r['outputs']['ACCESS.json']);paths={}
        for e in events:
            if 'path' in e and 'sha256' in e:
                if e['path'] in paths:assert paths[e['path']]==e['sha256']
                paths[e['path']]=e['sha256']
        for path,pin in paths.items():stream(path,pin)
        oldrec=obj(OLD/'assess/COMPLETE.json',OLD_ASSESS);oldscore=obj(OLD/'score/COMPLETE.json',OLD_SCORE)
        assert oldrec['summary']['predecessor_sha256']==OLD_SCORE
        for phase,rec in [('assess',oldrec),('score',oldscore)]:
            for n,pin in rec['outputs'].items():stream(OLD/phase/n,pin)
        readers={};manifests={};opened=[]
        for origin,(path,pin,mpin) in ARCHIVES.items():
            path=ROOT/path;stream(path,pin);z=zipfile.ZipFile(path);zips.append(z);mr=z.read('manifest.json');assert hashlib.sha256(mr).hexdigest()==mpin;man=ac.json_unique(mr)['files'];manifests[origin]=man
            def member(name,z=z,man=man,origin=origin):
                allowed=(name in ('scoring/schema.json','scoring/panels.json','scoring/frame.npz')) if origin=='parent' else name.startswith(('prediction_csv/','expected/'))
                if not allowed:raise ValueError('assessment-only member allowlist')
                raw=z.read(name);assert hashlib.sha256(raw).hexdigest()==man[name]['sha256'];opened.append({'origin':origin,'member':name,'sha256':man[name]['sha256']});return raw
            readers[origin]=member
        # No typed target materialization until complete sources/phase barriers.
        import numpy as np
        import pandas as pd
        parent,addon=readers['parent'],readers['KL addon']
        schema=ac.json_unique(parent('scoring/schema.json'));panelids=ac.json_unique(parent('scoring/panels.json'))
        with np.load(io.BytesIO(parent('scoring/frame.npz')),allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
        original=unpack(schema,arrays,np,pd);frame=original.copy(deep=True);assert len(frame)==29856 and len(panelids)==31
        def parse(raw):return pd.read_csv(io.BytesIO(raw),low_memory=False)
        def serialized(f):return pd.read_csv(io.StringIO(f.to_csv(index=False)),low_memory=False)
        overlay(frame,OLDKL,lambda s:addon('prediction_csv/'+s+'.csv'),np,pd)
        pd.testing.assert_frame_equal(serialized(frame),parse(addon('expected/all_row_predictions.csv')),check_exact=True)
        overlay(frame,PAIRED,lambda s:a.read(OLD/'score'/f'predictions_{s}.csv',oldscore['outputs'][f'predictions_{s}.csv'],64*2**20),np,pd)
        oldframe=frame.copy(deep=True)
        pd.testing.assert_frame_equal(serialized(oldframe),parse(a.read(OLD/'assess/all_row_predictions.csv',oldrec['outputs']['all_row_predictions.csv'],64*2**20)),check_exact=True)
        overlay(frame,list(ac.NEW),lambda s:a.read(P/'score'/f'predictions_{s}.csv',score['outputs'][f'predictions_{s}.csv'],64*2**20),np,pd)
        tables={n:parse(a.read(P/'assess'/(n+'.csv'),r['outputs'][n+'.csv'],64*2**20)) for n in TABLES}
        pd.testing.assert_frame_equal(serialized(frame),tables['all_row_predictions'],check_exact=True);tables['all_row_predictions']=frame
        labels=list(tables['panel_metrics'].candidate.unique());oldlabels=[x for x in labels if x not in ac.NEW]
        assert len(labels)==21 and len(oldlabels)==19 and set(ac.NEW)<=set(labels)
        for name in ('panel_metrics','expected_harm_metrics','intervention_metrics'):
            t=tables[name];assert not t.duplicated(['candidate','panel']).any()
            expected_labels=ac.NEW if name=='intervention_metrics' else labels
            assert set(zip(t.candidate,t.panel))=={(l,p) for l in expected_labels for p in panelids}
        summary_schema(tables,labels)
        t=tables['harm_metrics'];assert not t.duplicated(['candidate','reference','panel']).any()
        assert set(zip(t.candidate,t.reference,t.panel))=={(l,b,p) for l in labels for b in REFS+['xlarge_CD','mean8_CD'] for p in panelids}
        t=tables['group_metrics'];assert not t.duplicated(['candidate','assignment','group']).any()
        expected_groups={(l,s,g) for s in (20260906,20260908) for g in frame.loc[frame.split.str.startswith(f'group_{s}_'),'group'].unique() for l in labels}
        assert set(zip(t.candidate,t.assignment,t.group))==expected_groups and len(t)==3906
        assert not tables['bundle_harm_metrics'].duplicated(['candidate','panel','identity']).any()
        assert not tables['bootstrap'].duplicated(['candidate','assignment','reference']).any()
        assert set(zip(tables['bootstrap'].candidate,tables['bootstrap'].assignment,tables['bootstrap'].reference))=={(l,s,b) for l in labels for s in (20260906,20260908) for b in REFS}
        assert (tables['bootstrap'].draws==20000).all() and (tables['bootstrap'].seed==2026090831).all()
        result=eqs.run(a,tables);panels=result.pop('panels')
        for name,mask in panels.items():np.testing.assert_array_equal(np.flatnonzero(mask),panelids[name])
        parity=[]
        for name,keys,refs in [('bootstrap',['candidate','assignment','reference'],OLD_REFS),('panel_metrics',['candidate','panel'],None),('group_metrics',['candidate','assignment','group'],None),('harm_metrics',['candidate','reference','panel'],OLD_REFS+['xlarge_CD','mean8_CD'])]:
            expected=parse(a.read(OLD/'assess'/(name+'.csv'),oldrec['outputs'][name+'.csv'],64*2**20)).set_index(keys).sort_index();actual=tables[name][tables[name].candidate.isin(oldlabels)]
            if refs is not None:actual=actual[actual.reference.isin(refs)]
            actual=actual.set_index(keys).sort_index();pd.testing.assert_frame_equal(actual,expected,check_exact=True);parity.append({'table':name,'rows':len(actual),'old_parsed_cells_exact':True})
        assert parity[0]['rows']==342
        olddifferences=obj(P/'assess/OLD_FLOAT_DIFFERENCES.json',r['outputs']['OLD_FLOAT_DIFFERENCES.json'])
        # Existing expected-corpus discrepancies are retained, not erased or
        # mistaken for new independent bootstrap significance.
        for d in olddifferences:assert d['within_inherited_audit_tolerance'] or d['known_zero_sign_diagnostic']
        ne=[e for e in events if e.get('operation')=='NPZ materialization']
        assert set((e['origin'],e['file']) for e in ne)=={('parent','scoring/frame.npz')} and len(ne)==len(arrays) and set(e['member'] for e in ne)==set(arrays)
        for e in ne:assert e['sha256']==manifests['parent']['scoring/frame.npz']['sha256'] and e['shape']==list(arrays[e['member']].shape) and e['dtype']==str(arrays[e['member']].dtype)
        score_reads=[e for e in events if e.get('operation')=='pandas.read_csv' and str(e.get('identity','')).startswith('score/')]
        assert Counter(e['identity'] for e in score_reads)==Counter('score/predictions_'+s+'.csv' for s in frame.split.unique())
        for e in score_reads:assert e['sha256']==score['outputs'][e['identity'].split('/')[-1]]
        details=[]
        for label in ac.NEW:
            for panel,mask in panels.items():
                part=frame[mask];y=part.measured_CD.to_numpy();error=part[label].to_numpy()-y;ae=abs(error)
                refs=['xlarge_CD','mean8_CD',PAIRED[list(ac.NEW).index(label)],'qualified_structural_harm_001' if label==ac.NEW[0] else 'qualified_structural_kl_harm_001','half_strength','unpenalized_transfer']
                details.append({'candidate':label,'panel':panel,'rows':len(part),'mae_CD':float(ae.mean()),'RMSE_CD_descriptive':float(np.sqrt(np.mean(error*error))),'p90_absolute_error_CD':float(np.quantile(ae,.9)),'comparisons':{ref:{'remaining_MAE_reduction_percent':float(100*(1-ae.sum()/abs(part[ref].to_numpy()-y).sum())),'worse_rows':int((ae>abs(part[ref].to_numpy()-y)+1e-12).sum())} for ref in refs}})
        for z in zips:z.close()
        used=0
        for name in reg['output_roots']:
            for path in (ROOT/name).rglob('*'):
                a.tick()
                if path.is_symlink():raise ValueError('storage symlink')
                if path.is_file():used+=path.stat().st_size
        assert used<=reg['logical_cap']-reg['failure_reserve']
        end=dict(a.inputs)
        for path,pin in end.items():stream(path,pin)
        a.tick();groups=tables['group_metrics']
        result.update(status='PASS_INDEPENDENT_SAVED_ASSESSMENT',binding=binding,source_sha256=sources,producer_seconds=r['seconds'],audit_seconds=time.monotonic()-start,outputs=14,labels=21,panels=31,bootstrap_rows=420,draws_each=20000,seed=2026090831,old_exact_parity=parity,old_float_differences=olddifferences,table_counts={n:len(f) for n,f in tables.items()},new_detailed_panels=details,new_negative_groups=groups[groups.candidate.isin(ac.NEW)&(groups.xlarge_improvement_percent< -1e-6)].to_dict('records'),opened_archive_members=opened,producer_events=len(events),typed_columns=len(original.columns),typed_members=len(arrays),all_consumed_end_pins=end,events=a.events,logical_bytes_at_audit=used,fits=0,scope='Existing frozen typed outcomes and predictions only; all 420 fixed conditional bootstrap records independently recomputed. No model/selection/confirmatory independence. Strict numerical-zero sign discrepancies retained with original tolerances.')
        with (out/'QA.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
        print(json.dumps({'status':result['status'],'sha256':hashlib.sha256((out/'QA.json').read_bytes()).hexdigest(),'seconds':result['audit_seconds'],'checks':result['checks'],'warnings':result['warnings']}))
    except BaseException as e:
        with (out/'FAILURE.json').open('x') as f:json.dump({'error':repr(e),'events':a.events},f,indent=2)
        raise
    finally:
        for z in zips:z.close()
def guarded_main():
    if len(sys.argv)!=3:raise ValueError('explicit binding path and SHA')
    old=signal.getsignal(signal.SIGALRM)
    def expired(*args):raise TimeoutError('whole assessment audit900seconds')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,900)
    try:return main(*sys.argv[1:])
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
if __name__=='__main__':guarded_main()
