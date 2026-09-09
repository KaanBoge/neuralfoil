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
    for family in ['capped','upper_free','positive_log']:
        f=original.copy()
        for key in ['interval_lower','interval_upper']:
            f[key]=f[key+'_'+family]
        for label in ['project_mean8','project_xlarge']:
            for suffix in ['','__intervened']:
                f[label+suffix]=f[label+'_'+family+suffix]
        f['interval_applicable']=boolean(f.interval_applicable)
        for label in ['project_mean8','project_xlarge']:f[label+'__intervened']=boolean(f[label+'__intervened'])
        cv=pd.read_csv(ROOT/'assessment/coverage_metrics.csv').query('family == @family').set_index('panel')
        bv=pd.read_csv(ROOT/'assessment/bundle_coverage.csv').query('family == @family').set_index(['panel','bundle'])
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
    tail=pd.read_csv(ROOT/'assessment/tail_metrics.csv')
    masks=independent.masks(original)
    for _,row in tail.iterrows():
        f=original[masks[row.panel]]
        b=f.mean8_CD.to_numpy();y=f.measured_CD.to_numpy()
        sel={'above_old_upper':y>2*b,'below_old_lower':y<.5*b,'within_old_bounds':(y>=.5*b)&(y<=2*b)}
        if row.stratum not in sel:print('STRATA',tail.stratum.unique());raise AssertionError(row.stratum)
        f=f[sel[row.stratum]];y=f.measured_CD.to_numpy();b=f.mean8_CD.to_numpy();p=f[row.candidate].to_numpy()
        v=dict(rows=len(f),mae_CD=float(abs(p-y).mean()) if len(f) else None,predictions_above_old_upper=int((p>2*b).sum()),predictions_below_old_lower=int((p<.5*b).sum()))
        for base in ['mean8_CD','xlarge_CD']:
            be=abs(f[base].to_numpy()-y)
            v[base+'_mae']=be.mean() if len(f) else None
            v[base+'_improvement_percent']=100*(1-abs(p-y).mean()/be.mean()) if len(f) and be.mean()>0 else None
        cmp(row,v)
    result=dict(status='PASS',families=totals,tail_records=len(tail))
    (HERE/'coverage_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result)
if __name__=='__main__':main()
