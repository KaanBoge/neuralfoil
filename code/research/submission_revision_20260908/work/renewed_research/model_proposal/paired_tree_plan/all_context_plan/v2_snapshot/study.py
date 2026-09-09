"""Two fixed D-bound confidence procedures; every real phase needs approval."""
import argparse,io,json,time,types
from pathlib import Path
import numpy as np
import pandas as pd
import adapter as a
import study_inputs as si

PREVIOUS={'preflight':'certificates_replay','calibrate':'preflight','score':'calibrate','assess':'score'}

def complete(phase,pin,regsha,ledger):
    if phase=='certificates_replay':return a.certificate_chain(phase,pin,regsha,ledger)
    root=a.HERE/phase;r=a.json_read(root/'COMPLETE.json',pin,ledger)
    if r.get('status')!='COMPLETE' or r.get('registry_sha256')!=regsha or r.get('phase')!=phase:raise ValueError('phase completion identity')
    for name,h in r['outputs'].items():a.read(root/name,h,ledger,'completed output authentication')
    if phase=='certificates_replay':
        contexts=r['summary']['contexts']
        if set(contexts)!=set(a.CONTEXTS):raise ValueError('all sixteen certificate barrier')
        for ctx in a.CONTEXTS[:-1]:
            e=contexts[ctx]
            if e.get('status')!='PASS_CONTEXT_REPLAY':raise ValueError('failed/missing context')
            cr=a.json_read(root/ctx/'COMPLETE.json',e['complete_sha256'],ledger)
            for name,h in cr['outputs'].items():a.read(root/ctx/name,h,ledger,'context output authentication')
        if contexts['final'].get('status')!='INHERITED_AUTHENTICATED':raise ValueError('final must inherit')
        a.inherited_final(ledger,True)
    else:
        previous=r.get('predecessor_sha256',r.get('summary',{}).get('predecessor_sha256'))
        if not previous:raise ValueError('missing recursive predecessor')
        complete(PREVIOUS[phase],previous,regsha,ledger)
    return r

def phase_file(phase,record,name,ledger,parser='json'):
    if name not in record['outputs'] or Path(name).name!=name:raise ValueError('exact phase output name')
    raw=a.read(a.HERE/phase/name,record['outputs'][name],ledger)
    if parser=='json':return a.parse(raw,ledger,phase+'/'+name)
    ledger.append({'identity':phase+'/'+name,'sha256':a.sha(raw),'operation':'pandas.read_csv'})
    return pd.read_csv(io.BytesIO(raw),low_memory=False)

def scalar_match(actual,expected,codec):
    for k in ['upper','bound','exact_mean']:
        if actual[k]!=(None if expected[k] is None else codec.fraction(expected[k])):raise ValueError('matched H witness')
    for k in ['t','groups','rows']:
        if actual[k]!=expected[k]:raise ValueError('matched H numeric field')
    if actual['group_means']!={k:codec.fraction(v) for k,v in expected['group_means'].items()}:raise ValueError('matched H group means')

