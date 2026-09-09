"""Independent saved-frame/source alignment and intervention diagnostics."""
from audit_metrics import *
def main():
    report=json.loads((S/'assessment/report.json').read_bytes());complete=json.loads((S/'predictions/complete.json').read_bytes())
    f=pd.read_csv(io.BytesIO(checked(S/'assessment/all_row_predictions.csv',report['output_sha256']['all_row_predictions.csv'])),low_memory=False)
    count=0
    for split,p in f.groupby('split',sort=False):
        name=f'predictions_{split}.csv';source=pd.read_csv(io.BytesIO(checked(S/'predictions'/name,complete['output_sha256'][name])),low_memory=False)
        if split not in ['SG_exposed','W_new_challenge']:
            assert not source.nf2_row_id.duplicated().any();source=source.set_index('nf2_row_id').loc[p.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(source.configuration,p.configuration)
        for k in ['Re','alpha','measured_CD','mean8_CD','xlarge_CD','qualified_matched_half','qualified_matched_full']+report['candidates']:
            np.testing.assert_allclose(source[k],p[k],rtol=0,atol=1e-13);count+=len(p)
    tables={k:pd.read_csv(io.BytesIO(checked(S/'assessment'/k,report['output_sha256'][k])),low_memory=False) for k in ['intervention_metrics.csv','calibration_summary.csv']}
    def panel(name):
        if name.startswith('history_'):
            _,seed,suffix=name.split('_',2);mask=f.split.str.startswith('group_'+seed+'_');return f[mask if suffix=='pooled' else mask&f.source.eq(suffix)]
        if name.startswith('strict_source_'):return f[f.split.eq(name)]
        eligible=name.startswith('eligible_only/')
        if eligible:_,split,config=name.split('/')
        else:
            split=next(s for s in ['SG_exposed','W_new_challenge'] if name.startswith(s+'_'));config=name[len(split)+1:]
        mask=f.split.eq(split)
        if config!='pooled':mask &= f.configuration.eq(config)
        if eligible:mask &= f.interval_applicable.astype(str).str.lower().eq('true')
        return f[mask]
    for r in tables['intervention_metrics.csv'].itertuples():
        p=panel(r.panel);y=p.measured_CD.to_numpy();pred=p[r.candidate].to_numpy();anchor=p.qualified_matched_half.to_numpy();sel=abs(pred-anchor)>1e-12;e=p[r.candidate+'__effective_fraction'].to_numpy()
        for key,v in {'rows':len(p),'interventions':sel.sum(),'physical_eligible_rows':p.interval_applicable.astype(str).str.lower().eq('true').sum(),'qualified_eligible_rows':p.qualified_gate.astype(str).str.lower().eq('true').sum(),'intervention_fraction':sel.mean(),'effective_fraction_min':e.min(),'effective_fraction_mean':e.mean(),'effective_fraction_max':e.max()}.items():eq(getattr(r,key),v)
        for ref in ['qualified_matched_half','proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
            d=abs(pred-y)-abs(p[ref].to_numpy()-y)
            for suffix,v in {'__selected_harm_fraction':(d[sel]>1e-12).mean() if sel.any() else None,'__selected_benefit_fraction':(d[sel]<-1e-12).mean() if sel.any() else None,'__selected_positive_excess_CD':np.maximum(d[sel],0).mean() if sel.any() else None}.items():eq(getattr(r,ref+suffix),v)
    freeze=json.loads(checked(S/'results/freeze.json',PIN))
    for r in tables['calibration_summary.csv'].itertuples():
        name=f'calibrator_{r.candidate}_{r.context}.json';v=json.loads(checked(S/'results'/name,freeze['artifact_sha256'][name]))
        for key,value in {'groups':v['groups'],'rows':v['rows'],'B':float(frac(v['bound'])),'upper':float(frac(v['upper'])),'endpoint_mean':float(frac(v['exact_mean'])),'t':v['t']}.items():eq(getattr(r,key),value)
    return {'status':'PASS','source_sha256':sha(__file__),'source_csv_contexts':17,'frame_values_checked':count,'intervention_rows':62,'scalar_summary_rows':32,'scope':'Source CSV to assembled-frame alignment uses inherited 1e-13 tolerance; exact native replay is separate.'}
if __name__=='__main__':
    out=HERE/'ALIGNMENT_EXTRAS_QA.json';assert not out.exists()
    try:r=main()
    except BaseException:
        with (HERE/'ALIGNMENT_EXTRAS_FAILURE.txt').open('x') as f:f.write(traceback.format_exc())
        raise
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
