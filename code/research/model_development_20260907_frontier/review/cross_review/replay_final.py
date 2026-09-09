"""Completed union historical prediction and common final metric replay, no fitting."""
from pathlib import Path
import json,sys,hashlib
import numpy as np
import pandas as pd
from replay_union_calibration import compare,gate
HERE=Path(__file__).resolve().parent;FRONT=HERE.parents[1]
sys.path.insert(0,str(FRONT));import frontier_assessment as a
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    directory=FRONT/'assessment_final';assert (directory/'report.json').is_file()
    report=json.loads((directory/'report.json').read_text());f=pd.read_csv(directory/'all_row_predictions.csv',low_memory=False)
    original,_,labels,hashes=a.load_frame(['capacity','kernel','conditional']);a.check_common(f,original)
    np.testing.assert_array_equal(f.split,original.split)
    np.testing.assert_allclose(f[labels+[a.REFERENCE]],original[labels+[a.REFERENCE]],rtol=0,atol=1e-15)
    udir=FRONT/'union_historical/results';u=pd.read_csv(udir/'all_row_predictions.csv',low_memory=False)
    a.check_common(f,u);np.testing.assert_array_equal(f.split,u.split)
    freeze=json.loads((udir/'freeze.json').read_text());assert len(freeze['weights_sha256'])==16
    for p,h in freeze['weights_sha256'].items():assert sha(p)==h
    maxpred=0.
    for split in u.split.unique():
        ext=split in ['SG_exposed','W_new_challenge'];p=udir/f"weights_{'final' if ext else split}.json";art=json.loads(p.read_text())
        part=u[u.split==split];cols=art['components'];assert len(cols)==27
        weights=np.array([art['solutions']['primary_union_both']['weights'][c] for c in cols]);pred=part[cols].to_numpy()@weights
        if ext:pred[~gate(part)]=part.mean8_CD.to_numpy()[~gate(part)]
        else:
            assert set(part.nf2_row_id).isdisjoint(art['training_nf2_row_ids'])
            assert set(part.group).isdisjoint(art['training_groups'])
        maxpred=max(maxpred,float(abs(pred-part.primary_union_both).max()))
    assert maxpred<1e-12
    np.testing.assert_array_equal(f.union_historical__primary_union_both,u.primary_union_both)
    panels=a.old.panels(f);panels.update({k:v for k,v in a.reconcile.external_panels(f).items() if k.startswith('eligible_only/')})
    table=pd.read_csv(directory/'panel_metrics.csv');maxmetric=0.
    for c in table.candidate.unique():maxmetric=max(maxmetric,compare(table[table.candidate==c],f,f[c].to_numpy(),panels))
    summary=pd.read_csv(directory/'candidate_summary.csv');fields=['xlarge_CD_improvement_percent','mean8_CD_improvement_percent']
    for _,row in summary.iterrows():
        t=table[table.candidate==row.candidate].set_index('panel')
        assert abs(row.minimum_all23_improvement_both_percent-t.loc[~t.index.str.startswith('eligible_only/'),fields].to_numpy().min())<1e-10
        assert abs(row.worst_strict_source_improvement_both_percent-t.loc[t.index.str.startswith('strict_source_'),fields].to_numpy().min())<1e-10
        assert abs(row.worst_eligible_external_improvement_both_percent-t.loc[t.index.str.startswith('eligible_only/'),fields].to_numpy().min())<1e-10
        assert row.eligible_external_negative_panel_baseline_pairs==(t.loc[t.index.str.startswith('eligible_only/'),fields].to_numpy()<0).sum()
    assert report['candidate_count_excluding_reference']==len(labels)+1
    for p,h in report['input_sha256'].items():assert sha(p)==h
    assert sha(FRONT/'final_assessment.py')==report['source_sha256'] and sha(FRONT/'frontier_assessment.py')==report['shared_assessment_sha256']
    result={'status':'PASS independent final union historical and all final metrics replay','historical_union_weight_artifacts':16,'max_union_prediction_abs_CD':maxpred,'max_metric_difference':maxmetric,'candidate_count_excluding_reference':len(labels)+1,'metric_rows':len(table),'practical_advances':report['practical_advances'],'provenance_sha256':{str(p):sha(p) for p in [Path(__file__),udir/'report.json',udir/'freeze.json',directory/'report.json']}}
    (HERE/'final_replay.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