def preflight(parent,addon,engines,prior,out,ledger,outputs):
    q,codec,n,c,fc,overlay,m,shared=engines
    info=parent.json('inventory.json')
    if info['contexts']!=a.CONTEXTS or set(info['native_contexts'])!=set(a.CONTEXTS+si.EXT):raise ValueError('reference contexts')
    old=parent.json('certificates/STAGE0_CERTIFICATE.json');oldB={r['context']:codec.fraction(r['B_structural']) for r in old['records']}
    bounds={}
    for ctx in a.CONTEXTS:
        section=prior['summary']['contexts'][ctx]['summary']
        # New paired codec has a distinct explicit tag from the legacy portable codec.
        from fractions import Fraction
        def decode(r):return Fraction(int(r['numerator'],16),int(r['denominator'],16))
        D=decode(section['D']['B']);R=decode(section['R']['B'])
        if not 0<=R<=D<=oldB[ctx]:raise ValueError('bound nesting')
        bounds[ctx]={'D':codec.encode(D),'R_diagnostic':codec.encode(R),'Stage0':codec.encode(oldB[ctx])}
        role=parent.json('roles/'+ctx+'.json');si.verify_roles(role)
        z=parent.arrays('calibration/'+ctx+'.npz',si.KEYS+['group','nf2_row_id']);si.schema(z)
        np.testing.assert_array_equal(z['indices'],role['calibration_indices']);np.testing.assert_array_equal(z['nf2_row_id'],role['calibration_nf2_row_ids'])
        if set(z['group'].astype(str))!=set(role['calibration_groups']):raise ValueError('calibration groups')
    for ctx in info['native_contexts']:
        z=parent.arrays('native/'+ctx+'.npz',si.KEYS);si.schema(z)
        if ctx not in ['final']+si.EXT:
            role=parent.json('roles/'+ctx+'.json');np.testing.assert_array_equal(z['indices'],role['test_indices'])
    outputs['REFERENCE_PASS.json']=a.save(out/'REFERENCE_PASS.json',{'bounds':bounds,'contexts':a.CONTEXTS,'native_contexts':info['native_contexts'],'target_members_materialized':False,'parity_scope':'inherited certified native b/c/h; no new feature inference'})

def calibrate(parent,addon,engines,prior,out,ledger,outputs):
    q,codec,n,c,fc,overlay,m,shared=engines
    refs=phase_file('preflight',prior,'REFERENCE_PASS.json',ledger)
    for ctx in a.CONTEXTS:
        z=parent.arrays('calibration/'+ctx+'.npz',si.KEYS+['group','nf2_row_id','MEAS_CD']);si.schema(z)
        role=parent.json('roles/'+ctx+'.json');si.verify_roles(role)
        np.testing.assert_array_equal(z['indices'],role['calibration_indices']);np.testing.assert_array_equal(z['nf2_row_id'],role['calibration_nf2_row_ids'])
        if set(z['group'].astype(str))!=set(role['calibration_groups']):raise ValueError('calibration identity mismatch')
        oldB=codec.fraction(refs['bounds'][ctx]['Stage0']);B=codec.fraction(refs['bounds'][ctx]['D'])
        values=(z['BASE_CD'],z['core'],z['anchor'],z['MEAS_CD'],z['group'].astype(str))
        oldH=parent.json(f'scalars/{si.OLD_H[0]}_{ctx}.json');h=n.fit_scalar(*values,oldB);scalar_match(h,oldH,codec)
        oldK=addon.json(f'scalars/{si.OLD_KL[0]}_{ctx}.json');k=c.fit_kl_scalar(*values,oldB);k.update(candidate=si.OLD_KL[0],context=ctx);shared.scalar_equal(k,oldK,codec)
        results=[n.fit_scalar(*values,B),c.fit_kl_scalar(*values,B)]
        for label,result in zip(si.LABELS,results):
            if B==oldB:
                if label==si.LABELS[0]:scalar_match(result,oldH,codec)
                else:
                    test=dict(result,candidate=si.OLD_KL[0],context=ctx);shared.scalar_equal(test,oldK,codec)
            result.update(candidate=label,context=ctx)
            name=f'calibrator_{label}_{ctx}.json';codec.write_json(out/name,result);outputs[name]=a.sha((out/name).read_bytes())
        name='membership_'+ctx+'.json';outputs[name]=a.save(out/name,role)
    if len([n for n in outputs if n.startswith('calibrator_')])!=32:raise ValueError('32 scalar freeze')

