"""NumPy-only reference replay; no fitted-model or label dependencies."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.path.insert(0, str(PROJECT / "model_development_20260907_search/portable"))
import portable_models as portable


def main():
    manifest = json.loads((HERE / "manifest.json").read_text())
    for path, expected in manifest["hashes"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
    artifact = json.loads((HERE / "hist62_regularized_half.json").read_text())
    with np.load(HERE / "inference_references.npz", allow_pickle=False) as refs:
        for name in ["historical", "SG_exposed", "W_new_challenge"]:
            d = {key: refs[f"{name}_{key}"] for key in ["X62", "BASE_CD"]}
            gate = refs[f"{name}_gate"]
            np.testing.assert_allclose(portable.predict(artifact, d), refs[f"{name}_expected_raw"], rtol=0, atol=1e-12)
            actual = portable.predict(artifact, d, inference_gate=gate)
            np.testing.assert_allclose(actual, refs[f"{name}_expected_gated"], rtol=0, atol=1e-12)
            np.testing.assert_array_equal(actual[~gate], d["BASE_CD"][~gate])
            print(name, len(actual), "rows: PASS")
    assert "sklearn" not in sys.modules and "scipy" not in sys.modules
    print("All hashes, NumPy-only replay and exact fallback: PASS")


if __name__ == "__main__":
    main()
