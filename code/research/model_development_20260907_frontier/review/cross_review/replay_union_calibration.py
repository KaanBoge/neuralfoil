"""Independent completed-output replay. No optimizers, fitting or pickle loading."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;FRONT=HERE.parents[1];OUT=FRONT/'union_calibration'
sys.path.insert(0,str(FRONT))
import frontier_assessment as assess

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gate(f):return f.inference_gate.map(lambda x:str(x).lower()=='true' or x==1).to_numpy(bool)
def compare(table,frame,pred,panels):
    assert len(table)==len(panels) and set(table.panel)==set(panels)
    worst=0.
    for name,idx in panels.items():
        row=table[table.panel==name].iloc[0];assert row.rows==len(idx)
        y=frame.measured_CD.to_numpy()[idx];error=abs(pred[idx]-y)
        vals={'mae_CD':error.mean(),'median_absolute_error_CD':np.median(error),'p90_absolute_error_CD':np.quantile(error,.9)}
        for b in ['mean8_CD','xlarge_CD']:
            be=abs(frame[b].to_numpy()[idx]-y)
            vals[b+'_mae']=be.mean();vals[b+'_improvement_percent']=100*(1-error.sum()/be.sum())
            assert row[b+'_worse_rows']==int((error>be+1e-14).sum())
        for k,v in vals.items():worst=max(worst,abs(v-row[k]))
    assert worst<1e-8,worst
    return worst

def main():
    assert (OUT/'complete_report.json').is_file(),'Wait for complete_report.json; never verify partial calibration as complete'
    manifest=json.loads((OUT/'complete_report.json').read_text())
    d,oldcols,_,hashes=assess.load_frame(['capacity','kernel','conditional'])
    columns=oldcols+[f'capacity__{f}__1' for f in assess.CAPACITY]+['kernel__kernel24_l1__1','kernel__kernel62_l1__1']+['conditional__re2','conditional__alpha2','conditional__re_alpha4']
    aliases=['union_component__'+c for c in columns]
    assert len(columns)==len(set(columns))==30
    assert aliases==manifest['components'] and dict(zip(aliases,columns))==manifest['component_aliases']
    assert hashes==manifest['input_sha256']
    inactive=d.split.isin(['SG_exposed','W_new_challenge']).to_numpy()&~gate(d);assert inactive.sum()==25
    matrix=d[columns].to_numpy().copy();matrix[inactive]=d.mean8_CD.to_numpy()[inactive,None]
    saved=pd.read_csv(OUT/'all_row_predictions.csv',low_memory=False)
    assess.check_common(d,saved);np.testing.assert_array_equal(d.split,saved.split)
    np.testing.assert_allclose(saved[columns],d[columns],rtol=0,atol=1e-15)
    np.testing.assert_allclose(saved[aliases],matrix,rtol=0,atol=1e-15)
    panels=assess.old.panels(d);eligible={k:v for k,v in assess.reconcile.external_panels(d).items() if k.startswith('eligible_only/')}
    assert len(panels)==23 and len(eligible)==8
    metrics=pd.read_csv(OUT/'panel_metrics.csv');em=pd.read_csv(OUT/'eligible_external_metrics.csv')
    details={};maxerr=0.;predictionerr=0.
    for obj,bases in [('both',['xlarge_CD','mean8_CD']),('xlarge',['xlarge_CD'])]:
        s=json.loads((OUT/f'blend_{obj}.json').read_text());assert set(s['weights'])==set(aliases)
        w=np.array([s['weights'][c] for c in aliases]);assert w.min()>=-1e-9 and abs(w.sum()-1)<1e-9
        pred=matrix@w;pred[inactive]=d.mean8_CD.to_numpy()[inactive]
        predictionerr=max(predictionerr,float(abs(pred-saved['union_blend_'+obj]).max()))
        np.testing.assert_allclose(pred[inactive],d.mean8_CD.to_numpy()[inactive],rtol=0,atol=1e-12)
        mt=metrics[metrics.candidate=='union_blend_'+obj]
        maxerr=max(maxerr,compare(mt,d,pred,panels),compare(em[em.candidate=='union_blend_'+obj],d,pred,eligible))
        actual=min(mt[b+'_improvement_percent'].min()/100 for b in bases)
        assert abs(actual-s['actual_min_improvement_fraction'])<1e-10
    holds=[('hold_sg6050',['sg6050']),('hold_sg6051',['sg6051']),('hold_w1011',['w1011']),('hold_w1015',['w1015']),('hold_SG_pair',['sg6050','sg6051']),('hold_W_pair',['w1011','w1015'])]
    for name,designs in holds:
        mask=d.split.isin(['SG_exposed','W_new_challenge'])&d.airfoil.astype(str).str.lower().isin(designs)
        held=np.flatnonzero(mask);train=np.flatnonzero(~mask);inverse={int(i):j for j,i in enumerate(train)}
        tp={k:np.array([inverse[int(i)] for i in ix if int(i) in inverse],dtype=int) for k,ix in panels.items()};tp={k:v for k,v in tp.items() if len(v)}
        trainframe=d.iloc[train].reset_index(drop=True);test=d.iloc[held].reset_index(drop=True)
        assert len(trainframe[trainframe.split.str.startswith('group_')])==16742
        assert not trainframe.airfoil.astype(str).str.lower().isin(designs).any()
        solution=json.loads((OUT/f'weights_{name}.json').read_text());assert solution['held_designs']==designs and solution['held_rows']==len(held)
        assert set(solution['weights'])==set(aliases) and solution['held_label_mutation_isolated']
        w=np.array([solution['weights'][c] for c in aliases]);assert w.min()>=-1e-9 and abs(w.sum()-1)<1e-9
        pred=matrix[held]@w;pred[~gate(test)]=test.mean8_CD.to_numpy()[~gate(test)]
        trainpred=matrix[train]@w
        hs=pd.read_csv(OUT/f'predictions_{name}.csv',low_memory=False);assess.check_common(test,hs)
        assert 'union_blend_both' not in hs and 'union_blend_xlarge' not in hs
        np.testing.assert_allclose(hs[aliases],matrix[held],rtol=0,atol=1e-15)
        predictionerr=max(predictionerr,float(abs(pred-hs.withheld_union_blend).max()))
        tg=gate(test);hp={'all_rows/pooled':np.arange(len(test)),'eligible_only/pooled':np.flatnonzero(tg)}
        for config in sorted(test.configuration.unique()):
            cm=(test.configuration==config).to_numpy();hp['all_rows/'+config]=np.flatnonzero(cm);hp['eligible_only/'+config]=np.flatnonzero(cm&tg)
        maxerr=max(maxerr,compare(pd.read_csv(OUT/f'metrics_{name}.csv'),test,pred,hp),compare(pd.read_csv(OUT/f'calibration_metrics_{name}.csv'),trainframe,trainpred,tp))
        assert solution['held_eligible_rows']==int(tg.sum())
        np.testing.assert_allclose(pred[~tg],test.mean8_CD.to_numpy()[~tg],rtol=0,atol=1e-12)
        # The actual LP's inputs are ONLY matrix[train], these training labels,
        # baselines and tp. Held outcomes cannot enter any of these arrays.
        mutated=d.measured_CD.to_numpy().copy();mutated[held]=np.nan
        np.testing.assert_array_equal(mutated[train],trainframe.measured_CD)
        details[name]={'held_rows':len(held),'eligible_rows':int(tg.sum()),'training_rows':len(train),'training_panels':len(tp),'held_label_isolation_replayed':True}
    assert predictionerr<1e-12
    for p,h in hashes.items():assert sha(p)==h
    for key,p in [('source_sha256',FRONT/'union_calibration.py'),('protocol_sha256',FRONT/'UNION_PROTOCOL.md'),('assessment_helper_sha256',FRONT/'frontier_assessment.py'),('feasibility_helper_sha256',Path(assess.old.__file__))]:assert sha(p)==manifest[key]
    provenance={str(p):sha(p) for p in OUT.glob('*') if p.is_file()}
    provenance[str(Path(__file__))]=sha(Path(__file__))
    result={'status':'PASS independent completed 30-component union calibration replay; no optimizer','components':30,'all_row_panels_per_objective':23,'eligible_panels_per_objective':8,'max_abs_prediction_CD':predictionerr,'max_metric_difference':maxerr,'withholding':details,'provenance_sha256':provenance,'scope':'retrospective exposed calibration and adaptive complete-design meta withholding; not blind validation'}
    (HERE/'union_calibration_replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
