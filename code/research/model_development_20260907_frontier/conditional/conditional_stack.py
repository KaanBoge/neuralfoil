"""Fixed low-capacity conditional mixtures, trained only on historical inner OOF."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import sys
import time
import warnings
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import linprog, OptimizeWarning

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
POSITIVE = PROJECT/"model_development_20260907_positive"
sys.path.insert(0, str(POSITIVE))
import historical_stack as prior

VARIANTS = ["re2", "alpha2", "re_alpha4"]
COMPONENTS = prior.COMPONENTS
OUT = HERE/"results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def basis(variant, re, alpha, endpoints):
    r = np.clip((np.log10(re)-endpoints[0])/max(endpoints[1]-endpoints[0],1e-12),0,1)
    a = np.clip(np.abs(alpha)/12,0,1)
    if variant == "re2": return np.column_stack([1-r,r])
    if variant == "alpha2": return np.column_stack([1-a,a])
    if variant == "re_alpha4": return np.column_stack([(1-r)*(1-a),(1-r)*a,r*(1-a),r*a])
    raise ValueError(variant)


def predict(model, component_matrix, re, alpha, base=None, inference_gate=None):
    matrix = np.asarray(component_matrix, dtype=float)
    w = np.asarray(model["corner_weights"], dtype=float)
    phi = basis(model["variant"], np.asarray(re), np.asarray(alpha), model["re_endpoints"])
    row_weights = phi@w
    assert np.isfinite(row_weights).all() and row_weights.min() >= -1e-8
    np.testing.assert_allclose(row_weights.sum(axis=1),1,atol=1e-8)
    pred = np.sum(matrix*row_weights,axis=1)
    if inference_gate is not None:
        gate = np.asarray(inference_gate)
        assert gate.dtype == bool and gate.shape == pred.shape
        pred = np.where(gate,pred,base)
    assert np.isfinite(pred).all() and (pred > 0).all()
    return pred


def lp(*args, **kwargs):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Unrecognized options detected.*", category=OptimizeWarning)
        return linprog(*args, method="highs-ipm", options={"threads":1}, **kwargs)


def fit_variant(frame, panels, center, variant, endpoints):
    start = time.monotonic()
    phi = basis(variant, frame.Re.to_numpy(), frame.alpha.to_numpy(), endpoints)
    core = frame[COMPONENTS].to_numpy()*1e4
    x = np.column_stack([core*phi[:,i,None] for i in range(phi.shape[1])])
    y = frame.measured_CD.to_numpy()*1e4
    n,p = x.shape
    k,b = len(COMPONENTS),phi.shape[1]
    # variables: p corner weights, n absolute errors, p L1 auxiliaries, ratio.
    size = p+n+p+1
    zero = sparse.csr_matrix((n,p+1))
    a = sparse.vstack([sparse.hstack([sparse.csr_matrix(x),-sparse.eye(n),zero]),
                       sparse.hstack([-sparse.csr_matrix(x),-sparse.eye(n),zero])],format="csr")
    rhs = [y,-y]
    constraints = sparse.lil_matrix((len(panels)*2+2*p+b,size))
    panel_info = []
    counter = 0
    for baseline in ["xlarge_CD","mean8_CD"]:
        be = np.abs(frame[baseline].to_numpy()*1e4-y)
        for name,(idx,weights) in panels.items():
            denominator = float(weights@be[idx])
            assert denominator > 0
            constraints[counter,p+idx] = weights/denominator
            constraints[counter,-1] = -1
            panel_info.append((name,baseline,denominator))
            counter += 1
    other_rhs = [0.]*counter
    target = np.tile(center,b)
    for j in range(p):
        constraints[counter,j],constraints[counter,p+n+j] = 1,-1
        other_rhs.append(target[j]);counter += 1
        constraints[counter,j],constraints[counter,p+n+j] = -1,-1
        other_rhs.append(-target[j]);counter += 1
    for corner in range(b):
        constraints[counter,p+n+corner*k:p+n+(corner+1)*k] = 1
        other_rhs.append(.5);counter += 1
    a = sparse.vstack([a,constraints.tocsr()],format="csr")
    rhs = np.concatenate(rhs+[np.asarray(other_rhs)])
    eq = sparse.lil_matrix((b,size))
    for corner in range(b):eq[corner,corner*k:(corner+1)*k] = 1
    bounds = [(0,1)]*p+[(0,None)]*n+[(0,None)]*p+[(0,None)]
    cost = np.zeros(size);cost[-1] = 1
    first = lp(cost,A_ub=a,b_ub=rhs,A_eq=eq.tocsr(),b_eq=np.ones(b),bounds=bounds)
    assert first.success,first.message
    second_cost = np.zeros(size)
    idx,weights = panels["group_pooled"]
    second_cost[p+idx] = weights
    bounds[-1] = (0,float(first.x[-1])+1e-7)
    second = lp(second_cost,A_ub=a,b_ub=rhs,A_eq=eq.tocsr(),b_eq=np.ones(b),bounds=bounds)
    assert second.success,second.message
    corners = second.x[:p].reshape(b,k)
    assert corners.min() >= -1e-8
    np.testing.assert_allclose(corners.sum(axis=1),1,atol=1e-8)
    distances = np.abs(corners-center).sum(axis=1)
    assert distances.max() <= .5+2e-6
    model = {"variant":variant,"re_endpoints":list(map(float,endpoints)),"corner_weights":corners.tolist(),
             "center_weights":center.tolist(),"components":COMPONENTS,"corner_l1_distances":distances.tolist()}
    pred = predict(model,frame[COMPONENTS].to_numpy(),frame.Re.to_numpy(),frame.alpha.to_numpy())*1e4
    np.testing.assert_allclose(pred,x@second.x[:p],atol=1e-9,rtol=1e-12)
    error = np.abs(pred-y)
    scores=[]
    for name,baseline,denominator in panel_info:
        idx,weights=panels[name]
        scores.append({"panel":name,"baseline":baseline,"actual_ratio":float(weights@error[idx]/denominator)})
    actual=max(s["actual_ratio"] for s in scores)
    violation=float(np.max(a@second.x-rhs))
    assert actual <= first.x[-1]+1e-7+2e-6 and actual >= first.x[-1]-2e-6
    assert violation < 2e-6
    model.update(first_optimal_ratio=float(first.x[-1]),actual_worst_training_ratio=actual,
                 maximum_lp_constraint_violation=violation,training_panels=scores,
                 seconds=time.monotonic()-start,solver_iterations=[int(first.nit),int(second.nit)])
    return model


def fit_one(name,variants=VARIANTS):
    manifest=json.loads((HERE/"manifest.json").read_text())
    assert all(sha(p)==digest for p,digest in manifest["helper_sha256"].items())
    frame,enclosing,hashes=prior.load_training(name)
    centerpath=POSITIVE/"historical_results"/f"weights_{name}.json"
    centerfile=json.loads(centerpath.read_text())
    assert hashes==centerfile["input_sha256"]
    assert set(frame.loc[frame.context=="group","nf2_row_id"])==set(centerfile["training_nf2_row_ids"])
    metadata=prior.v2.load_data()
    ids=frame.historical_index.to_numpy()
    frame["Re"],frame["alpha"]=metadata["Re"][ids],metadata["alpha"][ids]
    endpoints=np.quantile(np.log10(frame.loc[frame.context=="group","Re"]),[.05,.95])
    center=np.asarray([centerfile["solutions"]["primary_both"]["weights"][c] for c in COMPONENTS])
    panel_map=prior.training_panels(frame)
    records=[]
    for variant in variants:
        output=OUT/f"{name}_{variant}.json"
        if output.exists():
            records.append({"split":name,"variant":variant,"status":"preserved_existing"});continue
        model=fit_variant(frame,panel_map,center,variant,endpoints)
        model.update(split=name,training_nf2_row_ids=centerfile["training_nf2_row_ids"],training_groups=centerfile["training_groups"],
                     input_sha256=hashes,center_file_sha256=sha(centerpath),prediction_context_rows=len(frame),unique_training_rows=len(enclosing))
        output.write_text(json.dumps(model,indent=2)+"\n")
        records.append({"split":name,"variant":variant,"ratio":model["actual_worst_training_ratio"],"seconds":model["seconds"]})
    return records


def evaluate():
    sys.path.insert(0,str(POSITIVE/"feasibility"))
    import solve_feasibility as f
    frame,components,hashes=f.load_inputs()
    assert set(components)==set(COMPONENTS)
    for variant in VARIANTS:frame[variant]=np.nan
    for split in frame.split.unique():
        external=split in ["SG_exposed","W_new_challenge"]
        ix=np.flatnonzero(frame.split==split);part=frame.iloc[ix]
        for variant in VARIANTS:
            model=json.loads((OUT/f"{'final' if external else split}_{variant}.json").read_text())
            if not external:
                assert not set(part.nf2_row_id)&set(model["training_nf2_row_ids"])
                assert not set(part.group)&set(model["training_groups"])
            gate=None
            if external:
                gate=part.inference_gate.map(lambda v:v is True or str(v).lower()=="true" or v==1).to_numpy(bool)
                assert gate.sum()=={"SG_exposed":234,"W_new_challenge":238}[split]
            pred=predict(model,part[COMPONENTS].to_numpy(),part.Re.to_numpy(),part.alpha.to_numpy(),part.mean8_CD.to_numpy(),gate)
            if external:np.testing.assert_array_equal(pred[~gate],part.mean8_CD.to_numpy()[~gate])
            frame.loc[ix,variant]=pred
    priorrows=pd.read_csv(POSITIVE/"historical_results/all_row_predictions.csv",low_memory=False)
    for col in ["input_file","input_row_index"]:np.testing.assert_array_equal(frame[col],priorrows[col])
    frame["global_stack"]=priorrows.primary_both.to_numpy()
    retros=json.loads((POSITIVE/"feasibility/blend_both.json").read_text())
    frame["retrospective_blend"]=frame[COMPONENTS].to_numpy()@np.asarray([retros["weights"][c] for c in COMPONENTS])
    labels=VARIANTS+["global_stack","cycle2_fixed__1","retrospective_blend"]
    panel_map=f.panels(frame)
    table=pd.concat([f.metrics(frame,frame[label].to_numpy(),panel_map,label) for label in labels],ignore_index=True)
    eligible={}
    gate=frame.inference_gate.map(lambda v:v is True or str(v).lower()=="true" or v==1).to_numpy(bool)
    for name,ix in panel_map.items():
        if name.startswith(("SG_exposed","W_new_challenge")):eligible[name+"_eligible"]=ix[gate[ix]]
    assert len(eligible)==8
    etable=pd.concat([f.metrics(frame,frame[label].to_numpy(),eligible,label) for label in labels],ignore_index=True)
    groups={f"{split}:{g}":np.flatnonzero((frame.split==split)&(frame.group==g)) for split in frame.split.unique()
            for g in sorted(frame.loc[frame.split==split,"group"].dropna().unique())}
    gtable=pd.concat([f.metrics(frame,frame[label].to_numpy(),groups,label) for label in labels],ignore_index=True)
    table.to_csv(OUT/"panel_metrics.csv",index=False);etable.to_csv(OUT/"eligible_external_metrics.csv",index=False)
    gtable.to_csv(OUT/"identity_group_metrics.csv",index=False)
    table.loc[(table.xlarge_CD_improvement_percent<0)|(table.mean8_CD_improvement_percent<0)].to_csv(OUT/"worsening_panels.csv",index=False)
    frame.to_csv(OUT/"all_row_predictions.csv",index=False)
    report={"status":"fixed_historical_training_only_variants_exploratory_outer_and_exposed_diagnostics","rows":len(frame),"input_sha256":hashes,
            "worst_allrow_percent":table.groupby("candidate")[["xlarge_CD_improvement_percent","mean8_CD_improvement_percent"]].min().to_dict(),
            "worst_eligible_external_percent":etable.groupby("candidate")[["xlarge_CD_improvement_percent","mean8_CD_improvement_percent"]].min().to_dict()}
    (OUT/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--pilot",action="store_true");args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    names=[p.stem.replace("weights_","",1) for p in sorted((POSITIVE/"historical_results").glob("weights_*.json"))]
    assert len(names)==16
    manifest=HERE/"manifest.json"
    if not manifest.exists():
        helpers=[POSITIVE/"historical_stack.py",POSITIVE/"feasibility/solve_feasibility.py",Path(prior.v2.__file__),Path(prior.v2.old.__file__)]
        manifest.write_text(json.dumps({"variants":VARIANTS,"source_sha256":sha(__file__),"protocol_sha256":sha(HERE/"PROTOCOL.md"),
            "helper_sha256":{str(p):sha(p) for p in helpers},"names":names,"workers":2,"highs_threads":1},indent=2)+"\n")
    assert sha(__file__)==json.loads(manifest.read_text())["source_sha256"]
    if args.pilot:
        print(json.dumps(fit_one("group_20260906_fold_0",["re2"])),flush=True);return
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(fit_one,name) for name in names]):print(json.dumps(future.result()),flush=True)
    evaluate()


if __name__=="__main__":main()
