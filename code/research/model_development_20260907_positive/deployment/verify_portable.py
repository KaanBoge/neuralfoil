"""Replay saved feature references using only stdlib and NumPy."""
from pathlib import Path
import hashlib
import json
import copy
import numpy as np
from predictor import predict

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE/"manifest.json").read_text())
    for name, key in [("retrospective_blend.json", "artifact_sha256"), ("predictor.py", "predictor_sha256"),
                      ("inference_references.npz", "inference_references_sha256")]:
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == manifest[key]
    artifact = json.loads((HERE/"retrospective_blend.json").read_text())
    with np.load(HERE/"inference_references.npz", allow_pickle=False) as refs:
        for cohort in ["historical", "SG_exposed", "W_new_challenge"]:
            features = {k: refs[cohort+"_"+k] for k in ["BASE_CD","X9","X62","all_model_CD","Re"]}
            gate = refs[cohort+"_gate"]
            got = predict(artifact, features, gate)
            np.testing.assert_allclose(got, refs[cohort+"_expected_CD"], atol=1e-12, rtol=0)
            np.testing.assert_array_equal(got[~gate], features["BASE_CD"][~gate])
            print(cohort, len(got), "rows: PASS")
        try:
            predict(artifact, features, gate.astype(int))
        except ValueError:
            pass
        else:
            raise AssertionError("Non-boolean gate accepted")
        for value in [float("nan"), float("inf"), float("-inf"), "0.1", None, True, -0.01, 2.]:
            invalid = copy.deepcopy(artifact)
            invalid["weights"]["smooth9_relative__1"] = value
            for test_gate in [np.ones_like(gate), np.zeros_like(gate)]:
                try:
                    predict(invalid, features, test_gate)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"Invalid artifact weight accepted: {value!r}")
    print("JSON/reference hashes, all-row parity, explicit gate and invalid-weight validation: PASS")


if __name__ == "__main__":
    main()
