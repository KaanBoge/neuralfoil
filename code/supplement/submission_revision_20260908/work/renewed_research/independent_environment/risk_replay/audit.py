"""Independent fixed arithmetic/assessment replay. No producer imports or fitting."""
from pathlib import Path
import hashlib,io,json
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
REV=HERE.parents[3]
PROJECT=REV.parent
P=REV/'work/renewed_research/model_proposal'
A=PROJECT/'model_development_20260907_cap_ablation'
LABEL='calibrated_incremental_harm_001'
LABELS=[LABEL,'proper_capped_half','proper_capped_full','project_mean8_capped','project_xlarge_capped','mean8_CD','xlarge_CD','capped_half','capped_full','unpenalized_transfer','half_strength']
REFS=['unpenalized_transfer','half_strength','proper_capped_half']
BASES=['xlarge_CD','mean8_CD']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def npz(p):
    with np.load(p,allow_pickle=False) as z:
        assert all(z[k].dtype.kind!='O' for k in z.files)
        return {k:z[k] for k in z.files}
def csv(p):return pd.read_csv(p,low_memory=False)
def dump(n,v):
    with (HERE/n).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def roundtrip(df):return pd.read_csv(io.StringIO(df.to_csv(index=False)))
def compare(name,df,keys,records):
    old=csv(P/'assessment'/f'{name}.csv').sort_values(keys).reset_index(drop=True)
    new=roundtrip(df).sort_values(keys).reset_index(drop=True)
    # CSV arithmetic is preserved explicitly, not compared to unparsed floats.
    assert set(new.columns)<=set(old.columns)
    assert len(new)==len(old),(name,len(new),len(old))
    deltas={}
    for key in new:
        x,y=new[key],old[key]
        if pd.api.types.is_numeric_dtype(x) and x.dtype!=bool:
            a,b=x.to_numpy(),y.to_numpy();assert np.array_equal(np.isnan(a),np.isnan(b))
            err=float(np.nanmax(np.abs(a-b),initial=0));deltas[key]=err
            # Source formulas/order are identical; no floating tolerance introduced.
            np.testing.assert_array_equal(a,b,err_msg=f'{name}:{key}')
        else:pd.testing.assert_series_equal(x,y,check_names=False)
    records.append({'table':name,'rows':len(new),'columns_checked':len(new.columns),'max_abs_differences':deltas,'exact_after_CSV_roundtrip':True})
