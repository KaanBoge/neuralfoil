"""Cycle 2 declared model comparison. All writes stay in this cycle's directory."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent/"model_development_20260906"
sys.path.insert(0,str(OLD))
import develop_drag as old

FAMILIES = ["prior9_log","gb16_log","gb16_relative","hist24_relative","hist24_relative_mixed","hist24_additive"]
STRENGTHS = [0.5,1.0]
F16 = ["alpha","lre","t2","tx2","c2","cx2","leR","teA","lcd8","cl8","lsp","conf","topxtr","botxtr","dsize","cm8"]
F24 = F16+["abs_alpha","cl8_squared","min_xtr","max_xtr","xtr_difference","relative_drag_spread","median_relative_drag","lift_std_sizes"]


def add_features(d):
    x = d["X16"]
    cd,cl = d["all_model_CD"],d["all_model_CL"]
    extra = np.column_stack([np.abs(x[:,0]),x[:,9]**2,np.minimum(x[:,12],x[:,13]),np.maximum(x[:,12],x[:,13]),
        x[:,12]-x[:,13],(np.percentile(cd,90,axis=1)-np.percentile(cd,10,axis=1))/d["BASE_CD"],
        np.median(cd,axis=1)/d["BASE_CD"]-1,np.std(cl,axis=1)])
    d["X24"] = np.column_stack([x,extra])
    assert np.isfinite(d["X24"]).all()
    return d


def load_data():
    return add_features(old.load_data(OLD/"reproduction/dataset_occurrence.npz",OLD/"methods_audit/entry_group_map.csv",OLD/"methods_audit/ambiguous_nf2_row_ids.csv")[0])


def feature_key(family):
    return "X9" if family=="prior9_log" else ("X24" if family.startswith("hist") else "X16")


def target_kind(family):
    return "log" if family.endswith("log") else ("additive" if family.endswith("additive") else "relative")


def fit(family,d,idx):
    x = d[feature_key(family)][idx]
    base,meas = d["BASE_CD"][idx],d["MEAS_CD"][idx]
    weights = old.balanced_weights(d["group"][idx],d["source"][idx])
    if family.endswith("mixed"): weights = (1+weights)/2
    kind = target_kind(family)
    if kind=="log": target = d["yCD"][idx]
    elif kind=="relative":
        target = np.clip((meas-base)/base,-0.5,1.0)
        weights *= base
    else: target = (meas-base)*1e4
    weights /= weights.mean()
    if family.startswith("hist"):
        model = HistGradientBoostingRegressor(loss="absolute_error",max_iter=200,max_leaf_nodes=15,min_samples_leaf=80,
            learning_rate=0.05,l2_regularization=1.0,early_stopping=False,categorical_features=None,random_state=824)
    else:
        model = GradientBoostingRegressor(loss="absolute_error",n_estimators=150,max_depth=2,min_samples_leaf=80,
            learning_rate=0.06,subsample=0.7,random_state=824)
    return model.fit(x,target,sample_weight=weights)


def correct(kind,raw,base,strength):
    if kind=="log": return base*np.exp(np.clip(strength*raw,np.log(.5),np.log(2)))
    if kind=="relative": return base*(1+np.clip(strength*raw,-.5,1.0))
    return np.clip(base+strength*raw/1e4,.5*base,2*base)


def select(d,idx):
    folds = old.group_folds(d["group"][idx],3,20260907)
    logs = [{"family":"identity","strength":0.0,"worst_ratio":1.0,"ratios":{"overall":1.0},"guard_pass":True}]
    pooled = minimax = ("identity",0.0)
    p_score = m_score = 1.0
    for family in FAMILIES:
        raw = np.full(len(idx),np.nan)
        for te in folds:
            tridx,teidx = idx[~te],idx[te]
            assert not set(d["group"][tridx])&set(d["group"][teidx])
            model = fit(family,d,tridx)
            raw[te] = model.predict(d[feature_key(family)][teidx])
        assert np.isfinite(raw).all()
        for strength in STRENGTHS:
            pred = correct(target_kind(family),raw,d["BASE_CD"][idx],strength)
            worst,ratios = old.score_candidate(pred,d,idx)
            guard = all(v<1 for key,v in ratios.items() if key!="overall")
            logs.append({"family":family,"strength":strength,"worst_ratio":worst,"ratios":ratios,"guard_pass":guard})
            if guard and ratios["overall"]<p_score-1e-12:
                pooled,p_score = (family,strength),ratios["overall"]
            if worst<m_score-1e-12:
                minimax,m_score = (family,strength),worst
    return pooled,minimax,logs


def label(choice):
    return "identity" if choice[0]=="identity" else f"{choice[0]}_{choice[1]:g}"


def evaluate(task):
    name,d,tr,te = task
    start = time.monotonic()
    assert not set(d["group"][tr])&set(d["group"][te])
    pooled,minimax,logs = select(d,tr)
    preds = {"identity":d["BASE_CD"][te].copy()}
    for family in FAMILIES:
        model = fit(family,d,tr)
        raw = model.predict(d[feature_key(family)][te])
        for strength in STRENGTHS:
            preds[f"{family}_{strength:g}"] = correct(target_kind(family),raw,d["BASE_CD"][te],strength)
    preds["guarded_pooled"] = preds[label(pooled)]
    preds["minimax"] = preds[label(minimax)]
    return {"name":name,"train_rows":len(tr),"test_rows":len(te),"train_groups":len(set(d["group"][tr])),
        "test_groups":len(set(d["group"][te])),"overlap_groups":0,"guarded_pooled":pooled,"minimax":minimax,
        "inner_scores":logs,"test_indices":te,"predictions":preds,"seconds":time.monotonic()-start}


def portable_predict(artifact,d):
    base = d["BASE_CD"]
    if artifact["family"]=="identity": return base.copy()
    x = np.asarray(d[artifact["feature_key"]],dtype=np.float64 if artifact["engine"]=="hist" else np.float32)
    assert np.isfinite(x).all()
    raw = np.full(len(x),artifact["b0"])
    for tree in artifact["trees"]:
        for i,row in enumerate(x):
            node = 0
            while not tree["leaf"][node]:
                f = tree["feature"][node]
                node = tree["left"][node] if float(row[f])<=tree["threshold"][node] else tree["right"][node]
            raw[i] += artifact["tree_scale"]*tree["value"][node]
    return correct(artifact["target_kind"],raw,base,artifact["strength"])


def export(choice,model,d,out):
    family,strength = choice
    artifact = {"family":family,"strength":strength,"status":"experimental_not_deployed",
        "domain":{"mach":0.0,"n_crit":9,"transition":"free","configuration":"clean","Re_positive_max":600000,
                  "abs_alpha_max":12,"thickness_ratio_min_max":[.05,.2]},
        "outside_domain":"mean8 fallback; eligibility is not a guarantee", "neuralfoil":"0.3.3","aerosandbox":"4.2.10"}
    if family!="identity":
        engine = "hist" if family.startswith("hist") else "classic"
        artifact.update(engine=engine,feature_key=feature_key(family),target_kind=target_kind(family),
            features=d[feature_key(family)].shape[1],feature_names=F24 if engine=="hist" else (F16 if family!="prior9_log" else ["alpha","lre","t2","c2","lcd8","cl8","lsp","topxtr","botxtr"]),
            input_dtype="float64" if engine=="hist" else "float32")
        if engine=="hist":
            artifact["b0"] = float(model._baseline_prediction[0,0])
            artifact["tree_scale"] = 1.0 # Histogram predictor node values include learning rate.
            trees = []
            for iteration in model._predictors:
                assert len(iteration)==1
                nodes = iteration[0].nodes
                assert not nodes["is_categorical"].any()
                trees.append({"feature":nodes["feature_idx"].tolist(),"threshold":nodes["num_threshold"].tolist(),
                    "left":nodes["left"].tolist(),"right":nodes["right"].tolist(),"leaf":nodes["is_leaf"].astype(bool).tolist(),"value":nodes["value"].tolist()})
            artifact["trees"] = trees
        else:
            artifact["b0"] = float(model.init_.constant_[0,0])
            artifact["tree_scale"] = float(model.learning_rate)
            artifact["trees"] = [{"feature":e.tree_.feature.tolist(),"threshold":e.tree_.threshold.tolist(),"left":e.tree_.children_left.tolist(),
                "right":e.tree_.children_right.tolist(),"leaf":(e.tree_.feature<0).tolist(),"value":e.tree_.value[:,0,0].tolist()} for e in model.estimators_[:,0]]
    staged = out/"candidate_unverified.json"
    old.dump(staged,artifact)
    loaded = json.loads(staged.read_text())
    expected = d["BASE_CD"].copy() if family=="identity" else correct(target_kind(family),model.predict(d[feature_key(family)]),d["BASE_CD"],strength)
    actual = portable_predict(loaded,d)
    delta = float(np.max(np.abs(actual-expected)))
    assert delta<1e-12,delta
    staged.replace(out/"candidate.json")
    np.savez_compressed(out/"inference_references.npz",X9=d["X9"],X16=d["X16"],X24=d["X24"],BASE_CD=d["BASE_CD"],expected_CD=expected)
    return {"rows":len(actual),"max_absolute_CD_difference":delta,"artifact_sha256":old.digest(out/"candidate.json"),"references_sha256":old.digest(out/"inference_references.npz")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers",type=int,default=3)
    args = ap.parse_args()
    out = ROOT/"results"
    out.mkdir(exist_ok=True)
    assert not (out/"results.json").exists(),"Preserve completed experiment"
    d = load_data()
    paths = [Path(__file__),ROOT/"PROTOCOL.md",OLD/"develop_drag.py",OLD/"reproduction/dataset_occurrence.npz",
             OLD/"methods_audit/entry_group_map.csv",OLD/"methods_audit/ambiguous_nf2_row_ids.csv"]
    manifest = {"started_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"hashes":{str(p):old.digest(p) for p in paths},
        "python":platform.python_version(),"numpy":np.__version__,"sklearn":sklearn.__version__,"rows":len(d["yCD"]),"groups":len(set(d["group"])),
        "historical_data_only":True,"SG605x_status":"exposed regression check; excluded from fitting and selection"}
    old.dump(out/"run_manifest.json",manifest)
    ids = np.arange(len(d["yCD"]))
    tasks = []
    for seed in [20260906,20260908]:
        for i,te in enumerate(old.group_folds(d["group"],5,seed)):
            tasks.append((f"group_{seed}_fold_{i}",d,ids[~te],ids[te]))
    holds = [(s,d["source"]==s) for s in sorted(set(d["source"]))]+[("all_uiuc_volumes",d["source"]!="stec8")]
    for s,te in holds:
        tr = ~te&~np.isin(d["group"],list(set(d["group"][te])))
        tasks.append((f"strict_source_{s}",d,ids[tr],ids[te]))
    frames,logs = [],[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        future = [pool.submit(evaluate,t) for t in tasks]
        for f in as_completed(future):
            r = f.result()
            te,preds = r.pop("test_indices"),r.pop("predictions")
            frame = pd.DataFrame({"split":r["name"],"nf2_row_id":d["nf2_row_id"][te],"group":d["group"][te],"source":d["source"][te],
                "entry":d["entry"][te],"Re":d["Re"][te],"alpha":d["alpha"][te],"measured_CD":d["MEAS_CD"][te],"mean8_CD":d["BASE_CD"][te],
                "xlarge_CD":d["XLARGE_CD"][te],**preds})
            previous = pd.read_csv(OLD/"verified_results"/f"predictions_{r['name']}.csv")
            merged = frame.merge(previous[["nf2_row_id","nested_selector"]],on="nf2_row_id",validate="one_to_one",how="left")
            assert len(merged)==len(frame) and merged.nested_selector.notna().all()
            merged.rename(columns={"nested_selector":"cycle1_nested"},inplace=True)
            merged.to_csv(out/f"predictions_{r['name']}.csv",index=False)
            frames.append(merged)
            logs.append(r)
            old.dump(out/"split_log.json",sorted(logs,key=lambda v:v["name"]))
            print(json.dumps({"finished":r["name"],"primary":r["guarded_pooled"],"minimax":r["minimax"],"seconds":round(r["seconds"],1)}),flush=True)
    allpred = pd.concat(frames,ignore_index=True)
    labels = ["group_20260906","group_20260908"]+[f"strict_source_{s}" for s,_ in holds]
    summaries = []
    prednames = ["identity","cycle1_nested","guarded_pooled","minimax"]+[f"{f}_{s:g}" for f in FAMILIES for s in STRENGTHS]
    for name in labels:
        frame = allpred[allpred.split.str.startswith(name)]
        assert not frame.nf2_row_id.duplicated().any()
        for predname in prednames:
            for base in ["xlarge_CD","mean8_CD"]:
                metric = old.metrics(frame.measured_CD.to_numpy(),frame[predname].to_numpy(),frame[base].to_numpy(),frame.group.to_numpy(),bootstrap=predname in ["guarded_pooled","minimax"])
                summaries.append({"evaluation":name,"candidate":predname,"baseline":base,**metric})
    primary = allpred[allpred.split.str.startswith("group_20260906")]
    primary.to_csv(out/"primary_oof.csv",index=False)
    strata = []
    masks = [(f"source_{s}",primary.source==s) for s in sorted(primary.source.unique())]
    masks += [(f"Re_{lo}_{hi}",(primary.Re>=lo)&(primary.Re<hi)) for lo,hi in [(0,75000),(75000,150000),(150000,250000),(250000,600001)]]
    for name,mask in masks:
        f = primary[mask]
        strata.append({"stratum":name,**old.metrics(f.measured_CD.to_numpy(),f.guarded_pooled.to_numpy(),f.xlarge_CD.to_numpy(),f.group.to_numpy())})
    print("Selecting final candidate using historical inner validation only",flush=True)
    chosen,second,selection = select(d,ids)
    model = None if chosen[0]=="identity" else fit(chosen[0],d,ids)
    parity = export(chosen,model,d,out)
    for path,expected in manifest["hashes"].items(): assert old.digest(path)==expected,path
    freeze = {"frozen_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"selected":chosen,"secondary_minimax":second,
        "selection_scores":selection,"parity":parity,"training_manifest_sha256":old.digest(out/"run_manifest.json"),
        "SG605x_scored_in_cycle2":False,"new_challenge_scored":False,"not_deployed":True}
    old.dump(out/"freeze.json",freeze)
    old.dump(out/"results.json",{"manifest":manifest,"summaries":summaries,"strata":strata,"freeze":freeze})
    pd.DataFrame([{k:v for k,v in x.items() if not isinstance(v,dict)} for x in summaries]).to_csv(out/"metric_summary.csv",index=False)
    print(json.dumps({"done":True,"chosen":chosen,"parity":parity}),flush=True)


if __name__=="__main__":main()
