"""Independent frozen-frame aggregates and paired bootstrap. No assessor imports."""
from audit_scalars import *
import pandas as pd
COUNT=0
WARNINGS=[]
def eq(actual,expected):
    global COUNT
    COUNT+=1
    if isinstance(expected,(bool,np.bool_)):assert actual==expected
    elif expected is None:assert pd.isna(actual)
    else:np.testing.assert_allclose(actual,expected,atol=2e-10,rtol=2e-12)
def main():
    report=json.loads((S/'assessment/report.json').read_bytes())
    frames={p[:-4]:pd.read_csv(io.BytesIO(checked(S/'assessment'/p,h)),low_memory=False) for p,h in report['output_sha256'].items()}
    f=frames['all_row_predictions'];assert len(f)==29856
    labels=report['candidates']+report['controls'];assert len(labels)==15
    panels={}
    for seed in [20260906,20260908]:
        m=f.split.str.startswith(f'group_{seed}_');assert m.sum()==f.loc[m,'nf2_row_id'].nunique()==8371
        panels[f'history_{seed}_pooled']=m
        for src in sorted(f.loc[m,'source'].unique()):panels[f'history_{seed}_{src}']=m&f.source.eq(src)
    for split in sorted(x for x in f.split.unique() if x.startswith('strict_source_')):panels[split]=f.split.eq(split)
    gate=f.interval_applicable.astype(str).str.lower();assert set(gate)<= {'true','false'}
    for split in ['SG_exposed','W_new_challenge']:
        m=f.split.eq(split);panels[split+'_pooled']=m;panels[f'eligible_only/{split}/pooled']=m&gate.eq('true')
        for config in sorted(f.loc[m,'configuration'].unique()):
            panels[f'{split}_{config}']=m&f.configuration.eq(config)
            panels[f'eligible_only/{split}/{config}']=m&f.configuration.eq(config)&gate.eq('true')
    assert len(panels)==31
    table=frames['panel_metrics'];assert len(table)==465 and set(table.panel)==set(panels)
    for r in table.itertuples():
        part=f[panels[r.panel]];y=part.measured_CD.to_numpy();er=abs(part[r.candidate].to_numpy()-y)
        for key,value in {'rows':len(part),'mae_CD':er.mean(),'mae_drag_counts':er.mean()*1e4,'median_absolute_error_CD':np.median(er),'p90_absolute_error_CD':np.quantile(er,.9)}.items():eq(getattr(r,key),value)
        for base in ['mean8_CD','xlarge_CD']:
            be=abs(part[base].to_numpy()-y)
            for suffix,value in {'_mae':be.mean(),'_improvement_percent':100*(1-er.sum()/be.sum()),'_worse_rows':(er>be+1e-12).sum(),'_worse_fraction':(er>be+1e-12).mean()}.items():eq(getattr(r,base+suffix),value)
    groups=frames['group_metrics'];assert len(groups)==2790
    boot=frames['bootstrap'];assert len(boot)==150
    for seed in [20260906,20260908]:
        part=f[panels[f'history_{seed}_pooled']];ids,inv=np.unique(part.group,return_inverse=True);assert len(ids)==93
        y=part.measured_CD.to_numpy();errs={k:abs(part[k].to_numpy()-y) for k in labels}
        sums={k:np.bincount(inv,weights=v) for k,v in errs.items()}
        counts=np.random.default_rng(2026090831).multinomial(93,np.full(93,1/93),size=20000)
        res={k:counts@v for k,v in sums.items()}
        for r in boot[boot.assignment.eq(seed)].itertuples():
            benefit=100*(1-res[r.candidate]/res[r.reference]);lo,hi=np.quantile(benefit,[.025,.975])
            for key,value in {'remaining_MAE_reduction_percent':100*(1-sums[r.candidate].sum()/sums[r.reference].sum()),'conditional_95pct_lower':lo,'conditional_95pct_upper':hi,'bootstrap_fraction_benefit_positive':(benefit>0).mean(),'draws':20000,'seed':2026090831}.items():
                if key=='bootstrap_fraction_benefit_positive' and abs(getattr(r,key)-value)>2e-10 and np.max(abs(benefit))<1e-10:
                    WARNINGS.append({'assignment':seed,'candidate':r.candidate,'reference':r.reference,'saved_fraction':getattr(r,key),'CSV_replay_fraction':float(value),'maximum_absolute_draw_benefit_pp':float(np.max(abs(benefit))),'interpretation':'Unstable strict-zero diagnostic for numerically equivalent predictions; not a positive improvement claim.'})
                    continue
                try:eq(getattr(r,key),value)
                except AssertionError:
                    print('BOOTSTRAP_DIAGNOSTIC',seed,r.candidate,r.reference,key,float(benefit.min()),float(benefit.max()),flush=True)
                    raise
        for r in groups[groups.assignment.eq(seed)].itertuples():
            mask=part.group.eq(r.group).to_numpy();er=errs[r.candidate][mask].mean();be=errs['xlarge_CD'][mask].mean();red=100*(1-er/be)
            for key,value in {'rows':mask.sum(),'mae_CD':er,'xlarge_mae_CD':be,'MAE_difference_vs_xlarge_CD':er-be,'xlarge_improvement_percent':red,'worse_than_xlarge':red< -1e-6}.items():eq(getattr(r,key),value)
    harm=frames['harm_metrics'];assert len(harm)==3255
    for r in harm.itertuples():
        p=f[panels[r.panel]];y=p.measured_CD.to_numpy();d=abs(p[r.candidate].to_numpy()-y)-abs(p[r.reference].to_numpy()-y);pos=np.maximum(d,0);w=d>1e-12;b=d< -1e-12;e=~(w|b)
        for key,value in {'rows':len(p),'mean_positive_excess_absolute_error_CD':pos.mean(),'mean_positive_excess_absolute_error_drag_counts':pos.mean()*1e4,'mean_signed_excess_absolute_error_CD':d.mean(),'p90_positive_excess_absolute_error_CD':np.quantile(pos,.9),'worse_rows':w.sum(),'better_rows':b.sum(),'equal_rows':e.sum(),'worse_fraction':w.mean(),'better_fraction':b.mean(),'equal_fraction':e.mean()}.items():eq(getattr(r,key),value)
    risk=frames['expected_harm_metrics'];assert len(risk)==465
    bundles=frames['bundle_harm_metrics'].set_index(['candidate','panel','identity'])
    for r in risk.itertuples():
        p=f[panels[r.panel]];y=p.measured_CD.to_numpy();loss=np.maximum(abs(p[r.candidate].to_numpy()-y)-abs(p.qualified_matched_half.to_numpy()-y),0)/p.mean8_CD.to_numpy()
        ids=p.airfoil.astype(str).to_numpy() if p.split.isin(['SG_exposed','W_new_challenge']).all() else p.group.astype(str).to_numpy()
        gm=[]
        for g in np.unique(ids):
            mask=ids==g;value=loss[mask].mean();gm.append(value);v=bundles.loc[(r.candidate,r.panel,g)]
            eq(v['rows'],mask.sum());eq(v['mean_normalized_positive_excess_vs_qualified_half'],value)
        for key,value in {'rows':len(p),'identity_count':len(gm),'equal_identity_mean_normalized_positive_excess_vs_qualified_half':np.mean(gm),'pooled_row_mean_normalized_positive_excess_vs_qualified_half':loss.mean(),'empirical_budget_exceeded':np.mean(gm)>.01}.items():eq(getattr(r,key),value)
    fields=['mean8_CD_improvement_percent','xlarge_CD_improvement_percent'];decisions=[]
    for r in frames['decisions'].itertuples():
        t=table[table.candidate.eq(r.candidate)];strict=t[t.panel.str.startswith('strict_source_')][fields].to_numpy();ex=t[t.panel.str.startswith('eligible_only/')][fields].to_numpy()
        ref=table[table.candidate.eq('unpenalized_transfer')&table.panel.str.startswith('eligible_only/')][fields].to_numpy()
        sp=bool((strict>=-1e-6).all());ep=bool((ex< -1e-6).sum()<=(ref< -1e-6).sum() and ex.min()>=ref.min()-1e-6);allpos=bool((t[fields].to_numpy()>=-1e-6).all())
        eq(r.strict_source_guard_pass,sp);eq(r.performance_external_guard_pass,ep);eq(r.all31_nonnegative_both_baselines,allpos)
        for prefix,reference in [('performance','unpenalized_transfer'),('robustness','half_strength')]:
            bs=boot[boot.candidate.eq(r.candidate)&boot.reference.eq(reference)];gain=bool((bs.remaining_MAE_reduction_percent>=1-1e-6).all());gp=True
            for seed in [20260906,20260908]:
                g=groups[groups.assignment.eq(seed)];cv=g[g.candidate.eq(r.candidate)].xlarge_improvement_percent.to_numpy();rv=g[g.candidate.eq(reference)].xlarge_improvement_percent.to_numpy();gp &= bool((cv< -1e-6).sum()<=(rv< -1e-6).sum() and max(0,-cv.min())<=max(0,-rv.min())+1e-6)
            advance=bool(gain and gp and (sp and ep if prefix=='performance' else allpos))
            eq(getattr(r,prefix+'_historical_gain_both_at_least_1pct'),gain);eq(getattr(r,prefix+'_identity_guard_both_assignments'),gp);eq(getattr(r,prefix+'_advance'),advance)
            decisions.append({'candidate':r.candidate,'rule':prefix,'advance':advance})
    return {'status':'PASS_WITH_ZERO_DIAGNOSTIC_QUALIFICATION','source_sha256':sha(__file__),'assessment_sha256':sha(S/'assessment/report.json'),'numeric_checks':COUNT,'panels':31,'procedures':15,'panel_rows':465,'bootstrap_intervals':150,'bootstrap_draws_each':20000,'identity_rows':2790,'harm_rows':3255,'expected_harm_rows':465,'bundle_rows':len(bundles),'decisions':decisions,'zero_diagnostic_warnings':WARNINGS,'scope':'Independent equations on authenticated frozen CSVs; conditional fixed-prediction bootstrap, no refitting or confirmatory inference.'}
if __name__=='__main__':
    out=HERE/'METRIC_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        dest=HERE/'METRIC_FAILURE.txt'
        n=2
        while dest.exists():dest=HERE/f'METRIC_FAILURE_{n}.txt';n+=1
        with dest.open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