def main():
    assert sha(P/'PROPOSAL.md')=='3f7c4b1f73b283e434c4d670fdd16c67c8d3eaff221dd634a47ba66dd39414f7'
    assert sha(A/'results/freeze.json')=='7d07b1beacb39de88f4c1c8b96b48ac6988c619f9e344843df3b565531c835f3'
    assert sha(P/'results/freeze.json')=='719b239b7799b156e57b35c19708fec154ea1687a4bd9e934542ef31a42e4861'
    fr=read(P/'results/freeze.json');co=read(P/'results/complete.json');ar=read(P/'assessment/report.json')
    witnesses={}
    for record in [fr,co,ar]:
        for field in ['source_input_sha256','artifact_sha256','external_input_sha256','output_sha256']:
            for path,h in record.get(field,{}).items():assert sha(path)==h,path;witnesses[path]=h
    assert len(fr['contexts'])==16 and fr['calibrator_count']==16 and fr['new_core_fits']==0
    assert len(fr['artifact_sha256'])==32 and fr['external_outcomes_opened'] is False
    assert fr['frozen_utc']<co['completed_utc']<ar['completed_utc']
    assert co['freeze_sha256']==sha(P/'results/freeze.json')
    calchecks=[];native=[];models={}
    for context in fr['contexts']:
        m=read(P/'results'/f'membership_{context}.json');assert m==read(A/'results'/f'membership_{context}.json')
        pg,cg,tg=map(set,[m['proper_groups'],m['calibration_groups'],m['test_groups']])
        assert not(pg&cg or pg&tg or cg&tg) and m['post_calibration_refit'] is False
        z=npz(A/'results'/f'calibration_{context}.npz')
        np.testing.assert_array_equal(z['indices'],m['calibration_indices'])
        np.testing.assert_array_equal(z['nf2_row_id'],m['calibration_nf2_row_ids'])
        assert set(z['group'].astype(str))==cg
        b,c,y=z['BASE_CD'],z['CORE_CD_capped'],z['MEAS_CD'];h=b+.5*(c-b)
        assert np.isfinite([b,c,y]).all() and (b>0).all() and (c>=.5*b).all() and (c<=2*b).all()
        losses=np.maximum(np.abs(c-y)-np.abs(h-y),0)/b
        ids=np.unique(z['group'].astype(str));values=np.array([np.mean(losses[z['group'].astype(str)==g]) for g in ids])
        u=min(.5,float(values.mean())+.5*np.sqrt(np.log(20)/(2*len(ids))))
        t=min(1.,.01/u);saved=read(P/'results'/f'calibrator_{context}.json')
        assert saved['t']==t and saved['upper_bound']==u and saved['endpoint_mean']==float(values.mean())
        np.testing.assert_array_equal(saved['group_endpoint_losses'],values)
        assert saved['group_names']==ids.tolist() and saved['groups']==len(cg)>=9
        models[context]=saved
        calchecks.append({'context':context,'proper_groups':len(pg),'calibration_groups':len(cg),'test_groups':len(tg),'rows':len(b),'t':t,'upper':float(u),'endpoint_mean':float(values.mean()),'native_exact':True})
    for context in fr['contexts']+['SG_exposed','W_new_challenge']:
        ext=context in ['SG_exposed','W_new_challenge'];model=models['final' if ext else context]
        original=npz(A/('exposed_results' if ext else 'results')/(f'{context}_inference.npz' if ext else f'inference_{context}.npz'))
        saved=npz(P/('exposed_results' if ext else 'results')/f'inference_{context}.npz')
        b,c,g=original['BASE_CD'],original['proper_core_capped'],original['gate'];assert g.dtype==bool
        if not ext:assert g.all()
        c=np.where(g,c,b);h=b+.5*(c-b);pred=np.where(g,h+model['t']*(c-h),b)
        for key,value in [('indices',original['indices']),('BASE_CD',b),('prediction',pred),('anchor',h),('endpoint',c),('gate',g),('applied_strength',np.where(g,.5+.5*model['t'],0.)),('intervened_vs_anchor',abs(pred-h)>1e-12),('intervened_vs_mean8',abs(pred-b)>1e-12)]:np.testing.assert_array_equal(saved[key],value)
        np.testing.assert_array_equal(pred[~g],b[~g]);native.append({'context':context,'rows':len(b),'eligible':int(g.sum()),'fallback_rows':int((~g).sum()),'all_native_arrays_exact':True})
    # Rebuild the assessor's input frame from authenticated source CSVs, avoiding
    # the additional rounding pass in its final all-row CSV.
    frame=csv(PROJECT/'model_development_20260907_geometry_frontier/assessment/all_row_predictions.csv')
    for split in frame.split.unique():
        ext=split in ['SG_exposed','W_new_challenge'];mask=frame.split.eq(split);old=frame.loc[mask]
        name=f'{split}_predictions.csv' if ext else f'predictions_{split}.csv'
        base=csv(A/('exposed_results' if ext else 'results')/name);fresh=csv(P/('exposed_results' if ext else 'results')/name)
        if not ext:
            assert not base.nf2_row_id.duplicated().any() and not fresh.nf2_row_id.duplicated().any()
            base=base.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index();fresh=fresh.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(base.configuration,old.configuration);np.testing.assert_array_equal(fresh.configuration,old.configuration)
        for label in LABELS:
            if label in ['mean8_CD','xlarge_CD','unpenalized_transfer','half_strength']:continue
            frame.loc[mask,label]=(fresh if label==LABEL else base)[label].to_numpy()
        frame.loc[mask,'interval_applicable']=base.interval_applicable.astype(bool).to_numpy()
        for key in [LABEL+'__strength',LABEL+'__intervened','calibration_t']:frame.loc[mask,key]=fresh[key].to_numpy()
    panels={}
    for seed in [20260906,20260908]:
        mask=frame.split.str.startswith(f'group_{seed}_');assert mask.sum()==8371 and frame.loc[mask].nf2_row_id.nunique()==8371
        panels[f'history_{seed}_pooled']=np.flatnonzero(mask)
        for s in sorted(frame.loc[mask,'source'].unique()):panels[f'history_{seed}_{s}']=np.flatnonzero(mask&frame.source.eq(s))
    for s in sorted(x for x in frame.split.unique() if x.startswith('strict_source_')):panels[s]=np.flatnonzero(frame.split.eq(s))
    for s in ['SG_exposed','W_new_challenge']:
        mask=frame.split.eq(s);gate=frame.interval_applicable.to_numpy(bool)
        panels[s+'_pooled']=np.flatnonzero(mask)
        for c in sorted(frame.loc[mask,'configuration'].unique()):panels[s+'_'+c]=np.flatnonzero(mask&frame.configuration.eq(c))
        panels[f'eligible_only/{s}/pooled']=np.flatnonzero(mask&gate)
        for c in sorted(frame.loc[mask,'configuration'].unique()):panels[f'eligible_only/{s}/{c}']=np.flatnonzero(mask&gate&frame.configuration.eq(c))
    assert len(frame)==29856 and len(panels)==31
    rows=[];targets=frame.measured_CD.to_numpy()
    for label in LABELS:
        err=abs(frame[label].to_numpy()-targets)
        for panel,ix in panels.items():
            e=err[ix];d={'candidate':label,'panel':panel,'rows':len(ix),'mae_CD':e.mean(),'mae_drag_counts':e.mean()*1e4,'median_absolute_error_CD':np.median(e),'p90_absolute_error_CD':np.quantile(e,.9),'row_equality_tolerance_CD':1e-12}
            for b in BASES:
                be=abs(frame[b].to_numpy()[ix]-targets[ix]);d.update({b+'_mae':be.mean(),b+'_improvement_percent':100*(1-e.sum()/be.sum()),b+'_worse_rows':int((e>be+1e-12).sum()),b+'_worse_fraction':float((e>be+1e-12).mean())})
            rows.append(d)
    tables=[];table=pd.DataFrame(rows);compare('panel_metrics',table,['candidate','panel'],tables)
    groups=[];boots=[]
    for seed in [20260906,20260908]:
        f=frame[frame.split.str.startswith(f'group_{seed}_')];ids,inv=np.unique(f.group,return_inverse=True);assert len(ids)==93
        y=f.measured_CD.to_numpy();sums={l:np.bincount(inv,weights=abs(f[l].to_numpy()-y)) for l in LABELS}
        draws=np.random.default_rng(2026090831).multinomial(93,np.full(93,1/93),size=20000)
        sampled={l:draws@sums[l] for l in LABELS}
        for ref in REFS:
            for l in LABELS:
                benefit=100*(1-sampled[l]/sampled[ref]);lo,hi=np.quantile(benefit,[.025,.975])
                boots.append({'candidate':l,'assignment':seed,'reference':ref,'rows':len(f),'groups':93,'remaining_MAE_reduction_percent':100*(1-sums[l].sum()/sums[ref].sum()),'conditional_95pct_lower':lo,'conditional_95pct_upper':hi,'bootstrap_fraction_benefit_positive':float((benefit>0).mean()),'draws':20000,'seed':2026090831})
        for g,part in f.groupby('group',sort=True):
            y=part.measured_CD.to_numpy();base=abs(part.xlarge_CD.to_numpy()-y).mean()
            for l in LABELS:
                e=abs(part[l].to_numpy()-y).mean();gain=100*(1-e/base)
                groups.append({'candidate':l,'assignment':seed,'group':g,'rows':len(part),'mae_CD':e,'xlarge_mae_CD':base,'MAE_difference_vs_xlarge_CD':e-base,'xlarge_improvement_percent':gain,'worse_than_xlarge':bool(gain< -1e-6)})
    groups=pd.DataFrame(groups);boots=pd.DataFrame(boots)
    compare('group_metrics',groups,['candidate','assignment','group'],tables);compare('bootstrap',boots,['candidate','assignment','reference'],tables)
    fields=[b+'_improvement_percent' for b in BASES];t=table[table.candidate.eq(LABEL)]
    ext=t[t.panel.str.startswith('eligible_only/')][fields].to_numpy();strict=t[t.panel.str.startswith('strict_source_')][fields].to_numpy()
    ref=table[table.candidate.eq('unpenalized_transfer')&table.panel.str.startswith('eligible_only/')][fields].to_numpy()
    strictok=bool((strict>=-1e-6).all());extok=int((ext< -1e-6).sum())<=int((ref< -1e-6).sum()) and ext.min()>=ref.min()-1e-6
    allok=bool((t[fields].to_numpy()>=-1e-6).all());dec={'candidate':LABEL,'strict_source_guard_pass':strictok,'performance_external_guard_pass':bool(extok),'all31_nonnegative_both_baselines':allok,'minimum_all31_improvement_both_percent':float(t[fields].to_numpy().min())}
    for ref,prefix in [('unpenalized_transfer','performance'),('half_strength','robustness')]:
        b=boots[boots.candidate.eq(LABEL)&boots.reference.eq(ref)];gain=bool((b.remaining_MAE_reduction_percent>=1-1e-6).all());guard=True
        for seed in [20260906,20260908]:
            c=groups[groups.candidate.eq(LABEL)&groups.assignment.eq(seed)];r=groups[groups.candidate.eq(ref)&groups.assignment.eq(seed)]
            guard &= int((c.xlarge_improvement_percent< -1e-6).sum())<=int((r.xlarge_improvement_percent< -1e-6).sum()) and max(0.,-c.xlarge_improvement_percent.min())<=max(0.,-r.xlarge_improvement_percent.min())+1e-6
        dec[prefix+'_historical_gain_both_at_least_1pct']=gain;dec[prefix+'_identity_guard_both_assignments']=bool(guard)
        dec[prefix+'_advance']=bool(gain and guard and (strictok and extok if prefix=='performance' else allok))
    compare('decisions',pd.DataFrame([dec]),['candidate'],tables)
    # Every row and adverse identity remains; descriptive risk is not certified.
    risk=[];harm=[]
    for panel,ix in panels.items():
        f=frame.iloc[ix];y=f.measured_CD.to_numpy();b=f.mean8_CD.to_numpy();anchor=f.proper_capped_half.to_numpy()
        ids=f.airfoil.astype(str).to_numpy() if f.split.isin(['SG_exposed','W_new_challenge']).all() else f.group.astype(str).to_numpy()
        for label in LABELS:
            loss=np.maximum(abs(f[label].to_numpy()-y)-abs(anchor-y),0)/b
            means=[loss[ids==g].mean() for g in np.unique(ids)]
            risk.append({'candidate':label,'panel':panel,'rows':len(f),'identity_count':len(means),'equal_identity_mean_normalized_positive_excess_vs_matched_half':np.mean(means),'pooled_row_mean_normalized_positive_excess_vs_matched_half':loss.mean(),'empirical_equal_identity_budget_exceeded':bool(np.mean(means)>.01)})
            for ref in REFS+BASES:
                delta=abs(f[label].to_numpy()-y)-abs(f[ref].to_numpy()-y);positive=np.maximum(delta,0);w=delta>1e-12;better=delta< -1e-12;equal=~(w|better)
                harm.append({'candidate':label,'reference':ref,'panel':panel,'rows':len(f),'mean_positive_excess_absolute_error_CD':positive.mean(),'mean_positive_excess_absolute_error_drag_counts':positive.mean()*1e4,'mean_signed_excess_absolute_error_CD':delta.mean(),'p90_positive_excess_absolute_error_CD':np.quantile(positive,.9),'worse_rows':int(w.sum()),'better_rows':int(better.sum()),'equal_rows':int(equal.sum()),'worse_fraction':float(w.mean()),'better_fraction':float(better.mean()),'equal_fraction':float(equal.mean()),'row_equality_tolerance_CD':1e-12})
    compare('expected_harm_metrics',pd.DataFrame(risk),['candidate','panel'],tables)
    compare('harm_metrics',pd.DataFrame(harm),['candidate','reference','panel'],tables)
    for p,h in witnesses.items():assert sha(p)==h
    dump('AUDIT.json',{'status':'PASS','scalar_calibrators':calchecks,'native_inference':native,'tables':tables,'decisions':dec,'source_sha256':witnesses,'proposal_sha256':sha(P/'PROPOSAL.md'),'audit_source_sha256':sha(__file__),'no_new_model_fits':True,'no_new_algorithm_or_tolerance':True,'scope':'Independent arithmetic and retained-outcome replay, not certification of IID future risk.'})
    print(json.dumps({'status':'PASS','calibrators':len(calchecks),'inference_cases':len(native),'tables':[(x['table'],x['rows']) for x in tables],'decisions':dec},indent=2))
if __name__=='__main__':main()
