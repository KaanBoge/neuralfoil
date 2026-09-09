"""Approved post-freeze assessment only; inherits unchanged adverse decisions."""
import argparse
import importlib.util
import io
import json
import sys
from pathlib import Path
import time
import numpy as np
import pandas as pd
import run_stage1 as run

OLD_REPORT='1c34134f311695a54a9c91c0ffa19699c7ce826eb1c8f50e671336f263cce9ff'
OLD_LABEL='calibrated_incremental_harm_001'
CONTROLS=['proper_capped_half','proper_capped_full','project_mean8_capped','project_xlarge_capped',
          'mean8_CD','xlarge_CD','capped_half','capped_full','unpenalized_transfer','half_strength',
          OLD_LABEL,'qualified_matched_half','qualified_matched_full']
LABELS=list(run.LABELS)+CONTROLS


def extras(frame,panels):
    risk=[];bundles=[];interventions=[]
    for panel,ix in panels.items():
        f=frame.iloc[ix];y=f.measured_CD.to_numpy();b=f.mean8_CD.to_numpy()
        anchor=f.qualified_matched_half.to_numpy()
        ext=f.split.isin(run.EXTERNAL)
        if not (ext.all() or not ext.any()):raise ValueError('mixed external panel')
        ids=f.airfoil.astype(str).to_numpy() if ext.all() else f.group.astype(str).to_numpy()
        for label in LABELS:
            delta=abs(f[label].to_numpy()-y)-abs(anchor-y)
            loss=np.maximum(delta,0)/b;gm=[]
            for identity in np.unique(ids):
                mask=ids==identity;value=float(loss[mask].mean());gm.append(value)
                bundles.append({'candidate':label,'panel':panel,'identity':identity,'rows':int(mask.sum()),
                    'mean_normalized_positive_excess_vs_qualified_half':value})
            risk.append({'candidate':label,'panel':panel,'rows':len(f),'identity_count':len(gm),
                'equal_identity_mean_normalized_positive_excess_vs_qualified_half':float(np.mean(gm)),
                'pooled_row_mean_normalized_positive_excess_vs_qualified_half':float(loss.mean()),
                'empirical_budget_exceeded':bool(np.mean(gm)>.01),
                'interpretation':'Descriptive reused outcomes, not certified'})
        for label in run.LABELS:
            p=f[label].to_numpy();selected=abs(p-anchor)>1e-12
            e=f[label+'__effective_fraction'].to_numpy()
            row={'candidate':label,'panel':panel,'rows':len(f),'interventions':int(selected.sum()),
                'physical_eligible_rows':int(f.interval_applicable.sum()),
                'qualified_eligible_rows':int(f.qualified_gate.sum()),
                'intervention_fraction':float(selected.mean()),'effective_fraction_min':float(e.min()),
                'effective_fraction_mean':float(e.mean()),'effective_fraction_max':float(e.max())}
            for ref in ['qualified_matched_half','proper_capped_half','half_strength','mean8_CD','xlarge_CD']:
                d=abs(p-y)-abs(f[ref].to_numpy()-y)
                row[ref+'__selected_harm_fraction']=float((d[selected]>1e-12).mean()) if selected.any() else None
                row[ref+'__selected_benefit_fraction']=float((d[selected]<-1e-12).mean()) if selected.any() else None
                row[ref+'__selected_positive_excess_CD']=float(np.maximum(d[selected],0).mean()) if selected.any() else None
            interventions.append(row)
    return pd.DataFrame(risk),pd.DataFrame(bundles),pd.DataFrame(interventions)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--implementation-sha256',required=True)
    parser.add_argument('--approval',required=True);parser.add_argument('--approval-sha256',required=True)
    args=parser.parse_args();args.phase='assess';run.authorize(args);run.begin_phase(args)
    dest=run.HERE/'assessment';dest.mkdir(exist_ok=False)
    import signal
    def timeout(*unused):raise TimeoutError('fixed 900-second assessment guard')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(900)
    try:assess(dest)
    except BaseException as exc:
        import traceback
        run.write_json(dest/'FAILURE.json',{'execution':run.receipt(),'exception':repr(exc),'traceback':traceback.format_exc()});raise
    finally:signal.alarm(0)


