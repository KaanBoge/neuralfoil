"""Export the two frozen Cycle 4 choices using the unchanged portable library."""
from pathlib import Path
import hashlib
import json
import pickle
import sys
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
LIB = PROJECT.parent / "model_development_20260907_search/portable"
sys.path[:0] = [str(LIB), str(PROJECT)]
import portable_models as pm
import run_transition as native


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not (ROOT / "manifest.json").exists(), "Preserve completed export"
    frozen_path = PROJECT / "results/freeze.json"
    frozen = json.loads(frozen_path.read_text())
    original = json.loads((PROJECT / "results/run_manifest.json").read_text())
    external = json.loads((PROJECT / "exposed_results/pre_score_manifest.json").read_text())
    for record in [original, external]:
        for path, expected in record["hashes"].items():
            assert digest(path) == expected, path
    choices = sorted({label.rsplit("__", 1)[0] for label in frozen["selected"].values()})
    assert choices == ["gate_shrink", "transition_mixed"], choices
    paths = [Path(__file__), Path(pm.__file__), frozen_path, PROJECT / "results/run_manifest.json",
             PROJECT / "exposed_results/pre_score_manifest.json", PROJECT / "shape_inputs.py", PROJECT / "transition_inputs.py"]
    for name in ["SG_exposed", "W_new_challenge"]:
        paths += [PROJECT / "exposed_results" / f"{name}_predictions.csv"]
    hashes = {str(p): digest(p) for p in paths}
    d = native.inputs.load_historical()
    cohorts = [("historical", d, np.ones(len(d["BASE_CD"]), dtype=bool), None)]
    for name in ["SG_exposed", "W_new_challenge"]:
        ext = native.inputs.load_exposed(name)
        frame = pd.read_csv(PROJECT / "exposed_results" / f"{name}_predictions.csv",
                            usecols=["inference_gate", "gate_shrink__1", "gate_shrink__0.5", "transition_mixed__1", "transition_mixed__0.5"])
        cohorts.append((name, ext, frame.inference_gate.to_numpy(dtype=bool), frame))
    checks, references = [], {}
    for family in choices:
        path = PROJECT / "results" / f"fit_{family}.pkl"
        expected_hash = frozen["artifacts"][family]["sha256"]
        assert digest(path) == expected_hash, "Only trusted local hash-verified pickles may be loaded"
        with path.open("rb") as f:
            model = pickle.load(f)
        artifact = pm.export_model(family, model, source_sha256=expected_hash)
        json_path = ROOT / f"{family}.json"
        json_path.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")
        loaded = json.loads(json_path.read_text())
        hashes[str(path)], hashes[str(json_path)] = expected_hash, digest(json_path)
        for name, values, gate, frame in cohorts:
            idx = np.arange(len(values["BASE_CD"]))
            expected = native.predict(family, model, values, idx)
            key = loaded["feature_key"]
            minimal = {key: values[key], "BASE_CD": values["BASE_CD"]}
            for strength in [1., .5]:
                this = dict(loaded, strength=strength)
                target = values["BASE_CD"] + strength * (expected - values["BASE_CD"])
                tick = time.monotonic()
                pred = pm.predict(this, minimal)
                seconds = time.monotonic() - tick
                difference = float(np.max(np.abs(pred - target)))
                assert difference < 1e-12, (family, name, strength, difference)
                gated = pm.predict(this, minimal, inference_gate=gate)
                expected_gated = np.where(gate, target, values["BASE_CD"])
                np.testing.assert_allclose(gated, expected_gated, rtol=0, atol=1e-12)
                np.testing.assert_array_equal(gated[~gate], values["BASE_CD"][~gate])
                csv_error = None
                if frame is not None:
                    csv_error = float(np.max(np.abs(gated - frame[f"{family}__{strength:g}"].to_numpy())))
                    assert csv_error < 1e-12
                references[f"{name}_{family}_{strength:g}_raw"] = target
                references[f"{name}_{family}_{strength:g}_gated"] = expected_gated
                checks.append({"family": family, "cohort": name, "strength": strength, "rows": len(pred),
                               "max_abs_CD_difference": difference, "frozen_csv_max_abs_CD_difference": csv_error,
                               "outside_gate_rows": int((~gate).sum()), "portable_seconds": seconds,
                               "label_free_inference": True, "mean8_fallback_exact": True})
            references[f"{name}_{key}"] = values[key]
            references[f"{name}_BASE_CD"] = values["BASE_CD"]
            references[f"{name}_inference_gate"] = gate
    np.savez_compressed(ROOT / "inference_references.npz", **references)
    hashes[str(ROOT / "inference_references.npz")] = digest(ROOT / "inference_references.npz")
    for path, expected in hashes.items():
        assert digest(path) == expected, path
    result = {"status": "experimental_not_deployed; serialization parity is not scientific confirmation",
              "selected": frozen["selected"], "source_portable_library": str(Path(pm.__file__)),
              "library_sha256": digest(pm.__file__), "checks": checks, "hashes": hashes}
    (ROOT / "manifest.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(checks), flush=True)


if __name__ == "__main__":
    main()
