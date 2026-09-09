"""Verify trusted source hashes before pickle loading; export and test JSON."""
from pathlib import Path
import hashlib
import json
import pickle
import sys
import time
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
C3 = PROJECT/"model_development_20260907_search"
C4 = PROJECT/"model_development_20260907_transition"
sys.path[:0] = [str(C3/"smooth"), str(C3/"ensemble"), str(C3/"portable"), str(C4), str(PROJECT/"model_development_20260906_v2")]
import smooth_models
import ensemble_models
import transition_models
import shape_inputs
from portable_models import export_hist, FEATURES
from predictor import predict, _spline, validate_weights


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert not (HERE/"manifest.json").exists(), "Preserve verified bundle"
    m3 = json.loads((C3/"exposed_results/fit_manifest.json").read_text())
    m4 = json.loads((C4/"results/freeze.json").read_text())
    sources = [("smooth9_relative", C3/"exposed_results/fit_smooth9_relative.pkl", m3),
               ("simplex8_re_l1", C3/"exposed_results/fit_simplex8_re_l1.pkl", m3),
               ("joint62_mixed", C4/"results/fit_joint62_mixed.pkl", m4)]
    models, verified = {}, {}
    for family, path, manifest in sources:
        digest = sha(path)
        assert digest == manifest["artifacts"][family]["sha256"], path
        verified[str(path)] = digest
        with path.open("rb") as f:
            models[family] = pickle.load(f)
    sm = models["smooth9_relative"]
    assert sm.spline.extrapolation == "constant" and not sm.spline.include_bias
    splines = [{"t": s.t.tolist(), "c": s.c.tolist(), "k": s.k} for s in sm.spline.bsplines_]
    blend_path = HERE.parent/"feasibility/blend_both.json"
    weights = json.loads(blend_path.read_text())["weights"]
    artifact = {"schema": "retrospective-neuralfoil-blend-v1", "status": "exposed_outcome_calibrated_not_independent_validation",
                "weights": {k:v for k,v in weights.items() if v != 0}, "source_pickle_sha256": verified,
                "weight_artifact_sha256": sha(blend_path),
                "input_contract": {"BASE_CD": "positive mean-eight CD", "X9": ["alpha","lre","t2","c2","lcd8","cl8","lsp","topxtr","botxtr"],
                    "X62": FEATURES["X62"], "all_model_CD": ["xxsmall","xsmall","small","medium","large","xlarge","xxlarge","xxxlarge"],
                    "Re": "positive Reynolds number", "inference_gate": "required full-row boolean; false means mean8 fallback"},
                "convention": "Preserved original AeroSandbox normalization, ncrit=9 mean8 and historical decimal formatting; X62 adds ncrit5,7,11,13 sensitivity and original Kulfan K18.",
                "smooth": {"keep": sm.keep.tolist(), "center": sm.center.tolist(), "coefficients": sm.coefficients.tolist(), "splines": splines},
                "simplex": {k: np.asarray(models["simplex8_re_l1"][k]).tolist() for k in ["coef","endpoints"]},
                "joint_hist": export_hist(models["joint62_mixed"]["model"])}
    validate_weights(artifact["weights"])
    target = HERE/"retrospective_blend.json"
    target.write_text(json.dumps(artifact, separators=(",", ":"))+"\n")
    loaded = json.loads(target.read_text())
    tests, refs = [], {}
    for cohort in ["historical", "SG_exposed", "W_new_challenge"]:
        data = shape_inputs.load_historical() if cohort == "historical" else shape_inputs.load_exposed(cohort)
        n = len(data["BASE_CD"])
        gate = np.ones(n, dtype=bool) if cohort == "historical" else pd.read_csv(C3/"exposed_results"/f"{cohort}_predictions.csv", usecols=["inference_gate"]).inference_gate.to_numpy()
        minimal = {k: data[k] for k in ["BASE_CD","X9","X62","all_model_CD","Re"]}
        ids = np.arange(n)
        originals = {"smooth9_relative__1": smooth_models.predict(models["smooth9_relative"], data, ids),
                     "simplex8_re_l1__1": ensemble_models.predict(models["simplex8_re_l1"], data, ids),
                     "joint62_mixed__1": transition_models.predict(models["joint62_mixed"], data, ids)}
        expected = np.where(gate, sum(artifact["weights"][k]*v for k,v in originals.items()), data["BASE_CD"])
        begin = time.monotonic()
        got, parts = predict(loaded, minimal, gate, return_components=True)
        elapsed = time.monotonic()-begin
        err = float(np.max(np.abs(got-expected)))
        assert err < 1e-12
        deltas = {}
        for key, raw in originals.items():
            deltas[key] = float(np.max(np.abs(parts[key]-np.where(gate,raw,data["BASE_CD"]))))
            assert deltas[key] < 1e-12
        if cohort != "historical":
            old3 = pd.read_csv(C3/"exposed_results"/f"{cohort}_predictions.csv")
            old4 = pd.read_csv(C4/"exposed_results"/f"{cohort}_predictions.csv")
            for key in originals:
                cached = old4[key] if key.startswith("joint") else old3[key]
                np.testing.assert_allclose(parts[key], cached, atol=1e-12, rtol=0)
            exposed_reference = sum(artifact["weights"][k]*(old4[k] if k.startswith("joint") else old3[k]) for k in originals)
            np.testing.assert_allclose(got, exposed_reference, atol=1e-12, rtol=0)
        np.testing.assert_array_equal(predict(loaded, minimal, np.zeros(n,dtype=bool)), data["BASE_CD"])
        altered = dict(minimal, MEAS_CD=np.full(n, np.nan), source=np.full(n,"unused"), configuration=np.full(n,"unused"))
        np.testing.assert_array_equal(predict(loaded, altered, gate), got)
        for key,value in minimal.items(): refs[cohort+"_"+key] = value
        refs[cohort+"_gate"], refs[cohort+"_expected_CD"] = gate, expected
        pd.DataFrame({"row":ids, "inference_gate":gate, "BASE_CD":data["BASE_CD"], "reference_CD":expected,"portable_CD":got, **parts}).to_csv(HERE/f"{cohort}_predictions.csv",index=False)
        tests.append({"cohort":cohort,"rows":n,"fallback_rows":int((~gate).sum()),"max_abs_CD_error":err,"component_max_errors":deltas,"portable_seconds":elapsed})
    # Check the spline evaluator at all knots and both clamped extrapolation ends.
    for spec, source in zip(splines, sm.spline.bsplines_):
        t = np.asarray(spec["t"])
        x = np.r_[t, t[0]-10, t[-1]+10]
        bounded = np.clip(x,t[source.k],t[-source.k-1])
        np.testing.assert_allclose(_spline(spec,x),source(bounded)[:,:-1],atol=1e-14,rtol=0)
    np.savez_compressed(HERE/"inference_references.npz",**refs)
    manifest = {"status":artifact["status"],"tests":tests,"source_hashes_verified_before_unpickle":verified,
                "artifact_sha256":sha(target),"predictor_sha256":sha(HERE/"predictor.py"),"artifact_bytes":target.stat().st_size,
                "inference_references_sha256":sha(HERE/"inference_references.npz"),
                "dependencies_inference":["Python","NumPy"],"spline_boundary_test":"passed","false_gate_exact_fallback":"passed","labels_identity_invariance":"passed"}
    (HERE/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
