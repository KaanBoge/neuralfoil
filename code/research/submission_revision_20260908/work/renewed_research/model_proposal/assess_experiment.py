"""Read-only inherited decision semantics; every new evaluation retained."""
import importlib.util
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd
import incremental_harm as policy
from run_experiment import HERE,A,OUT,EXPOSED,SEAL_SHA,checked,sha,dump,now,load_npz

CANDIDATES=[policy.LABEL]
CONTROLS=['proper_capped_half','proper_capped_full','project_mean8_capped','project_xlarge_capped',
          'mean8_CD','xlarge_CD','capped_half','capped_full','unpenalized_transfer','half_strength']
LABELS=CANDIDATES+CONTROLS


def extra_metrics(frame,panels):
    risk_rows=[];bundle_rows=[];intervention_rows=[]
    for panel,ix in panels.items():
        f=frame.iloc[ix].copy()
        ext=f.split.isin(['SG_exposed','W_new_challenge'])
        assert ext.all() or not ext.any()
        # External nominal design, retaining all configurations in pooled views.
        f['audit_identity']=f.airfoil.astype(str) if ext.all() else f.group.astype(str)
        y=f.measured_CD.to_numpy();b=f.mean8_CD.to_numpy();anchor=f.proper_capped_half.to_numpy()
        for label in LABELS:
            error=abs(f[label].to_numpy()-y)
            delta=error-abs(anchor-y);loss=np.maximum(delta,0)/b
            gm=[]
            for identity,part in f.groupby('audit_identity',sort=True):
                mask=f.audit_identity.eq(identity).to_numpy()
                value=float(loss[mask].mean());gm.append(value)
                bundle_rows.append({'candidate':label,'panel':panel,'identity':identity,
                    'rows':int(mask.sum()),'mean_normalized_positive_excess_vs_matched_half':value})
            risk_rows.append({'candidate':label,'panel':panel,'rows':len(f),'identity_count':len(gm),
                'equal_identity_mean_normalized_positive_excess_vs_matched_half':float(np.mean(gm)),
                'pooled_row_mean_normalized_positive_excess_vs_matched_half':float(loss.mean()),
                'empirical_equal_identity_budget_exceeded':bool(np.mean(gm)>.01),
                'interpretation':'Descriptive reused outcomes, not verification of future IID risk control'})
        pred=f[policy.LABEL].to_numpy();mask=abs(pred-anchor)>1e-12
        row={'panel':panel,'rows':len(f),'eligible_rows':int(f.interval_applicable.sum()),
             'interventions_vs_matched_half':int(mask.sum()),'intervention_fraction':float(mask.mean()),
             'interventions_vs_mean8':int((abs(pred-b)>1e-12).sum()),
             'applied_strength_min':float(f[policy.LABEL+'__strength'].min()),
             'applied_strength_mean':float(f[policy.LABEL+'__strength'].mean()),
             'applied_strength_max':float(f[policy.LABEL+'__strength'].max())}
        for ref in ['proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
            d=abs(pred-y)-abs(f[ref].to_numpy()-y)
            row[ref+'__selected_harm_fraction']=float((d[mask]>1e-12).mean()) if mask.any() else None
            row[ref+'__selected_benefit_fraction']=float((d[mask]<-1e-12).mean()) if mask.any() else None
            row[ref+'__selected_positive_excess_CD']=float(np.maximum(d[mask],0).mean()) if mask.any() else None
        intervention_rows.append(row)
    return pd.DataFrame(risk_rows),pd.DataFrame(bundle_rows),pd.DataFrame(intervention_rows)


def main():
    dest=HERE/'assessment';assert not dest.exists()
    complete=json.loads((OUT/'complete.json').read_text());freeze=json.loads((OUT/'freeze.json').read_text())
    assert complete['freeze_sha256']==sha(OUT/'freeze.json')
    assert freeze['calibrator_count']==16 and freeze['new_core_fits']==0 and freeze['external_outcomes_opened'] is False
    hashes={}
    for record in [freeze,complete]:
        for key in ['source_input_sha256','artifact_sha256','external_input_sha256','output_sha256']:
            for p,h in record.get(key,{}).items():checked(p,h);hashes[p]=h
    seal=json.loads(checked(A/'DELIVERY_QA.json',SEAL_SHA))
    p=A/'assess_cap.py';h=seal['source_and_result_sha256'][str(p)];checked(p,h)
    spec=importlib.util.spec_from_file_location('incremental_prior_cap_assessment',p)
    cap=importlib.util.module_from_spec(spec);spec.loader.exec_module(cap)
    frame,panels,metrics,prior,inherited=cap.load();hashes.update(inherited)
    for split in frame.split.unique():
        external=split in ['SG_exposed','W_new_challenge']
        p=(EXPOSED if external else OUT)/(f'{split}_predictions.csv' if external else f'predictions_{split}.csv')
        fresh=pd.read_csv(io.BytesIO(checked(p,complete['output_sha256'][str(p)])),low_memory=False)
        mask=frame.split.eq(split);old=frame.loc[mask]
        if not external:
            assert not fresh.nf2_row_id.duplicated().any()
            fresh=fresh.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(fresh.configuration,old.configuration)
        assert len(fresh)==len(old)
        for field in ['Re','alpha','measured_CD','mean8_CD','xlarge_CD','proper_capped_half','proper_capped_full']:
            np.testing.assert_allclose(fresh[field],old[field],rtol=0,atol=1e-13)
        for field in [policy.LABEL,policy.LABEL+'__strength',policy.LABEL+'__intervened','calibration_t']:
            frame.loc[mask,field]=fresh[field].to_numpy()
    assert len(frame)==29856 and len(panels)==31
    # Configure imported non-fitting metric functions in memory only.
    metrics.LABELS=LABELS;metrics.CANDIDATES=CANDIDATES;metrics.CONTROLS=CONTROLS
    metrics.REFERENCES=['unpenalized_transfer','half_strength','proper_capped_half']
    metrics.SEED=2026090831;metrics.N_BOOTSTRAP=20000
    table=metrics.panel_metrics(frame,panels);boot=metrics.bootstrap(frame);groups=metrics.group_metrics(frame)
    decisions=metrics.decisions(table,boot,groups)
    risk,bundles,interventions=extra_metrics(frame,panels)
    cal=[]
    for context in freeze['contexts']:
        p=OUT/f'calibrator_{context}.json';v=json.loads(checked(p,freeze['artifact_sha256'][str(p)]))
        cal.append({k:v[k] for k in ['context','groups','rows','endpoint_mean','hoeffding_penalty','upper_bound','t','inside_gate_strength','status']})
    outputs={'panel_metrics':table,'bootstrap':boot,'group_metrics':groups,'decisions':decisions,
        'candidate_summary':metrics.summary(table,boot,groups),'harm_metrics':metrics.harms(frame,panels),
        'expected_harm_metrics':risk,'bundle_harm_metrics':bundles,'intervention_metrics':interventions,
        'calibration_summary':pd.DataFrame(cal),'all_row_predictions':frame}
    assert len(table)==341 and len(boot)==66 and len(groups)==2046 and len(decisions)==1
    for p,h in hashes.items():checked(p,h)
    hashes[str(OUT/'freeze.json')]=sha(OUT/'freeze.json');hashes[str(OUT/'complete.json')]=sha(OUT/'complete.json')
    dest.mkdir()
    for name,value in outputs.items():value.to_csv(dest/f'{name}.csv',index=False,mode='x')
    report={'completed_utc':now(),'status':'complete_exploratory_not_certified','new_core_fits':0,
        'calibrator_count':16,'candidates':CANDIDATES,'controls':CONTROLS,'panels':31,'split_row_instances':29856,
        'bootstrap_draws':20000,'bootstrap_seed':2026090831,'epsilon':.01,'delta':.05,'B':.5,
        'performance_advances':decisions.loc[decisions.performance_advance,'candidate'].tolist(),
        'robustness_advances':decisions.loc[decisions.robustness_advance,'candidate'].tolist(),
        'source_input_sha256':hashes,'output_sha256':{str(dest/f'{n}.csv'):sha(dest/f'{n}.csv') for n in outputs},
        'warning':'Matched proper-half risk reference differs from all-training half. No IID certification, prospective validation, or default change.'}
    dump(dest/'report.json',report)
    print(decisions.to_string(index=False));print(outputs['candidate_summary'].to_string(index=False))


if __name__=='__main__':main()
