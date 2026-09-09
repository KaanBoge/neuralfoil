"""Read-only independent cross-checks; no fits or optimization."""
from pathlib import Path
import hashlib,importlib.util,json,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;FRONT=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    union=module('cross_union',FRONT/'union_historical/run_union.py')
    assert len(union.loader.COMPONENTS)==21 and len(union.solver.COMPONENTS)==27
    ready=sorted((FRONT/'union_historical/results').glob('weights_*.json'))
    assert ready
    checked=[]
    for path in ready:
        art=json.loads(path.read_text());frame,idx,hashes=union.training(art['split'])
        assert set(frame.historical_index)<=set(idx)
        assert set(frame.nf2_row_id)==set(art['training_nf2_row_ids'])
        assert hashes==art['input_sha256']
        w=np.array([art['solutions']['primary_union_both']['weights'][c] for c in union.COMPONENTS])
        assert w.min()>=-1e-9 and abs(w.sum()-1)<1e-9
        checked.append({'split':art['split'],'context_rows':len(frame),'unique_training_rows':len(idx)})
    stage=sys.argv[1] if len(sys.argv)>1 else 'capacity'
    assert stage in ['capacity','final']
    assessment=FRONT/('assessment_'+stage)
    frame=pd.read_csv(assessment/'all_row_predictions.csv',low_memory=False)
    boot=pd.read_csv(assessment/'conditional_paired_bootstrap.csv')
    table=pd.read_csv(assessment/'panel_metrics.csv')
    decisions=pd.read_csv(assessment/'operational_decisions.csv')
    for split,n in [('SG_exposed',234),('W_new_challenge',238)]:
        f=frame[frame.split==split];raw=f.inference_gate
        explicit=raw.map(lambda v:str(v).lower()=='true' or v==1).to_numpy(bool)
        np.testing.assert_array_equal(explicit,raw.to_numpy(dtype=bool));assert explicit.sum()==n
        for c in decisions.candidate:
            np.testing.assert_allclose(f[c].to_numpy()[~explicit],f.mean8_CD.to_numpy()[~explicit],rtol=0,atol=1e-15)
    reference='reference_primary_both';maxerr=0.
    for seed in [20260906,20260908]:
        f=frame[frame.split.str.startswith(f'group_{seed}_')]
        assert len(f)==8371 and f.nf2_row_id.nunique()==8371
        _,inv=np.unique(f.group,return_inverse=True);ng=len(np.unique(inv))
        y=f.measured_CD.to_numpy();re=np.bincount(inv,weights=abs(f[reference].to_numpy()-y));xb=np.bincount(inv,weights=abs(f.xlarge_CD.to_numpy()-y))
        counts=np.random.default_rng(2026090717).multinomial(ng,np.ones(ng)/ng,size=20000)
        for _,row in boot[boot.assignment==seed].iterrows():
            ce=np.bincount(inv,weights=abs(f[row.candidate].to_numpy()-y));benefit=100*(1-counts@ce/(counts@re));pp=100*((counts@re)-(counts@ce))/(counts@xb)
            actual=[100*(1-ce.sum()/re.sum()),*np.quantile(benefit,[.025,.975]),*np.quantile(pp,[.025,.975])]
            stored=[row.relative_remaining_MAE_reduction_percent,row.conditional_95pct_lower,row.conditional_95pct_upper,row.increment_conditional_95pct_lower_pp,row.increment_conditional_95pct_upper_pp]
            maxerr=max(maxerr,float(np.max(np.abs(np.array(actual)-stored))))
    assert maxerr<1e-10
    fields=['xlarge_CD_improvement_percent','mean8_CD_improvement_percent']
    external=table.panel.str.startswith('eligible_only/')
    r=table[(table.candidate==reference)&external][fields].to_numpy();assert r.shape==(8,2)
    for _,row in decisions.iterrows():
        b=boot[boot.candidate==row.candidate];t=table[table.candidate==row.candidate]
        source=t[t.panel.str.startswith('strict_source_')][fields].to_numpy();e=t[t.panel.str.startswith('eligible_only/')][fields].to_numpy()
        assert source.shape==(5,2) and e.shape==(8,2)
        expected=bool((b.relative_remaining_MAE_reduction_percent>=1).all() and (source>=0).all() and (e<0).sum()<=(r<0).sum() and e.min()>=r.min()-1e-6)
        assert expected==row.operational_frontier_advance
    paths=[FRONT/'kernel/kernel_models.py',FRONT/'kernel/run_kernel.py',FRONT/'kernel/PROTOCOL.md',FRONT/'union_historical/run_union.py',FRONT/'union_historical/PROTOCOL.md',FRONT/'frontier_assessment.py',Path(union.loader.__file__),Path(__file__)]
    for branch,mfile in [('kernel','run_manifest.json'),('union_historical','manifest.json')]:
        manifest=json.loads((FRONT/branch/'results'/mfile).read_text())
        for p,h in manifest['hashes'].items():assert sha(p)==h
    out={'status':'PASS available union assemblies and assessment replay; no refits','stage':stage,'union_completed_weights_checked':checked,'kernel_and_union_manifest_hashes_match':True,'bootstrap_20k_all_candidates_max_abs_error':maxerr,'operational_decisions_identical':True,'source_sha256':{str(p):sha(p) for p in paths}}
    (HERE/('cross_checks.json' if stage=='capacity' else 'final_cross_checks.json')).write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out),flush=True)

if __name__=='__main__':main()