def assess(dest):
    # Authenticate the entire new parity/scalar/prediction chain BEFORE old target-bearing loaders.
    complete=json.loads((run.HERE/'predictions/complete.json').read_bytes())
    freeze=json.loads((run.HERE/'results/freeze.json').read_bytes())
    _,parity_hash=run.read_parity()
    if complete['freeze_sha256']!=run.sha((run.HERE/'results/freeze.json').read_bytes()) or freeze['calibrator_count']!=32 or freeze['external_outcomes_opened'] or freeze['parity_sha256']!=parity_hash:
        raise ValueError('32-scalar freeze/parity barrier required')
    for record in [freeze,complete]:
        if record.get('execution',{}).get('implementation_sha256')!=run._EXECUTION.get('implementation_sha256'):
            raise ValueError('assessment implementation provenance mismatch')
        for path,h in record['source_input_sha256'].items():run.read_checked(path,h)
    for path,h in freeze['artifact_sha256'].items():run.read_checked(run.HERE/'results'/path,h)
    for path,h in complete['output_sha256'].items():run.read_checked(run.HERE/'predictions'/path,h)
    old=run.json_checked(run.OLD/'assessment/report.json',OLD_REPORT)
    # Authenticate old data/metric code before invoking the inherited non-fitting loader.
    for path,h in old['source_input_sha256'].items():run.read_checked(path,h)
    a_qa=run.json_checked(run.A/'DELIVERY_QA.json',run.PINS['a_qa'])
    path=run.A/'assess_cap.py'
    source=run.read_checked(path,a_qa['source_and_result_sha256'][str(path)])
    spec=importlib.util.spec_from_file_location('qualified_inherited_cap_assessment',path)
    cap=importlib.util.module_from_spec(spec);exec(compile(source,str(path),'exec'),cap.__dict__)
    frame,panels,metrics,prior,inherited=cap.load()
    old_csv=run.OLD/'assessment/all_row_predictions.csv'
    old_frame=pd.read_csv(io.BytesIO(run.read_checked(old_csv,old['output_sha256'][str(old_csv)])),low_memory=False)
    if len(frame)!=29856 or len(panels)!=31 or len(old_frame)!=len(frame):raise ValueError('full panel inventory')
    # Match the original row-instance ordering, never join on a nominal name alone.
    np.testing.assert_array_equal(frame.split.astype(str),old_frame.split.astype(str))
    for col in ['mean8_CD','xlarge_CD','measured_CD']:
        np.testing.assert_allclose(frame[col],old_frame[col],rtol=0,atol=1e-13)
    frame[OLD_LABEL]=old_frame[OLD_LABEL].to_numpy()
    for split in frame.split.unique():
        name=f'predictions_{split}.csv'
        f=pd.read_csv(io.BytesIO(run.read_checked(run.HERE/'predictions'/name,complete['output_sha256'][name])),low_memory=False)
        mask=frame.split.eq(split);previous=frame.loc[mask]
        if len(f)!=len(previous):raise ValueError('split rows')
        if split not in run.EXTERNAL:
            if f.nf2_row_id.duplicated().any():raise ValueError('duplicate historical row ID')
            f=f.set_index('nf2_row_id').loc[previous.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(f.configuration,previous.configuration)
        for key in ['Re','alpha','mean8_CD','xlarge_CD','measured_CD']:
            np.testing.assert_allclose(f[key],previous[key],rtol=0,atol=1e-13)
        for key in ['qualified_matched_half','qualified_matched_full','qualified_gate']+[
            k for label in run.LABELS for k in [label,label+'__strength',label+'__effective_fraction',label+'__intervened']]:
            frame.loc[mask,key]=f[key].to_numpy()
    metrics.CANDIDATES=list(run.LABELS);metrics.CONTROLS=CONTROLS;metrics.LABELS=LABELS
    metrics.REFERENCES=['unpenalized_transfer','half_strength','proper_capped_half',
                        'qualified_matched_half',run.LABELS[1]]
    metrics.SEED=2026090831;metrics.N_BOOTSTRAP=20000
    table=metrics.panel_metrics(frame,panels);boot=metrics.bootstrap(frame);groups=metrics.group_metrics(frame)
    decisions=metrics.decisions(table,boot,groups)
    risk,bundles,interventions=extras(frame,panels)
    scalar=[]
    for context in freeze['contexts']:
        for label in run.LABELS:
            name=f'calibrator_{label}_{context}.json'
            z=run.json_checked(run.HERE/'results'/name,freeze['artifact_sha256'][name])
            scalar.append({'context':context,'candidate':label,'groups':z['groups'],'rows':z['rows'],
                'B':float(run.fraction(z['bound'])),'upper':float(run.fraction(z['upper'])),
                'endpoint_mean':float(run.fraction(z['exact_mean'])) if z['exact_mean'] else None,'t':z['t']})
    outputs={'panel_metrics':table,'bootstrap':boot,'group_metrics':groups,'decisions':decisions,
        'candidate_summary':metrics.summary(table,boot,groups),'harm_metrics':metrics.harms(frame,panels),
        'expected_harm_metrics':risk,'bundle_harm_metrics':bundles,'intervention_metrics':interventions,
        'calibration_summary':pd.DataFrame(scalar),'all_row_predictions':frame}
    if len(table)!=31*len(LABELS) or len(decisions)!=2:raise ValueError('assessment inventory')
    for name,value in outputs.items():value.to_csv(dest/f'{name}.csv',index=False,mode='x')
    run.write_json(dest/'report.json',{'status':'EXPLORATORY_NOT_CERTIFIED','new_core_fits':0,'scalar_count':32,
        'execution':run.receipt(),
        'candidates':run.LABELS,'controls':CONTROLS,'rows_with_repeated_contexts':29856,'panels':31,
        'bootstrap_draws':20000,'bootstrap_seed':2026090831,'row_tolerance_CD':1e-12,'PP_TOL':1e-6,
        'performance_advances':decisions.loc[decisions.performance_advance,'candidate'].tolist(),
        'robustness_advances':decisions.loc[decisions.robustness_advance,'candidate'].tolist(),
        'source_input_sha256':{**inherited,**complete['source_input_sha256'],str(old_csv):old['output_sha256'][str(old_csv)],
            str(run.HERE/'results/freeze.json'):complete['freeze_sha256']},
        'output_sha256':{name+'.csv':run.sha((dest/(name+'.csv')).read_bytes()) for name in outputs}})

if __name__=='__main__':main()
