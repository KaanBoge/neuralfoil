"""Frozen Cycle 2 testing. No fitting; no measurement outcomes in model inputs."""
from __future__ import annotations
import json
from pathlib import Path
import platform
import sys
import time
import zipfile
import numpy as np
import pandas as pd

import develop_v2 as v
sys.path.insert(0,str(v.OLD))
import score_external as prior
sys.path.insert(0,str(v.OLD/"reproduction"))
from reproduce_doubleclean import build_context,load_pts

ROOT=v.ROOT
WCONFIGS=["w1011-20","w1011-30","w1015-20","w1015-30"]


def rich(values):
    d={"X9":values["X9"],"X16":values["X16"],"BASE_CD":values["BASE_CD"],
       "all_model_CD":values["all_CD"],"all_model_CL":values["all_CL"]}
    return v.add_features(d)


def parse_w(path,metadata):
    lines=[line.strip() for line in path.read_text(encoding="latin1").splitlines()]
    headers={}
    for field in ["Airfoil","Builder","Comment"]:
        matches=[line.split(":",1)[1].strip() for line in lines if line.startswith(field+":")]
        assert len(matches)==1,(path.name,field,len(matches))
        expected=[h["value"] for h in metadata["headers"] if h.get("field")==field]
        assert matches==expected,(field,matches,expected)
        headers[field]=matches[0]
    assert headers["Comment"].startswith("Clean, Cf/C = ") and "Flap = 0" in headers["Comment"]
    rows,blocks=[],[]
    for i,line in enumerate(lines):
        if not line.startswith("Average Reynolds #:"): continue
        re=float(lines[i+1].strip())
        j=i+2
        while j<len(lines) and not lines[j].startswith("Number of angles of attack:"): j+=1
        assert j+2<len(lines)
        n=int(lines[j+1].strip())
        k=j+2
        while k<len(lines) and not lines[k].strip().lower().startswith("alpha"): k+=1
        assert k+n<len(lines)
        p=k+n+1
        while p<len(lines) and not lines[p].strip(): p+=1
        provenance=lines[p].strip() if p<len(lines) else ""
        assert provenance.startswith("Tabulated from data in file "),provenance
        block=len(blocks)
        for offset in range(n):
            values=[float(a) for a in lines[k+1+offset].split()]
            assert len(values)>=3 and np.isfinite(values).all()
            span=(max(values[3:])-min(values[3:]))/2 if len(values)>4 else None
            rows.append({"configuration":path.name.removesuffix("_f0_drag.dat"),"airfoil":path.name.split("-")[0],
                "block":block,"source_line":k+offset+2,"Re":re,"alpha":values[0],"measured_CL":values[1],"measured_CD":values[2],
                "spanwise_half_spread_CD":span,"run_provenance":provenance,"config_comment":headers["Comment"]})
        blocks.append({"block":block,"Re":re,"rows":n,"provenance":provenance})
    assert len(rows)==metadata["declared_point_rows_total"]
    assert [b["rows"] for b in blocks]==metadata["point_count_metadata"]
    assert [b["Re"] for b in blocks]==metadata["reynolds_metadata"]
    return pd.DataFrame(rows),{"file":path.name,"headers":headers,"blocks":blocks,"rows":len(rows)}


