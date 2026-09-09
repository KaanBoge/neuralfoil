"""Exploratory nested-group drag correction; immutable inputs, separate outputs.

Run using the project venv. See EXPERIMENT_PROTOCOL.md for prespecified choices.
Never imports or executes recovered scripts with output side effects.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import GradientBoostingRegressor

ROOT = Path(__file__).resolve().parent
FAMILIES = ["ridge_log", "gb_l1_log", "gb_l1_add", "gb_huber_add"]
STRENGTHS = [0.5, 1.0]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def group_folds(groups, k, seed):
    names = np.array(sorted(set(groups)))
    np.random.default_rng(seed).shuffle(names)
    return [np.isin(groups, names[i::k]) for i in range(k)]


def balanced_weights(groups, sources):
    # Each source has equal mass; within it each distinct group has equal mass.
    frame = pd.DataFrame({"group": groups, "source": sources})
    count = frame.groupby(["source", "group"])["source"].transform("size").to_numpy()
    ng = frame.groupby("source")["group"].transform("nunique").to_numpy()
    w = 1.0 / (count * ng)
    return w / w.mean()


def ridge_design16(x):
    a, lr, t, _, _, _, _, _, lcd, cl, lsp, conf, _, _, _, _ = x.T
    return np.column_stack([
        np.ones(len(x)), lr, lr**2, a, a**2, a**3, t, t**2,
        lcd, lsp, conf, cl, cl**2, lr*a, lr*t, a*t, lr*lcd,
        a*cl, lr*cl, lsp*lr, lcd*a,
    ])


def train(family, d, idx):
    x = d["X9"][idx]
    w = balanced_weights(d["group"][idx], d["source"][idx])
    if family == "ridge_log":
        x = ridge_design16(d["X16"][idx])
        mu = np.average(x, axis=0, weights=w)
        sd = np.sqrt(np.average((x-mu)**2, axis=0, weights=w))
        sd[sd == 0] = 1
        mu[0], sd[0] = 0, 1
        z = (x-mu)/sd
        reg = 0.03 * w.sum() * np.eye(z.shape[1])
        coef = np.linalg.solve(z.T @ (z*w[:, None]) + reg, z.T @ (d["yCD"][idx]*w))
        return {"mu": mu, "sd": sd, "coef": coef}
    target = d["yCD"][idx] if family.endswith("log") else (d["MEAS_CD"][idx]-d["BASE_CD"][idx])*1e4
    loss = "huber" if family == "gb_huber_add" else "absolute_error"
    model = GradientBoostingRegressor(
        loss=loss, alpha=0.9, n_estimators=150, learning_rate=0.06,
        max_depth=2, min_samples_leaf=80, subsample=0.7, random_state=824,
    )
    return model.fit(x, target, sample_weight=w)


def predict_residual(family, model, d, idx):
    if family == "ridge_log":
        x = (ridge_design16(d["X16"][idx])-model["mu"])/model["sd"]
        return x @ model["coef"]
    return model.predict(d["X9"][idx])


def correct(family, residual, base, strength):
    if family.endswith("log"):
        return base * np.exp(np.clip(strength*residual, np.log(0.5), np.log(2.0)))
    return np.clip(base+strength*residual/1e4, 0.5*base, 2.0*base)


def score_candidate(pred, d, idx):
    base = np.abs(d["BASE_CD"][idx]-d["MEAS_CD"][idx])
    error = np.abs(pred-d["MEAS_CD"][idx])
    ratios = {"overall": float(error.sum()/base.sum())}
    sources = d["source"][idx]
    for name in sorted(set(sources)):
        mask = sources == name
        ratios[f"source_{name}"] = float(error[mask].sum()/base[mask].sum())
    frame = pd.DataFrame({"group": d["group"][idx], "b": base, "e": error})
    means = frame.groupby("group")[["b", "e"]].mean()
    ratios["equal_group"] = float(means.e.mean()/means.b.mean())
    return max(ratios.values()), ratios


def select(d, idx):
    inner = group_folds(d["group"][idx], 3, 20260907)
    log = [{"family": "identity", "strength": 0.0, "worst_ratio": 1.0, "ratios": {"all": 1.0}}]
    best = ("identity", 0.0)
    best_score = 1.0
    for family in FAMILIES:
        residual = np.full(len(idx), np.nan)
        for te in inner:
            tr_idx, te_idx = idx[~te], idx[te]
            assert not set(d["group"][tr_idx]) & set(d["group"][te_idx])
            model = train(family, d, tr_idx)
            residual[te] = predict_residual(family, model, d, te_idx)
        assert np.isfinite(residual).all()
        for strength in STRENGTHS:
            pred = correct(family, residual, d["BASE_CD"][idx], strength)
            worst, ratios = score_candidate(pred, d, idx)
            log.append({"family": family, "strength": strength, "worst_ratio": worst, "ratios": ratios})
            if worst < best_score - 1e-12:
                best, best_score = (family, strength), worst
    return best, log


def evaluate_task(task):
    name, d, tr, te = task
    start = time.monotonic()
    overlap = set(d["group"][tr]) & set(d["group"][te])
    assert not overlap, (name, overlap)
    chosen, inner_log = select(d, tr)
    preds = {"identity": d["BASE_CD"][te].copy()}
    for family in FAMILIES:
        model = train(family, d, tr)
        resid = predict_residual(family, model, d, te)
        for strength in STRENGTHS:
            preds[f"{family}_{strength:g}"] = correct(family, resid, d["BASE_CD"][te], strength)
    key = "identity" if chosen[0] == "identity" else f"{chosen[0]}_{chosen[1]:g}"
    preds["nested_selector"] = preds[key]
    control = GradientBoostingRegressor(
        n_estimators=150, learning_rate=0.06, max_depth=2,
        min_samples_leaf=80, subsample=0.7, random_state=824,
    ).fit(d["X9"][tr], d["yCD"][tr])
    preds["recovered_squared_log_control"] = correct("control_log", control.predict(d["X9"][te]), d["BASE_CD"][te], 1.0)
    return {"name": name, "train_rows": len(tr), "test_rows": len(te),
            "train_groups": len(set(d["group"][tr])), "test_groups": len(set(d["group"][te])),
            "overlap_groups": 0, "selection": list(chosen), "inner_scores": inner_log,
            "seconds": time.monotonic()-start, "test_indices": te, "predictions": preds}


def metrics(y, pred, base, groups, bootstrap=False):
    e, b = np.abs(pred-y)*1e4, np.abs(base-y)*1e4
    frame = pd.DataFrame({"group": groups, "e": e, "b": b})
    agg = frame.groupby("group")[["e", "b"]].agg(["sum", "mean"])
    result = {
        "rows": len(y), "groups": len(agg), "baseline_mae_counts": float(b.mean()),
        "candidate_mae_counts": float(e.mean()), "relative_reduction_percent": float(100*(1-e.sum()/b.sum())),
        "candidate_median_counts": float(np.median(e)), "candidate_p90_counts": float(np.quantile(e, .9)),
        "baseline_median_counts": float(np.median(b)), "baseline_p90_counts": float(np.quantile(b, .9)),
        "worse_rows": int((e>b).sum()), "equal_rows": int((e==b).sum()),
        "worse_groups": int((agg[("e","mean")]>agg[("b","mean")]).sum()),
        "equal_group_relative_reduction_percent": float(100*(1-agg[("e","mean")].sum()/agg[("b","mean")].sum())),
    }
    if bootstrap:
        rng = np.random.default_rng(20260909)
        es, bs = agg[("e","sum")].to_numpy(), agg[("b","sum")].to_numpy()
        values = []
        for _ in range(20):
            draw = rng.integers(0, len(es), (1000, len(es)))
            values.extend(100*(1-es[draw].sum(axis=1)/bs[draw].sum(axis=1)))
        result["conditional_cluster_bootstrap"] = {
            "replicates": 20000, "two_sided_95_percent": np.quantile(values, [.025, .975]).tolist(),
            "one_sided_95_lower_percent": float(np.quantile(values, .05)),
            "warning": "Exploratory frozen-prediction interval; excludes retraining, adaptive development and facility systematics",
        }
    return result


def export_model(family, strength, model, d, out):
    artifact = {"family": family, "strength": strength, "status": "experimental_not_deployed",
                "domain": {"Re_max": 600000, "abs_alpha_max": 12, "thickness_range": [.05,.2], "configuration": "clean"},
                "outside_domain": "use uncorrected mean8; no accuracy guarantee",
                "features9": ["alpha","lre","t2","c2","lcd8","cl8","lsp","topxtr","botxtr"]}
    if family == "ridge_log":
        artifact.update({k: v.tolist() for k,v in model.items()})
    elif family != "identity":
        artifact["learning_rate"] = model.learning_rate
        artifact["b0"] = float(model.init_.constant_[0,0])
        artifact["trees"] = [
            {"feature": e.tree_.feature.tolist(), "threshold": e.tree_.threshold.tolist(),
             "left": e.tree_.children_left.tolist(), "right": e.tree_.children_right.tolist(),
             "value": e.tree_.value[:,0,0].tolist()} for e in model.estimators_[:,0]
        ]
    draft = out.with_name("candidate_unverified.json")
    dump(draft, artifact)
    # Serialize/reload JSON and compare all development rows, not just a sample.
    loaded = json.loads(draft.read_text())
    if family == "identity":
        reference = got = d["BASE_CD"].copy()
    else:
        reference = correct(family, predict_residual(family, model, d, np.arange(len(d["yCD"]))), d["BASE_CD"], strength)
        if family == "ridge_log":
            raw = ((ridge_design16(d["X16"])-np.array(loaded["mu"]))/np.array(loaded["sd"])) @ np.array(loaded["coef"])
        else:
            # sklearn tree inference casts inputs to float32; mirror that exactly.
            x = d["X9"].astype(np.float32)
            raw = np.full(len(x), loaded["b0"])
            for tree in loaded["trees"]:
                for i,row in enumerate(x):
                    node = 0
                    while tree["feature"][node] >= 0:
                        f = tree["feature"][node]
                        node = tree["left"][node] if float(row[f]) <= tree["threshold"][node] else tree["right"][node]
                    raw[i] += loaded["learning_rate"]*tree["value"][node]
        got = correct(family, raw, d["BASE_CD"], strength)
    delta = float(np.max(np.abs(got-reference)))
    assert delta < 1e-12, delta
    draft.replace(out)
    return {"checked_rows": len(got), "max_absolute_CD_difference": delta, "sha256": digest(out)}


def load_data(dataset, groupmap, exclusions):
    with np.load(dataset, allow_pickle=False) as archive:
        d = {key: archive[key] for key in archive.files}
    if "source" not in d: d["source"] = d["src"]
    if "nf2_row_id" not in d: raise ValueError("Stable nf2_row_id required")
    mapping = pd.read_csv(groupmap)
    if not {"entry", "group_id"} <= set(mapping): raise ValueError(f"Unexpected groupmap schema {list(mapping)}")
    lookup = dict(zip(mapping.entry, mapping.group_id))
    entries = np.char.add(np.char.add(d["source"].astype(str), "|"), d["af"].astype(str))
    d["entry"] = entries
    d["group"] = np.array([lookup[e] for e in entries], dtype=str)
    excluded = pd.read_csv(exclusions)
    drop = set(excluded.nf2_row_id)
    keep = ~np.isin(d["nf2_row_id"], list(drop))
    before = len(keep)
    # Retain only row-aligned arrays; feature names/scalar metadata stay in original archive.
    d = {key: val[keep] for key,val in d.items() if val.ndim and len(val)==before}
    for key in ("X9", "X16", "yCD", "MEAS_CD", "BASE_CD", "XLARGE_CD"):
        assert np.isfinite(d[key]).all(), key
    return d, {"occurrence_domain_rows": before, "ambiguous_rows_excluded": int((~keep).sum()), "development_rows": int(keep.sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--groups", type=Path, required=True)
    ap.add_argument("--exclusions", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--repeat", action="store_true")
    ap.add_argument("--output-name", default="development_results")
    args = ap.parse_args()
    if Path(args.output_name).name != args.output_name:
        raise ValueError("Output name must be one directory name")
    out = ROOT / args.output_name
    out.mkdir(exist_ok=True)
    if (out/"results.json").exists(): raise FileExistsError("Completed results exist; preserve them and use a new experiment directory")
    d, cohort = load_data(args.dataset, args.groups, args.exclusions)
    manifest = {"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
                "scipy": scipy.__version__, "pandas": pd.__version__, "cohort": cohort,
                "hashes": {str(p): digest(p) for p in [Path(__file__), ROOT/"EXPERIMENT_PROTOCOL.md", args.dataset, args.groups, args.exclusions]},
                "claim_status": "internal_exploratory_not_universal"}
    dump(out/"run_manifest.json", manifest)
    tasks = []
    seeds = [20260906, 20260908] if args.repeat else [20260906]
    allidx = np.arange(len(d["yCD"]))
    for seed in seeds:
        for i,te in enumerate(group_folds(d["group"], 5, seed)):
            tasks.append((f"group_{seed}_fold_{i}", d, allidx[~te], allidx[te]))
    holds = [(s, d["source"]==s) for s in sorted(set(d["source"]))]
    holds += [("all_uiuc_volumes", d["source"]!="stec8")]
    for s,te in holds:
        tr = ~te & ~np.isin(d["group"], list(set(d["group"][te])))
        if tr.sum() and te.sum(): tasks.append((f"strict_source_{s}", d, allidx[tr], allidx[te]))
    result_rows, split_logs = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(evaluate_task, t): t[0] for t in tasks}
        for future in as_completed(futures):
            result = future.result()
            idx = result.pop("test_indices")
            preds = result.pop("predictions")
            split_logs.append(result)
            frame = pd.DataFrame({"split": result["name"], "row_index": idx, "nf2_row_id": d["nf2_row_id"][idx],
                                  "entry": d["entry"][idx], "group": d["group"][idx], "source": d["source"][idx],
                                  "Re": 10**d["X9"][idx,1], "alpha": d["X9"][idx,0],
                                  "measured_CD": d["MEAS_CD"][idx], "mean8_CD": d["BASE_CD"][idx], "xlarge_CD": d["XLARGE_CD"][idx], **preds})
            frame.to_csv(out/f"predictions_{result['name']}.csv", index=False)
            result_rows.append(frame)
            dump(out/"split_log.json", sorted(split_logs, key=lambda r:r["name"]))
            print(json.dumps({"finished": result["name"], "chosen": result["selection"], "seconds": round(result["seconds"],1), "test_rows": result["test_rows"]}), flush=True)
    allpred = pd.concat(result_rows, ignore_index=True)
    summaries = []
    pred_names = ["identity", "recovered_squared_log_control", "nested_selector"] + [f"{f}_{s:g}" for f in FAMILIES for s in STRENGTHS]
    evaluations = [(f"group_{seed}", allpred[allpred.split.str.startswith(f"group_{seed}_")]) for seed in seeds]
    evaluations += [(name, allpred[allpred.split==name]) for name in sorted(allpred.split.unique()) if name.startswith("strict_source_")]
    for label, frame in evaluations:
        assert not frame.nf2_row_id.duplicated().any()
        for predname in pred_names:
            for basename in ("mean8_CD", "xlarge_CD"):
                met = metrics(frame.measured_CD.to_numpy(), frame[predname].to_numpy(), frame[basename].to_numpy(), frame.group.to_numpy(), bootstrap=predname=="nested_selector")
                summaries.append({"evaluation": label, "candidate": predname, "baseline": basename, **met})
    # Prespecified source/Re diagnostics on primary nested OOF; no subsequent retuning.
    main_oof = evaluations[0][1]
    main_oof.to_csv(out/"primary_oof_predictions.csv", index=False)
    strata = []
    masks = [(f"source_{s}", main_oof.source==s) for s in sorted(main_oof.source.unique())]
    for lo,hi in [(0,75000),(75000,150000),(150000,250000),(250000,600001)]:
        masks.append((f"Re_{lo}_{hi}", (main_oof.Re>=lo)&(main_oof.Re<hi)))
    for name, mask in masks:
        f = main_oof[mask]
        if len(f): strata.append({"stratum": name, **metrics(f.measured_CD.to_numpy(), f.nested_selector.to_numpy(), f.xlarge_CD.to_numpy(), f.group.to_numpy())})
    print("Selecting final experimental candidate using development-only inner validation", flush=True)
    chosen, final_log = select(d, allidx)
    model = None if chosen[0]=="identity" else train(chosen[0], d, allidx)
    parity = export_model(*chosen, model, d, out/"frozen_candidate.json")
    freeze = {"frozen_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "selected": list(chosen), "inner_selection": final_log,
              "artifact_parity": parity, "training_data_sha256": digest(args.dataset), "protocol_sha256": digest(ROOT/"EXPERIMENT_PROTOCOL.md"),
              "external_outcomes_scored": False, "not_deployed": True}
    for path, expected in manifest["hashes"].items():
        assert digest(path) == expected, f"Input/code changed during run: {path}"
    dump(out/"candidate_freeze.json", freeze)
    dump(out/"results.json", {"manifest": manifest, "summaries": summaries, "strata": strata, "freeze": freeze})
    pd.DataFrame([{k:v for k,v in row.items() if not isinstance(v,dict)} for row in summaries]).to_csv(out/"metric_summary.csv", index=False)
    print(json.dumps({"completed": True, "selected": chosen, "artifact": str(out/"frozen_candidate.json")}), flush=True)


if __name__ == "__main__":
    main()
