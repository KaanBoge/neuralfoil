#!/usr/bin/env python3
"""Outcome-blind metadata screening; never parses aerodynamic response rows.

Remote measurement files are streamed through an allowlist, not saved. Only
metadata and column headings are retained. No CL/CD numeric tokens are parsed,
printed, summarized, or passed to a predictor. Local CSVs are read only for the
explicitly listed identity columns; other cells are never accessed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

STARTER = Path(__file__).resolve().parents[2] / "validation_extension/export_intake_20260906/payload_n805d74v/NeuralFoil-export-starter-2026-09-06"
OUT = Path(__file__).resolve().parent
ROOT = "https://m-selig.ae.illinois.edu/"
NUMERIC = re.compile(r"^[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?$")
FIELD = re.compile(r"^(Airfoil|Builder|Comment|Average Reynolds #|Number of Reynolds #'s|Number of angles of attack|Number of points|Run #)\s*:?\s*(.*)$", re.I)


def headers_only(lines):
    result, pending = [], None
    for raw in lines:
        line = raw.decode("latin-1").strip() if isinstance(raw, bytes) else raw.strip()
        if pending is not None:
            # Only scalar numeric metadata following an exact safe label.
            if NUMERIC.fullmatch(line):
                result.append({"field": pending, "value": line})
                pending = None
                continue
            if line:
                pending = None
        match = FIELD.match(line)
        if match:
            name, value = match.groups()
            if value:
                result.append({"field": name, "value": value})
            elif name.lower() not in {"airfoil", "builder", "comment"}:
                pending = name
            continue
        if re.match(r"^(alpha|alfa|aoa)\s", line, re.I):
            # A heading must contain alphabetic labels and no decimal tokens.
            if not re.search(r"[-+]?\d*\.\d+", line):
                result.append({"column_heading": line})
        if line.startswith("Tabulated from data in file ") or (line.startswith("File ") and "created using program" in line):
            result.append({"run_provenance": line})
        # All other lines, including every numeric response row, are discarded.
    return result


def remote_headers(relative):
    url = ROOT + relative
    with urllib.request.urlopen(url, timeout=30) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > 100_000:
            raise ValueError("Remote file exceeds the metadata audit size limit")
        metadata = headers_only(response)
        return {"url": url, "content_length": length, "headers": metadata}


def main():
    zpath = STARTER / "scratchpad/lsat/volume06.zip"
    with zipfile.ZipFile(zpath) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        volume6 = {
            "archive_relative_path": "scratchpad/lsat/volume06.zip",
            "sha256": hashlib.file_digest(zpath.open("rb"), "sha256").hexdigest(),
            "members": [{"name": i.filename, "uncompressed_bytes": i.file_size} for i in infos],
            "zero_filename_headers": {},
        }
        for entry in infos:
            if "_f0_" in entry.filename:
                with archive.open(entry) as member:
                    volume6["zero_filename_headers"][entry.filename] = headers_only(member)

    historical = {}
    for name in ("lsat-corpus.csv", "lsat-nf.csv", "lsat-nf2.csv", "lsat-xfoil.csv"):
        with (STARTER / "scratchpad/lsat" / name).open(newline="") as f:
            reader = csv.DictReader(f)
            allowed = [k for k in ("source", "airfoil_raw", "airfoil", "config", "foil") if k in reader.fieldnames]
            distinct = {k: set() for k in allowed}
            for row in reader:
                for key in allowed:
                    distinct[key].add(row[key])
            historical[name] = {"inspected_columns": allowed, "distinct_identity_values": {k: sorted(v) for k, v in distinct.items()}}

    remote = {}
    for relative in (
        "pd/pub/lsat/vol4/e387_c_drg.txt", "pd/pub/lsat/vol4/e387_c_lft.txt",
        "pd/pub/lsat/vol4/s834_c_drg.txt", "pd/pub/lsat/vol4/s834_c_lft.txt",
        "uiuc_lsat/SG6050-SG6051-1998/SG6050A.DRG",
        "uiuc_lsat/SG6050-SG6051-1998/SG6050B.LFT",
        "uiuc_lsat/SG6050-SG6051-1998/SG6051A.DRG",
        "uiuc_lsat/SG6050-SG6051-1998/SG6051A.LFT",
    ):
        try:
            remote[relative] = remote_headers(relative)
        except Exception as error:
            remote[relative] = {"error": str(error), "url": ROOT + relative}

    captured = {}
    for path in sorted((OUT / "sealed_measurements").rglob("*")):
        if path.is_file():
            with path.open("rb") as source:
                captured[str(path.relative_to(OUT))] = headers_only(source)
    coordinates = {}
    for path in sorted((OUT / "nominal_coordinates").glob("*.dat")):
        lines = path.read_text().splitlines()
        points = []
        for line in lines[1:]:
            cells = line.split()
            if len(cells) == 2 and all(NUMERIC.fullmatch(s) for s in cells):
                points.append(tuple(float(s) for s in cells))
        coordinates[path.name] = {"title": lines[0], "coordinate_rows": len(points), "x_min": min(p[0] for p in points), "x_max": max(p[0] for p in points), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "geometry_status": "Published nominal/design geometry; as-built experimental model not established."}
    report = {
        "screening_date": "2026-09-06",
        "blinding": "This screening script does not parse, print, summarize or score candidate aerodynamic response values; numerical rows are discarded. Only exact safe header fields, identity columns, filenames and byte sizes are retained. Consult exposure_log.json for separate team-level incidental exposures; the overall external evaluation is not strictly blind.",
        "volume6": volume6, "historical_identity_audit": historical, "remote_header_audit": remote,
        "captured_header_audit": captured, "nominal_coordinate_metadata": coordinates,
    }
    # Generated metadata-only output is a mechanical artifact of this script.
    (OUT / "metadata_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"archive_files": len(volume6["members"]), "zero_filename_files": len(volume6["zero_filename_headers"]), "remote_files": len(remote), "remote_errors": {k: v["error"] for k, v in remote.items() if "error" in v}, "output": "metadata_audit.json"}, indent=2))


if __name__ == "__main__":
    main()