def score(parent,addon,engines,prior,out,ledger,outputs):
    q,codec,n,c,fc,overlay,m,shared=engines
    info=parent.json('inventory.json')
    for ctx in info['native_contexts']:
        z=parent.arrays('native/'+ctx+'.npz',si.KEYS);si.schema(z)
        scalarctx='final' if ctx in si.EXT else ctx
        table={'indices':z['indices'],'BASE_CD':z['BASE_CD'],'qualified_gate':z['gate']}
        for label in si.LABELS:
            scalar=phase_file('calibrate',prior,f'calibrator_{label}_{scalarctx}.json',ledger)
            if scalar['candidate']!=label or scalar['context']!=scalarctx:raise ValueError('scalar identity')
            pred,e=n.predictions(scalar,z['BASE_CD'],z['core'],z['anchor'],z['gate'])
            for v,b,h,core,g in zip(pred,z['BASE_CD'],z['anchor'],z['core'],z['gate']):
                if not g and v!=b:raise ValueError('fallback')
                if g and core!=h and not 0<=(q.rat(v)-q.rat(h))/(q.rat(core)-q.rat(h))<=q.rat(scalar['t']):raise ValueError('inward fraction')
            table.update({label:pred,label+'__effective_fraction':e,label+'__strength':np.where(z['gate'],.5+.5*scalar['t'],0.),label+'__intervened':abs(pred-z['anchor'])>1e-12})
        name=f'inference_{ctx}.npz'
        with (out/name).open('xb') as f:np.savez_compressed(f,**z,**{k:v for k,v in table.items() if k not in z})
        outputs[name]=a.sha((out/name).read_bytes())
        if ctx!='final':
            if ctx not in si.EXT:table['nf2_row_id']=parent.json('roles/'+ctx+'.json')['test_nf2_row_ids']
            name=f'predictions_{ctx}.csv';pd.DataFrame(table).to_csv(out/name,index=False,mode='x');outputs[name]=a.sha((out/name).read_bytes())
    if sum(n.startswith('inference_') for n in outputs)!=18 or sum(n.startswith('predictions_') for n in outputs)!=17:raise ValueError('score inventory')

def exact_key_parity(old,new,keys):
    if old.duplicated(keys).any() or new.duplicated(keys).any():raise ValueError('duplicate metric keys')
    x=old.set_index(keys).sort_index();y=new.set_index(keys).reindex(x.index)
    if len(y)!=len(x) or y.isna().any().any() and not x.isna().any().any():raise ValueError('missing old metric keys')
    pd.testing.assert_frame_equal(x,y[x.columns],check_exact=True)

