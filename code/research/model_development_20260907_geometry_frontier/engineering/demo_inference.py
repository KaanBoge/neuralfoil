"""Three-row label-free demonstration; not an accuracy evaluation."""
from pathlib import Path
import hashlib
import io
import json
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE / "fast_inference"))
from checked_loader import load_prepared_checked
from prepared import MANIFEST_SHA256


def main():
    package = PROJECT / "model_development_20260907_risk_policy/portable"
    model = load_prepared_checked(package)
    manifest_bytes = (package / "manifest.json").read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == MANIFEST_SHA256
    manifest = json.loads(manifest_bytes)
    reference_bytes = (package / "inference_references.npz").read_bytes()
    assert hashlib.sha256(reference_bytes).hexdigest() == manifest["package_hashes"]["inference_references.npz"]
    with np.load(io.BytesIO(reference_bytes), allow_pickle=False) as refs:
        args = [refs["historical_" + key][:3] for key in ["X62", "BASE_CD", "all_model_CD", "gate"]]
        for label in ["risk_transfer", "unpenalized_transfer", "risk_group"]:
            cd, strength = model.predict(*args, label=label)
            print(json.dumps({"policy": label, "predicted_CD": cd.tolist(), "applied_strength": strength.tolist()}))
    print("Label-free software demonstration only; these rows do not measure accuracy.")


if __name__ == "__main__":
    main()
