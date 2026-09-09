"""Geometry-only scope audit; no measured arrays or outcome files are read."""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import aerosandbox as asb
import neuralfoil as nf
import numpy as np

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
OLD = PROJECT / "model_development_20260906"
sys.path.insert(0, str(OLD / "reproduction"))
from reproduce_doubleclean import PAYLOAD_REL, load_pts
from tie_safe_normalization import normalize_tie_safe, to_kulfan_tie_safe


def mirror(coords):
    out = coords[::-1].copy()
    out[:, 1] *= -1
    return out


def fit_parity(name, points):
    original = asb.Airfoil(name=name, coordinates=points)
    reflected = asb.Airfoil(name=name+"_reflected", coordinates=mirror(points))
    before = [f.normalize(return_dict=True) for f in [original, reflected]]
    after = [to_kulfan_tie_safe(f, return_dict=True) for f in [original, reflected]]
    delta = float(np.max(np.abs(mirror(after[0]["airfoil"].coordinates)-after[1]["airfoil"].coordinates)))
    assert delta < 1e-13, (name, delta)
    k, km = [r["kulfan_airfoil"] for r in after]
    errors = {"upper_lower": float(np.max(np.abs(k.upper_weights+km.lower_weights))),
              "lower_upper": float(np.max(np.abs(k.lower_weights+km.upper_weights))),
              "leading_edge": float(abs(k.leading_edge_weight+km.leading_edge_weight)),
              "te_thickness": float(abs(k.TE_thickness-km.TE_thickness))}
    assert max(errors.values()) < 1e-10, (name, errors)
    alpha = np.array([-8., -2., 0., 3., 9.])
    a = nf.get_aero_from_kulfan_parameters(k.kulfan_parameters, alpha=alpha, Re=2e5, model_size="xlarge")
    b = nf.get_aero_from_kulfan_parameters(km.kulfan_parameters, alpha=-alpha, Re=2e5, model_size="xlarge")
    aero_errors = {key: float(np.max(np.abs(a[key] - sign*b[key]))) for key, sign in [("CD", 1), ("CL", -1), ("CM", -1)]}
    assert max(aero_errors.values()) < 1e-10, (name, aero_errors)
    return {"name": name, "tie_count": after[0]["le_tie_count"],
            "old_rotation_degrees": [float(x["rotation_angle"]) for x in before],
            "new_rotation_degrees": [float(x["rotation_angle"]) for x in after],
            "old_coordinate_reflection_max_abs": float(np.max(np.abs(mirror(before[0]["airfoil"].coordinates)-before[1]["airfoil"].coordinates))),
            "new_coordinate_reflection_max_abs": delta, "kulfan_parity_max_abs": errors,
            "synthetic_condition_aero_parity_max_abs": aero_errors}


