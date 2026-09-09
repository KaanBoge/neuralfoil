"""Frozen input-only ncrit sensitivity computation; see INPUT_PROTOCOL.md."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import time
import traceback
import zipfile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "model_development_20260906_v2"))
import evaluate_external_v2 as ext
from reproduce_doubleclean import PAYLOAD_REL

GRID = [5, 7, 9, 11, 13]
FIELDS = {"CD": 6, "CL": 5, "confidence": 4, "Top_Xtr": 4, "Bot_Xtr": 4}
OUT = ROOT / "inputs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def calc(coordinates, alpha, reynolds):
    import aerosandbox as asb
    foil = asb.Airfoil(name="transition_sensitivity", coordinates=coordinates).to_kulfan_airfoil()
    matrices = {key: np.empty((len(alpha), len(GRID))) for key in FIELDS}
    for j, ncrit in enumerate(GRID):
        results = foil.get_aero_from_neuralfoil(alpha=alpha, Re=reynolds, mach=0., n_crit=ncrit,
                                               model_size="xlarge", xtr_upper=1., xtr_lower=1.)
        for key, digits in FIELDS.items():
            values = results["analysis_confidence" if key == "confidence" else key]
            matrices[key][:, j] = [float(f"{float(v):.{digits}f}") for v in np.atleast_1d(values)]
    assert all(np.isfinite(a).all() for a in matrices.values())
    assert (matrices["CD"] > 0).all()
    return matrices


def supplement(x24, matrices):
    extras = []
    for j in [0, 1, 3, 4]:
        extras += [np.log(matrices["CD"][:, j] / matrices["CD"][:, 2])]
        extras += [matrices[key][:, j] - matrices[key][:, 2] for key in ["CL", "confidence", "Top_Xtr", "Bot_Xtr"]]
    return np.column_stack([x24] + extras)


def cohort(name, d, groups, reader, reference, extra_ids):
    tick = time.monotonic()
    arrays = {key: np.full((len(groups), 5), np.nan) for key in FIELDS}
    checks = []
    for number, group in enumerate(sorted(set(groups))):
        idx = np.flatnonzero(groups == group)
        text, origin, coordinate_hash = reader(group)
        coords = ext.load_pts(text)
        matrices = calc(coords, d["alpha"][idx], d["Re"][idx])
        diffs = {key: float(np.max(np.abs(matrices[key][:, 2] - reference[key][idx]))) for key in FIELDS}
        for key in FIELDS:
            arrays[key][idx] = matrices[key]
        checks.append({"entry": str(group), "rows": len(idx), "coordinate_origin": origin,
                       "coordinate_sha256": coordinate_hash, "ncrit9_max_abs_difference": diffs})
        dump(OUT / f"{name}_progress.json", {"completed": len(checks), "total": len(set(groups)), "checks": checks})
        if max(diffs.values()) > 1e-12:
            np.savez_compressed(OUT / f"{name}_failed_entry.npz", row_id=idx, **{f"ncrit_{k}": v for k, v in matrices.items()})
            raise AssertionError(f"ncrit9 parity failed {name} {group}: {diffs}")
        if number % 20 == 0:
            print(json.dumps({"cohort": name, "completed": number + 1, "total": len(set(groups))}), flush=True)
    assert all(np.isfinite(a).all() for a in arrays.values())
    x44 = supplement(d["X24"], arrays)
    assert x44.shape == (len(groups), 44) and np.isfinite(x44).all()
    np.savez_compressed(OUT / f"{name}.npz", X44=x44, row_id=np.arange(len(groups)), alpha=d["alpha"], Re=d["Re"],
                        ncrit_grid=np.asarray(GRID), **extra_ids, **{f"ncrit_{k}": v for k, v in arrays.items()})
    return {"name": name, "rows": len(groups), "entries": len(checks), "checks": checks,
            "seconds": time.monotonic() - tick, "output_sha256": digest(OUT / f"{name}.npz")}


def main():
    import aerosandbox, neuralfoil
    assert aerosandbox.__version__ == "4.2.10" and neuralfoil.__version__ == "0.3.3"
    OUT.mkdir(exist_ok=True)
    assert not (OUT / "started_manifest.json").exists(), "Preserve prior runs and failures"
    base = ROOT.parent / PAYLOAD_REL / "scratchpad/lsat"
    geompath = base / "lsat-geometry.json"
    geometry = json.loads(geompath.read_text())
    paths = [Path(__file__), ROOT / "INPUT_PROTOCOL.md", ROOT / "transition_inputs.py", geompath,
             ext.v.OLD / "reproduction/dataset_occurrence.npz", ext.v.OLD / "methods_audit/entry_group_map.csv",
             ext.v.OLD / "methods_audit/ambiguous_nf2_row_ids.csv", Path(ext.v.__file__), Path(ext.prior.__file__)]
    for name in ["SG_exposed", "W_new_challenge"]:
        paths += [ext.ROOT / "external_results" / f"{name}_predictions.csv",
                  ROOT.parent / "model_development_20260907_search/exposed_inputs/forward_verified" / f"{name}.npz"]
    manifest = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "python": platform.python_version(),
                "numpy": np.__version__, "aerosandbox": aerosandbox.__version__, "neuralfoil": neuralfoil.__version__,
                "grid": GRID, "hashes": {str(path): digest(path) for path in paths},
                "status": "Input-only computation. No external fitting. No measured labels used in predictors.",
                "ncrit_semantics": "Computed sensitivity assumptions, not measured tunnel conditions"}
    dump(OUT / "started_manifest.json", manifest)
    results = []

    def historical_reader(entry):
        rel = geometry[entry]["path"]
        local = base / rel
        if local.exists():
            data = local.read_bytes()
            text = data.decode(errors="replace")
            origin = str(local)
        else:
            if rel.startswith("coords/"):
                archive, member = base / "coord_seligFmt.zip", rel[7:]
            elif rel.startswith("stec8/"):
                archive, member = base / "Stec8.zip", rel[6:]
            else:
                raise ValueError(rel)
            with zipfile.ZipFile(archive) as z:
                data = z.read(member)
            text, origin = data.decode("latin-1"), f"{archive}::{member}"
        return text, origin, hashlib.sha256(data).hexdigest()

    def external_reader(airfoil):
        path = (ext.v.OLD if airfoil.startswith("sg") else ext.ROOT) / "external_screening/nominal_coordinates" / f"{airfoil}.dat"
        return path.read_text(), str(path), digest(path)

    try:
        d = ext.v.load_data()
        assert len(d["BASE_CD"]) == 8371 and len(set(d["group"])) == 93
        reference = {"CD": d["XLARGE_CD"], "CL": d["all_model_CL"][:, 5], "confidence": d["X16"][:, 11],
                     "Top_Xtr": d["X16"][:, 12], "Bot_Xtr": d["X16"][:, 13]}
        results.append(cohort("historical", d, d["entry"], historical_reader, reference,
                              {"nf2_row_id": d["nf2_row_id"], "entry": d["entry"]}))
        for name in ["SG_exposed", "W_new_challenge"]:
            frame = pd.read_csv(ext.ROOT / "external_results" / f"{name}_predictions.csv",
                                usecols=["airfoil", "alpha", "Re", "xlarge_CD"])
            prior = ROOT.parent / "model_development_20260907_search/exposed_inputs/forward_verified" / f"{name}.npz"
            with np.load(prior, allow_pickle=False) as archive:
                d = {key: archive[key].copy() for key in archive.files}
            assert np.array_equal(d["alpha"], frame.alpha.to_numpy()) and np.array_equal(d["Re"], frame.Re.to_numpy())
            np.testing.assert_allclose(d["XLARGE_CD"], frame.xlarge_CD.to_numpy(), rtol=0, atol=1e-12)
            reference = {"CD": frame.xlarge_CD.to_numpy(), "CL": d["all_model_CL"][:, 5], "confidence": d["X16"][:, 11],
                         "Top_Xtr": d["X16"][:, 12], "Bot_Xtr": d["X16"][:, 13]}
            results.append(cohort(name, d, frame.airfoil.to_numpy(), external_reader, reference, {"airfoil": frame.airfoil.to_numpy(dtype=str)}))
        for path, expected in manifest["hashes"].items():
            assert digest(path) == expected, path
        dump(OUT / "manifest.json", {**manifest, "cohorts": results, "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        print(json.dumps({"complete": True, "cohorts": [{k: v for k, v in c.items() if k != "checks"} for c in results]}), flush=True)
    except Exception:
        dump(OUT / "failure.json", {"traceback": traceback.format_exc(), "completed_cohorts": results})
        raise


if __name__ == "__main__":
    main()
