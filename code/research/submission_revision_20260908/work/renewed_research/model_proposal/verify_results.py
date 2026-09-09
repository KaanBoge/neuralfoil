"""Separate arithmetic replay, without importing calibration or metric functions."""
from pathlib import Path
import io,json,hashlib,math,time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PROJECT=next(p for p in HERE.parents if p.name=='NeuralFoil_Research_Paper')
A=PROJECT/'model_development_20260907_cap_ablation'
LABEL='calibrated_incremental_harm_001'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def checked(p,h):
    z=Path(p).read_bytes();assert hashlib.sha256(z).hexdigest()==h,p
    return z
def npz(p,h):
    with np.load(io.BytesIO(checked(p,h)),allow_pickle=False) as z:return {k:z[k] for k in z.files}
def close(a,b,atol=1e-11):np.testing.assert_allclose(a,b,rtol=0,atol=atol)


def main():
    dest=HERE/'verification';assert not dest.exists()
    freeze=read(HERE/'results/freeze.json');complete=read(HERE/'results/complete.json')
    report=read(HERE/'assessment/report.json');af=read(A/'results/freeze.json');ac=read(A/'results/complete.json')
    assert freeze['external_outcomes_opened'] is False and freeze['calibrator_count']==16
    assert sha(HERE/'results/freeze.json')==complete['freeze_sha256']
    assert freeze['frozen_utc']<=complete['completed_utc']
    verified={}
    for record in [freeze,complete,report]:
        for key in ['artifact_sha256','source_input_sha256','external_input_sha256','output_sha256']:
            for p,h in record.get(key,{}).items():checked(p,h);verified[p]=h
    models={};groups_checked=0
    for context in freeze['contexts']:
        m=read(HERE/'results'/f'calibrator_{context}.json');models[context]=m
        source=A/'results'/f'calibration_{context}.npz';z=npz(source,af['artifact_sha256'][str(source)])
        member=read(HERE/'results'/f'membership_{context}.json')
        for a,b in [('proper_groups','calibration_groups'),('proper_groups','test_groups'),('calibration_groups','test_groups')]:
            assert not set(member[a])&set(member[b])
        b,c,y=z['BASE_CD'],z['CORE_CD_capped'],z['MEAS_CD'];h=b+(c-b)/2
        assert ((c>=b/2)&(c<=2*b)).all()
        loss=np.maximum(np.abs(c-y)-np.abs(h-y),0)/b
        assert (loss<=.5).all()
        names=sorted(set(z['group']));values=np.array([np.mean(loss[z['group']==g]) for g in names])
        upper=min(.5,float(values.mean())+.5*math.sqrt(math.log(20)/(2*len(names))))
        close(m['upper_bound'],upper,1e-16);close(m['t'],min(1,.01/upper),1e-16)
        close(m['group_endpoint_losses'],values,1e-16)
        assert names==m['group_names'];groups_checked+=len(names)
    native_rows=0;max_delta=0.
    for context in freeze['contexts']+['SG_exposed','W_new_challenge']:
        ext=context in ['SG_exposed','W_new_challenge'];folder='exposed_results' if ext else 'results'
        old=A/folder/(f'{context}_inference.npz' if ext else f'inference_{context}.npz')
        h=(ac['output_sha256'] if ext else af['artifact_sha256'])[str(old)];z=npz(old,h)
        fresh=HERE/folder/f'inference_{context}.npz';n=npz(fresh,complete['output_sha256'][str(fresh)])
        b,c,g=z['BASE_CD'],z['proper_core_capped'],z['gate'];c=np.where(g,c,b)
        anchor=b+.5*(c-b);t=models['final' if ext else context]['t']
        expected=np.where(g,anchor+t*(c-anchor),b)
        np.testing.assert_array_equal(n['prediction'],expected)
        np.testing.assert_array_equal(n['prediction'][~g],b[~g])
        np.testing.assert_array_equal(n['applied_strength'],np.where(g,.5+.5*t,0))
        native_rows+=len(b);max_delta=max(max_delta,float(abs(expected-n['prediction']).max(initial=0)))
    frame=pd.read_csv(HERE/'assessment/all_row_predictions.csv',low_memory=False)
    table=pd.read_csv(HERE/'assessment/panel_metrics.csv');boot=pd.read_csv(HERE/'assessment/bootstrap.csv')
    groups=pd.read_csv(HERE/'assessment/group_metrics.csv');harms=pd.read_csv(HERE/'assessment/harm_metrics.csv')
    decisions=pd.read_csv(HERE/'assessment/decisions.csv')
    panels={}
    for seed in [20260906,20260908]:
        mask=frame.split.str.startswith(f'group_{seed}_');panels[f'history_{seed}_pooled']=mask
        for source in frame.loc[mask,'source'].unique():panels[f'history_{seed}_{source}']=mask&frame.source.eq(source)
    for split in frame.split.unique():
        if split.startswith('strict_source_'):panels[split]=frame.split.eq(split)
        if split in ['SG_exposed','W_new_challenge']:
            mask=frame.split.eq(split);panels[split+'_pooled']=mask
            eligible=mask&frame.interval_applicable.astype(bool);panels[f'eligible_only/{split}/pooled']=eligible
            for config in frame.loc[mask,'configuration'].unique():
                panels[f'{split}_{config}']=mask&frame.configuration.eq(config)
                panels[f'eligible_only/{split}/{config}']=eligible&frame.configuration.eq(config)
    assert len(panels)==31 and len(frame)==29856
    for row in table.to_dict('records'):
        f=frame[panels[row['panel']]];err=abs(f[row['candidate']]-f.measured_CD).to_numpy()
        assert len(f)==row['rows'];close(err.mean(),row['mae_CD'],1e-14)
        close(np.quantile(err,.9),row['p90_absolute_error_CD'],1e-14)
        close(np.median(err),row['median_absolute_error_CD'],1e-14)
        for ref in ['mean8_CD','xlarge_CD']:
            baseline=abs(f[ref]-f.measured_CD).to_numpy()
            close(100*(1-err.sum()/baseline.sum()),row[ref+'_improvement_percent'],1e-9)
            assert int((err>baseline+1e-12).sum())==row[ref+'_worse_rows']
    for row in harms.to_dict('records'):
        f=frame[panels[row['panel']]];delta=abs(f[row['candidate']]-f.measured_CD)-abs(f[row['reference']]-f.measured_CD)
        close(np.maximum(delta,0).mean(),row['mean_positive_excess_absolute_error_CD'],1e-14)
        assert int((delta>1e-12).sum())==row['worse_rows']
    for seed in [20260906,20260908]:
        f=frame[frame.split.str.startswith(f'group_{seed}_')];ids,inv=np.unique(f.group,return_inverse=True)
        assert len(ids)==93 and f.nf2_row_id.nunique()==8371
        weights=np.random.default_rng(2026090831).multinomial(93,np.full(93,1/93),size=20000)
        sums={label:np.bincount(inv,weights=abs(f[label]-f.measured_CD)) for label in table.candidate.unique()}
        for row in boot[boot.assignment.eq(seed)].to_dict('records'):
            ratio=100*(1-(weights@sums[row['candidate']])/(weights@sums[row['reference']]))
            close(np.quantile(ratio,[.025,.975]),[row['conditional_95pct_lower'],row['conditional_95pct_upper']],1e-9)
            close(100*(1-sums[row['candidate']].sum()/sums[row['reference']].sum()),row['remaining_MAE_reduction_percent'],1e-9)
    # Replay conjunctions independently, including both native baseline columns.
    r=decisions.iloc[0];t=table[table.candidate.eq(LABEL)];fields=['xlarge_CD_improvement_percent','mean8_CD_improvement_percent']
    ext=t[t.panel.str.startswith('eligible_only/')][fields].to_numpy()
    strict=t[t.panel.str.startswith('strict_source_')][fields].to_numpy()
    performance_ref=table[table.candidate.eq('unpenalized_transfer')&table.panel.str.startswith('eligible_only/')][fields].to_numpy()
    extok=(ext< -1e-6).sum()<=(performance_ref< -1e-6).sum() and ext.min()>=performance_ref.min()-1e-6
    for ref,prefix in [('unpenalized_transfer','performance'),('half_strength','robustness')]:
        gain=(boot[boot.candidate.eq(LABEL)&boot.reference.eq(ref)].remaining_MAE_reduction_percent>=1-1e-6).all()
        guard=True
        for seed in [20260906,20260908]:
            c=groups[groups.candidate.eq(LABEL)&groups.assignment.eq(seed)].xlarge_improvement_percent
            z=groups[groups.candidate.eq(ref)&groups.assignment.eq(seed)].xlarge_improvement_percent
            guard&=(c< -1e-6).sum()<=(z< -1e-6).sum() and max(0,-c.min())<=max(0,-z.min())+1e-6
        additional=bool((strict>=-1e-6).all() and extok) if prefix=='performance' else bool((t[fields].to_numpy()>=-1e-6).all())
        assert bool(gain and guard and additional)==bool(r[prefix+'_advance'])
    result={'status':'PASS','checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
       'calibrators':16,'calibration_identity_contexts':groups_checked,'native_reference_rows':native_rows,
       'native_max_abs_delta_CD':max_delta,'native_fallback_exact':True,'panel_records_replayed':len(table),
       'harm_records_replayed':len(harms),'bootstrap_records_replayed':len(boot),'decisions_replayed':1,
       'input_hash_count':len(verified),'source_sha256':sha(__file__),
       'assessment_report_sha256':sha(HERE/'assessment/report.json'),
       'scope':'Independent arithmetic implementation by producer agent; not independent scientific validation or another reviewer signoff.'}
    dest.mkdir();(dest/'report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
