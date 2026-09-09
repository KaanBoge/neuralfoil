"""Condition-only input regeneration for previously exposed SG/W cohorts."""
import hashlib
import json
from pathlib import Path
import sys
import time
import aerosandbox
import neuralfoil
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
OLD = PROJECT/"model_development_20260906"
V2 = PROJECT/"model_development_20260906_v2"
sys.path.insert(0, str(OLD))
import score_external as legacy
from predict_tie_safe import predict_base, rich
from audit_tie_safe import mirror
from reproduce_doubleclean import load_pts


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert aerosandbox.__version__ == "4.2.10" and neuralfoil.__version__ == "0.3.3"
    out = HERE/"inputs"
    out.mkdir(exist_ok=True)
    assert not (out/"manifest.json").exists(), "Inputs are frozen; do not overwrite"
    code_paths = [HERE/"predict_tie_safe.py", HERE/"tie_safe_normalization.py", HERE/"generate_inputs.py",
                  OLD/"score_external.py", OLD/"reproduction/reproduce_doubleclean.py", V2/"develop_v2.py"]
    code_hashes = {str(p): sha(p) for p in code_paths}
    # Freeze before any evaluation; only synthetic/input parity runs occur here.
    (out/"code_freeze.json").write_text(json.dumps(code_hashes, indent=2)+"\n")
    logs = []
    begin = time.monotonic()
    for cohort in ["SG_exposed", "W_new_challenge"]:
        path = V2/"external_results"/f"{cohort}_predictions.csv"
        frame = pd.read_csv(path, usecols=["airfoil", "alpha", "Re"])
        conditions_sha = hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
        pieces, tests = {}, []
        with np.load(HERE.parent/"exposed_inputs/forward_verified"/f"{cohort}.npz", allow_pickle=False) as a:
            reference = {k: a[k] for k in ["X9", "X16", "X24", "BASE_CD", "XLARGE_CD", "all_model_CD", "all_model_CL"]}
        for name in sorted(frame.airfoil.unique()):
            idx = np.flatnonzero(frame.airfoil.to_numpy() == name)
            geometry = (OLD if name.startswith("sg") else V2)/"external_screening/nominal_coordinates"/f"{name}.dat"
            points = np.asarray(load_pts(geometry.read_text()))
            alpha, re = frame.alpha.to_numpy()[idx], frame.Re.to_numpy()[idx]
            values = predict_base(points, alpha, re)
            data = rich(values)
            for key, array in data.items():
                if key not in pieces:
                    pieces[key] = np.full((len(frame),)+array.shape[1:], np.nan)
                pieces[key][idx] = array
            legacy_delta = {k: float(np.max(np.abs(data[k]-reference[k][idx]))) for k in data}
            if name != "w1015":
                for key in data:
                    np.testing.assert_array_equal(data[key], reference[key][idx], err_msg=f"{name}:{key}")
                direct = legacy.predict_base(points, alpha, re)
                for key in ["X9", "X16", "BASE_CD", "XLARGE_CD", "all_CD", "all_CL"]:
                    np.testing.assert_array_equal(values[key], direct[key], err_msg=f"direct {name}:{key}")
            reflected = predict_base(mirror(points), -alpha, re)
            cd_error = float(np.max(np.abs(values["all_CD"]-reflected["all_CD"])))
            cl_error = float(np.max(np.abs(values["all_CL"]+reflected["all_CL"])))
            assert cd_error < 1e-12 and cl_error < 1e-12
            tests.append({"airfoil": name, "rows": len(idx), "geometry_sha256": sha(geometry),
                          "legacy_input_max_abs_changes": legacy_delta,
                          "quantized_all8_CD_reflection_max_abs": cd_error,
                          "quantized_all8_CL_reflection_max_abs": cl_error,
                          "original_geometry_descriptors": values["stat"],
                          "reflected_geometry_descriptors": reflected["stat"]})
        pieces.update(Re=frame.Re.to_numpy(), alpha=frame.alpha.to_numpy())
        assert all(np.isfinite(a).all() for a in pieces.values())
        output = out/f"{cohort}.npz"
        np.savez_compressed(output, **pieces)
        logs.append({"cohort": cohort, "condition_columns": ["airfoil", "alpha", "Re"],
                     "condition_csv_sha256": conditions_sha, "rows": len(frame),
                     "npz_sha256": sha(output), "tests": tests})
    assert code_hashes == {str(p): sha(p) for p in code_paths}
    report = {"status": "frozen_optional_input_convention_not_accuracy_claim", "seconds": time.monotonic()-begin,
              "code_hashes": code_hashes, "versions": {"aerosandbox": aerosandbox.__version__, "neuralfoil": neuralfoil.__version__, "numpy": np.__version__},
              "measurement_arrays_accessed": False, "cohorts": logs,
              "feature_limitation": "foil_stats2 geometry descriptors intentionally unchanged; camber-location near ties can break complete X reflection parity"}
    (out/"manifest.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
