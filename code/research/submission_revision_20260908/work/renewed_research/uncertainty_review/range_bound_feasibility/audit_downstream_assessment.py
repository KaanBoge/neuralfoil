"""Independent full assessment equations on authenticated reconstructed typed inputs."""
import ast,json,hashlib,zipfile,io,time,traceback,collections
import numpy as np
import pandas as pd
from audit_downstream_calibration import HERE,ROOT,P,read,obj
PIN='341b16e2b738a8f01592d2671e57615e602b0fd896f2108241b0c2f53d0a46bc'
LABELS=['qualified_paired_D_harm_001','qualified_paired_D_kl_harm_001']
OLDKL=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
def main():
    start=time.monotonic();r=obj(P/'assess/COMPLETE.json',PIN);assert len(r['outputs'])==14
    assert not (P/'assess/FAILURE.json').exists() and read(P/'assess/COMPLETE.pending.json')==read(P/'assess/COMPLETE.json')
    reg=obj(P/'REGISTRY.json',r['registry_sha256']);assert r['registry_sha256']=='f55a993c6b9029db25bb53e0329d84f8f6f4b4efdb14107ceabd7af5b82b2b17'
    for n,s in reg['sources'].items():read(P/n,s)
    for n,s in reg['external_sources'].items():read(ROOT/n,s)
    ap=obj(P/'ROOT_ASSESS_APPROVAL.json',r['approval_sha256']);assert r['approval_sha256']=='678fe0eff4106937e43ace74290977c3b1cb7d5d67c86969bf35cc883784ad2b'
    assert ap['phase']=='assess' and ap['actual_execution_authorized'] and ap['workers']==1 and ap['seconds']==900
    score=obj(P/'score/COMPLETE.json',r['summary']['predecessor_sha256']);assert score['finish_utc']<r['start_utc']
    assert ap['predecessor_sha256']==r['summary']['predecessor_sha256'] and ap['registry_sha256']==r['registry_sha256']
    for phase,rec in [('score',score),('assess',r)]:
        for n,s in rec['outputs'].items():read(P/phase/n,s)
    access=obj(P/'assess/ACCESS.json');pins={}
    for e in access:
        if 'path' in e and 'sha256' in e:
            assert e['path'] not in pins or pins[e['path']]==e['sha256'];pins[e['path']]=e['sha256']
    for p,s in pins.items():read(p,s)
    opened=[]
    def archive(path,pin,mpin):
        z=zipfile.ZipFile(io.BytesIO(read(path,pin)));mn=next(n for n in z.namelist() if n.endswith('manifest.json'));prefix=mn[:-13];raw=z.read(mn);assert hashlib.sha256(raw).hexdigest()==mpin;man=json.loads(raw)['files']
        def member(n):
            b=z.read(prefix+n);assert hashlib.sha256(b).hexdigest()==man[n]['sha256'];opened.append({'archive':path.name,'member':n});return b
        return member,man
    parent,pm=archive(ROOT/'model_proposal/range_bound_feasibility/stage1_v2/portable_plan/qualified_harm_private_v1.zip','673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3','3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154')
    addon,am=archive(ROOT/'model_proposal/kl_bound_study/portable_plan/kl_harm_private_v1.zip','45b9616d621ecdb2f841a69361860c2ef7700973dc785c55a78ffb51fd32956b','dc8c65e9a4cfc8d9937036019f10fb6aacff141a7f370916c3b8eaa6dfdacb7d')
    schema=json.loads(parent('scoring/schema.json'));panelids=json.loads(parent('scoring/panels.json'))
    with np.load(io.BytesIO(parent('scoring/frame.npz')),allow_pickle=False) as z:arrays={k:z[k].copy() for k in z.files}
    cols={}
    for row in schema['columns']:
        v=arrays[row['key']]
        if row['dtype']=='object':v=np.array([None if t==0 else str(s) if t==1 else s=='1' if t==2 else int(s) if t==3 else float.fromhex(s) if t==4 else (_ for _ in ()).throw(ValueError('tag')) for s,t in zip(v,arrays[row['key']+'_kind'])],object)
        cols[row['name']]=v
    original=pd.DataFrame(cols);frame=original.copy(deep=True)
    def overlay(labels,loader):
        before=frame.copy(deep=True)
        for split in frame.split.unique():
            f=pd.read_csv(io.BytesIO(loader(split)),low_memory=False);mask=frame.split.eq(split);assert len(f)==mask.sum()
            if split not in ['SG_exposed','W_new_challenge']:
                assert f.nf2_row_id.is_unique and set(f.nf2_row_id)==set(frame.loc[mask,'nf2_row_id']);f=f.set_index('nf2_row_id').loc[frame.loc[mask,'nf2_row_id']]
            else:np.testing.assert_array_equal(f['indices'],np.arange(mask.sum()))
            np.testing.assert_allclose(f.BASE_CD,frame.loc[mask,'mean8_CD'],atol=1e-13,rtol=0)
            for label in labels:
                for suffix in ['', '__effective_fraction','__strength','__intervened']:frame.loc[mask,label+suffix]=f[label+suffix].to_numpy()
        pd.testing.assert_frame_equal(frame[before.columns],before,check_exact=True)
    overlay(OLDKL,lambda s:addon('prediction_csv/'+s+'.csv'));oldframe=frame.copy(deep=True)
    oldexpected=pd.read_csv(io.BytesIO(addon('expected/all_row_predictions.csv')),low_memory=False)
    pd.testing.assert_frame_equal(pd.read_csv(io.StringIO(oldframe.to_csv(index=False)),low_memory=False),oldexpected,check_exact=True)
    overlay(LABELS,lambda s:read(P/'score'/f'predictions_{s}.csv',score['outputs'][f'predictions_{s}.csv']))
    tables={n[:-4]:pd.read_csv(io.BytesIO(read(P/'assess'/n,s)),low_memory=False) for n,s in r['outputs'].items() if n.endswith('.csv')}
    pd.testing.assert_frame_equal(pd.read_csv(io.StringIO(frame.to_csv(index=False)),low_memory=False),tables['all_row_predictions'],check_exact=True)
    tables['all_row_predictions']=frame
    # Independent equations previously authored by reviewer; no scientific assessor imports.
    src=read(HERE/'stage1_v2_audit/audit_metrics.py');tree=ast.parse(src);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');node.body=node.body[2:]
    body=ast.unparse(node).replace("labels = report['candidates'] + report['controls']","labels = list(table_labels)")
    for old,new in [('len(labels) == 15','len(labels) == 19'),('len(table) == 465','len(table) == 589'),('len(groups) == 2790','len(groups) == 3534'),('len(boot) == 150','len(boot) == 342'),('len(harm) == 3255','len(harm) == 6479'),('len(risk) == 465','len(risk) == 589')]:body=body.replace(old,new)
    parsed=ast.parse(body);parsed.body[0].body[-1]=ast.parse("return {'checks': COUNT, 'warnings': WARNINGS, 'decisions': decisions, 'panels':panels}").body[0]
    ns={'np':np,'pd':pd,'frames':tables,'table_labels':list(tables['panel_metrics'].candidate.unique()),'COUNT':0,'WARNINGS':[]}
    exec('\n'.join(ast.unparse(n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='eq'),ns);exec(compile(ast.fix_missing_locations(parsed),'<independent equations>','exec'),ns)
    result=ns['main']();panels=result.pop('panels');eq=ns['eq']
    for name,mask in panels.items():np.testing.assert_array_equal(np.flatnonzero(mask),panelids[name])
    oldlabels=[l for l in tables['panel_metrics'].candidate.unique() if l not in LABELS];assert len(oldlabels)==17
    oldrefs=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half','qualified_generic_harm_001','qualified_structural_harm_001','qualified_generic_kl_harm_001']
    parity=[]
    for name,keys,refs in [('bootstrap',['candidate','assignment','reference'],oldrefs),('panel_metrics',['candidate','panel'],None),('group_metrics',['candidate','assignment','group'],None),('harm_metrics',['candidate','reference','panel'],oldrefs+['xlarge_CD','mean8_CD'])]:
        expected=pd.read_csv(io.BytesIO(addon('expected/'+name+'.csv')),low_memory=False).set_index(keys).sort_index();actual=tables[name][tables[name].candidate.isin(oldlabels)]
        if refs is not None:actual=actual[actual.reference.isin(refs)]
        actual=actual.set_index(keys).sort_index();pd.testing.assert_frame_equal(actual,expected,check_exact=True);parity.append({'table':name,'rows':len(actual),'exact_parsed_cells':True})
    assert obj(P/'assess/OLD_FLOAT_DIFFERENCES.json')==[]
    details=[]
    for row in tables['intervention_metrics'].itertuples():
        part=frame[panels[row.panel]];y=part.measured_CD.to_numpy();p=part[row.candidate].to_numpy();anchor=part.qualified_matched_half.to_numpy();selected=abs(p-anchor)>1e-12;e=part[row.candidate+'__effective_fraction'].to_numpy()
        vals={'rows':len(part),'interventions':selected.sum(),'physical_eligible_rows':part.interval_applicable.sum(),'qualified_eligible_rows':part.qualified_gate.sum(),'intervention_fraction':selected.mean(),'effective_fraction_min':e.min(),'effective_fraction_mean':e.mean(),'effective_fraction_max':e.max()}
        for ref in ['qualified_matched_half','proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
            d=abs(p-y)-abs(part[ref].to_numpy()-y)
            vals.update({ref+'__selected_harm_fraction':(d[selected]>1e-12).mean() if selected.any() else None,ref+'__selected_benefit_fraction':(d[selected]<-1e-12).mean() if selected.any() else None,ref+'__selected_positive_excess_CD':np.maximum(d[selected],0).mean() if selected.any() else None})
        for k,v in vals.items():eq(getattr(row,k),v)
    pmets=tables['panel_metrics'];boots=tables['bootstrap'];groups=tables['group_metrics'];fields=['mean8_CD_improvement_percent','xlarge_CD_improvement_percent']
    for _,row in tables['candidate_summary'].iterrows():
        t=pmets[pmets.candidate.eq(row.candidate)]
        for k,v in {'minimum_all31_improvement_both_percent':t[fields].min().min(),'minimum_eligible8_improvement_both_percent':t[t.panel.str.startswith('eligible_only/')][fields].min().min(),'worst_strict_source_improvement_both_percent':t[t.panel.str.startswith('strict_source_')][fields].min().min()}.items():eq(getattr(row,k),v)
        for seed in [20260906,20260908]:
            s=t[t.panel.eq(f'history_{seed}_pooled')].iloc[0];g=groups[groups.assignment.eq(seed)&groups.candidate.eq(row.candidate)]
            for key in ['xlarge_CD_improvement_percent','mean8_CD_improvement_percent','mae_CD','median_absolute_error_CD','p90_absolute_error_CD']:eq(getattr(row,f'{seed}_{key}'),s[key])
            eq(getattr(row,f'{seed}_negative_identity_groups'),(g.xlarge_improvement_percent < -1e-6).sum());eq(getattr(row,f'{seed}_worst_group_improvement_percent'),g.xlarge_improvement_percent.min())
            for b in boots[boots.assignment.eq(seed)&boots.candidate.eq(row.candidate)].itertuples():eq(getattr(row,f'{seed}_remaining_MAE_reduction_vs_{b.reference}_percent'),b.remaining_MAE_reduction_percent)
    # Additional fixed descriptive RMSE, never an advancement/selection rule.
    for label in LABELS:
        for panel,mask in panels.items():
            part=frame[mask];y=part.measured_CD.to_numpy();e=part[label].to_numpy()-y
            refs=['xlarge_CD','mean8_CD','qualified_structural_harm_001' if label==LABELS[0] else 'qualified_structural_kl_harm_001','half_strength','unpenalized_transfer']
            details.append({'candidate':label,'panel':panel,'rows':len(part),'mae_CD':float(abs(e).mean()),'RMSE_CD_descriptive':float(np.sqrt(np.mean(e*e))),'p90_absolute_error_CD':float(np.quantile(abs(e),.9)),'comparisons':{ref:{'remaining_MAE_reduction_percent':float(100*(1-abs(e).sum()/abs(part[ref].to_numpy()-y).sum())),'worse_rows':int((abs(e)>abs(part[ref].to_numpy()-y)+1e-12).sum())} for ref in refs}})
    ne=[e for e in access if e.get('operation')=='NPZ materialization'];assert set((e['origin'],e['file']) for e in ne)=={('parent','scoring/frame.npz')} and set(e['member'] for e in ne)==set(arrays) and len(ne)==len(arrays)
    for e in ne:assert e['sha256']==pm[e['file']]['sha256']
    score_reads=[e for e in access if e.get('operation')=='pandas.read_csv' and str(e.get('identity','')).startswith('score/')];assert len(score_reads)==17
    for e in score_reads:assert e['sha256']==score['outputs'][e['identity'].split('/')[-1]]
    for n,s in r['outputs'].items():read(P/'assess'/n,s)
    assert time.monotonic()-start<900
    result.update(status='PASS_INDEPENDENT_FIXED_ASSESSMENT',complete_sha256=PIN,audit_sha256=hashlib.sha256(read(__file__)).hexdigest(),independent_equations_sha256=hashlib.sha256(src).hexdigest(),producer_seconds=r['seconds'],audit_seconds=time.monotonic()-start,checks=ns['COUNT'],outputs=14,events=len(access),unique_path_pins=len(pins),typed_columns=len(original.columns),typed_members=len(arrays),rows=len(frame),labels=19,panels=31,bootstrap_rows=342,old_exact_parity=parity,table_counts={n:len(f) for n,f in tables.items()},new_detailed_panels=details,new_negative_groups=groups[groups.candidate.isin(LABELS)&(groups.xlarge_improvement_percent< -1e-6)].to_dict('records'),source_opened_members=opened,scope='Fixed frozen predictions; independent aggregate/20k bootstrap replay, no fits/tuning/new data. Conditional bootstrap, not generalization evidence. RMSE descriptive only.')
    return result
if __name__=='__main__':
    out=HERE/'DOWNSTREAM_ASSESSMENT_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/('DOWNSTREAM_ASSESSMENT_FAILURE_'+str(time.time_ns())+'.txt')).open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps({k:v for k,v in r.items() if k not in ['new_detailed_panels','new_negative_groups','source_opened_members']},indent=2))
