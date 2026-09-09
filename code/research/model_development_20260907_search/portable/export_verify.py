"""Verify trusted locally frozen Cycle 3 pickles, export JSON, test parity."""
from pathlib import Path
import hashlib
import json
import pickle
import sys
import time
import numpy as np
import pandas as pd
import sklearn
import portable_models as pm

ROOT = Path(__file__).resolve().parent
SEARCH = ROOT.parent
sys.path.insert(0, str(SEARCH))
import search as search


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not (ROOT / "manifest.json").exists(), "Preserve completed export"
    manifest_path = SEARCH / "exposed_results/fit_manifest.json"
    fitted_manifest = json.loads(manifest_path.read_text())
    for path, expected in fitted_manifest["hashes"].items():
        assert digest(path) == expected, path
    d = search.v2.load_data()
    cohorts = [("historical", d, np.ones(len(d["BASE_CD"]), dtype=bool))]
    for name in ["SG_exposed", "W_new_challenge"]:
        with np.load(SEARCH / "exposed_inputs/forward_verified" / f"{name}.npz", allow_pickle=False) as archive:
            ext = {key: archive[key].copy() for key in archive.files}
        frame = pd.read_csv(SEARCH / "exposed_results" / f"{name}_predictions.csv", usecols=["inference_gate", "gate_shrink__1", "cycle2_fixed__1"])
        cohorts.append((name, ext, frame.inference_gate.to_numpy(dtype=bool)))
    results = []
    references = {}
    hashes = {str(manifest_path): digest(manifest_path), str(Path(__file__)): digest(__file__), str(Path(pm.__file__)): digest(pm.__file__)}
    for family in ["gate_shrink", "cycle2_fixed"]:
        path = SEARCH / "exposed_results" / f"fit_{family}.pkl"
        expected_hash = fitted_manifest["artifacts"][family]["sha256"]
        assert digest(path) == expected_hash, "Only locally created hash-verified pickles can be loaded"
        with path.open("rb") as f:
            model = pickle.load(f)
        artifact = pm.export_model(family, model, source_sha256=expected_hash)
        artifact["reference_versions"]["sklearn_training"] = sklearn.__version__
        artifact_path = ROOT / f"{family}.json"
        artifact_path.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")
        loaded = json.loads(artifact_path.read_text())
        for name, values, gate in cohorts:
            idx = np.arange(len(values["BASE_CD"]))
            expected = search.predict(family, model, values, idx)
            minimal = {k: values[k] for k in ["X24", "BASE_CD"]}
            tick = time.monotonic()
            pred = pm.predict(loaded, minimal)
            seconds = time.monotonic() - tick
            difference = float(np.max(np.abs(pred - expected)))
            assert difference < 1e-12, (family, name, difference)
            gated = pm.predict(loaded, minimal, inference_gate=gate)
            expected_gated = np.where(gate, expected, values["BASE_CD"])
            np.testing.assert_allclose(gated, expected_gated, rtol=0, atol=1e-12)
            half = dict(loaded, strength=.5)
            np.testing.assert_allclose(pm.predict(half, minimal), values["BASE_CD"] + .5 * (expected - values["BASE_CD"]), rtol=0, atol=1e-12)
            if name != "historical":
                frame = pd.read_csv(SEARCH / "exposed_results" / f"{name}_predictions.csv", usecols=[f"{family}__1"])
                np.testing.assert_allclose(gated, frame[f"{family}__1"].to_numpy(), rtol=0, atol=1e-12)
            references[f"{name}_{family}_full"] = expected
            references[f"{name}_{family}_with_domain_fallback"] = expected_gated
            references[f"{name}_X24"] = values["X24"]
            references[f"{name}_BASE_CD"] = values["BASE_CD"]
            references[f"{name}_inference_gate"] = gate
            results.append({"family": family, "cohort": name, "rows": len(pred), "max_abs_CD_difference": difference,
                            "outside_gate_rows": int((~gate).sum()), "portable_seconds": seconds,
                            "label_free_inference": True, "half_strength_parity": True, "domain_fallback_parity": True})
        hashes[str(path)] = expected_hash
        hashes[str(artifact_path)] = digest(artifact_path)
    np.savez_compressed(ROOT / "inference_references.npz", **references)
    hashes[str(ROOT / "inference_references.npz")] = digest(ROOT / "inference_references.npz")
    (ROOT / "manifest.json").write_text(json.dumps({"status": "experimental_not_deployed; feature-array parity only", "checks": results, "hashes": hashes}, indent=2) + "\n")
    print(json.dumps(results), flush=True)


if __name__ == "__main__":
    main()
