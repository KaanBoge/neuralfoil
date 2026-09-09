"""Read matched original coordinates and extract fixed-order Kulfan parameters."""
from pathlib import Path
import hashlib
import json
import platform
import sys
import time
import traceback
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "model_development_20260906_v2"))
import evaluate_external_v2 as ext
OUT = ROOT / "shape_inputs"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    import aerosandbox as asb
    assert asb.__version__ == "4.2.10"
    OUT.mkdir(exist_ok=True)
    assert not (OUT / "started_manifest.json").exists(), "Preserve completed or failed extraction"
    transition_manifest = json.loads((ROOT / "inputs/manifest.json").read_text())
    paths = [Path(__file__), ROOT / "shape_inputs.py", ROOT / "SHAPE_INPUT_PROTOCOL.md", ROOT / "inputs/manifest.json",
             ROOT / "transition_inputs.py"]
    paths += [ROOT / "inputs" / f"{c['name']}.npz" for c in transition_manifest["cohorts"]]
    for c in transition_manifest["cohorts"]:
        assert digest(ROOT / "inputs" / f"{c['name']}.npz") == c["output_sha256"]
    manifest = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "python": platform.python_version(), "numpy": np.__version__, "aerosandbox": asb.__version__,
                "feature_order": [f"upper_weights_{i}" for i in range(8)] + [f"lower_weights_{i}" for i in range(8)] + ["leading_edge_weight", "TE_thickness"],
                "hashes": {str(p): digest(p) for p in paths},
                "status": "Coordinate-only shape features; no external fit and no unscored outcomes accessed"}
    dump(OUT / "started_manifest.json", manifest)
    outputs = []
    try:
        for c in transition_manifest["cohorts"]:
            tick = time.monotonic()
            name = c["name"]
            with np.load(ROOT / "inputs" / f"{name}.npz", allow_pickle=False) as archive:
                original = {k: archive[k].copy() for k in archive.files}
            groups = original["entry" if name == "historical" else "airfoil"]
            parameters = np.full((len(groups), 18), np.nan)
            checks = []
            for check in c["checks"]:
                origin = check["coordinate_origin"]
                if "::" in origin:
                    archive, member = origin.split("::", 1)
                    with zipfile.ZipFile(archive) as z:
                        raw = z.read(member)
                    text = raw.decode("latin-1")
                else:
                    raw = Path(origin).read_bytes()
                    text = raw.decode(errors="replace")
                assert hashlib.sha256(raw).hexdigest() == check["coordinate_sha256"], origin
                coordinates = ext.load_pts(text)
                foil = asb.Airfoil(name="shape_sensitivity", coordinates=coordinates).to_kulfan_airfoil()
                k18 = np.concatenate([np.asarray(foil.upper_weights), np.asarray(foil.lower_weights),
                                      [float(foil.leading_edge_weight), float(foil.TE_thickness)]])
                assert k18.shape == (18,) and np.isfinite(k18).all()
                rows = groups == check["entry"]
                assert int(rows.sum()) == check["rows"]
                parameters[rows] = k18
                checks.append({"entry": check["entry"], "rows": int(rows.sum()), "coordinate_origin": origin,
                               "coordinate_sha256": check["coordinate_sha256"], "K18": k18.tolist()})
            assert np.isfinite(parameters).all()
            ids = {k: original[k] for k in ["row_id", "alpha", "Re", "nf2_row_id", "entry", "airfoil"] if k in original}
            np.savez_compressed(OUT / f"{name}.npz", K18=parameters, **ids)
            outputs.append({"name": name, "rows": len(groups), "entries": len(checks), "checks": checks,
                            "seconds": time.monotonic() - tick, "output_sha256": digest(OUT / f"{name}.npz")})
            print(json.dumps({"cohort": name, "rows": len(groups), "entries": len(checks), "seconds": outputs[-1]["seconds"]}), flush=True)
        for path, expected in manifest["hashes"].items():
            assert digest(path) == expected, path
        dump(OUT / "manifest.json", {**manifest, "cohorts": outputs,
                                     "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    except Exception:
        dump(OUT / "failure.json", {"traceback": traceback.format_exc(), "completed_cohorts": outputs})
        raise


if __name__ == "__main__":
    main()