def main():
    assert asb.__version__ == "4.2.10" and nf.__version__ == "0.3.3"
    base = PROJECT / PAYLOAD_REL / "scratchpad/lsat"
    geometries = json.loads((base/"lsat-geometry.json").read_text())
    assert len(geometries) == 203
    # Select only identifiers from the compressed historical archive. This does
    # not deserialize measured or modeled coefficient arrays.
    with np.load(OLD/"reproduction/dataset_occurrence.npz", allow_pickle=False) as archive:
        entries = archive["entry"]
        row_ids = archive["nf2_row_id"]
    with (OLD/"methods_audit/ambiguous_nf2_row_ids.csv").open() as handle:
        excluded = {int(r["nf2_row_id"]) for r in csv.DictReader(handle)}
    entries = entries[~np.isin(row_ids, list(excluded))]
    assert len(entries) == 8371
    counts = Counter(entries)
    audit, unique_examples, errors = [], [], []
    with zipfile.ZipFile(base/"coord_seligFmt.zip") as zc, zipfile.ZipFile(base/"Stec8.zip") as zs:
        for key, geometry in sorted(geometries.items()):
            path = geometry["path"]
            try:
                if (base/path).exists():
                    data = (base/path).read_bytes()
                    text = data.decode(errors="replace")
                elif path.startswith("coords/"):
                    data = zc.read(path[len("coords/"):])
                    text = data.decode("latin-1")
                elif path.startswith("stec8/"):
                    data = zs.read(path[len("stec8/"):])
                    text = data.decode("latin-1")
                else:
                    raise FileNotFoundError(path)
                pts = np.asarray(load_pts(text))
                foil = asb.Airfoil(name=key, coordinates=pts)
                legacy = foil.normalize(return_dict=True)
                fixed = normalize_tie_safe(foil, return_dict=True)
                reflected = normalize_tie_safe(asb.Airfoil(name=key, coordinates=mirror(pts)))
                parity_error = float(np.max(np.abs(mirror(fixed["airfoil"].coordinates)-reflected.coordinates)))
                change = float(np.max(np.abs(legacy["airfoil"].coordinates-fixed["airfoil"].coordinates)))
                assert parity_error < 1e-13, (key, parity_error)
                if not fixed["tie_safe_applied"]:
                    np.testing.assert_array_equal(legacy["airfoil"].coordinates, fixed["airfoil"].coordinates)
                    if len(unique_examples) < 3:
                        unique_examples.append((key, pts))
                audit.append({"entry": key, "path": path, "sha256": hashlib.sha256(data).hexdigest(),
                              "historical_rows": counts[key], "tie_count": fixed["le_tie_count"],
                              "tie_safe_applied": fixed["tie_safe_applied"], "coordinate_change_max_abs": change,
                              "reflection_error_max_abs": parity_error,
                              "old_rotation_degrees": float(legacy["rotation_angle"]),
                              "new_rotation_degrees": float(fixed["rotation_angle"])})
            except Exception as exc:
                errors.append({"entry": key, "path": path, "error": repr(exc),
                               "historical_rows": counts[key],
                               "nominal_coordinates_absent": "There are no nominal coordinates for this airfoil." in text})
    paths = [PROJECT/"model_development_20260906_v2/external_screening/nominal_coordinates"/f"{n}.dat" for n in ["w1015", "w1011"]]
    paths += [OLD/"external_screening/nominal_coordinates"/f"{n}.dat" for n in ["sg6050", "sg6051"]]
    tests = [fit_parity(p.stem, np.asarray(load_pts(p.read_text()))) for p in paths]
    tests += [fit_parity(name, points) for name, points in unique_examples]
    # The only inherited loader failure must be the explicit coordinate-absence
    # notice, and must not remove any of the 8,371 historical rows from the audit.
    assert len(errors) == 1 and errors[0]["entry"] == "stec8|DF103"
    assert errors[0]["nominal_coordinates_absent"] and errors[0]["historical_rows"] == 0
    assert sum(r["historical_rows"] for r in audit) == 8371
    changed = [r for r in audit if r["coordinate_change_max_abs"] > 0]
    report = {"scope": "Geometry only; identifiers only from historical dataset; no measured coefficient arrays accessed",
              "versions": {"aerosandbox": asb.__version__, "neuralfoil": nf.__version__, "numpy": np.__version__},
              "mapping_count": len(geometries), "successful_geometry_count": len(audit), "geometry_errors": errors,
              "historical_rows": len(entries), "historical_entries": len(counts),
              "tie_entries": sum(r["tie_safe_applied"] for r in audit), "changed_mapping_entries": len(changed),
              "changed_historical_entries": sum(r["historical_rows"] > 0 for r in changed),
              "changed_historical_rows": sum(r["historical_rows"] for r in changed),
              "changed_entries": changed, "tests": tests}
    (HERE/"scope_audit.json").write_text(json.dumps(report, indent=2)+"\n")
    with (HERE/"geometry_audit.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(audit[0]))
        writer.writeheader()
        writer.writerows(audit)
    print(json.dumps(report, indent=2))
    print("PASS: all available geometries, all historical rows, and seven Kulfan/NF parity tests")


if __name__ == "__main__":
    main()
