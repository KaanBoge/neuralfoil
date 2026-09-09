"""Authenticate the completed addendum without fitting or rewriting old work."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def main():
    out = HERE/"DELIVERY_QA.json"
    assert not out.exists(), "Preserve existing delivery seal"
    complete = read(HERE/"results/complete.json")
    assessment = read(HERE/"assessment/report.json")
    witnessed = {}
    for record, keys in [(complete, ["artifact_sha256", "output_sha256", "source_input_sha256", "external_input_sha256"]),
                         (assessment, ["input_source_sha256", "output_sha256"])]:
        for key in keys:
            for path, digest in record[key].items():
                assert path not in witnessed or witnessed[path] == digest
                witnessed[path] = digest
    for path, digest in witnessed.items():
        assert sha(path) == digest, path
    assert assessment["performance_advances"] == assessment["robustness_advances"] == []
    assert assessment["empirically_certified"] is False and assessment["deployed"] is False
    reviews = {}
    for filename in ["selective_audit.json", "assessment_audit.json", "cap_floor_audit.json"]:
        path = HERE/"review"/filename
        record = read(path)
        assert record["status"] == "PASS"
        if "assessment_report_sha256" in record:
            assert record["assessment_report_sha256"] == sha(HERE/"assessment/report.json")
        if "complete_sha256" in record:
            assert record["complete_sha256"] == sha(HERE/"results/complete.json")
        reviews[str(path)] = sha(path)
    # The delivered 32-page article and 73-page supplement are preserved.
    paper = HERE.parent/"paper_revision_20260907"
    prior = read(paper/"FINAL_QA.json")
    protected = {}
    stems = {"main": "NeuralFoil_Measurement_Informed_Drag_Correction",
             "supplement": "NeuralFoil_Measurement_Audit_Supplement"}
    for role, stem in stems.items():
        for extension in ["docx", "pdf"]:
            p = paper/"deliverables"/(stem+"."+extension)
            expected = prior["artifacts"][role][extension+"_sha256"]
            assert sha(p) == expected, p
            protected[str(p)] = expected
    # Every relative report link resolves; primary web sources are not fetched here.
    local_links = []
    for target in re.findall(r"\]\(([^)]+)\)", (HERE/"REPORT.md").read_text()):
        if not target.startswith("http"):
            p = (HERE/target).resolve()
            assert p.is_file(), target
            local_links.append(str(p))
    test = subprocess.run([sys.executable, "-m", "unittest", "-v", "test_selective.py", "test_assessment.py"],
        cwd=HERE, capture_output=True, text=True, check=True)
    evidence = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix in [".py", ".md", ".csv", ".json", ".npz", ".pkl"]:
            evidence[str(p)] = sha(p)
    result = {"status": "PASS", "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "interpretation": "Verified fixed exploratory experiment and explanatory addendum; no accuracy advance, no deployment, no independent experimental certification or journal acceptance.",
              "witnessed_files_reauthenticated": len(witnessed), "source_and_result_sha256": witnessed,
              "independent_reviews_sha256": reviews, "earlier_four_manuscript_artifacts_unchanged": True,
              "protected_manuscript_sha256": protected, "local_report_links_verified": len(local_links),
              "unit_test_output": test.stdout+test.stderr, "addendum_evidence_sha256": evidence,
              "report_sha256": sha(HERE/"REPORT.md"), "performance_advances": [], "robustness_advances": []}
    with out.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({k: result[k] for k in ["status", "witnessed_files_reauthenticated", "earlier_four_manuscript_artifacts_unchanged", "local_report_links_verified", "report_sha256"]}))


if __name__ == "__main__":
    main()