def feature_preflight():
    d=v.load_data()
    context=build_context(ROOT.parent)
    records=[]
    for source in sorted(set(d["source"])):
        entry=sorted(set(d["entry"][d["source"]==source]))[0]
        ids=np.flatnonzero(d["entry"]==entry)
        ix=ids[::max(1,len(ids)//12)]
        gp=context["geometry_paths"][entry]
        if gp.startswith("coords/"):
            with zipfile.ZipFile(context["base"]/"coord_seligFmt.zip") as z: text=z.read(gp[7:]).decode("latin1")
        else:
            with zipfile.ZipFile(context["base"]/"Stec8.zip") as z: text=z.read(gp[6:]).decode("latin1")
        got=prior.predict_base(load_pts(text),d["alpha"][ix],d["Re"][ix])
        new=rich(got)
        row={"entry":str(entry),"rows":len(ix),"nf2_row_ids":d["nf2_row_id"][ix].tolist(),
             "max_CD_difference":float(np.max(np.abs(got["all_CD"]-d["all_model_CD"][ix]))),
             "max_CL_difference":float(np.max(np.abs(got["all_CL"]-d["all_model_CL"][ix]))),
             "max_X16_difference":float(np.max(np.abs(new["X16"]-d["X16"][ix]))),
             "max_X24_difference":float(np.max(np.abs(new["X24"]-d["X24"][ix])))}
        records.append(row)
    return records


def apply(frame,coords,candidate,cycle1):
    values=prior.predict_base(coords,frame.alpha.to_numpy(),frame.Re.to_numpy())
    d=rich(values)
    t=values["stat"]["t"]
    domain=(frame.Re>0)&(frame.Re<=600000)&(frame.alpha.abs()<=12)&(.05<=t)&(t<=.20)&np.isfinite(values["BASE_CD"])&(values["BASE_CD"]>0)
    new=v.portable_predict(candidate,d)
    former=prior.read_candidate(cycle1,d["X9"],d["X16"],d["BASE_CD"])
    frame=frame.copy()
    frame["inference_gate"]=domain
    frame["eligible"]=domain&(frame.measured_CD>0)
    frame["exclusion_reason"]=[";".join(reason for yes,reason in [(r.Re<=0 or r.Re>600000,"Re_outside_domain"),(abs(r.alpha)>12,"alpha_outside_12deg"),
        (not .05<=t<=.2,"thickness_outside_domain"),(r.measured_CD<=0,"nonpositive_measured_drag")] if yes) for r in frame.itertuples()]
    frame["thickness_ratio"]=t
    frame["mean8_CD"],frame["xlarge_CD"]=values["BASE_CD"],values["XLARGE_CD"]
    frame["cycle1_CD"]=np.where(domain,former,values["BASE_CD"])
    frame["cycle2_CD"]=np.where(domain,new,values["BASE_CD"])
    frame["prediction_status"]="finite_returned"
    assert np.isfinite(frame[["measured_CD","mean8_CD","xlarge_CD","cycle1_CD","cycle2_CD"]].to_numpy()).all()
    assert np.array_equal(frame.loc[~domain,"cycle2_CD"].to_numpy(),frame.loc[~domain,"mean8_CD"].to_numpy())
    return frame,values["stat"]


def summarize(frame):
    result=[]
    for cohort,mask in [("primary_eligible",frame.eligible.to_numpy()),("all_complete_with_fallback",np.ones(len(frame),dtype=bool))]:
        part=frame[mask]
        subsets=[("pooled",part)]+[(s,part[part.airfoil==s]) for s in sorted(part.airfoil.unique())]
        if part.configuration.nunique()>part.airfoil.nunique():
            subsets += [(s,part[part.configuration==s]) for s in sorted(part.configuration.unique())]
        for name,sub in subsets:
            if not len(sub):continue
            for baseline in ["xlarge_CD","mean8_CD","cycle1_CD"]:
                metric=v.old.metrics(sub.measured_CD.to_numpy(),sub.cycle2_CD.to_numpy(),sub[baseline].to_numpy(),sub.airfoil.to_numpy(),bootstrap=False)
                result.append({"cohort":cohort,"subset":name,"candidate":"cycle2_CD","baseline":baseline,**metric})
    return result


def main():
    import aerosandbox,neuralfoil
    assert aerosandbox.__version__=="4.2.10" and neuralfoil.__version__=="0.3.3" and np.__version__=="2.3.5"
    out=ROOT/"external_results"
    out.mkdir(exist_ok=True)
    assert not (out/"results.json").exists(),"Do not silently rescore completed external test"
    assert not (out/"W_FIRST_OUTCOME_EXPOSURE.json").exists(),"W outcomes were already opened; preserve the marker and audit any interrupted-run recovery explicitly"
    freeze=json.loads((ROOT/"results/freeze.json").read_text())
    artifact_path=ROOT/"results/candidate.json"
    assert v.old.digest(artifact_path)==freeze["parity"]["artifact_sha256"]
    candidate=json.loads(artifact_path.read_text())
    original_path=v.OLD/"verified_results/frozen_candidate.json"
    cycle1=json.loads(original_path.read_text())
    train_manifest=json.loads((ROOT/"results/run_manifest.json").read_text())
    for path,h in train_manifest["hashes"].items():assert v.old.digest(path)==h,path
    refs_path=ROOT/"results/inference_references.npz"
    assert v.old.digest(refs_path)==freeze["parity"]["references_sha256"]
    with np.load(refs_path,allow_pickle=False) as refs:
        actual=v.portable_predict(candidate,{k:refs[k] for k in refs.files})
        delta=float(np.max(np.abs(actual-refs["expected_CD"])))
        assert delta<1e-12,delta
    screen=ROOT/"external_screening"
    inputs=json.loads((screen/"input_manifest.json").read_text())
    captured={r["path"]:r["sha256"] for r in inputs["captures"]}
    paths=[Path(__file__),ROOT/"EXTERNAL_PROTOCOL.md",ROOT/"develop_v2.py",v.OLD/"score_external.py",v.OLD/"develop_drag.py",
        v.OLD/"reproduction/reproduce_doubleclean.py",artifact_path,original_path,refs_path,screen/"input_manifest.json"]
    paths += [Path(p) for p in train_manifest["hashes"]]+[ROOT/"results/freeze.json",ROOT/"results/run_manifest.json"]
    for config in WCONFIGS:
        paths += [screen/"sealed_measurements/vol6"/f"{config}_f0_drag.dat"]
    paths += [screen/"nominal_coordinates"/f"{name}.dat" for name in ["w1011","w1015"]]
    for name in ["sg6050","sg6051"]:
        paths += [v.OLD/"external_screening/sealed_measurements/sg605x"/f"{name.upper()}A.DRG",v.OLD/"external_screening/nominal_coordinates"/f"{name}.dat"]
    for p in paths:
        if str(p).startswith(str(screen)) and str(p.relative_to(screen)) in captured:
            assert v.old.digest(p)==captured[str(p.relative_to(screen))]
    manifest={"frozen_before_outcome_parse_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "hashes":{str(p):v.old.digest(p) for p in paths},"python":platform.python_version(),"numpy":np.__version__,
        "aerosandbox":aerosandbox.__version__,"neuralfoil":neuralfoil.__version__,"all_training_reference_parity_max_CD":delta,
        "SG_status":"exposed regression check","W_status":"previously unscored zero-flap configuration-transfer challenge; author prior exposure unconfirmed"}
    v.old.dump(out/"pre_score_manifest.json",manifest)
    checks=feature_preflight()
    v.old.dump(out/"fresh_feature_parity.json",checks)
    for row in checks:
        assert row["max_CD_difference"]<=1.000001e-6 and row["max_CL_difference"]<=1.000001e-5
        assert row["max_X16_difference"]<=1e-4 and row["max_X24_difference"]<=1e-4
    print("Feature and model parity passed before outcome scoring",flush=True)
    results={"manifest":manifest,"groups":{}}
    # SG is exposed; parse it and W only after the common immutable freeze above.
    sg=[]
    for name in ["sg6050","sg6051"]:
        rows,info=prior.parse_drag(v.OLD/"external_screening/sealed_measurements/sg605x"/f"{name.upper()}A.DRG")
        frame=pd.DataFrame(rows)
        frame["configuration"]=name
        coords=load_pts((v.OLD/"external_screening/nominal_coordinates"/f"{name}.dat").read_text())
        frame,_=apply(frame,coords,candidate,cycle1)
        sg.append(frame)
    sg=pd.concat(sg,ignore_index=True)
    assert len(sg)==242 and int(sg.eligible.sum())==234
    sg.to_csv(out/"SG_exposed_predictions.csv",index=False)
    results["groups"]["SG_exposed"]={"complete_rows":len(sg),"eligible_rows":int(sg.eligible.sum()),"summaries":summarize(sg)}
    w,parsed=[],[]
    results["W_first_outcome_parse_utc"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    with (out/"W_FIRST_OUTCOME_EXPOSURE.json").open("x") as record:
        json.dump({"first_outcome_parse_utc":results["W_first_outcome_parse_utc"],"candidate_sha256":v.old.digest(artifact_path),
            "scoring_code_sha256":v.old.digest(__file__),"pre_score_manifest_sha256":v.old.digest(out/"pre_score_manifest.json"),
            "status":"Persisted immediately before first W coefficient parse; retain even if the run fails"},record,indent=2)
        record.write("\n")
    for config in WCONFIGS:
        rel=f"sealed_measurements/vol6/{config}_f0_drag.dat"
        frame,info=parse_w(screen/rel,inputs["measurements"][rel])
        coords=load_pts((screen/"nominal_coordinates"/f"{config.split('-')[0]}.dat").read_text())
        frame,stats=apply(frame,coords,candidate,cycle1)
        w.append(frame)
        parsed.append({**info,"nominal_geometry_stats":stats,"eligible_rows":int(frame.eligible.sum())})
    w=pd.concat(w,ignore_index=True)
    assert len(w)==255
    w.to_csv(out/"W_new_challenge_predictions.csv",index=False)
    results["groups"]["W_new_challenge"]={"complete_rows":len(w),"eligible_rows":int(w.eligible.sum()),"nominal_designs":2,
        "configurations":4,"parser":parsed,"summaries":summarize(w)}
    for path,h in manifest["hashes"].items(): assert v.old.digest(path)==h,path
    results["completed_utc"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    v.old.dump(out/"results.json",results)
    for name,group in results["groups"].items():
        print(json.dumps({"set":name,"complete_rows":group["complete_rows"],"eligible_rows":group["eligible_rows"],
            "pooled_primary":[r for r in group["summaries"] if r["cohort"]=="primary_eligible" and r["subset"]=="pooled"]}),flush=True)


if __name__=="__main__":main()
