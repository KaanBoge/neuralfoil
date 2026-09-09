"""Read-only verification of completed Cycle 3 split artifacts; no fitting."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
RESULTS=ROOT/'results'
sys.path.insert(0,str(ROOT.parent/'model_development_20260906_v2'))
import develop_v2 as v


def close(a,b,label):
    assert np.allclose(a,b,atol=1e-9,rtol=1e-11),label


def groupsplit(groups,k,seed):
    names=np.unique(groups).copy()
    np.random.default_rng(seed).shuffle(names)
    return [np.isin(groups,names[i::k]) for i in range(k)]


def ratios(pred,idx):
    e=np.abs(pred-d['MEAS_CD'][idx]);b=np.abs(d['BASE_CD'][idx]-d['MEAS_CD'][idx])
    assert b.sum()>0
    value={'overall':float(e.sum()/b.sum())}
    for s in np.unique(d['source'][idx]):
        mask=d['source'][idx]==s;assert b[mask].sum()>0
        value['source_'+s]=float(e[mask].sum()/b[mask].sum())
    f=pd.DataFrame({'g':d['group'][idx],'e':e,'b':b}).groupby('g')[['e','b']].mean()
    value['equal_group']=float(f.e.sum()/f.b.sum())
    return value


def assert_predictions(z,idx,csv=False):
    for label in labels:
        x=z[label];assert x.shape==(len(idx),) and np.isfinite(x).all() and (x>0).all(),label
        if label not in ['identity','xlarge_fixed']:
            assert np.all(x>=.5*d['BASE_CD'][idx]-1e-12) and np.all(x<=2*d['BASE_CD'][idx]+1e-12)
    for name,key in [('identity','BASE_CD'),('xlarge_fixed','XLARGE_CD')]:
        if csv:assert np.allclose(z[name],d[key][idx],atol=1e-14,rtol=0)
        else:assert np.array_equal(z[name],d[key][idx])
    for family in manifest['families']:
        close(z[family+'__0.5'],d['BASE_CD'][idx]+.5*(z[family+'__1']-d['BASE_CD'][idx]),family+' shrinkage')


def check_selection(prefix,expected_idx,selection,recorded_choices):
    group_path=RESULTS/(prefix+'_inner_group.npz')
    with np.load(group_path,allow_pickle=False) as z:
        idx=z['indices'];assert np.array_equal(idx,expected_idx),prefix+' indices'
        assert_predictions(z,idx)
        oof={label:z[label].copy() for label in labels}
    if selection is not None:
        folds=groupsplit(d['group'][idx],3,20260907)
        assert np.all(np.sum(folds,axis=0)==1)
        for te,record in zip(folds,selection['group_folds']):
            assert not set(d['group'][idx[te]])&set(d['group'][idx[~te]])
            assert record['train_rows']==int((~te).sum()) and record['test_rows']==int(te.sum())
    transferred={name:{} for name in labels};support=[]
    for source in sorted(set(d['source'][idx])):
        te=d['source'][idx]==source
        tr=~te&~np.isin(d['group'][idx],d['group'][idx[te]])
        available=len(set(d['group'][idx[tr]]))>=6 and tr.sum()>=300
        support.append({'source':source,'train_rows':int(tr.sum()),'train_groups':len(set(d['group'][idx[tr]])),
            'test_rows':int(te.sum()),'scored':bool(available)})
        if selection is not None:
            record=next(x for x in selection['source_folds'] if x['source']==source)
            assert (record['status']=='scored')==available
            assert record['train_rows']==int(tr.sum())
        p=RESULTS/(prefix+'_inner_transfer_'+source+'.npz')
        if not available:
            assert not p.exists();continue
        with np.load(p,allow_pickle=False) as z:
            assert np.array_equal(z['train_indices'],idx[tr]) and np.array_equal(z['test_indices'],idx[te])
            assert not set(d['group'][z['train_indices']])&set(d['group'][z['test_indices']])
            assert set(d['source'][z['test_indices']])=={source} and source not in set(d['source'][z['train_indices']])
            assert_predictions(z,idx[te])
            denom=np.abs(d['BASE_CD'][idx[te]]-d['MEAS_CD'][idx[te]]).sum()
            for label in labels:transferred[label][source]=float(np.abs(z[label]-d['MEAS_CD'][idx[te]]).sum()/denom)
    n=sum(x['scored'] for x in support)
    chosen={k:'identity' for k in ['guarded_pooled','minimax','transfer_minimax']};best={k:1. for k in chosen}
    for label in labels:
        rr=ratios(oof[label],idx);worst=max(rr.values());guard=all(x<1 for k,x in rr.items() if k!='overall')
        trans=max([worst]+list(transferred[label].values())) if n>=2 else worst
        if selection is not None:
            rec=next(x for x in selection['candidates'] if x['candidate']==label)
            assert set(rr)==set(rec['group_ratios']) and set(transferred[label])==set(rec['purged_source_ratios'])
            for key,value in rr.items():close(value,rec['group_ratios'][key],(prefix,label,key))
            for key,value in transferred[label].items():close(value,rec['purged_source_ratios'][key],(prefix,label,key))
            close(worst,rec['group_worst_ratio'],(prefix,label,'worst'));assert guard==rec['guard_pass']
            close(trans,rec['transfer_objective'],(prefix,label,'transfer'))
        for rule,score in [('guarded_pooled',rr['overall'] if guard else np.inf),('minimax',worst),('transfer_minimax',trans)]:
            if score<best[rule]-1e-12:chosen[rule]=label;best[rule]=score
    if recorded_choices is not None:assert chosen==recorded_choices,(prefix,chosen,recorded_choices)
    if selection is not None:assert selection['transfer_fallback_to_group_minimax']==(n<2)
    return {'split':prefix,'inner_rows':len(idx),'chosen':chosen,'source_support':support,'transfer_fallback':n<2}


def independently_metric(f,candidate,baseline,bootstrap):
    e=(f[candidate]-f.measured_CD).abs()*1e4;b=(f[baseline]-f.measured_CD).abs()*1e4
    g=pd.DataFrame({'g':f.group,'e':e,'b':b}).groupby('g')[['e','b']].agg(['sum','mean'])
    ret={'rows':len(f),'groups':len(g),'candidate_mae_counts':float(e.mean()),'baseline_mae_counts':float(b.mean()),
        'relative_reduction_percent':float(100*(1-e.sum()/b.sum())),
        'candidate_median_counts':float(e.median()),'candidate_p90_counts':float(e.quantile(.9)),
        'baseline_median_counts':float(b.median()),'baseline_p90_counts':float(b.quantile(.9)),
        'worse_rows':int((e>b).sum()),'equal_rows':int((e==b).sum()),
        'worse_groups':int((g[('e','mean')]>g[('b','mean')]).sum()),
        'equal_group_relative_reduction_percent':float(100*(1-g[('e','mean')].sum()/g[('b','mean')].sum()))}
    if bootstrap:
        rng=np.random.default_rng(20260909);ii=rng.integers(len(g),size=(20000,len(g)))
        gain=100*(1-g[('e','sum')].to_numpy()[ii].sum(axis=1)/g[('b','sum')].to_numpy()[ii].sum(axis=1))
        ret['bootstrap_95']=np.quantile(gain,[.025,.975]).tolist();ret['bootstrap_one_sided']=float(np.quantile(gain,.05))
    return ret


d=v.load_data();ids=np.arange(len(d['BASE_CD']))
manifest=json.loads((RESULTS/'run_manifest.json').read_text());labels=manifest['candidate_labels']
assert len(labels)==len(set(labels)) and len(d['BASE_CD'])==8371 and len(set(d['group']))==93
assert np.all((d['Re']>0)&(d['Re']<=600000)&(np.abs(d['alpha'])<=12)&(d['X16'][:,2]>=.05)&(d['X16'][:,2]<=.2))
assert set(d['source'])=={'stec8','vol1','vol2','vol3'}
assert not np.isin(np.char.lower(d['af']),['sg6050','sg6051','w1011','w1015']).any()
for path,h in manifest['hashes'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
allframes=[];audit=[]
for logpath in sorted(RESULTS.glob('log_*.json')):
    log=json.loads(logpath.read_text());split=log['split']
    if split.startswith('group_'):
        seed=int(split.split('_')[1]);fold=int(split.rsplit('_',1)[1]);te=groupsplit(d['group'],5,seed)[fold];tr=~te
    else:
        source=split.removeprefix('strict_source_');te=d['source']!='stec8' if source=='all_uiuc_volumes' else d['source']==source
        tr=~te&~np.isin(d['group'],d['group'][te])
    assert not set(d['group'][tr])&set(d['group'][te])
    assert log['train_rows']==int(tr.sum()) and log['test_rows']==int(te.sum())
    assert log['train_groups']==len(set(d['group'][tr])) and log['test_groups']==len(set(d['group'][te]))
    audit.append(check_selection(split,ids[tr],log['selection'],log['selected']))
    f=pd.read_csv(RESULTS/('predictions_'+split+'.csv'))
    assert not f.nf2_row_id.duplicated().any() and np.array_equal(f.nf2_row_id,d['nf2_row_id'][te])
    for col,key in [('group','group'),('source','source'),('entry','entry'),('Re','Re'),('alpha','alpha'),('measured_CD','MEAS_CD'),('mean8_CD','BASE_CD'),('xlarge_CD','XLARGE_CD')]:
        if col in ['group','source','entry']:assert np.array_equal(f[col],d[key][te])
        else:close(f[col],d[key][te],(split,col))
    assert_predictions({k:f[k].to_numpy() for k in labels},ids[te],csv=True)
    for rule,label in log['selected'].items():assert np.array_equal(f[rule],f[label])
    prior=pd.read_csv(v.ROOT/'results'/('predictions_'+split+'.csv'))
    z=f.merge(prior[['nf2_row_id','guarded_pooled','cycle1_nested']],on='nf2_row_id',validate='one_to_one',suffixes=('_new','_old'))
    assert len(z)==len(f)==len(prior)
    assert np.array_equal(z.cycle2_nested,z.guarded_pooled_old)
    assert np.array_equal(z.cycle1_nested_new,z.cycle1_nested_old)
    allframes.append(f)
metrics_checks=0;primary=[]
if (RESULTS/'metrics.json').exists():
    assert len(audit)==15,'Metrics must represent all15 splits'
    allpred=pd.concat(allframes,ignore_index=True)
    saved=json.loads((RESULTS/'metrics.json').read_text())
    evaluations=['group_20260906','group_20260908']+['strict_source_'+s for s in ['stec8','vol1','vol2','vol3','all_uiuc_volumes']]
    metric_labels=labels+['guarded_pooled','minimax','transfer_minimax','cycle1_nested','cycle2_nested']
    expected={(ev,c,b) for ev in evaluations for c in metric_labels for b in ['xlarge_CD','mean8_CD']}
    observed=[(s['evaluation'],s['candidate'],s['baseline']) for s in saved]
    assert len(observed)==len(set(observed)) and set(observed)==expected
    for ev in sorted(set(s['evaluation'] for s in saved)):
        f=allpred[allpred.split.str.startswith(ev)];assert not f.nf2_row_id.duplicated().any()
        if ev.startswith('group_'):assert len(f)==8371
        for s in [s for s in saved if s['evaluation']==ev]:
            got=independently_metric(f,s['candidate'],s['baseline'],'conditional_cluster_bootstrap' in s)
            for key,value in got.items():
                if key=='bootstrap_95':close(value,s['conditional_cluster_bootstrap']['two_sided_95_percent'],(ev,s['candidate'],key))
                elif key=='bootstrap_one_sided':close(value,s['conditional_cluster_bootstrap']['one_sided_95_lower_percent'],(ev,s['candidate'],key))
                else:close(value,s[key],(ev,s['candidate'],key))
            metrics_checks+=1
            if s['candidate'] in ['guarded_pooled','minimax','transfer_minimax','cycle1_nested','cycle2_nested'] and s['baseline']=='xlarge_CD':
                primary.append({'evaluation':ev,'candidate':s['candidate'],**got})
final=None
if (RESULTS/'freeze.json').exists():
    freeze=json.loads((RESULTS/'freeze.json').read_text())
    final=check_selection('final',ids,freeze['selection'],freeze['selected'])
    for name,h in freeze['artifact_hashes'].items():assert hashlib.sha256((RESULTS/name).read_bytes()).hexdigest()==h
summary={'completed_split_checks':len(audit),'candidate_labels':len(labels),'selection_checks':audit,
    'metric_combinations_checked':metrics_checks,'primary_results':primary,'final_selection_check':final,
    'scope':'Independent artifact arithmetic/disjointness/metadata audit, no fitting; cannot reconstruct native training from predictions alone',
    'manifest_sha256':hashlib.sha256((RESULTS/'run_manifest.json').read_bytes()).hexdigest()}
name='complete_qa.json' if final is not None else 'partial_qa.json'
(OUT/name).write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(json.dumps({'splits':len(audit),'metrics':metrics_checks,'final':final,'primary':primary},indent=2))
