"""Authenticate completed A/B rounds and protect the four earlier paper artifacts.

This is delivery QA, not another training or scientific evaluation run.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
STAGES = ["model_development_20260907_cap_ablation", "model_development_20260908_adaptive_scale"]


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def check(hashes):
    for path, expected in hashes.items():
        assert sha(path) == expected, path


def main():
    protected = read(PROJECT / "model_development_20260907_selective/DELIVERY_QA.json")["protected_manuscript_sha256"]
    check(protected)
    for stage, test in zip(STAGES, ["test_cap_models.py", "test_adaptive_scale.py"]):
        directory = PROJECT / stage
        output = directory / "DELIVERY_QA.json"
        assert not output.exists(), "Preserve earlier seals"
        complete, frozen, assessed = [read(directory / p) for p in ["results/complete.json", "results/freeze.json", "assessment/report.json"]]
        assert complete["freeze_sha256"] == sha(directory / "results/freeze.json")
        assert frozen["external_outcomes_opened"] is False
        witnessed = {}
        for record in [complete, frozen, assessed]:
            for field in ["source_input_sha256", "input_source_sha256", "artifact_sha256", "output_sha256", "external_input_sha256"]:
                values = record.get(field, {})
                check(values)
                for path, digest in values.items():
                    assert path not in witnessed or witnessed[path] == digest, path
                    witnessed[path] = digest
        reviews = {}
        for name in ["models_audit.json", "assessment_audit.json", "coverage_audit.json"]:
            path = directory / "review" / name
            record = read(path)
            assert record["status"] == "PASS", path
            if "assessment_report_sha256" in record:
                assert record["assessment_report_sha256"] == sha(directory / "assessment/report.json")
            if "audit_code_sha256" in record:
                code = record["audit_code_sha256"]
                if isinstance(code, dict):
                    check(code)
            reviews[str(path)] = sha(path)
        for path in sorted((directory / "review").glob("*.py")) + [directory / "review/AUDIT.md"]:
            reviews[str(path)] = sha(path)
        report = directory / "REPORT.md"
        links = []
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", report.read_text()):
            if target.startswith(("https://", "http://", "#")):
                continue
            path = (report.parent / target.split("#", 1)[0]).resolve()
            assert path.is_file(), (report, target)
            links.append(str(path))
        run = subprocess.run([sys.executable, "-m", "unittest", test, "-v"], cwd=directory,
                             check=True, capture_output=True, text=True)
        assert assessed["performance_advances"] == assessed["robustness_advances"] == []
        evidence = {str(p): sha(p) for p in [report, directory / "PROTOCOL.md", directory / "results/freeze.json",
                    directory / "results/complete.json", directory / "assessment/report.json", Path(__file__)]}
        check(witnessed)
        check(protected)
        record = {"status": "PASS", "created_utc": datetime.now(timezone.utc).isoformat(),
                  "interpretation": "Numerical and provenance QA, not independent scientific validation or publication clearance",
                  "witnessed_files_reauthenticated": len(witnessed), "source_and_result_sha256": witnessed,
                  "independent_review_sha256": reviews, "delivery_evidence_sha256": evidence,
                  "protected_manuscript_sha256": protected, "earlier_four_manuscript_artifacts_unchanged": True,
                  "local_report_links_verified": links, "unit_test_output": run.stdout + run.stderr,
                  "performance_advances": [], "robustness_advances": [], "deployed": False}
        with output.open("x") as handle:
            json.dump(record, handle, indent=2, allow_nan=False)
            handle.write("\n")
        print(stage, "PASS", len(witnessed), "authenticated paths,", len(links), "local report links")


if __name__ == "__main__":
    main()
