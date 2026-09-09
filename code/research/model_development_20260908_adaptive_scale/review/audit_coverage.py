"""Independent memberships, calibration, native predictions and coverage replay.
No producer/assessor/selective imports and no fitting.
Writes only review evidence.
"""
from pathlib import Path
import hashlib,json,pickle,sys,traceback
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
PROJECT=ROOT.parent
verified={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def same(a,b):np.testing.assert_array_equal(a,b)
def close(a,b):np.testing.assert_allclose(a,b,rtol=0,atol=1e-13)
def boolean(s):
    assert s.notna().all() and set(s.astype(str).str.lower())<={'true','false'}
    return s.astype(str).str.lower().eq('true').to_numpy()
def verify(mapping):
    for p,h in mapping.items():assert sha(p)==h,p;verified[p]=h
def native(model,x,b):
    return np.clip(b*(1+np.clip(model.predict(x),-.5,1)),.5*b,2*b)
def cmp(row,values):
    for k,v in values.items():
        if v is None:assert pd.isna(row[k]),(k,row[k])
        elif isinstance(v,(bool,np.bool_)):assert bool(row[k])==bool(v),(k,row[k],v)
        elif isinstance(v,(int,np.integer)):assert int(row[k])==int(v),(k,row[k],v)
        else:np.testing.assert_allclose(float(row[k]),v,rtol=0,atol=1e-10,err_msg=k)

def main():
    import audit_metrics as independent
    original=pd.read_csv(ROOT/'assessment/all_row_predictions.csv',low_memory=False)
    totals=[]
    for family in ['fixed_mean8_scale','adaptive_scale']:
        f=original.copy()
        for key in ['interval_lower','interval_upper']:
            f[key]=f[key+'_upper_free'] if family=='fixed_mean8_scale' else f[key]
        for label in ['project_mean8','project_xlarge']:
            for suffix in ['','__intervened']:
                f[label+suffix]=f[label+'_upper_free'+suffix] if family=='fixed_mean8_scale' else f['adaptive_'+label+suffix]
        f['interval_applicable']=boolean(f.interval_applicable)
        for label in ['project_mean8','project_xlarge']:f[label+'__intervened']=boolean(f[label+'__intervened'])
        cv=pd.read_csv(ROOT/'assessment/coverage_metrics.csv').query('method == @family').set_index('panel')
        bv=pd.read_csv(ROOT/'assessment/bundle_coverage.csv').query('method == @family').set_index(['panel','bundle'])
        bundle_count=0;coverage_records=[]
        for panel,mask in independent.masks(f).items():
            part=f[mask].copy();g=part.interval_applicable.to_numpy();y=part.measured_CD.to_numpy();lo=part.interval_lower.to_numpy();hi=part.interval_upper.to_numpy();covered=(y>=lo)&(y<=hi);tolerant=(y>=lo-1e-12)&(y<=hi+1e-12)
            part['bundle']=np.where(part.split.isin(['SG_exposed','W_new_challenge']),part.split+':'+part.configuration.astype(str),part.group)
            part['covered']=covered;success=[]
            for bundle,h in part.groupby('bundle'):
                sub=h[h.interval_applicable];ok=None if not len(sub) else bool(sub.covered.all())
                if ok is not None:success.append(ok)
                vals=dict(rows=len(h),eligible_rows=len(sub),fully_covered_eligible_bundle=ok,eligible_row_coverage=None if not len(sub) else sub.covered.mean())
                for label,base in [('project_mean8','mean8_CD'),('project_xlarge','xlarge_CD')]:
                    delta=abs(h[label]-h.measured_CD)-abs(h[base]-h.measured_CD)
                    vals.update({label+'__any_harmed_row':bool((delta>1e-12).any()),label+'__worse_group_mae':bool(delta.mean()>1e-12),label+'__intervened_rows':int(h[label+'__intervened'].sum())})
                cmp(bv.loc[panel,bundle],vals);bundle_count+=1
            widths=(hi-lo)[g]
            vals=dict(rows=len(part),eligible_rows=int(g.sum()),outside_gate_rows_unassessed=int((~g).sum()),assessed_bundles=len(success),fully_covered_bundles=sum(success),eligible_row_coverage=covered[g].mean(),eligible_bundle_coverage=np.mean(success),covered_rows_at_1e12_tolerance=int(tolerant[g].sum()),covered_rows_exact_endpoints=int(covered[g].sum()),median_interval_width_CD=np.median(widths),mean_interval_width_CD=np.mean(widths),p90_interval_width_CD=np.quantile(widths,.9),unbounded_eligible_intervals=int(np.isinf(widths).sum()))
            for label,base in [('project_mean8','mean8_CD'),('project_xlarge','xlarge_CD')]:
                act=part[label+'__intervened'].to_numpy();delta=abs(part[label].to_numpy()-y)-abs(part[base].to_numpy()-y)
                assert not (act&~g).any();viol=covered&g&(delta>1e-12);assert not viol.any()
                vals.update({label+'__intervened_rows':int(act.sum()),label+'__intervention_fraction_all':act.mean(),label+'__intervention_fraction_eligible':act[g].mean(),label+'__worse_rows_vs_supplied_baseline':int((delta>1e-12).sum()),label+'__harm_fraction_among_interventions':(delta[act]>1e-12).mean() if act.any() else None,label+'__benefit_fraction_among_interventions':(delta[act]<-1e-12).mean() if act.any() else None,label+'__mean_signed_excess_error_among_interventions_CD':delta[act].mean() if act.any() else None,label+'__covered_target_projection_violations':int(viol.sum())})
            cmp(cv.loc[panel],vals)
            coverage_records.append({'panel':panel,**{k:(v.item() if isinstance(v,np.generic) else v) for k,v in vals.items()}})
    
        totals.append(dict(family=family,coverage_panels=len(coverage_records),bundle_records=bundle_count))
    dist=pd.read_csv(ROOT/'assessment/scale_distributions.csv')
    scores=pd.read_csv(ROOT/'assessment/calibration_scores.csv')
    for _,row in dist.iterrows():
        ext=row.context in ['SG_exposed','W_new_challenge']
        stem={'proper_training':'scale_training','calibration':'calibration','outer_holdout':'inference','all_history_not_holdout':'inference'}
        path=ROOT/'exposed_results'/f'{row.context}_inference.npz' if ext else ROOT/'results'/f'{stem[row.role]}_{row.context}.npz'
        z=np.load(path);mask=z['gate'] if row.role=='eligible_exposed' else np.ones(len(z['BASE_CD']),bool)
        s,b=z['dimensionless_scale'][mask],z['BASE_CD'][mask]
        cal=read(ROOT/'results'/('calibrator_final.json' if ext else f'calibrator_{row.context}.json'))
        vals={'rows':len(s)}
        for prefix,x in [('dimensionless_scale',s),('scale_CD',b*s),('potential_interval_width_CD',2*cal['q']*b*s)]:
            vals.update({prefix+'_min':x.min(),prefix+'_max':x.max(),prefix+'_mean':x.mean()})
            for q in [.01,.05,.5,.95,.99]:vals[prefix+f'_p{int(q*100):02d}']=np.quantile(x,q)
        cmp(row,vals)
    for _,row in scores.iterrows():
        cal=read(ROOT/f'results/calibrator_{row.context}.json');i=cal['group_ids'].index(row.group)
        cmp(row,{'score':cal['group_scores'][i],'calibration_groups':cal['calibration_groups'],'rank':cal['rank'],'q':cal['q']})
    result=dict(status='PASS',methods=totals,distribution_records=len(dist),calibration_score_records=len(scores))
    (HERE/'coverage_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result)
if __name__=='__main__':main()

