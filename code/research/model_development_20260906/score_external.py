"""One-shot exploratory SG605x challenge; no fitting on external outcomes."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "reproduction"))
from reproduce_doubleclean import load_pts, foil_stats2, build_context, SIZES
import develop_drag as dev


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_candidate(artifact, x9, x16, base):
    family, strength = artifact["family"], artifact["strength"]
    if family == "identity": return base.copy()
    if family == "ridge_log":
        raw = ((dev.ridge_design16(x16)-np.array(artifact["mu"]))/np.array(artifact["sd"])) @ np.array(artifact["coef"])
    else:
        x = np.asarray(x9, dtype=np.float32)
        raw = np.full(len(x), artifact["b0"])
        for tree in artifact["trees"]:
            for i, row in enumerate(x):
                node = 0
                while tree["feature"][node] >= 0:
                    f = tree["feature"][node]
                    node = tree["left"][node] if float(row[f]) <= tree["threshold"][node] else tree["right"][node]
                raw[i] += artifact["learning_rate"]*tree["value"][node]
    return dev.correct(family, raw, np.asarray(base), strength)


def portability_references():
    """Run with project venv: independent JSON reader vs freshly refit frozen family."""
    out = ROOT/"verified_results"
    frozen = json.loads((out/"candidate_freeze.json").read_text())
    artifact_path = out/"frozen_candidate.json"
    assert sha(artifact_path) == frozen["artifact_parity"]["sha256"]
    artifact = json.loads(artifact_path.read_text())
    d, _ = dev.load_data(ROOT/"reproduction/dataset_occurrence.npz", ROOT/"methods_audit/entry_group_map.csv", ROOT/"methods_audit/ambiguous_nf2_row_ids.csv")
    family, strength = frozen["selected"]
    if family == "identity": reference = d["BASE_CD"].copy()
    else:
        model = dev.train(family, d, np.arange(len(d["yCD"])))
        reference = dev.correct(family, dev.predict_residual(family, model, d, np.arange(len(d["yCD"]))), d["BASE_CD"], strength)
    actual = read_candidate(artifact, d["X9"], d["X16"], d["BASE_CD"])
    delta = float(np.max(np.abs(reference-actual)))
    assert delta < 1e-12, delta
    np.savez_compressed(out/"portability_references.npz", X9=d["X9"], X16=d["X16"], BASE_CD=d["BASE_CD"], expected_CD=reference)
    dev.dump(out/"portability_check.json", {"rows": len(reference), "max_absolute_CD_difference": delta,
        "artifact_sha256": sha(artifact_path), "reader_sha256": sha(__file__), "references_sha256": sha(out/"portability_references.npz")})
    print("Portability references verified on", len(reference), "training conditions", flush=True)


def parse_drag(path):
    lines = path.read_text(encoding="latin-1").splitlines()
    name = next(l.split(":",1)[1].strip() for l in lines if l.startswith("Airfoil:"))
    comment = next(l.split(":",1)[1].strip() for l in lines if l.startswith("Comment:"))
    assert comment.lower() == "clean", comment
    declared = None
    rows, blocks = [], []
    i = 0
    while i < len(lines):
        if lines[i].startswith("Number of Reynolds"):
            declared = int(lines[i+1].strip())
        if lines[i].startswith("Average Reynolds"):
            re = float(lines[i+1].strip())
            j = i+2
            while j < len(lines) and not lines[j].startswith("Number of angles"):
                j += 1
            assert j+2 < len(lines)
            count = int(lines[j+1].strip())
            k = j+2
            while k < len(lines) and "alpha" not in lines[k].lower(): k += 1
            assert k+count < len(lines)
            block_id = len(blocks)
            provenance = lines[k+count+1].strip() if k+count+1 < len(lines) else ""
            assert provenance.startswith("Tabulated from data in file"), provenance
            for n in range(count):
                v = [float(t) for t in lines[k+1+n].split()]
                assert len(v) >= 3 and np.isfinite(v).all()
                span = (max(v[3:])-min(v[3:]))/2 if len(v)>4 else None
                rows.append({"airfoil": name.lower(), "block": block_id, "source_line": k+n+2,
                             "run_provenance": provenance,
                             "Re": re, "alpha": v[0], "measured_CL": v[1], "measured_CD": v[2],
                             "spanwise_half_spread_CD": span, "config": comment})
            blocks.append({"block": block_id, "Re": re, "declared_points": count, "run_provenance": provenance})
            i = k+count
        i += 1
    return rows, {"airfoil": name, "declared_blocks": declared, "actual_complete_blocks": len(blocks), "rows": len(rows), "blocks": blocks}


def predict_base(coordinates, alpha, re):
    import aerosandbox as asb
    foil = asb.Airfoil(name="external_evaluation", coordinates=coordinates).to_kulfan_airfoil()
    outputs = {size: foil.get_aero_from_neuralfoil(alpha=np.asarray(alpha), Re=np.asarray(re), mach=0.0, n_crit=9, model_size=size) for size in SIZES}
    # Literal historical formatting, then parse back to float.
    quant = lambda values, digits: np.array([float(f"{float(v):.{digits}f}") for v in np.atleast_1d(values)])
    cds = np.column_stack([quant(outputs[s]["CD"],6) for s in SIZES])
    cls = np.column_stack([quant(outputs[s]["CL"],5) for s in SIZES])
    cms = np.column_stack([np.atleast_1d(outputs[s]["CM"]) for s in SIZES])
    xl = outputs["xlarge"]
    top, bot = quant(xl["Top_Xtr"],4), quant(xl["Bot_Xtr"],4)
    conf, cm8 = quant(xl["analysis_confidence"],4), quant(cms.mean(axis=1),5)
    stat = foil_stats2(coordinates.tolist())
    cd8, cl8 = cds.mean(axis=1), cls.mean(axis=1)
    spread = np.maximum(np.percentile(cds,90,axis=1)-np.percentile(cds,10,axis=1),1e-6)
    n = len(alpha)
    fill = lambda key: np.full(n,stat[key])
    x9 = np.column_stack([alpha,np.log10(re),fill("t"),fill("c"),np.log(cd8),cl8,np.log(spread),top,bot])
    x16 = np.column_stack([alpha,np.log10(re),fill("t"),fill("tx"),fill("c"),fill("cx"),fill("leR"),fill("teA"),
                          np.log(cd8),cl8,np.log(spread),conf,top,bot,np.log(cds[:,0])-np.log(cds[:,7]),cm8])
    assert np.isfinite(x9).all() and np.isfinite(x16).all() and (cd8>0).all()
    return {"X9":x9,"X16":x16,"BASE_CD":cd8,"XLARGE_CD":cds[:,5],"all_CD":cds,"all_CL":cls,"stat":stat}


def historical_inference_check():
    context = build_context(ROOT.parent)
    # Fixed metadata-only sample: first eligible entry in each source.
    records = []
    rows = context["rows"]
    with np.load(ROOT/"reproduction/dataset_occurrence.npz",allow_pickle=False) as d:
        for source in sorted(set(d["source"])):
            entry = sorted(set(d["entry"][d["source"]==source]))[0]
            ix = np.flatnonzero(d["entry"]==entry)[::max(1,int(np.sum(d["entry"]==entry))//12)]
            rawids = d["nf2_row_id"][ix]
            geompath = context["geometry_paths"][entry]
            base = context["base"]
            import zipfile
            if geompath.startswith("coords/"):
                with zipfile.ZipFile(base/"coord_seligFmt.zip") as z: text = z.read(geompath[7:]).decode("latin-1")
            else:
                with zipfile.ZipFile(base/"Stec8.zip") as z: text = z.read(geompath[6:]).decode("latin-1")
            coords = load_pts(text)
            got = predict_base(coords,d["alpha"][ix],d["Re"][ix])
            records.append({"entry":entry,"rows":len(ix),"nf2_row_ids":rawids.tolist(),
                "max_absolute_CD_difference":float(np.max(np.abs(got["all_CD"]-d["all_model_CD"][ix]))),
                "max_absolute_CL_difference":float(np.max(np.abs(got["all_CL"]-d["all_model_CL"][ix]))),
                "max_absolute_X9_difference":float(np.max(np.abs(got["X9"]-d["X9"][ix])))})
    return records


def main():
    if "--references" in sys.argv:
        portability_references()
        return
    import neuralfoil
    import aerosandbox
    import sklearn
    assert neuralfoil.__version__ == "0.3.3"
    assert aerosandbox.__version__ == "4.2.10"
    frozen_dir = ROOT/"verified_results"
    freeze = json.loads((frozen_dir/"candidate_freeze.json").read_text())
    training_manifest = json.loads((frozen_dir/"run_manifest.json").read_text())
    for path, expected in training_manifest["hashes"].items():
        p = Path(path)
        if not p.is_absolute(): p = ROOT.parent.parent/p
        assert sha(p) == expected, f"Training input/code changed: {p}"
    artifact_path = frozen_dir/"frozen_candidate.json"
    assert sha(artifact_path) == freeze["artifact_parity"]["sha256"]
    artifact = json.loads(artifact_path.read_text())
    refs_file = frozen_dir/"portability_references.npz"
    portability = json.loads((frozen_dir/"portability_check.json").read_text())
    assert portability["reader_sha256"] == sha(__file__)
    assert portability["references_sha256"] == sha(refs_file)
    with np.load(refs_file, allow_pickle=False) as refs:
        got = read_candidate(artifact,refs["X9"],refs["X16"],refs["BASE_CD"])
        maxdiff = float(np.max(np.abs(got-refs["expected_CD"])))
        assert maxdiff < 1e-12
    out = ROOT/"external_results"
    out.mkdir(exist_ok=True)
    if (out/"results.json").exists(): raise FileExistsError("External results already exist; do not silently rescore")
    inputs = ROOT/"external_screening"
    paths = [inputs/"sealed_measurements/sg605x"/f"{s.upper()}A.DRG" for s in ["sg6050","sg6051"]]
    paths += [inputs/"nominal_coordinates"/f"{s}.dat" for s in ["sg6050","sg6051"]]
    capture = json.loads((inputs/"capture_manifest.json").read_text())
    captured = {r["path"]:r["sha256"] for r in capture["files"] if "sha256" in r}
    for p in paths: assert sha(p)==captured[str(p.relative_to(inputs))]
    manifest = {"started_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "candidate_sha256":sha(artifact_path),"protocol_sha256":sha(ROOT/"EXTERNAL_TEST_PROTOCOL.md"),
        "reader_sha256":sha(__file__),"input_sha256":{str(p):sha(p) for p in paths},
        "dependency_sha256":{str(p):sha(p) for p in [ROOT/"develop_drag.py",ROOT/"reproduction/reproduce_doubleclean.py"]},
        "python":platform.python_version(),"numpy":np.__version__,"neuralfoil":neuralfoil.__version__,
        "aerosandbox":aerosandbox.__version__,"sklearn_imported_not_used_for_fitting":sklearn.__version__,
        "portability_max_abs_CD_difference":maxdiff,
        "status":"newly_scored_external_exploratory_not_confirmatory; author prior exposure pending"}
    dev.dump(out/"run_manifest.json",manifest)
    history = historical_inference_check()
    dev.dump(out/"historical_inference_check.json",history)
    print("Historical inference parity sample",history,flush=True)
    for row in history:
        assert row["max_absolute_CD_difference"] <= 1.000001e-6, "Fresh CD differs by more than one historical storage unit"
        assert row["max_absolute_CL_difference"] <= 1.000001e-5, "Fresh CL differs by more than one historical storage unit"
        assert row["max_absolute_X9_difference"] <= 1e-4, "Fresh correction features differ beyond the fixed parity tolerance"
    frames, parser = [], []
    for name in ["sg6050","sg6051"]:
        rows, info = parse_drag(inputs/"sealed_measurements/sg605x"/f"{name.upper()}A.DRG")
        assert info["airfoil"].lower() == name
        assert info["rows"] == {"sg6050":136,"sg6051":106}[name]
        frame = pd.DataFrame(rows)
        coords = load_pts((inputs/"nominal_coordinates"/f"{name}.dat").read_text())
        values = predict_base(coords,frame.alpha.to_numpy(),frame.Re.to_numpy())
        t = values["stat"]["t"]
        eligible = (frame.Re<=600000)&(frame.alpha.abs()<=12)&(frame.measured_CD>0)&(.05<=t)&(t<=.2)
        pred = read_candidate(artifact,values["X9"],values["X16"],values["BASE_CD"])
        frame["eligible"] = eligible
        frame["exclusion_reason"] = [";".join(reason for condition,reason in [(r.Re>600000,"Re_above_600k"),(abs(r.alpha)>12,"alpha_outside_12deg"),(r.measured_CD<=0,"nonpositive_measured_drag"),(not .05<=t<=.2,"thickness_outside_domain")] if condition) for r in frame.itertuples()]
        frame["thickness_ratio"] = t
        frame["mean8_CD"], frame["xlarge_CD"] = values["BASE_CD"],values["XLARGE_CD"]
        frame["candidate_CD"] = np.where(eligible,pred,values["BASE_CD"])
        frame["prediction_status"] = "returned_finite"
        frames.append(frame)
        parser.append({**info,"geometry_stats":values["stat"],"eligible_rows":int(eligible.sum())})
    frame = pd.concat(frames,ignore_index=True)
    assert np.isfinite(frame[["measured_CD","mean8_CD","xlarge_CD","candidate_CD"]].to_numpy()).all()
    frame.to_csv(out/"all_predictions.csv",index=False)
    summaries = []
    for label, mask in [("all_complete_rows_with_domain_fallback",np.ones(len(frame),dtype=bool)),("primary_in_domain",frame.eligible.to_numpy())]:
        part = frame[mask]
        groups = [("pooled",part)]+[(s,part[part.airfoil==s]) for s in sorted(part.airfoil.unique())]
        for name,g in groups:
            for baseline in ["xlarge_CD","mean8_CD"]:
                summaries.append({"cohort":label,"airfoil":name,"baseline":baseline,
                    **dev.metrics(g.measured_CD.to_numpy(),g.candidate_CD.to_numpy(),g[baseline].to_numpy(),g.airfoil.to_numpy(),bootstrap=False)})
    result = {"manifest":manifest,"parser":parser,"summaries":summaries,
        "prediction_failures":0,"total_complete_rows":len(frame),"primary_rows":int(frame.eligible.sum()),
        "interpretation":"Two related airfoils from one facility; descriptive newly scored external challenge, not a universal or independently confirmed threshold claim.",
        "finished_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    assert sha(artifact_path)==manifest["candidate_sha256"]
    assert sha(__file__)==manifest["reader_sha256"]
    for path,expected in manifest["input_sha256"].items(): assert sha(path)==expected
    for path,expected in manifest["dependency_sha256"].items(): assert sha(path)==expected
    dev.dump(out/"results.json",result)
    print(json.dumps(result,indent=2),flush=True)


if __name__ == "__main__": main()
