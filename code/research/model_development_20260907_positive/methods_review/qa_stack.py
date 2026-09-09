"""Independent bounded tests; writes only this review directory, never fits real models."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('reviewed_stack', ROOT/'historical_stack.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def targeted():
    frame, enclosing, _ = m.load_training('group_20260906_fold_0')
    original = m.v2.load_data
    d = original()
    altered = {k: np.array(v, copy=True) for k,v in d.items()}
    outside = np.setdiff1d(np.arange(len(d['MEAS_CD'])), enclosing)
    altered['MEAS_CD'][outside] = 987654321.
    m.v2.load_data = lambda: altered
    try:
        again, idx, _ = m.load_training('group_20260906_fold_0')
    finally:
        m.v2.load_data = original
    pd.testing.assert_frame_equal(frame, again)
    np.testing.assert_array_equal(enclosing, idx)
    # A two-sided constant residual admits an exact convex solution.
    y = np.array([20., 30., 40., 50.])/1e4
    toy = pd.DataFrame({'measured_CD':y,'mean8_CD':y+.0005,'xlarge_CD':y-.0005,
                        'group':['a','a','b','b'],'source':['s','s','s','s'],'context':['group']*4})
    for j,c in enumerate(m.COMPONENTS): toy[c] = y + (.0005 if j%2==0 else -.0005)
    results = {}
    for key,baselines in m.OBJECTIVES.items():
        sol=m.solve(toy,m.training_panels(toy),baselines)
        w=np.array([sol['weights'][c] for c in m.COMPONENTS]);p=toy[m.COMPONENTS].to_numpy()@w
        assert w.min()>=-1e-9 and abs(w.sum()-1)<1e-9
        assert np.max(np.abs(p-y))<1e-9
        assert sol['first_optimal_ratio']<1e-7
        results[key]={'first_ratio':sol['first_optimal_ratio'],'max_error_CD':float(np.max(np.abs(p-y)))}
    return {'outside_training_labels_mutated':len(outside),'training_frame_unchanged':True,'synthetic_convex_tests':results}

def saved():
    out=ROOT/'historical_results'
    if not (out/'all_row_predictions.csv').exists(): return {'status':'not_complete_no_polling'}
    d=pd.read_csv(out/'all_row_predictions.csv',float_precision='round_trip',low_memory=False)
    maxdelta=0.;training_records=0;hashes=0
    for path in sorted(out.glob('weights_*.json')):
        a=json.loads(path.read_text());name=a['split'];f,idx,h=m.load_training(name)
        for p,digest in a['input_sha256'].items():
            assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest;hashes+=1
        assert set(a['training_nf2_row_ids'])==set(f.loc[f.context=='group','nf2_row_id'])
        for key,s in a['solutions'].items():
            w=np.array([s['weights'][c] for c in m.COMPONENTS]);assert w.min()>=-1e-9 and abs(w.sum()-1)<1e-9
            pred=f[m.COMPONENTS].to_numpy()@w
            for score in s['training_panels']:
                pn=score['panel']
                if pn.startswith('group_source_'):mask=(f.context=='group')&(f.source==pn.removeprefix('group_source_'))
                elif pn in ['group_pooled','group_equal_identity']:mask=f.context=='group'
                else:mask=f.context==pn.rsplit('_',2)[0] if pn.endswith('_equal_identity') else f.context==pn.removesuffix('_pooled')
                ix=np.flatnonzero(mask);assert len(ix)==score['rows']
                wt=np.ones(len(ix))/len(ix)
                if pn.endswith('equal_identity'):
                    counts=f.iloc[ix].group.value_counts();wt=np.array([1/(len(counts)*counts[g]) for g in f.iloc[ix].group])
                e=np.abs(pred[ix]-f.measured_CD.to_numpy()[ix]);be=np.abs(f[score['baseline']].to_numpy()[ix]-f.measured_CD.to_numpy()[ix])
                ratio=float(wt@e/(wt@be));assert abs(ratio-score['actual_ratio'])<1e-10
                training_records+=1
            splits=['SG_exposed','W_new_challenge'] if name=='final' else [name]
            for split in splits:
                part=d[d.split==split];p=part[m.COMPONENTS].to_numpy()@w
                if name=='final':
                    gate=part.inference_gate.map(lambda x:str(x).lower()=='true' or x==1).to_numpy(bool)
                    p[~gate]=part.mean8_CD.to_numpy()[~gate]
                    np.testing.assert_array_equal(part[key].to_numpy()[~gate],part.mean8_CD.to_numpy()[~gate])
                else:
                    assert set(part.nf2_row_id).isdisjoint(a['training_nf2_row_ids'])
                    assert set(part.group).isdisjoint(a['training_groups'])
                delta=float(np.max(np.abs(p-part[key].to_numpy())));maxdelta=max(maxdelta,delta);assert delta<1e-12
    metrics=pd.read_csv(out/'panel_metrics.csv',float_precision='round_trip');checked=0
    for _,row in metrics.iterrows():
        pn=row.panel
        if pn.startswith('history_'):
            _,seed,source=pn.split('_',2);mask=d.split.str.startswith('group_'+seed+'_')
            if source!='pooled':mask &= d.source==source
        elif pn.startswith('strict_source_'):mask=d.split==pn
        else:
            prefix='SG_exposed' if pn.startswith('SG_exposed') else 'W_new_challenge';suffix=pn[len(prefix)+1:];mask=d.split==prefix
            if suffix!='pooled':mask &= d['airfoil' if prefix=='SG_exposed' else 'configuration']==suffix
        f=d[mask];assert len(f)==row.rows
        err=np.abs(f[row.candidate].to_numpy()-f.measured_CD.to_numpy())
        for key,val in [('mae_CD',err.mean()),('median_absolute_error_CD',np.median(err)),('p90_absolute_error_CD',np.quantile(err,.9))]:assert abs(row[key]-val)<1e-12
        for base in ['xlarge_CD','mean8_CD']:
            be=np.abs(f[base].to_numpy()-f.measured_CD.to_numpy())
            assert abs(row[base+'_improvement_percent']-100*(1-err.sum()/be.sum()))<1e-8
            assert row[base+'_worse_rows']==int((err>be+1e-14).sum())
        checked+=1
    return {'status':'complete','training_panel_records':training_records,'input_hashes_verified':hashes,'panel_candidate_rows':checked,'max_prediction_delta_CD':maxdelta,
            'external_panel_rows':metrics[metrics.panel.isin(['SG_exposed_pooled','W_new_challenge_pooled'])][['candidate','panel','rows']].to_dict('records')}

def reconciliation():
    tables=pd.read_csv(ROOT/'external_comparisons.csv',float_precision='round_trip')
    sources={k:pd.read_csv(ROOT/k/'all_row_predictions.csv',float_precision='round_trip',low_memory=False) for k in tables.prediction_origin.unique()}
    def check(row,f):
        assert len(f)==row.rows
        e=np.abs(f[row.candidate].to_numpy()-f.measured_CD.to_numpy())
        for key,value in [('mae_CD',e.mean()),('median_absolute_error_CD',np.median(e)),('p90_absolute_error_CD',np.quantile(e,.9))]:assert abs(row[key]-value)<1e-12
        for base in ['xlarge_CD','mean8_CD']:
            be=np.abs(f[base].to_numpy()-f.measured_CD.to_numpy())
            assert abs(row[base+'_improvement_percent']-100*(1-e.sum()/be.sum()))<1e-8
            assert row[base+'_worse_rows']==int((e>be+1e-14).sum())
    for _,row in tables.iterrows():
        d=sources[row.prediction_origin];scope,cohort,subset=row.panel.split('/');mask=d.split==cohort
        if scope=='eligible_only':mask &= d.inference_gate.map(lambda x:str(x).lower()=='true' or x==1)
        if subset!='pooled':mask &= d['airfoil' if cohort=='SG_exposed' else 'configuration']==subset
        check(row,d[mask])
    d=sources['historical_results'];counts={}
    for filename in ['split_metrics.csv','identity_group_metrics.csv']:
        t=pd.read_csv(ROOT/'historical_results'/filename,float_precision='round_trip')
        for _,row in t.iterrows():
            split,sep,group=row.panel.partition(':');f=d[d.split==split]
            if sep:f=f[f.group==group]
            check(row,f)
        counts[filename]=len(t)
    prov=json.loads((ROOT/'completion_provenance.json').read_text());n=0
    for section in ['rechecked_input_sha256','additional_dependencies_recorded_at_completion_not_before_fit','output_sha256']:
        for p,h in prov[section].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;n+=1
    eligible=tables[(tables.candidate=='primary_both')&tables.panel.str.startswith('eligible_only/')]
    return {'external_comparison_records':len(tables),'additional_metric_records':counts,'completion_hash_records':n,
            'primary_eligible':eligible[['panel','rows','mae_drag_counts','xlarge_CD_improvement_percent','mean8_CD_improvement_percent']].to_dict('records')}

if __name__=='__main__':
    result={'source_sha256':hashlib.sha256((ROOT/'historical_stack.py').read_bytes()).hexdigest(),'targeted':targeted(),'saved':saved()}
    if (ROOT/'reconciliation.json').exists(): result['reconciliation']=reconciliation()
    (HERE/'qa_stack_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
