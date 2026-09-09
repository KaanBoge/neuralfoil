"""Final read-only evidence checks, followed by one new delivery record."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
C = PROJECT / "reproduction_20260908_private"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output = HERE / "FINAL_QA.json"
    assert not output.exists(), "Preserve previous delivery records"
    hashes = {}
    def check(values):
        for path, digest in values.items():
            assert sha(path) == digest, path
            assert str(path) not in hashes or hashes[str(path)] == digest, path
            hashes[str(path)] = digest
    for name in ["model_development_20260907_cap_ablation", "model_development_20260908_adaptive_scale"]:
        path = PROJECT / name / "DELIVERY_QA.json"
        record = read(path)
        assert record["status"] == "PASS"
        assert record["performance_advances"] == record["robustness_advances"] == []
        assert record["earlier_four_manuscript_artifacts_unchanged"] is True
        for field in ["source_and_result_sha256", "independent_review_sha256", "delivery_evidence_sha256", "protected_manuscript_sha256"]:
            check(record[field])
        hashes[str(path)] = sha(path)
    package = read(C / "verification_complete.json")
    audit = read(HERE / "work/PACKAGE_AUDIT.json")
    assert package["status"] == audit["status"] == "PASS"
    assert audit["tests"] == 33 and audit["fits"] == 160 and audit["calibrators"] == 64
    assert package["independently_provisioned_environment"] is False
    assert package["report"]["native_array_parity"] == package["report"]["calibrator_parity"] == "exact"
    check({C / "verification_complete.json": audit["verification_sha256"],
           HERE / "work/audit_package.py": audit["audit_sha256"],
           C / "private_reproduction.zip": package["zip_sha256"],
           C / "fresh_extraction_transcript.txt": package["transcript_sha256"],
           C / "bundle/manifest.json": package["manifest_sha256"]})
    extracted = Path(package["temporary_extraction"])
    check({extracted / "manifest.json": package["extracted_manifest_sha256"]})
    manifest = read(C / "bundle/manifest.json")
    assert len(manifest["files"]) == audit["bundle_files"] == 138
    with zipfile.ZipFile(C / "private_reproduction.zip") as archive:
        assert set(archive.namelist()) == {"private_reproduction/" + p for p in [*manifest["files"], "manifest.json"]}
        for path, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read("private_reproduction/" + path)).hexdigest() == digest
            check({C / "bundle" / path: digest, extracted / path: digest})
    check({extracted / path: digest for path, digest in package["output_sha256"].items()})
    links = []
    for doc in [HERE / "RESEARCH_FRONTIER.md", C / "VERIFICATION.md"]:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", doc.read_text()):
            if target.startswith(("http://", "https://", "#")):
                continue
            path = (doc.parent / target.split("#", 1)[0]).resolve()
            assert path.is_file(), (doc, target)
            links.append(str(path))
        hashes[str(doc)] = sha(doc)
    for path in [HERE / "CONTINUATION.md", HERE / "work/FINAL_REVIEW.md", HERE / "work/CONTRIBUTION_REVIEW.md",
                 HERE / "work/PACKAGE_AUDIT.json", C / "VERIFICATION.md", C / "build_package.py", C / "verify_fresh.py", Path(__file__)]:
        hashes[str(path)] = sha(path)
    record = {"status": "PASS", "created_utc": datetime.now(timezone.utc).isoformat(),
              "queue": "A and B completed with no advances; C private reproduction verified",
              "scientific_interpretation": "Practical scoped checkpoint, not an absolute limit, independent confirmation or publication clearance",
              "protected_previous_manuscript_artifacts_unchanged": 4,
              "new_manuscript_edition_created": False, "public_release": False, "deployment": False,
              "package_native_parity": "exact", "package_tests": 33, "package_refits": 160,
              "package_calibrators": 64, "independently_provisioned_environment": False,
              "verified_local_links": links, "evidence_sha256": hashes,
              "witnessed_files_reauthenticated": len(hashes),
              "next_evidence_needed": "Qualified independent data and custody history; venue, rights and author decisions for submission"}
    with output.open("x") as handle:
        json.dump(record, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": "PASS", "paths_reauthenticated": len(hashes), "local_links": len(links),
                      "refits": 160, "calibrators": 64, "tests": 33}))


if __name__ == "__main__":
    main()
