#!/usr/bin/env python3
"""Descriptive failure diagnostics; no fitting, tuning, or untouched-data access.

Run /opt/anaconda3/bin/python diagnose_cycle1.py. Inputs are confined to the
completed cycle-1 experiment plus its already-exposed SG6050/SG6051 coordinates.
All generated outputs remain beside this script. Outcome-based strata are
diagnostic descriptions, never proposed deployment filters.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ['MPLCONFIGDIR']=str(HERE/'mplcache')
import hashlib
import json
import numpy as np
import pandas as pd
PROJECT=HERE.parents[1]
OLD=PROJECT/'model_development_20260906'
sys.path.insert(0,str(OLD))
import score_external as previous

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def weighted_quantile(x,w,q):
    order=np.argsort(x); x=np.asarray(x)[order]; w=np.asarray(w)[order]
    return float(x[np.searchsorted(np.cumsum(w),q*w.sum())])

def summary(f):
    b=f.base_error.to_numpy(); e=f.error.to_numpy(); gain=b-e
    z=f.true_log.to_numpy(); p=f.pred_log.to_numpy()
    def value(a):
        return {'mean':float(np.mean(a)),'median':float(np.median(a)),
                'q25':float(np.quantile(a,.25)),'q75':float(np.quantile(a,.75)),
                'p90':float(np.quantile(a,.9)),'max':float(np.max(a))}
    result={'rows':len(f),'groups':int(f.group.nunique()),'base_mae':float(b.mean()),
            'candidate_mae':float(e.mean()),'mean8_relative_reduction_percent':float(100*gain.sum()/b.sum()),
            'xlarge_mae':float(f.xlarge_error.mean()),
            'xlarge_relative_reduction_percent':float(100*(1-e.sum()/f.xlarge_error.sum())),
            'sum_error_change_counts':float(-gain.sum()),'worse_rows':int((gain<0).sum()),
            'base_error_median':float(np.median(b)),'candidate_error_median':float(np.median(e)),
            'base_p90':float(np.quantile(b,.9)),'candidate_p90':float(np.quantile(e,.9)),
            'median_true_log':float(np.median(z)),'median_pred_log':float(np.median(p)),
            'mean_true_increment_counts':float(f.true_delta.mean()),'mean_pred_increment_counts':float(f.pred_delta.mean()),
            'positive_truth_rows':int((f.true_delta>0).sum()),'positive_prediction_rows':int((f.pred_delta>0).sum()),
            'wrong_direction_rows':int((f.direction=='wrong_direction').sum()),
            'right_direction_harmful_overshoot_rows':int((f.direction=='right_direction_harmful_overshoot').sum()),
            'signed_truth_prediction_correlation':float(np.corrcoef(z,p)[0,1]) if np.std(p)>0 and np.std(z)>0 else None}
    return result

def decorate(f):
    f=f.copy()
    f['true_delta']=(f.measured_CD-f.mean8_CD)*1e4
    f['pred_delta']=(f.candidate_CD-f.mean8_CD)*1e4
    f['base_error']=f.true_delta.abs()
    f['error']=(f.candidate_CD-f.measured_CD).abs()*1e4
    f['xlarge_error']=(f.xlarge_CD-f.measured_CD).abs()*1e4
    f['true_log']=np.log(f.measured_CD/f.mean8_CD)
    f['pred_log']=np.log(f.candidate_CD/f.mean8_CD)
    product=f.true_delta*f.pred_delta
    f['direction']=np.select([product<0,(product>0)&(f.error>f.base_error),product>0],
        ['wrong_direction','right_direction_harmful_overshoot','right_direction_nonharmful'],default='zero_truth_or_correction')
    f['truth_sign']=np.where(f.true_delta>0,'underpredicted_by_mean8',np.where(f.true_delta<0,'overpredicted_by_mean8','exact_mean8'))
    f['prediction_sign']=np.where(f.pred_delta>0,'increase_drag',np.where(f.pred_delta<0,'decrease_drag','unchanged'))
    f['ensemble_disagreement_counts']=(f.xlarge_CD-f.mean8_CD)*1e4
    f['ensemble_disagreement_sign']=np.where(f.ensemble_disagreement_counts>0,'xlarge_above_mean8',np.where(f.ensemble_disagreement_counts<0,'xlarge_below_mean8','equal'))
    return f

def attach_features(frame,dataset):
    lookup={int(n):i for i,n in enumerate(dataset['nf2_row_id'])}
    idx=np.array([lookup[int(n)] for n in frame.nf2_row_id])
    assert np.array_equal(dataset['nf2_row_id'][idx],frame.nf2_row_id)
    assert np.allclose(dataset['BASE_CD'][idx],frame.mean8_CD,atol=1e-15,rtol=0)
    out=frame.copy()
    for j,name in enumerate(['alpha_feature','log10_Re','t','tx','camber','cx','leR','teA','log_cd8','CL8','log_spread','confidence','topxtr','botxtr','size_log_ratio','cm8']):
        out[name]=dataset['X16'][idx,j]
    out['spread_counts']=np.exp(out.log_spread)*1e4
    out['spread_relative']=np.exp(out.log_spread)/out.mean8_CD
    out['measured_CL']=dataset['MEAS_CL'][idx]
    out['geometry_hash']=dataset['geometry_hash'][idx]
    out['geometry_path']=dataset['geometry_path'][idx]
    return out

def main():
    sourcefiles=[OLD/'external_results/all_predictions.csv',OLD/'external_results/results.json',
      OLD/'verified_results/primary_oof_predictions.csv',OLD/'verified_results/predictions_strict_source_stec8.csv',
      OLD/'verified_results/predictions_strict_source_all_uiuc_volumes.csv',
      OLD/'verified_results/frozen_candidate.json',OLD/'score_external.py',OLD/'develop_drag.py',
      OLD/'reproduction/reproduce_doubleclean.py',OLD/'reproduction/dataset_occurrence.npz']
    sourcefiles += [OLD/'external_screening/nominal_coordinates'/f'{s}.dat' for s in ['sg6050','sg6051']]
    hashes={str(p.relative_to(PROJECT)):sha(p) for p in sourcefiles}
    with np.load(OLD/'reproduction/dataset_occurrence.npz',allow_pickle=False) as z:
        dataset={k:z[k] for k in z.files}
    cohorts={}
    for name,file in [('primary_fixed_family_oof','primary_oof_predictions.csv'),
                      ('strict_stec8_fixed_family','predictions_strict_source_stec8.csv'),
                      ('strict_volumes_fixed_family','predictions_strict_source_all_uiuc_volumes.csv')]:
        f=pd.read_csv(OLD/'verified_results'/file,float_precision='round_trip')
        f=attach_features(f,dataset)
        f['candidate_CD']=f.gb_l1_log_1
        cohorts[name]=decorate(f)
    ext=pd.read_csv(OLD/'external_results/all_predictions.csv',float_precision='round_trip')
    ext['external_row_id']=np.arange(len(ext))
    assert len(ext)==242 and set(ext.airfoil)=={'sg6050','sg6051'}
    artifact=json.loads((OLD/'verified_results/frozen_candidate.json').read_text())
    extparts=[]; parity=[]; geoms={}; feature_npz={}
    for name in ['sg6050','sg6051']:
        f=ext[ext.airfoil==name].copy()
        coords=previous.load_pts((OLD/'external_screening/nominal_coordinates'/f'{name}.dat').read_text())
        values=previous.predict_base(coords,f.alpha.to_numpy(),f.Re.to_numpy())
        pred=previous.read_candidate(artifact,values['X9'],values['X16'],values['BASE_CD'])
        mask=f.eligible.to_numpy(dtype=bool)
        pred=np.where(mask,pred,values['BASE_CD'])
        delta=float(np.max(np.abs(pred-f.candidate_CD)))
        assert delta<1e-12
        assert np.allclose(values['BASE_CD'],f.mean8_CD,atol=1e-14,rtol=0)
        parity.append({'airfoil':name,'rows':len(f),'max_candidate_CD_difference':delta})
        for j,col in enumerate(['alpha_feature','log10_Re','t','tx','camber','cx','leR','teA','log_cd8','CL8','log_spread','confidence','topxtr','botxtr','size_log_ratio','cm8']):
            f[col]=values['X16'][:,j]
        f['spread_counts']=np.exp(f.log_spread)*1e4
        f['spread_relative']=np.exp(f.log_spread)/f.mean8_CD
        f['group']=f.airfoil; f['source']='exposed_SG_challenge'; f['entry']=f.airfoil
        extparts.append(f); geoms[name]=values['stat']
        for key in ['X9','X16','all_CD','all_CL']:
            feature_npz[f'{name}_{key}']=values[key]
        feature_npz[f'{name}_external_row_id']=f.external_row_id.to_numpy()
    np.savez_compressed(HERE/'sg_exposed_features.npz',**feature_npz)
    extfull=decorate(pd.concat(extparts,ignore_index=True))
    cohorts['exposed_SG_eligible']=extfull[extfull.eligible].copy()
    extfull.to_csv(HERE/'sg_exposed_rows.csv',index=False)
    assert len(cohorts['exposed_SG_eligible'])==234
    results={'status':'descriptive_posthoc_development_diagnostics_no_fitting',
             'input_sha256':hashes,'external_feature_parity':parity,'geometry':geoms,
             'cohorts':{name:summary(f) for name,f in cohorts.items()}}
    strata=[]
    bins={'Re':[0,75000,150000,250000,600001], 'alpha':[-np.inf,-4,0,4,8,12.00001,np.inf],
          'CL8':[-np.inf,0,.5,1,1.5,np.inf], 'measured_CL':[-np.inf,0,.5,1,1.5,np.inf],
          'topxtr':[0,.1,.3,.6,.9,1.00001],'botxtr':[0,.1,.3,.6,.9,1.00001],
          'confidence':[0,.8,.9,.99,1.00001], 'spread_counts':[0,5,10,20,50,np.inf],
          'spread_relative':[0,.02,.05,.1,.2,np.inf], 't':[0,.09,.12,.15,.20],
          'base_error':[0,5,20,50,100,np.inf], 'pred_log':[-np.inf,-.2,-.05,0,.05,.2,np.inf]}
    categories=['source','entry','truth_sign','prediction_sign','direction','ensemble_disagreement_sign']
    for name,f in cohorts.items():
        for variable,b in bins.items():
            labels=pd.cut(f[variable],b,right=False)
            for label,part in f.groupby(labels,observed=True):
                strata.append({'cohort':name,'variable':variable,'level':str(label),**summary(part)})
        for variable in categories:
            for label,part in f.groupby(variable,observed=True):
                strata.append({'cohort':name,'variable':variable,'level':str(label),**summary(part)})
        for label,part in f.groupby(['truth_sign','prediction_sign']):
            strata.append({'cohort':name,'variable':'truth_x_prediction_sign','level':' / '.join(label),**summary(part)})
        tail=f.sort_values('error',ascending=False).head(int(np.ceil(.1*len(f))))
        strata.append({'cohort':name,'variable':'outcome_selected_tail','level':'largest_10pct_candidate_errors',**summary(tail)})
    sg=cohorts['exposed_SG_eligible'].copy()
    sg['nominal_Re']=np.round(sg.Re/50000)*50000
    for labels,part in sg.groupby(['airfoil','nominal_Re']):
        strata.append({'cohort':'exposed_SG_eligible','variable':'airfoil_x_nominal_Re','level':f'{labels[0]} / {int(labels[1])}',**summary(part)})
    pd.DataFrame(strata).to_csv(HERE/'stratified_diagnostics.csv',index=False)
    for name,f in cohorts.items():
        columns=['entry','source','Re','alpha','CL8','topxtr','botxtr','base_error','error','true_delta','pred_delta','true_log','pred_log','direction']
        f.assign(error_change=f.error-f.base_error).sort_values('error_change',ascending=False).head(25)[columns+['error_change']].to_csv(HERE/f'{name}_largest_harms.csv',index=False)
    primary=cohorts['primary_fixed_family_oof'].copy()
    counts=primary.groupby(['source','group']).source.transform('size')
    ng=primary.groupby('source').group.transform('nunique')
    w=1/(counts*ng); primary['training_weight']=w/w.mean()
    sources=[]
    for source,f in primary.groupby('source'):
        weights=f.training_weight.to_numpy()
        sources.append({'source':source,'rows':len(f),'groups':f.group.nunique(),
          'row_share':len(f)/len(primary),'training_weight_share':weights.sum()/primary.training_weight.sum(),
          'true_log_median':float(np.median(f.true_log)),'true_log_weighted_median':weighted_quantile(f.true_log,weights,.5),
          'true_log_weighted_mean':float(np.average(f.true_log,weights=weights)),
          'positive_true_log_row_share':float(np.mean(f.true_log>0)),
          'positive_true_log_weight_share':float(np.average(f.true_log>0,weights=weights)),
          'mean_xlarge_minus_mean8_counts':float(f.ensemble_disagreement_counts.mean()),
          'mean_true_delta_counts':float(f.true_delta.mean()),'mean_pred_delta_counts':float(f.pred_delta.mean())})
    results['source_weights_and_residuals']=sources
    results['pooled_residual_weighting']={'row_median_true_log':float(np.median(primary.true_log)),
      'weighted_median_true_log':weighted_quantile(primary.true_log,primary.training_weight,.5),
      'row_positive_residual_share':float(np.mean(primary.true_log>0)),
      'weighted_positive_residual_share':float(np.average(primary.true_log>0,weights=primary.training_weight))}
    geometry=primary.drop_duplicates('geometry_hash').copy()
    fields=['t','tx','camber','cx','leR','teA']
    scale=geometry[fields].quantile(.75)-geometry[fields].quantile(.25)
    near=[]
    for name,part in sg.groupby('airfoil'):
        target=part.iloc[0][fields].to_numpy(dtype=float)
        distance=np.sqrt((((geometry[fields]-target)/scale)**2).sum(axis=1))
        best=geometry.assign(descriptor_IQR_scaled_distance=distance).nsmallest(8,'descriptor_IQR_scaled_distance')
        for _,row in best.iterrows():
            near.append({'SG_airfoil':name,**row[['entry','source','geometry_path','descriptor_IQR_scaled_distance']+fields].to_dict()})
    pd.DataFrame(near).to_csv(HERE/'geometry_nearest_descriptors.csv',index=False)
    results['geometry_unique_file_count']=len(geometry)
    results['geometry_train_ranges']={field:{'min':float(geometry[field].min()),'max':float(geometry[field].max()),'q25':float(geometry[field].quantile(.25)),'q75':float(geometry[field].quantile(.75))} for field in fields}
    results['input_hashes_unchanged']=all(sha(PROJECT/path)==h for path,h in hashes.items())
    assert results['input_hashes_unchanged']
    (HERE/'diagnostic_results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    print(json.dumps(results,indent=2,allow_nan=False))

if __name__=='__main__':
    main()