def assess(parent,addon,engines,prior,out,ledger,outputs):
    q,codec,n,c,fc,overlay,m,shared=engines
    frame=fc.unpack(parent.arrays('scoring/frame.npz'),parent.json('scoring/schema.json'))
    panels={k:np.array(v,int) for k,v in parent.json('scoring/panels.json').items()}
    if len(frame)!=29856 or len(panels)!=31:raise ValueError('sole frame/panel inventory')
    oldframes={ctx:addon.csv(f'prediction_csv/{ctx}.csv') for ctx in frame.split.unique()}
    frame=overlay.overlay(frame,oldframes);oldlabels=list(m.LABELS)
    if len(oldlabels)!=17 or list(m.REFERENCES)!=si.OLD_REFS:raise ValueError('old label/reference namespace')
    oldboot=m.bootstrap(frame);oldpanel=m.panel_metrics(frame,panels);oldgroups=m.group_metrics(frame);oldharms=m.harms(frame,panels)
    differences=[]
    for name,table in [('all_row_predictions',frame),('bootstrap',oldboot),('panel_metrics',oldpanel),('group_metrics',oldgroups),('harm_metrics',oldharms)]:
        raw=addon.raw('expected/'+name+'.csv','expected CSV comparison parse')
        shared.compare_tables(name,table,raw,ledger,differences)
    outputs['OLD_FLOAT_DIFFERENCES.json']=a.save(out/'OLD_FLOAT_DIFFERENCES.json',differences)
    if any(not d['within_inherited_audit_tolerance'] and not d['known_zero_sign_diagnostic'] for d in differences):raise ValueError('old metric discrepancy beyond inherited contract')
    original=frame.copy(deep=True)
    frame=si.typed_overlay(frame,{ctx:phase_file('score',prior,f'predictions_{ctx}.csv',ledger,'csv') for ctx in frame.split.unique()},si.LABELS)
    pd.testing.assert_frame_equal(frame[original.columns],original,check_exact=True)
    m.CONTROLS=oldlabels;m.CANDIDATES=list(si.LABELS);m.LABELS=si.LABELS+oldlabels;m.REFERENCES=list(si.REFS);m.run=types.SimpleNamespace(LABELS=si.LABELS,EXTERNAL=si.EXT)
    tables={'panel_metrics':m.panel_metrics(frame,panels),'bootstrap':m.bootstrap(frame),'group_metrics':m.group_metrics(frame),'harm_metrics':m.harms(frame,panels)}
    tb=tables['bootstrap']
    exact_key_parity(oldboot,tb[tb.candidate.isin(oldlabels)&tb.reference.isin(si.OLD_REFS)],['candidate','assignment','reference'])
    exact_key_parity(oldpanel,tables['panel_metrics'].query('candidate in @oldlabels'),['candidate','panel'])
    exact_key_parity(oldgroups,tables['group_metrics'].query('candidate in @oldlabels'),['candidate','assignment','group'])
    oldharmrefs=si.OLD_REFS+list(m.BASELINES)
    exact_key_parity(oldharms,tables['harm_metrics'].query('candidate in @oldlabels and reference in @oldharmrefs'),['candidate','reference','panel'])
    tables['decisions']=m.decisions(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
    tables['candidate_summary']=m.summary(tables['panel_metrics'],tables['bootstrap'],tables['group_metrics'])
    risk,bundles,interventions=m.extras(frame,panels)
    tables.update(expected_harm_metrics=risk,bundle_harm_metrics=bundles,intervention_metrics=interventions,all_row_predictions=frame)
    if len(tables['panel_metrics'])!=589 or len(tables['bootstrap'])!=342 or len(tables['harm_metrics'])!=6479 or len(tables['decisions'])!=2:raise ValueError('fixed19-label assessment counts')
    for name,t in tables.items():
        path=out/(name+'.csv');t.to_csv(path,index=False,mode='x');outputs[path.name]=a.sha(path.read_bytes())
    outputs['PARITY.json']=a.save(out/'PARITY.json',{'old_columns_exact':True,'old_seven_reference_bootstrap_exact_by_keys':True,'old_panel_group_harm_metrics_exact_by_keys':True,'old_float_difference_cells':len(differences),'old_differences_require_independent_review':bool(differences),'counts':{k:len(v) for k,v in tables.items()}})

def execute(args):
    def work(out,ledger,outputs,deadline):
        reg=a.json_read(a.HERE/a.REGISTRY_NAME,args.registry_sha256,ledger)
        ap=a.authenticate(reg,args.registry_sha256,args.approval,args.approval_sha256,args.phase,ledger)
        prior=complete(PREVIOUS[args.phase],ap['predecessor_sha256'],args.registry_sha256,ledger)
        parent=si.Reader(si.archive(a.ROOT/si.PARENT,si.PARENT_SHA,si.PARENT_MANIFEST,ledger),args.phase,'parent',ledger)
        addon=si.Reader(si.archive(a.ROOT/si.ADDON,si.ADDON_SHA,si.ADDON_MANIFEST,ledger),args.phase,'KL addon',ledger)
        with si.engines(reg,parent,addon,ledger) as eng:globals()[args.phase](parent,addon,eng,prior,out,ledger,outputs)
        a.authenticate(reg,args.registry_sha256,args.approval,args.approval_sha256,args.phase,ledger)
        complete(PREVIOUS[args.phase],ap['predecessor_sha256'],args.registry_sha256,ledger)
        for name,pin in [(si.PARENT,si.PARENT_SHA),(si.ADDON,si.ADDON_SHA)]:a.read(a.ROOT/name,pin,ledger,'end archive authentication')
        return {'new_fits':0,'new_labels':si.LABELS,'R_scored':False,'predecessor_sha256':ap['predecessor_sha256'],'phase':args.phase}
    # Predecessor copied into durable top receipt after approved read by work,
    # without any arrays being materialized outside the protected attempt.
    return a.attempt(a.HERE/args.phase,{'phase':args.phase,'registry_sha256':args.registry_sha256,'approval_sha256':args.approval_sha256},work)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=list(PREVIOUS))
    for k in ['registry-sha256','approval','approval-sha256']:p.add_argument('--'+k,required=True)
    print(json.dumps(execute(p.parse_args()),sort_keys=True))
