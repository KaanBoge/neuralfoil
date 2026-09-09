#!/usr/bin/env python3
"""Capture authorized prospective holdout inputs without examining outcomes.

The files below are copied byte-for-byte and hashed. Aerodynamic measurement
rows are never parsed or printed here. Screened metadata is supplied separately.
No source coordinate files marked proprietary are requested.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = "https://m-selig.ae.illinois.edu/"
FILES = {
    **{f"sealed_measurements/vol4/{name}": f"pd/pub/lsat/vol4/{name}" for name in (
        "e387_c_drg.txt", "e387_c_lft.txt", "fx63137_c_drg.txt", "fx63137_c_lft.txt",
        "s822_c_drg.txt", "S822_c_lft.txt", "s834_c_drg.txt", "s834_c_lft.txt",
        "sd2030_c_drg.txt", "sd2030_c_lft.txt", "sh3055_c_drg.txt", "sh3055_c_lft.txt")},
    **{f"sealed_measurements/sg605x/{name}": f"uiuc_lsat/SG6050-SG6051-1998/{name}" for name in (
        "SG6050A.DRG", "SG6050B.LFT", "SG6051A.DRG", "SG6051A.LFT")},
    "source_documents/NREL-SR-500-34515.pdf": "uiuc_lsat/vol4/NREL-SR-500-34515.pdf",
    "source_documents/SG605x-00-readme.txt": "uiuc_lsat/SG6050-SG6051-1998/00-readme.txt",
    "source_documents/UIUC-pd.html": "pd.html",
    "source_documents/UIUC-GPL.txt": "pd/pub/lsat/GPL.TXT",
    "source_documents/UIUC-manifest.html": "pd/pub/lsat/MANIFEST.html",
    "nominal_coordinates/sg6050.dat": "ads/coord/sg6050.dat",
    "nominal_coordinates/sg6051.dat": "ads/coord/sg6051.dat",
}


def main():
    prior_path = HERE / "capture_manifest.json"
    prior = {row["path"]: row for row in json.loads(prior_path.read_text())["files"] if "sha256" in row} if prior_path.exists() else {}
    record = {"captured_utc_date": "2026-09-06", "authorization": "Parent requested byte-for-byte download and hashes before candidate freeze; no aerodynamic values examined.", "files": []}
    for local, relative in FILES.items():
        url = ROOT + relative
        path = HERE / local
        try:
            if path.exists() and local in prior:
                if hashlib.sha256(path.read_bytes()).hexdigest() != prior[local]["sha256"]:
                    raise ValueError("Existing capture hash mismatch; refusing overwrite")
                record["files"].append(prior[local])
                continue
            with urllib.request.urlopen(url, timeout=30) as response:
                blob = response.read(5_000_001)
                if len(blob) > 5_000_000:
                    raise ValueError("Capture exceeds fixed 5 MB limit")
                # Raw download capture only, not a source edit.
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(blob)
                record["files"].append({"path": local, "url": url, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "last_modified": response.headers.get("Last-Modified")})
        except Exception as error:
            record["files"].append({"path": local, "url": url, "error": str(error)})
    (HERE / "capture_manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"files_captured": sum("sha256" in r for r in record["files"]), "errors": [r for r in record["files"] if "error" in r]}, indent=2))


if __name__ == "__main__":
    main()
