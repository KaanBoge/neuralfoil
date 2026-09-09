#!/usr/bin/env python3
"""Fixed-list Cycle 2 capture with strictly metadata-only measurement screening.

Never prints/parses numerical aerodynamic response rows. A raw byte copy/hash is
not an outcome inspection. Only names, Re, row-count metadata and run IDs leave
the measurement reader. No candidate inference, score, plot or ranking occurs.
"""
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
PRIOR = PROJECT / "model_development_20260906/external_screening"
STARTER = PROJECT / "validation_extension/export_intake_20260906/payload_n805d74v/NeuralFoil-export-starter-2026-09-06"
ORIGIN = "https://m-selig.ae.illinois.edu/"
NUMBER = re.compile(r"^[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?$")
SAFE = re.compile(r"^(Airfoil|Builder|Comment|Average Reynolds #|Number of Reynolds #'s|Number of angles of attack)\s*:\s*(.*)$", re.I)


def safe_headers(stream):
    rows, pending = [], None
    for raw in stream:
        line = raw.decode("latin1").strip()
        if pending:
            if NUMBER.fullmatch(line):
                rows.append({"field": pending, "value": line})
                pending = None
                continue
            if line:
                pending = None
        m = SAFE.match(line)
        if m:
            field, value = m.groups()
            if value:
                rows.append({"field": field, "value": value})
            elif field.lower() not in ("airfoil", "builder", "comment"):
                pending = field
        elif re.match(r"^alpha\s", line, re.I) and not re.search(r"\d*\.\d+", line):
            rows.append({"column_heading": line})
        elif line.startswith("Tabulated from data in file ") or (line.startswith("File ") and "created using program" in line):
            rows.append({"run_provenance": line})
        # Every other line, including numeric response rows, is discarded.
    return rows


def copy_capture(relative, blob, source, **extra):
    path = HERE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(blob).hexdigest()
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f"Existing capture differs: {relative}")
    if not path.exists():
        path.write_bytes(blob)
    return {"path": relative, "source": source, "bytes": len(blob), "sha256": digest, **extra}


def download_capture(relative, url, cap=200_000):
    path = HERE / relative
    if path.exists():
        blob = path.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=45) as response:
            blob = response.read(cap + 1)
        if len(blob) > cap:
            raise RuntimeError("Exceeded fixed source capture cap")
    return copy_capture(relative, blob, url)


def main():
    captures = []
    zpath = STARTER / "scratchpad/lsat/volume06.zip"
    archive_hash = hashlib.sha256(zpath.read_bytes()).hexdigest()
    with zipfile.ZipFile(zpath) as archive:
        for airfoil in ("w1011", "w1015"):
            for chord in (20, 30):
                for outcome in ("drag", "lift"):
                    name = f"{airfoil}-{chord}_f0_{outcome}.dat"
                    member = f"vol6/{name}"
                    captures.append(copy_capture(f"sealed_measurements/vol6/{name}", archive.read(member), "supplied starter scratchpad/lsat/volume06.zip", member=member, archive_sha256=archive_hash, official_url=ORIGIN + "pd/pub/lsat/vol6/" + name))
    for foil in ("e387", "sd2030"):
        for outcome in ("drg", "lft"):
            name = f"{foil}_c_{outcome}.txt"
            source = PRIOR / "sealed_measurements/vol4" / name
            captures.append(copy_capture(f"sealed_measurements/vol4/{name}", source.read_bytes(), ORIGIN + "pd/pub/lsat/vol4/" + name))
    for foil in ("w1011", "w1015"):
        captures.append(download_capture(f"nominal_coordinates/{foil}.dat", ORIGIN + f"ads/coord_updates/{foil}.dat"))
    for foil in ("e387", "sd2030"):
        captures.append(download_capture(f"nominal_coordinates/{foil}.dat", ORIGIN + f"ads/coord/{foil}.dat"))
    captures.append(download_capture("source_documents/Williamson-2012-UIUC-MS-Thesis.pdf", ORIGIN + "uiuc_lsat/Williamson-2012-UIUC-MS-Thesis.pdf", cap=15_000_000))
    for name in ("UIUC-pd.html", "UIUC-GPL.txt", "UIUC-manifest.html"):
        captures.append(copy_capture("source_documents/" + name, (PRIOR / "source_documents" / name).read_bytes(), "prior verified official UIUC capture"))

    measurements = {}
    for entry in captures:
        if entry["path"].startswith("sealed_measurements/"):
            with (HERE / entry["path"]).open("rb") as f:
                headers = safe_headers(f)
            counts = [int(r["value"]) for r in headers if r.get("field") == "Number of angles of attack"]
            reynolds = [float(r["value"]) for r in headers if r.get("field") == "Average Reynolds #"]
            measurements[entry["path"]] = {"headers": headers, "actual_block_headings": len(reynolds), "declared_point_rows_total": sum(counts), "point_count_metadata": counts, "reynolds_metadata": reynolds}
    geometries = {}
    for entry in captures:
        if entry["path"].startswith("nominal_coordinates/"):
            lines = (HERE / entry["path"]).read_text().splitlines()
            points = [tuple(map(float, line.split())) for line in lines[1:] if len(line.split()) == 2 and all(NUMBER.fullmatch(s) for s in line.split())]
            assert len(points) > 30, "Invalid coordinate file"
            geometries[entry["path"]] = {"title": lines[0], "coordinate_rows": len(points), "geometry_status": "Published nominal/design geometry, not as-built measurement", "x_range": [min(p[0] for p in points), max(p[0] for p in points)]}
    report = {"date": "2026-09-06", "status": "METADATA_ONLY_UNSCORED", "captures": captures, "measurements": measurements, "nominal_geometries": geometries, "author_prior_use": "Unconfirmed", "blinding": "No Cycle 2 candidate numerical CL/CD rows inspected or scored by this agent. Do not use fixed head/tail previews on measurement files. Prior SG605x was exposed and is excluded."}
    (HERE / "input_manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"captured_files": len(captures), "candidate_metadata": {k: {p: v[p] for p in ("actual_block_headings", "declared_point_rows_total", "reynolds_metadata")} for k, v in measurements.items()}, "nominal_geometries": geometries}, indent=2))


if __name__ == "__main__":
    main()
