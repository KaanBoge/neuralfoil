"""Frozen nested kernel check with archive-matched controls; no old writes."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import pickle
import sys
import time
import traceback
import numpy as np
import pandas as pd
import sklearn
import kernel_models as models

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
C3 = PROJECT / "model_development_20260907_search"
C4 = PROJECT / "model_development_20260907_transition"
sys.path.insert(0, str(C4))
import shape_inputs as inputs
v2 = inputs.transition.v2
OUT = ROOT / "results"
CONTROLS = ["identity", "xlarge_fixed", "cycle2_fixed__1", "gate_shrink__1"]
LABELS = CONTROLS + [f"{family}__{s:g}" for family in models.FAMILIES for s in [.5, 1.]]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def new_predictions(d, tr, te):
    assert len(tr) and len(te) and not set(d["group"][tr]) & set(d["group"][te])
    preds, durations = {}, {}
    for family in models.FAMILIES:
        tick = time.monotonic()
        model = models.fit(family, d, tr)
        full = models.predict(model, d, te)
        assert full.shape == (len(te),) and np.isfinite(full).all()
        for strength in [.5, 1.]:
            preds[f"{family}__{strength:g}"] = d["BASE_CD"][te] + strength * (full - d["BASE_CD"][te])
        durations[family] = time.monotonic() - tick
    return preds, durations


def archived_controls(path, expected_idx, expected_train=None):
    with np.load(path, allow_pickle=False) as archive:
        key = "indices" if expected_train is None else "test_indices"
        np.testing.assert_array_equal(archive[key], expected_idx)
        if expected_train is not None:
            np.testing.assert_array_equal(archive["train_indices"], expected_train)
        return {label: archive[label].copy() for label in CONTROLS}


def group_ratios(d, idx, pred):
    errors = np.abs(pred - d["MEAS_CD"][idx])
    ratios = {}
    for baseline, key in [("mean8", "BASE_CD"), ("xlarge", "XLARGE_CD")]:
        be = np.abs(d[key][idx] - d["MEAS_CD"][idx])
        assert be.sum() > 0
        ratios[f"{baseline}:pooled"] = float(errors.sum() / be.sum())
        for source in sorted(set(d["source"][idx])):
            mask = d["source"][idx] == source
            assert be[mask].sum() > 0
            ratios[f"{baseline}:source_{source}"] = float(errors[mask].sum() / be[mask].sum())
        frame = pd.DataFrame({"group": d["group"][idx], "error": errors, "base": be})
        means = frame.groupby("group")[["error", "base"]].mean()
        ratios[f"{baseline}:equal_group"] = float(means.error.mean() / means.base.mean())
    return ratios


def select(d, idx, prefix):
    controls = archived_controls(C3 / "results" / f"{prefix}_inner_group.npz", idx)
    oof = {**controls, **{label: np.full(len(idx), np.nan) for label in LABELS if label not in CONTROLS}}
    logs, transfers = [], {label: {} for label in LABELS}
    for number, test in enumerate(v2.old.group_folds(d["group"][idx], 3, 20260907)):
        pred, timing = new_predictions(d, idx[~test], idx[test])
        for label, values in pred.items():
            oof[label][test] = values
        logs.append({"kind": "group", "fold": number, "train_rows": int((~test).sum()), "test_rows": int(test.sum()), "seconds": timing})
    assert all(np.isfinite(values).all() for values in oof.values())
    np.savez_compressed(OUT / f"{prefix}_inner_group.npz", indices=idx, **oof)
    for source in sorted(set(d["source"][idx])):
        test = d["source"][idx] == source
        train = ~test & ~np.isin(d["group"][idx], d["group"][idx[test]])
        if len(set(d["group"][idx[train]])) < 6 or train.sum() < 300:
            logs.append({"kind": "source", "source": source, "status": "insufficient_training_support", "train_rows": int(train.sum())})
            continue
        pr = archived_controls(C3 / "results" / f"{prefix}_inner_transfer_{source}.npz", idx[test], idx[train])
        new, timing = new_predictions(d, idx[train], idx[test])
        pr.update(new)
        for baseline, key in [("mean8", "BASE_CD"), ("xlarge", "XLARGE_CD")]:
            denominator = np.abs(d[key][idx[test]] - d["MEAS_CD"][idx[test]]).sum()
            assert denominator > 0
            for label in LABELS:
                transfers[label][f"{baseline}:transfer_{source}"] = float(np.abs(pr[label] - d["MEAS_CD"][idx[test]]).sum() / denominator)
        np.savez_compressed(OUT / f"{prefix}_inner_transfer_{source}.npz", train_indices=idx[train], test_indices=idx[test], **pr)
        logs.append({"kind": "source", "source": source, "status": "scored", "train_rows": int(train.sum()), "test_rows": int(test.sum()), "seconds": timing})
    records, chosen, best_worst, best_pooled = [], None, float("inf"), float("inf")
    for label in LABELS:
        ratios = {**group_ratios(d, idx, oof[label]), **transfers[label]}
        worst = max(ratios.values())
        pooled = (ratios["mean8:pooled"] + ratios["xlarge:pooled"]) / 2
        records.append({"candidate": label, "worst_ratio": worst, "pooled_tiebreak": pooled,
                        "passes_both_baselines": worst < 1., "ratios": ratios})
        if worst < best_worst - 1e-12 or (abs(worst - best_worst) <= 1e-12 and pooled < best_pooled - 1e-12):
            chosen, best_worst, best_pooled = label, worst, pooled
    return chosen, {"candidate_scores": records, "fits": logs, "selected_worst_ratio": best_worst, "selected_guard_pass": best_worst < 1.}


def evaluate(task):
    name, d, tr, te = task
    tick = time.monotonic()
    chosen, selection = select(d, tr, name)
    new, timing = new_predictions(d, tr, te)
    previous = pd.read_csv(C3 / "results" / f"predictions_{name}.csv")
    np.testing.assert_array_equal(previous.nf2_row_id.to_numpy(), d["nf2_row_id"][te])
    keys = ["split", "nf2_row_id", "group", "source", "entry", "Re", "alpha", "measured_CD", "mean8_CD", "xlarge_CD"] + CONTROLS
    frame = previous[keys].copy()
    for label, values in new.items():
        frame[label] = values
    frame["both_minimax_selector"] = frame[chosen]
    frame.to_csv(OUT / f"predictions_{name}.csv", index=False)
    result = {"split": name, "train_rows": len(tr), "test_rows": len(te), "group_overlap": 0,
              "selected": chosen, "selection": selection, "outer_seconds": timing, "seconds": time.monotonic() - tick}
    dump(OUT / f"log_{name}.json", result)
    return result


def summarize():
    allpred = pd.concat([pd.read_csv(path) for path in sorted(OUT.glob("predictions_*.csv"))], ignore_index=True)
    summaries = []
    names = ["group_20260906", "group_20260908"] + [f"strict_source_{source}" for source in ["stec8", "vol1", "vol2", "vol3", "all_uiuc_volumes"]]
    for name in names:
        f = allpred[allpred.split.str.startswith(name)]
        assert not f.nf2_row_id.duplicated().any()
        for label in LABELS + ["both_minimax_selector"]:
            for base in ["xlarge_CD", "mean8_CD"]:
                metric = v2.old.metrics(f.measured_CD.to_numpy(), f[label].to_numpy(), f[base].to_numpy(), f.group.to_numpy())
                summaries.append({"evaluation": name, "candidate": label, "baseline": base, **metric})
    pd.DataFrame(summaries).to_csv(OUT / "metric_summary.csv", index=False)
    return summaries


def exposed(models_fit, chosen):
    out = ROOT / "exposed_results"
    out.mkdir(exist_ok=True)
    rows = []
    for name in ["SG_exposed", "W_new_challenge"]:
        d = inputs.load_exposed(name)
        frame = pd.read_csv(C3 / "exposed_results" / f"{name}_predictions.csv")
        np.testing.assert_array_equal(frame.alpha.to_numpy(), d["alpha"])
        np.testing.assert_array_equal(frame.Re.to_numpy(), d["Re"])
        gate = frame.inference_gate.to_numpy(dtype=bool)
        base, idx = d["BASE_CD"], np.arange(len(frame))
        for family, model in models_fit.items():
            raw = models.predict(model, d, idx)
            for strength in [.5, 1.]:
                frame[f"{family}__{strength:g}"] = np.where(gate, base + strength * (raw - base), base)
        frame["both_minimax_selector"] = np.where(gate, frame[chosen], base)
        frame.to_csv(out / f"{name}_predictions.csv", index=False)
        for population, mask in [("all_complete", np.ones(len(frame), dtype=bool)), ("eligible", frame.eligible.to_numpy(dtype=bool))]:
            part = frame[mask]
            panels = [("pooled", part)] + [(f"airfoil_{a}", part[part.airfoil == a]) for a in sorted(part.airfoil.unique())]
            panels += [(f"configuration_{c}", part[part.configuration == c]) for c in sorted(part.configuration.unique())]
            for panel, f in panels:
                for label in LABELS + ["both_minimax_selector"]:
                    for baseline in ["xlarge_CD", "mean8_CD"]:
                        rows.append({"cohort": name, "population": population, "panel": panel, "candidate": label, "baseline": baseline,
                                     **v2.old.metrics(f.measured_CD.to_numpy(), f[label].to_numpy(), f[baseline].to_numpy(), f.airfoil.to_numpy())})
    pd.DataFrame(rows).to_csv(out / "metric_summary.csv", index=False)
    dump(out / "results.json", {"selected": chosen, "status": "Previously exposed diagnostics; no external fitting", "metrics": rows})


def main():
    OUT.mkdir(exist_ok=True)
    assert not (OUT / "run_manifest.json").exists(), "Preserve all started/completed runs"
    d = inputs.load_historical()
    assert d["X62"].shape == (8371, 62) and len(set(d["group"])) == 93
    np.testing.assert_allclose(models.balanced_weights(d["group"], d["source"]), v2.old.balanced_weights(d["group"], d["source"]), rtol=0, atol=1e-13)
    paths = [ROOT / "pilot_manifest.json", Path(__file__), Path(models.__file__), ROOT / "PROTOCOL.md", Path(inputs.__file__), C4 / "transition_inputs.py", C4 / "shape_inputs/manifest.json", C4 / "inputs/manifest.json"]
    paths += [C4 / section / f"{name}.npz" for section in ["inputs", "shape_inputs"] for name in ["historical", "SG_exposed", "W_new_challenge"]]
    paths += list((C3 / "results").glob("*_inner_*.npz")) + list((C3 / "results").glob("predictions_*.csv"))
    paths += [C3 / "exposed_results" / f"{name}_predictions.csv" for name in ["SG_exposed", "W_new_challenge"]]
    hashes = {str(p): sha(p) for p in paths}
    manifest = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "hashes": hashes,
                "sklearn": sklearn.__version__, "numpy": np.__version__, "families": models.FAMILIES,
                "candidates": LABELS, "historical_rows": 8371, "groups": 93, "workers": 1,
                "status": "Adaptive fixed kernel exploration; all fitting and selection historical only"}
    dump(OUT / "run_manifest.json", manifest)
    ids = np.arange(len(d["BASE_CD"]))
    tasks = []
    for seed in [20260906, 20260908]:
        for fold, test in enumerate(v2.old.group_folds(d["group"], 5, seed)):
            tasks.append((f"group_{seed}_fold_{fold}", d, ids[~test], ids[test]))
    for source in sorted(set(d["source"])) + ["all_uiuc_volumes"]:
        test = d["source"] != "stec8" if source == "all_uiuc_volumes" else d["source"] == source
        train = ~test & ~np.isin(d["group"], d["group"][test])
        tasks.append((f"strict_source_{source}", d, ids[train], ids[test]))
    logs, failures = [], []
    with ProcessPoolExecutor(max_workers=1) as pool:
        jobs = {pool.submit(evaluate, task): task[0] for task in tasks}
        for job in as_completed(jobs):
            try:
                log = job.result()
                logs.append(log)
                print(json.dumps({"finished": log["split"], "selected": log["selected"], "inner_worst_ratio": log["selection"]["selected_worst_ratio"], "seconds": log["seconds"]}), flush=True)
            except Exception:
                failure = {"split": jobs[job], "traceback": traceback.format_exc()}
                failures.append(failure)
                dump(OUT / f"failure_{jobs[job]}.json", failure)
    if failures:
        dump(OUT / "incomplete.json", {"failures": failures, "completed": [r["split"] for r in logs]})
        raise RuntimeError("Preserved failures; do not claim completed evaluation")
    metrics = summarize()
    print("All outer evaluations finished; final historical-only selection", flush=True)
    chosen, selection = select(d, ids, "final")
    fitted, artifacts = {}, {}
    for family in models.FAMILIES:
        model = models.fit(family, d, ids)
        pred = models.predict(model, d, ids)
        path = OUT / f"fit_{family}.pkl"
        with path.open("wb") as f:
            pickle.dump(model, f, protocol=5)
        digest = sha(path)
        assert sha(path) == digest
        with path.open("rb") as f:
            reloaded = pickle.load(f)
        err = float(np.max(np.abs(models.predict(reloaded, d, ids) - pred)))
        assert err < 1e-12
        artifacts[family] = {"sha256": digest, "reload_max_abs_CD": err}
        fitted[family] = reloaded
    for path, expected in hashes.items():
        assert sha(path) == expected, path
    dump(OUT / "freeze.json", {"selected": chosen, "selection": selection, "artifacts": artifacts,
                               "status": "historical_only_fits; experimental_not_deployed", "external_scored_at_freeze": False})
    exposed(fitted, chosen)
    for path, expected in hashes.items():
        assert sha(path) == expected, path
    dump(OUT / "results.json", {"manifest": manifest, "selected": chosen, "folds": logs, "metrics": metrics, "failures": []})
    print(json.dumps({"complete": True, "selected": chosen, "artifacts": artifacts}), flush=True)


if __name__ == "__main__":
    main()

